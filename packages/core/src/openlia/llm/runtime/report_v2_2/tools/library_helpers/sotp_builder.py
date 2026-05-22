"""sotp_builder — sum-of-the-parts valuation for conglomerates and multi-segment companies.

Registered name: "sotp_builder"

Values each operating segment at an appropriate method (DCF, EBITDA multiple,
book value, peer P/S, user-supplied), sums the segment EVs, applies a
conglomerate discount, deducts net debt, and produces consolidated equity value.

Supported segment valuation methods:
  "ebitda_multiple"   — segment_ev = metric_value * multiple
  "peer_ps"           — segment_ev = revenue * ps_multiple
  "peer_pe"           — segment_equity = net_income * pe_multiple (equity method)
  "book_value"        — segment_ev = book_value * multiple (default multiple 1.0)
  "dcf"               — segment_ev from dcf_engine output in method_inputs["enterprise_value"]
  "user_supplied"     — segment_ev = method_inputs["value"]

Design ref: planning/2026-05-22-helpers-design-supplement.md §6
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

_MAX_SEGMENTS_WARN = 10
_CONCENTRATION_WARN_THRESHOLD = 0.70  # warn if top segment > 70% of total EV


# ---------------------------------------------------------------------------
# Per-segment EV computation
# ---------------------------------------------------------------------------


def _compute_segment_ev(seg: dict[str, Any]) -> tuple[float, list[str]]:
    """Compute EV for a single segment dict. Returns (ev, warnings)."""
    method = seg.get("valuation_method") or seg.get("method", "")
    metric_value = float(seg.get("metric_value") or seg.get("value", 0.0))
    method_inputs: dict[str, Any] = seg.get("method_inputs") or {}
    warnings: list[str] = []

    if method == "ebitda_multiple":
        if metric_value < 0:
            raise ValueError(
                f"Segment '{seg.get('name', '?')}' has negative EBITDA "
                f"({metric_value}). Cannot apply EBITDA multiple on a loss-making segment. "
                "Use book_value, dcf, or user_supplied instead."
            )
        multiple = float(method_inputs.get("multiple", 8.0))
        ev = metric_value * multiple
        seg["_multiple_used"] = multiple

    elif method == "peer_ps":
        multiple = float(method_inputs.get("multiple", 2.0))
        ev = metric_value * multiple
        seg["_multiple_used"] = multiple

    elif method == "peer_pe":
        # Equity-value method — PE * net_income
        # For SOTP consistency, treat as equity value (no debt allocation)
        multiple = float(method_inputs.get("multiple", method_inputs.get("pe", 15.0)))
        ev = metric_value * multiple
        seg["_multiple_used"] = multiple
        warnings.append(
            f"Segment '{seg.get('name', '?')}': peer_pe yields equity value, "
            "not enterprise value. Ensure segment-specific debt is excluded from "
            "consolidated net_debt or the bridge will double-count."
        )

    elif method == "book_value":
        multiple = float(method_inputs.get("multiple", 1.0))
        ev = metric_value * multiple
        seg["_multiple_used"] = multiple

    elif method == "dcf":
        # Caller must pass dcf_engine output in method_inputs
        ev_raw = method_inputs.get("enterprise_value")
        if ev_raw is None:
            raise ValueError(
                f"Segment '{seg.get('name', '?')}' uses dcf method but "
                "method_inputs['enterprise_value'] is missing. "
                "Run dcf_engine for this segment first and pass its output."
            )
        ev = float(ev_raw)
        seg["_multiple_used"] = None

    elif method == "user_supplied":
        val = method_inputs.get("value")
        if val is None:
            raise ValueError(
                f"Segment '{seg.get('name', '?')}' uses user_supplied method but "
                "method_inputs['value'] is missing."
            )
        ev = float(val)
        seg["_multiple_used"] = None
        warnings.append(
            f"Segment '{seg.get('name', '?')}': value is analyst-supplied override. "
            "Narrative should cite the source of this estimate."
        )

    else:
        raise ValueError(
            f"Unknown valuation_method '{method}' for segment '{seg.get('name', '?')}'. "
            "Valid: ebitda_multiple, peer_ps, peer_pe, book_value, dcf, user_supplied."
        )

    # Ownership adjustment
    ownership_pct = float(seg.get("ownership_pct", 1.0))
    if ownership_pct != 1.0:
        ev = ev * ownership_pct

    # Control premium / discount
    ctrl = seg.get("control_premium_or_discount")
    if ctrl is not None:
        ev = ev * (1.0 + float(ctrl))

    return ev, warnings


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    segments: list[dict[str, Any]],
    corporate_overhead: float | None = None,
    corporate_overhead_capitalization_multiple: float = 8.0,
    non_operating_assets: float = 0.0,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    shares_outstanding: float,
    conglomerate_discount_pct: float = 0.0,
    tax_on_segment_sale: bool = False,
    current_price: float | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Build a sum-of-the-parts valuation.

    Args:
        segments: List of segment dicts, each with:
            name: str
            valuation_method: ebitda_multiple|peer_ps|peer_pe|book_value|dcf|user_supplied
            metric_value: float (EBITDA, revenue, book value, net income depending on method)
            method_inputs: dict of method-specific inputs (multiple, pe, enterprise_value, value)
            ownership_pct: float (default 1.0)
            control_premium_or_discount: float | None (e.g. 0.20 for 20% premium)
            comparable_set: list[str] (informational; included in output)
        corporate_overhead: Unallocated HQ cost (EBITDA/year basis). Capitalized at multiple.
        corporate_overhead_capitalization_multiple: Multiple used to capitalize overhead cost.
        non_operating_assets: Equity-method investments, excess cash, etc.
        net_debt: Consolidated net debt (total_debt - cash).
        minority_interest: Non-controlling interest at fair value.
        shares_outstanding: Diluted shares outstanding.
        conglomerate_discount_pct: Empirical discount on SOTP (0.10 = 10%).
        tax_on_segment_sale: If True, apply implied tax on segment uplift vs book.
        current_price: For implied upside/downside.
        data_as_of: ISO date of underlying data.
        source_provenance: Citation IDs.
    """
    if not segments:
        raise ValueError("segments must be a non-empty list.")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive.")

    warnings: list[str] = []

    # Flag degenerate SOTP
    single_segment = len(segments) == 1
    if single_segment:
        warnings.append(
            "Single-segment SOTP: equivalent to a direct single-method valuation. "
            "SOTP structure adds no incremental insight here."
        )

    if len(segments) > _MAX_SEGMENTS_WARN:
        warnings.append(
            f"{len(segments)} segments: large segment count can introduce spurious precision. "
            "Verify each segment's standalone valuation is independently supportable."
        )

    # Compute per-segment EVs
    computed_segments: list[dict[str, Any]] = []
    sum_ev = 0.0
    for seg in segments:
        seg_copy = dict(seg)
        seg_ev, seg_warnings = _compute_segment_ev(seg_copy)
        warnings.extend(seg_warnings)
        sum_ev += seg_ev
        computed_segments.append(
            {
                "name": seg_copy.get("name", "unnamed"),
                "valuation_method": seg_copy.get("valuation_method") or seg_copy.get("method", ""),
                "metric_kind": seg_copy.get("metric_kind", ""),
                "metric_value": seg_copy.get("metric_value") or seg_copy.get("value", 0.0),
                "multiple_used": seg_copy.get("_multiple_used"),
                "ownership_pct": float(seg_copy.get("ownership_pct", 1.0)),
                "control_premium_or_discount": seg_copy.get("control_premium_or_discount"),
                "segment_ev": seg_ev,
                "comparable_set": seg_copy.get("comparable_set"),
            }
        )

    # Tag concentration percentages (preliminary, before overhead / discount)
    for s in computed_segments:
        s["pct_of_gross_ev"] = (s["segment_ev"] / sum_ev) if sum_ev > 0 else 0.0

    # Top-segment concentration warning
    if computed_segments:
        top_pct = max(s["pct_of_gross_ev"] for s in computed_segments)
        if top_pct > _CONCENTRATION_WARN_THRESHOLD:
            top_name = max(computed_segments, key=lambda s: s["pct_of_gross_ev"])["name"]
            warnings.append(
                f"Top segment '{top_name}' represents {top_pct:.0%} of gross SOTP EV. "
                "At this concentration SOTP may not add meaningful valuation insight "
                "over a direct single-segment approach."
            )

    # Corporate overhead deduction
    overhead_capitalized = 0.0
    if corporate_overhead is not None and corporate_overhead > 0:
        overhead_capitalized = corporate_overhead * corporate_overhead_capitalization_multiple

    adjusted_sum_ev = sum_ev - overhead_capitalized

    # Conglomerate discount
    discount_amount = adjusted_sum_ev * conglomerate_discount_pct
    post_discount_ev = adjusted_sum_ev - discount_amount

    # Tax on segment sale (simplified: flat upside tax on total EV over book)
    # Full segment-level attribution deferred — apply as a summary warning instead
    tax_drag_note: str | None = None
    if tax_on_segment_sale:
        tax_drag_note = (
            "Tax-on-segment-sale flag set. Estimated tax drag depends on book values "
            "of individual segments. Apply segment-level analysis for a precise figure."
        )
        warnings.append(tax_drag_note)

    # Equity bridge
    implied_equity_value = post_discount_ev + non_operating_assets - net_debt - minority_interest

    # Per-share
    implied_value_per_share = implied_equity_value / shares_outstanding
    implied_upside_pct: float | None = None
    if current_price is not None and current_price > 0:
        implied_upside_pct = (implied_value_per_share - current_price) / current_price

    # Concentration ratio: top segment's share of gross EV
    concentration_ratio = max((s["pct_of_gross_ev"] for s in computed_segments), default=0.0)

    # Narrative
    narrative_parts: list[str] = [f"SOTP: {len(segments)} segments, gross EV {sum_ev:,.0f}."]
    if overhead_capitalized > 0:
        narrative_parts.append(f"Corporate overhead deduction {overhead_capitalized:,.0f}.")
    if conglomerate_discount_pct > 0:
        narrative_parts.append(
            f"Conglomerate discount {conglomerate_discount_pct:.0%} = {discount_amount:,.0f}."
        )
    narrative_parts.append(
        f"Equity value {implied_equity_value:,.0f} = {implied_value_per_share:.2f}/share."
    )
    if current_price is not None and implied_upside_pct is not None:
        direction = "upside" if implied_upside_pct >= 0 else "downside"
        narrative_parts.append(
            f"vs current ${current_price:.2f}, {abs(implied_upside_pct) * 100:.1f}% {direction}."
        )

    return {
        "segment_values": computed_segments,
        "sum_segment_ev": sum_ev,
        "corporate_overhead": corporate_overhead,
        "corporate_overhead_capitalization_multiple": corporate_overhead_capitalization_multiple,
        "corporate_overhead_deduction": overhead_capitalized,
        "adjusted_sum_ev": adjusted_sum_ev,
        "conglomerate_discount_pct": conglomerate_discount_pct,
        "conglomerate_discount_amount": discount_amount,
        "post_discount_ev": post_discount_ev,
        "non_operating_assets": non_operating_assets,
        "net_debt": net_debt,
        "minority_interest": minority_interest,
        "implied_equity_value": implied_equity_value,
        "shares_outstanding": shares_outstanding,
        "implied_value_per_share": implied_value_per_share,
        "current_price": current_price,
        "implied_upside_pct": implied_upside_pct,
        "concentration_ratio": concentration_ratio,
        "single_segment": single_segment,
        "tax_on_segment_sale": tax_on_segment_sale,
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
        name="sotp_builder",
        category=Category.ALTERNATIVE_VALUATION,
        one_liner=(
            "Sum-of-the-parts valuation: segment EVs, overhead deduction, "
            "conglomerate discount, equity bridge."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Value each operating segment independently (DCF, multiples, book value) "
            "and sum to a consolidated equity value. Designed for conglomerates, "
            "holding companies, and multi-segment businesses where segments have "
            "materially different growth, margin, or risk profiles."
        ),
        when_to_use=[
            "Initiation reports for conglomerates or holding companies with multiple segments.",
            "Post-segment-restructuring updates (spin-off, acquisition, divestiture)"
            " where segment mix changes.",
            "When segment-level valuations use different methods (industrial arm at EBITDA"
            " multiple, tech arm at P/S, finance arm at P/B).",
            "When an activist or strategic scenario involves monetizing individual segments.",
        ],
        when_not_to_use=[
            "Single-segment companies — direct dcf_engine or comparables.run is simpler.",
            "Companies without segment-level financials — segment EVs become unanchored.",
            "When all segments share the same industry/risk — comparables.run suffices.",
            "As the only valuation method — SOTP precision is illusory on rough estimates.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "segments": HelperParam(
                type="list[dict]",
                description=(
                    "Segment definitions. Each dict: name, valuation_method, metric_value, "
                    "method_inputs, ownership_pct (default 1.0), control_premium_or_discount, "
                    "comparable_set (informational)."
                ),
                required=True,
            ),
            "shares_outstanding": HelperParam(
                type="float",
                description="Diluted shares outstanding for per-share computation.",
                required=True,
            ),
            "net_debt": HelperParam(
                type="float",
                default=0.0,
                description="Consolidated net debt (total_debt - cash). Negative = net cash.",
                required=False,
            ),
            "corporate_overhead": HelperParam(
                type="float",
                default=None,
                description=(
                    "Annual unallocated corporate overhead (EBITDA basis)."
                    " Capitalized at the overhead multiple."
                ),
                required=False,
            ),
            "corporate_overhead_capitalization_multiple": HelperParam(
                type="float",
                default=8.0,
                description="Multiple used to capitalize overhead into an EV deduction.",
                required=False,
            ),
            "non_operating_assets": HelperParam(
                type="float",
                default=0.0,
                description=(
                    "Equity-method investments, excess cash, or real estate not in segment EVs."
                ),
                required=False,
            ),
            "minority_interest": HelperParam(
                type="float",
                default=0.0,
                description="Non-controlling interest at fair value. Subtracted from equity value.",
                required=False,
            ),
            "conglomerate_discount_pct": HelperParam(
                type="float",
                default=0.0,
                description=(
                    "Empirical conglomerate discount as a fraction (e.g. 0.10 = 10%)."
                    " Berger-Ofek 1995 range: 10-15%."
                ),
                required=False,
            ),
            "tax_on_segment_sale": HelperParam(
                type="bool",
                default=False,
                description=(
                    "If True, emit a warning about implied tax friction on segment monetization."
                ),
                required=False,
            ),
            "current_price": HelperParam(
                type="float",
                default=None,
                description="Current market price for upside/downside computation.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="sotp_output",
                type="structured_object",
                description=(
                    "Per-segment EV and pct_of_gross_ev, sum_segment_ev, overhead deduction, "
                    "conglomerate discount, equity bridge, implied_value_per_share, "
                    "concentration_ratio, and warnings."
                ),
            ),
        ],
        produces_artifacts=["sotp_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
    skill_doc=SkillDocRef(
        path="skills/sotp_builder.md",
        estimated_tokens=2000,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
