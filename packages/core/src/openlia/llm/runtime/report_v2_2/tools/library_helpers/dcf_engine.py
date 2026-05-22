"""dcf_engine — full FCFF-based DCF valuation engine.

Registered name: "dcf_engine"

Supersedes the skeleton dcf_valuation.py wrapper (PR 0.2). That wrapper remains
registered for backward compatibility but is deprecated; callers should migrate
to dcf_engine for full FCFF methodology, three TV methods, mid-year convention,
and TV/EV concentration warnings.

Methods:
  "perpetuity"    — Gordon growth: TV = FCFF_{N+1} / (WACC - g)
  "exit_multiple" — TV = EBITDA_N * exit_multiple
  "key_value_driver" — McKinsey: TV = NOPAT_{N+1} * (1 - g/ROIC) / (WACC - g)
  All three TV values computed when terminal_method is not "exit_multiple";
  the declared terminal_method drives the primary EV.

Design ref: planning/2026-05-22-helpers-design-supplement.md §3
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
# Constants
# ---------------------------------------------------------------------------

_TV_PCT_WARN = 0.75  # warn if TV/EV > 75%
_TV_PCT_HIGH = 0.85  # verifier flag: extreme TV dependence


def _coerce_path(value: float | list[float], n: int) -> list[float]:
    """Expand a scalar or list to length n."""
    if isinstance(value, (int, float)):
        return [float(value)] * n
    if len(value) == n:
        return [float(v) for v in value]
    raise ValueError(f"Expected scalar or list of length {n}, got list of length {len(value)}")


# ---------------------------------------------------------------------------
# Core math
# ---------------------------------------------------------------------------


def _compute_fcff_schedule(
    revenue_path: list[float],
    op_margin_path: list[float],
    tax_rate_path: list[float],
    da_path: list[float],  # D&A pct of revenue
    capex_path: list[float],  # capex pct of revenue
    nwc_pct: list[float],  # NWC pct of revenue
) -> list[dict[str, float]]:
    n = len(revenue_path)
    schedule: list[dict[str, float]] = []
    prev_revenue = 0.0  # for delta NWC in year 1 we assume 0 prior revenue
    for t in range(n):
        rev = revenue_path[t]
        ebit = rev * op_margin_path[t]
        nopat = ebit * (1.0 - tax_rate_path[t])
        da = rev * da_path[t]
        capex = rev * capex_path[t]
        delta_nwc = (rev - prev_revenue) * nwc_pct[t]
        fcff = nopat + da - capex - delta_nwc
        schedule.append(
            {
                "year": t + 1,
                "revenue": rev,
                "ebit": ebit,
                "nopat": nopat,
                "da": da,
                "capex": capex,
                "delta_nwc": delta_nwc,
                "fcff": fcff,
            }
        )
        prev_revenue = rev
    return schedule


def _discount_factor(wacc: float, t: int, mid_year: bool) -> float:
    exponent = (t - 0.5) if mid_year else float(t)
    return 1.0 / (1.0 + wacc) ** exponent


def _perpetuity_tv(fcff_n: float, growth: float, wacc: float) -> float:
    if growth >= wacc:
        raise ValueError(
            f"terminal_growth ({growth}) must be < WACC ({wacc}). "
            "Gordon growth formula diverges when g >= WACC."
        )
    return fcff_n * (1.0 + growth) / (wacc - growth)


def _exit_multiple_tv(ebitda_n: float, multiple: float) -> float:
    return ebitda_n * multiple


def _kvd_tv(nopat_n: float, growth: float, roic: float, wacc: float) -> float:
    """McKinsey key value driver formula."""
    if growth >= wacc:
        raise ValueError(f"terminal_growth ({growth}) must be < WACC ({wacc}).")
    reinvestment_rate = growth / roic if roic != 0 else 0.0
    return nopat_n * (1.0 + growth) * (1.0 - reinvestment_rate) / (wacc - growth)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    revenue_path: list[float],
    operating_margin_path: float | list[float],
    tax_rate_path: float | list[float],
    da_pct_of_revenue: float | list[float],
    capex_pct_of_revenue: float | list[float],
    nwc_pct_of_revenue: float | list[float],
    cost_of_capital: dict[str, Any],
    terminal_method: str,
    terminal_growth: float = 0.025,
    terminal_exit_multiple: float | None = None,
    terminal_roic: float | None = None,
    mid_year_convention: bool = True,
    net_debt: float = 0.0,
    shares_outstanding: float = 0.0,
    non_operating_assets: float = 0.0,
    current_price: float | None = None,
    tv_pct_warn_threshold: float = _TV_PCT_WARN,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Run a full FCFF DCF.

    Args:
        revenue_path: Explicit forecast revenues, year 1..N (list of floats).
        operating_margin_path: EBIT margin per year or scalar.
        tax_rate_path: Tax rate per year or scalar.
        da_pct_of_revenue: D&A as % of revenue per year or scalar.
        capex_pct_of_revenue: Capex as % of revenue per year or scalar.
        nwc_pct_of_revenue: NWC intensity for delta NWC computation.
        cost_of_capital: Output from cost_of_capital_builder (dict with 'wacc').
        terminal_method: "perpetuity" | "exit_multiple" | "key_value_driver".
        terminal_growth: Long-run FCF growth rate for perpetuity / KVD TV.
        terminal_exit_multiple: EV/EBITDA exit multiple for exit_multiple method.
        terminal_roic: Terminal ROIC for KVD method.
        mid_year_convention: Discount at t-0.5 (institutional default).
        net_debt: Total debt minus cash for EV→equity bridge.
        shares_outstanding: Diluted shares for per-share computation.
        non_operating_assets: Excess cash / investments to add to equity value.
        current_price: Current market price for upside computation.
        tv_pct_warn_threshold: TV/EV fraction above which a warning is emitted.
        data_as_of: ISO date for data freshness.
        source_provenance: Citation IDs.
    """
    if terminal_method not in ("perpetuity", "exit_multiple", "key_value_driver"):
        raise ValueError(
            f"terminal_method must be perpetuity|exit_multiple|key_value_driver, "
            f"got {terminal_method!r}"
        )

    n = len(revenue_path)
    if n == 0:
        raise ValueError("revenue_path must be non-empty")

    wacc: float = cost_of_capital["wacc"]
    if wacc is None or wacc <= 0:
        raise ValueError("cost_of_capital.wacc must be a positive float")

    # Expand scalar paths
    op_margins = _coerce_path(operating_margin_path, n)
    taxes = _coerce_path(tax_rate_path, n)
    da_pcts = _coerce_path(da_pct_of_revenue, n)
    capex_pcts = _coerce_path(capex_pct_of_revenue, n)
    nwc_pcts = _coerce_path(nwc_pct_of_revenue, n)

    # Build FCFF schedule
    schedule = _compute_fcff_schedule(
        revenue_path, op_margins, taxes, da_pcts, capex_pcts, nwc_pcts
    )

    # Discount each period
    sum_pv_fcff = 0.0
    for row in schedule:
        t = row["year"]
        df = _discount_factor(wacc, t, mid_year_convention)
        pv = row["fcff"] * df
        row["discount_factor"] = df
        row["pv_fcff"] = pv
        sum_pv_fcff += pv

    warnings: list[str] = []

    # Terminal year values
    last_row = schedule[-1]
    fcff_n = last_row["fcff"]
    ebitda_n = last_row["ebit"] + last_row["da"]  # EBITDA = EBIT + D&A
    nopat_n = last_row["nopat"]
    rev_n = last_row["revenue"]

    # --- Terminal value computation ---
    tv_perpetuity: float | None = None
    tv_exit_multiple_val: float | None = None
    tv_kvd: float | None = None

    if terminal_growth >= wacc:
        raise ValueError(
            f"terminal_growth ({terminal_growth:.4f}) >= WACC ({wacc:.4f}). "
            "This produces a negative or infinite terminal value. Reduce terminal_growth."
        )

    # Gordon perpetuity
    tv_perpetuity = _perpetuity_tv(fcff_n, terminal_growth, wacc)

    # Exit multiple
    if terminal_exit_multiple is not None:
        tv_exit_multiple_val = _exit_multiple_tv(ebitda_n, terminal_exit_multiple)
        # Cross-check: implied perpetuity growth from exit multiple TV
        fcff_n1 = fcff_n * (1.0 + terminal_growth)
        if tv_exit_multiple_val > 0 and fcff_n1 > 0:
            implied_g = wacc - fcff_n1 / tv_exit_multiple_val
            if implied_g >= wacc:
                warnings.append(
                    f"Exit multiple TV implies g={implied_g:.3f} >= WACC={wacc:.3f}; "
                    "exit multiple may be too high."
                )

    # KVD
    if terminal_roic is not None:
        try:
            tv_kvd = _kvd_tv(nopat_n, terminal_growth, terminal_roic, wacc)
        except ValueError as exc:
            warnings.append(f"KVD TV error: {exc}")

    # Select primary TV based on terminal_method
    if terminal_method == "perpetuity":
        primary_tv = tv_perpetuity
    elif terminal_method == "exit_multiple":
        if tv_exit_multiple_val is None:
            raise ValueError("terminal_exit_multiple required for exit_multiple method")
        primary_tv = tv_exit_multiple_val
    else:  # key_value_driver
        if tv_kvd is None:
            raise ValueError("terminal_roic required for key_value_driver method")
        primary_tv = tv_kvd

    # PV of terminal value (end-of-period convention for TV)
    pv_tv_factor = 1.0 / (1.0 + wacc) ** n
    pv_tv = primary_tv * pv_tv_factor

    enterprise_value = sum_pv_fcff + pv_tv
    tv_pct_of_ev = pv_tv / enterprise_value if enterprise_value > 0 else 0.0

    if tv_pct_of_ev > tv_pct_warn_threshold:
        warnings.append(
            f"Terminal value is {tv_pct_of_ev * 100:.1f}% of EV "
            f"(threshold {tv_pct_warn_threshold * 100:.0f}%). "
            "Valuation is highly sensitive to terminal assumptions."
        )

    # EV → equity bridge
    # equity = EV - net_debt + non_operating_assets
    # net_debt = total_debt - cash (caller's responsibility to net correctly)
    equity_value = enterprise_value - net_debt + non_operating_assets

    # Per-share
    implied_value_per_share: float | None = None
    implied_upside_pct: float | None = None
    if shares_outstanding > 0:
        implied_value_per_share = equity_value / shares_outstanding
        if current_price is not None and current_price > 0:
            implied_upside_pct = (implied_value_per_share - current_price) / current_price

    # Assumption echo
    assumption_echo: dict[str, Any] = {
        "operating_margin_terminal_year": op_margins[-1],
        "capex_pct_terminal_year": capex_pcts[-1],
        "da_pct_terminal_year": da_pcts[-1],
        "implied_terminal_roic": (
            (nopat_n / (rev_n * capex_pcts[-1])) if capex_pcts[-1] > 0 else None
        ),
    }

    # Terminal value block
    tv_block: dict[str, Any] = {
        "method": terminal_method,
        "terminal_growth": terminal_growth,
        "wacc": wacc,
        "fcff_year_n": fcff_n,
        "fcff_year_n_plus_one": fcff_n * (1.0 + terminal_growth),
        "ebitda_year_n": ebitda_n,
        "terminal_value_nominal": primary_tv,
        "pv_terminal_value": pv_tv,
        "tv_pct_of_ev": tv_pct_of_ev,
        "terminal_exit_multiple_used": terminal_exit_multiple,
        "terminal_roic_used": terminal_roic,
        "all_methods": {
            "perpetuity": tv_perpetuity,
            "exit_multiple": tv_exit_multiple_val,
            "key_value_driver": tv_kvd,
        },
    }

    # Narrative
    narrative_parts: list[str] = []
    if implied_value_per_share is not None and current_price is not None:
        direction = "upside" if (implied_upside_pct or 0) >= 0 else "downside"
        narrative_parts.append(
            f"Implied ${implied_value_per_share:.2f}/share vs current ${current_price:.2f}, "
            f"{abs((implied_upside_pct or 0) * 100):.1f}% {direction}."
        )
    narrative_parts.append(
        f"Terminal value is {tv_pct_of_ev * 100:.1f}% of EV "
        f"({terminal_method} method, g={terminal_growth * 100:.1f}%, WACC={wacc * 100:.1f}%)."
    )
    if assumption_echo.get("implied_terminal_roic"):
        narrative_parts.append(
            f"Implied terminal ROIC {assumption_echo['implied_terminal_roic'] * 100:.1f}%."
        )

    return {
        "explicit_period_years": n,
        "fcff_schedule": schedule,
        "sum_pv_fcff": sum_pv_fcff,
        "terminal_value": tv_block,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "non_operating_assets": non_operating_assets,
        "implied_equity_value": equity_value,
        "shares_outstanding_diluted": shares_outstanding,
        "implied_value_per_share": implied_value_per_share,
        "current_price": current_price,
        "implied_upside_pct": implied_upside_pct,
        "assumption_echo": assumption_echo,
        "mid_year_convention": mid_year_convention,
        "narrative": " ".join(narrative_parts),
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
        name="dcf_engine",
        category=Category.DCF,
        one_liner=(
            "Full FCFF DCF engine: explicit-period cash flows, "
            "three terminal value methods, mid-year convention, equity bridge."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute intrinsic equity value via discounted FCFF. "
            "Accepts revenue/margin paths and a cost_of_capital_builder output, "
            "projects per-period FCFF, discounts at WACC (mid-year convention), "
            "and computes TV via perpetuity, exit multiple, or key value driver. "
            "Supersedes the dcf_valuation skeleton helper."
        ),
        when_to_use=[
            "Primary intrinsic valuation in an initiation or update report.",
            "When you need all three TV methods for triangulation.",
            "When sensitivity analysis over WACC x terminal growth is required (pair with sensitivity_table).",  # noqa: E501
            "When explicit-period margin and capex paths are available from the forecast_builder.",
        ],
        when_not_to_use=[
            "Quick comps-only analysis — use comparables.run instead.",
            "Dividend-paying names as primary valuation — use ddm_family instead.",
            "FCFE (equity FCF) basis — dcf_engine uses FCFF only; FCFE support deferred.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "revenue_path": HelperParam(
                type="list[float]",
                description="Explicit forecast revenues year 1..N.",
                required=True,
            ),
            "operating_margin_path": HelperParam(
                type="float | list[float]",
                description="EBIT margin per year or scalar applied to all years.",
                required=True,
            ),
            "tax_rate_path": HelperParam(
                type="float | list[float]",
                description="Tax rate per year or scalar.",
                required=True,
            ),
            "da_pct_of_revenue": HelperParam(
                type="float | list[float]",
                description="D&A as fraction of revenue per year or scalar.",
                required=True,
            ),
            "capex_pct_of_revenue": HelperParam(
                type="float | list[float]",
                description="Capex as fraction of revenue per year or scalar.",
                required=True,
            ),
            "nwc_pct_of_revenue": HelperParam(
                type="float | list[float]",
                description="NWC intensity: delta NWC = (Rev_t - Rev_{t-1}) * nwc_pct.",
                required=True,
            ),
            "cost_of_capital": HelperParam(
                type="dict",
                description="Output from cost_of_capital_builder with 'wacc' key.",
                required=True,
            ),
            "terminal_method": HelperParam(
                type="str",
                description="perpetuity | exit_multiple | key_value_driver.",
                required=True,
            ),
            "terminal_growth": HelperParam(
                type="float",
                default=0.025,
                description="Long-run FCFF growth rate. Must be < WACC.",
                required=False,
            ),
            "terminal_exit_multiple": HelperParam(
                type="float",
                default=None,
                description="EV/EBITDA exit multiple; required for exit_multiple method.",
                required=False,
            ),
            "terminal_roic": HelperParam(
                type="float",
                default=None,
                description="Terminal ROIC; required for key_value_driver method.",
                required=False,
            ),
            "mid_year_convention": HelperParam(
                type="bool",
                default=True,
                description="Discount at t-0.5 (institutional default). Set False for end-of-year.",
                required=False,
            ),
            "net_debt": HelperParam(
                type="float",
                default=0.0,
                description="Net debt = total_debt - cash. Negative = net cash position.",
                required=False,
            ),
            "shares_outstanding": HelperParam(
                type="float",
                default=0.0,
                description="Diluted shares outstanding for per-share computation.",
                required=False,
            ),
            "non_operating_assets": HelperParam(
                type="float",
                default=0.0,
                description="Excess cash / investments to add to equity value.",
                required=False,
            ),
            "current_price": HelperParam(
                type="float",
                default=None,
                description="Current market price for upside/downside computation.",
                required=False,
            ),
            "tv_pct_warn_threshold": HelperParam(
                type="float",
                default=0.75,
                description="TV/EV fraction above which a terminal-heavy warning is emitted.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="dcf_output",
                type="dcf_output",
                description=(
                    "FCFF schedule, discounted PV per period, terminal value block "
                    "(all three methods), EV, equity value, per-share value, and warnings."
                ),
            ),
        ],
        produces_artifacts=["dcf_output"],
        consumes_artifacts=["cost_of_capital_output"],
        data_dependencies=["cost_of_capital_builder"],
    ),
    skill_doc=SkillDocRef(
        path="skills/dcf_engine.md",
        estimated_tokens=2200,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
