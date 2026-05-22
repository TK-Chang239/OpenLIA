"""forensic_panel — Composite forensic concern score (0-100, higher = worse).

Registered name: "forensic_panel"

Aggregates 4 sub-signals:
  1. One-time item intensity (from one_time_item_identification output)
  2. Accruals from QoE panel (from quality_of_earnings_panel output)
  3. SBC intensity (from sbc_intensity output)
  4. Channel-stuffing signal: AR/Revenue surge detector (computed inline)

Score 0-100: 0 = no concerns, 100 = maximum forensic concerns.
Concern levels: 0-25 = low, 26-50 = moderate, 51-75 = elevated, 76-100 = high.

This helper is listed as complex (18-list per schema-and-skills §6).
Skill doc: skills/forensic_panel.md
"""

from __future__ import annotations

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

# Signal weights (must sum to 1.0)
_WEIGHTS = {
    "one_time_items": 0.25,
    "accruals": 0.30,
    "sbc_intensity": 0.20,
    "channel_stuffing": 0.25,
}

# Concern thresholds
_CONCERN_LEVELS = [
    (76, "high"),
    (51, "elevated"),
    (26, "moderate"),
    (0, "low"),
]


def _concern_level(score: float) -> str:
    for threshold, label in _CONCERN_LEVELS:
        if score >= threshold:
            return label
    return "low"


def _score_one_time_items(one_time_output: dict[str, Any] | None) -> float:
    """Score 0-100 for one-time item intensity.

    Based on pct_of_net_income (absolute). > 20% = max concern.
    """
    if one_time_output is None:
        return 0.0
    pct = one_time_output.get("pct_of_net_income")
    if pct is None:
        return 0.0
    # Scale: 0% = 0, 20%+ = 100
    return min(abs(pct) / 20.0 * 100.0, 100.0)


def _score_accruals(qoe_output: dict[str, Any] | None) -> float:
    """Score 0-100 for accruals concern.

    Uses accruals_pct_of_ni. >20% threshold is flagged.
    Also uses Sloan ratio: >0.10 adds concern.
    """
    if qoe_output is None:
        return 0.0

    score = 0.0
    accruals_pct = qoe_output.get("accruals_pct_of_ni")
    if accruals_pct is not None:
        # Scale: 0% = 0, 40%+ = 60 points (accruals component)
        score += min(abs(accruals_pct) / 40.0 * 60.0, 60.0)

    sloan = qoe_output.get("sloan_ratio")
    if sloan is not None:
        # Sloan > 0.10 is concern; scale to 40 points
        score += min(max(sloan, 0.0) / 0.20 * 40.0, 40.0)

    return min(score, 100.0)


def _score_sbc_intensity(sbc_output: dict[str, Any] | None) -> float:
    """Score 0-100 for SBC intensity concern.

    Based on sbc_pct_revenue: >10% = max concern.
    """
    if sbc_output is None:
        return 0.0
    pct = sbc_output.get("sbc_pct_revenue")
    if pct is None:
        return 0.0
    # Scale: 0% = 0, 10%+ = 100
    return min(pct / 10.0 * 100.0, 100.0)


def _score_channel_stuffing(
    ar_current: float,
    ar_prior: float,
    revenue_current: float,
    revenue_prior: float,
) -> float:
    """AR/Revenue surge detector (channel-stuffing signal).

    Computes change in AR/Revenue ratio. If AR grows much faster than revenue,
    flags channel-stuffing risk.
    Score 0-100: based on YoY change in AR/Revenue ratio.
    """
    if revenue_current <= 0 or revenue_prior <= 0:
        return 0.0
    ar_rev_current = ar_current / revenue_current
    ar_rev_prior = ar_prior / revenue_prior
    if ar_rev_prior == 0:
        return 0.0

    # % change in AR/Revenue ratio
    ar_rev_change = (ar_rev_current - ar_rev_prior) / ar_rev_prior * 100.0
    # Scale: 0% change = 0, 50%+ change = 100
    return min(max(ar_rev_change, 0.0) / 50.0 * 100.0, 100.0)


def execute(
    one_time_item_output: dict[str, Any] | None = None,
    quality_of_earnings_output: dict[str, Any] | None = None,
    sbc_intensity_output: dict[str, Any] | None = None,
    ar_current: float = 0.0,
    ar_prior: float = 0.0,
    revenue_current: float = 0.0,
    revenue_prior: float = 0.0,
) -> dict[str, Any]:
    """Compute composite forensic concern score.

    Aggregates 4 sub-signals into a weighted 0-100 score.
    Higher score = more forensic concern.

    Args:
        one_time_item_output: Output from one_time_item_identification helper.
        quality_of_earnings_output: Output from quality_of_earnings_panel helper.
        sbc_intensity_output: Output from sbc_intensity helper.
        ar_current: Accounts receivable, current period (for channel stuffing).
        ar_prior: Accounts receivable, prior period (for channel stuffing).
        revenue_current: Revenue, current period (for channel stuffing).
        revenue_prior: Revenue, prior period (for channel stuffing).

    Returns:
        Dict with per-signal scores, weights, composite score 0-100, and concern level.
    """
    signal_scores: dict[str, float] = {
        "one_time_items": _score_one_time_items(one_time_item_output),
        "accruals": _score_accruals(quality_of_earnings_output),
        "sbc_intensity": _score_sbc_intensity(sbc_intensity_output),
        "channel_stuffing": _score_channel_stuffing(
            ar_current, ar_prior, revenue_current, revenue_prior
        ),
    }

    composite = sum(signal_scores[k] * _WEIGHTS[k] for k in signal_scores)

    level = _concern_level(composite)

    # Top contributing signals (sorted by weighted contribution, descending)
    contributions = {k: signal_scores[k] * _WEIGHTS[k] for k in signal_scores}
    top_signals = sorted(contributions.items(), key=lambda x: x[1], reverse=True)

    return {
        "composite_score": round(composite, 1),
        "concern_level": level,
        "signal_scores": {k: round(v, 1) for k, v in signal_scores.items()},
        "signal_weights": _WEIGHTS,
        "signal_contributions": {k: round(v, 1) for k, v in contributions.items()},
        "top_signals": [{"signal": k, "contribution": round(v, 1)} for k, v in top_signals[:2]],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="forensic_panel",
        category=Category.FORENSIC,
        one_liner="Composite forensic concern score 0-100 from 4 sub-signals.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Aggregate one-time item intensity, accruals (QoE), SBC intensity, "
            "and channel-stuffing signals into a single forensic concern score "
            "0-100 (higher = worse). "
            "Produces a concern level: low/moderate/elevated/high."
        ),
        when_to_use=[
            "Top-level forensic summary in an equity research report.",
            "Screening for accounting risk before deep-dive analysis.",
        ],
        when_not_to_use=[
            "Individual signal detail — call the constituent helpers directly.",
            "Credit/solvency analysis — use ft_solvency_ratios or ft_altman_z_score.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "one_time_item_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output from one_time_item_identification. "
                    "Provides one-time item intensity."
                ),
            ),
            "quality_of_earnings_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description="Output from quality_of_earnings_panel. Provides accruals and Sloan.",
            ),
            "sbc_intensity_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description="Output from sbc_intensity. Provides SBC/revenue.",
            ),
            "ar_current": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="AR balance, current period. For channel-stuffing signal.",
            ),
            "ar_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="AR balance, prior period. For channel-stuffing signal.",
            ),
            "revenue_current": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Revenue, current period. For channel-stuffing signal.",
            ),
            "revenue_prior": HelperParam(
                type="float",
                required=False,
                default=0.0,
                description="Revenue, prior period. For channel-stuffing signal.",
            ),
        },
        outputs=[
            HelperOutput(
                name="forensic_panel",
                type="dict",
                description=(
                    "composite_score (0-100), concern_level, signal_scores, "
                    "signal_weights, signal_contributions, top_signals."
                ),
            ),
        ],
        produces_artifacts=["forensic_panel_output"],
        consumes_artifacts=[
            "one_time_item_output",
            "quality_of_earnings_output",
            "sbc_intensity_output",
        ],
    ),
    skill_doc=SkillDocRef(path="skills/forensic_panel.md", estimated_tokens=800),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
