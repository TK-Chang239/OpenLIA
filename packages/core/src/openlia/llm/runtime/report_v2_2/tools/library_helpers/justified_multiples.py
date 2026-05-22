"""justified_multiples — fundamental-derived justified trading multiples.

Registered name: "justified_multiples"

Derives the multiples a company should trade at from its fundamentals
(ROE, growth, payout, cost of equity, WACC), then computes spreads against
actual current multiples.

Multiples supported:
  forward_pe:  payout / (Re - g)
  trailing_pe: payout * (1 + g) / (Re - g)
  pb:          (ROE - g) / (Re - g)
  ev_ebitda:   approximate formula from ROIC, WACC, g — with capital-intensity warning

Design ref: planning/2026-05-22-helpers-design-supplement.md §5
"""

from __future__ import annotations

import datetime
from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Verdict bands for spread interpretation
# ---------------------------------------------------------------------------

_BAND_INLINE = 0.05
_BAND_NOTABLE = 0.20
_BAND_EXTREME = 0.50


def _spread_verdict(spread_pct: float) -> str:
    abs_s = abs(spread_pct)
    direction = "premium" if spread_pct > 0 else "discount"
    if abs_s < _BAND_INLINE:
        return "in line"
    if abs_s < _BAND_NOTABLE:
        return f"modest {direction} to fundamentals"
    if abs_s < _BAND_EXTREME:
        return f"material {direction} to fundamentals"
    return f"extreme {direction} to fundamentals"


# ---------------------------------------------------------------------------
# Per-multiple computation
# ---------------------------------------------------------------------------


def _forward_pe(payout: float, re: float, g: float) -> dict[str, Any]:
    """Forward P/E = payout / (Re - g)."""
    denom = re - g
    value = payout / denom
    return {
        "value": value,
        "formula": f"payout / (Re - g) = {payout:.4f} / {denom:.4f}",
        "inputs_used": {"payout": payout, "re": re, "g": g},
    }


def _trailing_pe(payout: float, re: float, g: float) -> dict[str, Any]:
    """Trailing P/E = payout * (1 + g) / (Re - g) = forward_PE * (1 + g)."""
    denom = re - g
    value = payout * (1.0 + g) / denom
    return {
        "value": value,
        "formula": f"payout * (1 + g) / (Re - g) = {payout:.4f} * {1 + g:.4f} / {denom:.4f}",
        "inputs_used": {"payout": payout, "re": re, "g": g},
    }


def _pb(roe: float, re: float, g: float) -> dict[str, Any]:
    """P/B = (ROE - g) / (Re - g)."""
    denom = re - g
    value = (roe - g) / denom
    return {
        "value": value,
        "formula": f"(ROE - g) / (Re - g) = ({roe:.4f} - {g:.4f}) / {denom:.4f}",
        "inputs_used": {"roe": roe, "re": re, "g": g},
    }


def _ev_ebitda(
    roic: float,
    wacc: float,
    g: float,
    tax_rate: float,
    reinvest_rate: float,
    capex_volatility_signal: bool,
) -> dict[str, Any]:
    """EV/EBITDA approximation from ROIC, WACC, g.

    Formula (decision #17 approximation):
      EV/EBITDA ≈ (1 - tax_rate) * (1 - reinvest_rate) / (WACC - g)

    This is an approximation. Reliable only when capital intensity is stable.
    Warning fires when capex_volatility_signal is True.
    """
    denom = wacc - g
    value = (1.0 - tax_rate) * (1.0 - reinvest_rate) / denom

    warnings: list[str] = []
    if capex_volatility_signal:
        warnings.append(
            "When capital intensity (capex/EBITDA) is shifting materially, "
            "this formula is approximate. Prefer DCF for capital-intensive cyclicals."
        )

    return {
        "value": value,
        "formula": (
            f"(1 - tax_rate) * (1 - reinvest_rate) / (WACC - g) = "
            f"(1 - {tax_rate:.4f}) * (1 - {reinvest_rate:.4f}) / {denom:.4f}"
        ),
        "inputs_used": {
            "roic": roic,
            "wacc": wacc,
            "g": g,
            "tax_rate": tax_rate,
            "reinvest_rate": reinvest_rate,
        },
        "when_not_to_use": (
            "When capital intensity (capex/EBITDA) is shifting materially — "
            "this formula assumes stable capital structure. Prefer DCF for "
            "capital-intensive cyclicals or during capex cycle transitions."
        ),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    cost_of_equity: float,
    growth: float,
    roe: float,
    payout_ratio: float | None = None,
    roic: float | None = None,
    wacc: float | None = None,
    tax_rate: float | None = None,
    reinvest_rate: float | None = None,
    capex_volatility_signal: bool = False,
    current_multiples: dict[str, float] | None = None,
    multiples_to_compute: list[str] | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute fundamental-justified multiples and compare to actuals.

    Args:
        cost_of_equity: Required return on equity (Re). From cost_of_capital_builder.
        growth: Long-run sustainable growth rate (g). Must be < Re.
        roe: Return on equity. Required for P/B and forward P/E derivation.
        payout_ratio: Dividend payout ratio. Derived from g/ROE if not supplied.
        roic: Return on invested capital. Required for ev_ebitda.
        wacc: Weighted average cost of capital. Required for ev_ebitda.
        tax_rate: Effective/marginal tax rate. Required for ev_ebitda.
        reinvest_rate: Reinvestment rate. Required for ev_ebitda.
        capex_volatility_signal: If True, triggers the capital-intensity warning on EV/EBITDA.
        current_multiples: Actual current multiples for spread computation.
        multiples_to_compute: Which multiples to compute. Default: all four multiples.
        data_as_of: ISO date of underlying data.
        source_provenance: Citation IDs.
    """
    re = cost_of_equity
    g = growth

    # Validation
    if re <= g:
        raise ValueError(
            f"cost_of_equity ({re}) must be > growth ({g}). "
            "Justified multiple formulas diverge when Re <= g."
        )

    if g > roe:
        raise ValueError(
            f"growth ({g}) must be <= ROE ({roe}). "
            "P/B and forward P/E formulas are meaningless when g > ROE "
            "(implied payout ratio becomes negative, violating the sustainable growth identity)."
        )

    # Derive payout if not given
    if payout_ratio is None:
        # Sustainable growth identity: g = ROE * (1 - payout) => payout = 1 - g/ROE
        payout_ratio = 1.0 - g / roe if roe > 0 else None

    if payout_ratio is not None and payout_ratio < 0:
        raise ValueError(
            f"Implied payout_ratio ({payout_ratio:.4f}) < 0. "
            "This means g > ROE — the sustainable growth identity is violated."
        )

    _to_compute = set(multiples_to_compute or ["forward_pe", "trailing_pe", "pb", "ev_ebitda"])
    justified: dict[str, Any] = {}
    warnings: list[str] = []

    # Forward P/E
    if "forward_pe" in _to_compute:
        if payout_ratio is None:
            justified["forward_pe"] = {"value": None, "reason": "payout_ratio not available"}
        else:
            justified["forward_pe"] = _forward_pe(payout=payout_ratio, re=re, g=g)

    # Trailing P/E
    if "trailing_pe" in _to_compute:
        if payout_ratio is None:
            justified["trailing_pe"] = {"value": None, "reason": "payout_ratio not available"}
        else:
            justified["trailing_pe"] = _trailing_pe(payout=payout_ratio, re=re, g=g)

    # P/B
    if "pb" in _to_compute:
        pb_result = _pb(roe=roe, re=re, g=g)
        if pb_result["value"] < 0:
            # This shouldn't happen given the g <= ROE guard above, but handle defensively
            warnings.append(
                "Justified P/B is negative. This indicates ROE < g, which the input guard "
                "should have caught. Review input consistency."
            )
        justified["pb"] = pb_result

    # EV/EBITDA
    if "ev_ebitda" in _to_compute:
        if wacc is None or tax_rate is None or reinvest_rate is None:
            justified["ev_ebitda"] = {
                "value": None,
                "reason": (
                    "Insufficient inputs for EV/EBITDA justified multiple. "
                    "Supply roic, wacc, tax_rate, and reinvest_rate."
                ),
            }
        elif wacc <= g:
            justified["ev_ebitda"] = {
                "value": None,
                "reason": f"WACC ({wacc}) must be > growth ({g}) for EV/EBITDA formula.",
            }
        else:
            _roic = roic if roic is not None else 0.0
            ev_result = _ev_ebitda(
                roic=_roic,
                wacc=wacc,
                g=g,
                tax_rate=tax_rate,
                reinvest_rate=reinvest_rate,
                capex_volatility_signal=capex_volatility_signal,
            )
            justified["ev_ebitda"] = ev_result
            warnings.extend(ev_result.get("warnings", []))

    # Spread computation
    spreads: dict[str, Any] | None = None
    if current_multiples is not None:
        spreads = {}
        for key, jdata in justified.items():
            if jdata.get("value") is None:
                spreads[key] = {
                    "spread_pct": None,
                    "verdict": "cannot compute — justified value unavailable",
                }
                continue
            actual = current_multiples.get(key)
            if actual is None:
                spreads[key] = {"spread_pct": None, "verdict": "no actual multiple provided"}
                continue
            j_val = jdata["value"]
            if j_val == 0:
                spreads[key] = {
                    "spread_pct": None,
                    "verdict": "justified value is zero — spread undefined",
                }
                continue
            spread_pct = (actual - j_val) / j_val
            spreads[key] = {
                "justified": j_val,
                "actual": actual,
                "spread_pct": spread_pct,
                "verdict": _spread_verdict(spread_pct),
            }
    else:
        spreads = None  # No actuals supplied; justified multiples still emitted

    # Narrative
    narrative_parts: list[str] = []
    fpe = justified.get("forward_pe", {}).get("value")
    pb_val = justified.get("pb", {}).get("value")
    if fpe is not None:
        narrative_parts.append(f"Justified forward P/E: {fpe:.1f}x.")
    if pb_val is not None:
        narrative_parts.append(f"Justified P/B: {pb_val:.2f}x.")
    if spreads:
        for k, s in spreads.items():
            if s.get("verdict") and s.get("spread_pct") is not None:
                narrative_parts.append(
                    f"{k.upper()} {s['verdict']} ({s['spread_pct'] * 100:+.1f}%)."
                )

    return {
        "fundamentals_used": {
            "cost_of_equity": re,
            "growth": g,
            "roe": roe,
            "payout_ratio": payout_ratio,
            "roic": roic,
            "wacc": wacc,
        },
        "justified_multiples": justified,
        "actual_multiples": current_multiples,
        "spreads": spreads,
        "narrative": " ".join(narrative_parts) if narrative_parts else None,
        "warnings": warnings,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="justified_multiples",
        category=Category.ALTERNATIVE_VALUATION,
        one_liner=(
            "Derive fundamental-justified P/E, P/B, EV/EBITDA from ROE/growth/payout; "
            "compare against actual multiples."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute the multiples a company should trade at given its fundamentals "
            "(ROE, growth, payout, cost of equity). Pairs with comparables.run to "
            "distinguish 'cheap vs. peers' from 'cheap vs. fundamentals'."
        ),
        when_to_use=[
            "Valuation triangulation in initiation reports alongside DCF and comparables.",
            "Post-results updates: check if multiple re-rating is justified by fundamentals.",
            "Sector cross-company analysis: rank stocks by justified-vs-actual spread.",
            "When the question is 'what multiple does this ROE profile deserve?'",
        ],
        when_not_to_use=[
            "Pre-dividend or zero-payout companies — forward P/E breaks down; use dcf_engine.",
            "Companies with ROE < growth — P/B justified multiple is negative;"
            " inputs violate the sustainable-growth identity.",
            "EV/EBITDA for capital-intensive cyclicals during capex transitions — use"
            " capex_volatility_signal flag and prefer dcf_engine.",
            "As the sole valuation method — quantifies implied quality premium/discount"
            " but does not anchor an intrinsic value independently.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "cost_of_equity": HelperParam(
                type="float",
                description="Required return on equity (Re). From cost_of_capital_builder.",
                required=True,
            ),
            "growth": HelperParam(
                type="float",
                description="Long-run sustainable growth rate. Must be < Re and <= ROE.",
                required=True,
            ),
            "roe": HelperParam(
                type="float",
                description="Return on equity. Required for P/B and forward P/E derivation.",
                required=True,
            ),
            "payout_ratio": HelperParam(
                type="float",
                default=None,
                description="Dividend payout ratio. Derived from 1 - g/ROE if not supplied.",
                required=False,
            ),
            "roic": HelperParam(
                type="float",
                default=None,
                description="Return on invested capital. Required for EV/EBITDA.",
                required=False,
            ),
            "wacc": HelperParam(
                type="float",
                default=None,
                description="WACC. Required for EV/EBITDA justified multiple.",
                required=False,
            ),
            "tax_rate": HelperParam(
                type="float",
                default=None,
                description="Effective/marginal tax rate. Required for EV/EBITDA.",
                required=False,
            ),
            "reinvest_rate": HelperParam(
                type="float",
                default=None,
                description="Reinvestment rate. Required for EV/EBITDA approximation.",
                required=False,
            ),
            "capex_volatility_signal": HelperParam(
                type="bool",
                default=False,
                description=(
                    "Set True if capital intensity is shifting — triggers"
                    " EV/EBITDA capital-intensity warning."
                ),
                required=False,
            ),
            "current_multiples": HelperParam(
                type="dict[str, float]",
                default=None,
                description=(
                    "Actual current multiples (forward_pe, trailing_pe, pb, ev_ebitda)."
                    " Spread computed when provided."
                ),
                required=False,
            ),
            "multiples_to_compute": HelperParam(
                type="list[str]",
                default=None,
                description=(
                    "Which multiples to compute. Default: [forward_pe, trailing_pe, pb, ev_ebitda]."
                ),
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="justified_multiples_output",
                type="structured_object",
                description=(
                    "justified_multiples dict (per-multiple formula + value), "
                    "actual_multiples, spreads (justified vs. actual %), and narrative."
                ),
            ),
        ],
        produces_artifacts=["justified_multiples_output"],
        consumes_artifacts=["cost_of_capital_output"],
        data_dependencies=["cost_of_capital_builder", "eodhd.fundamentals"],
    ),
    skill_doc=SkillDocRef(
        path="skills/justified_multiples.md",
        estimated_tokens=1700,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
