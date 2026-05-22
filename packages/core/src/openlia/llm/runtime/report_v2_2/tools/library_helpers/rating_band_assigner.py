"""rating_band_assigner — maps ETR + R/R to a rating recommendation.

Registered name: "rating_band_assigner"

Translates expected total return (ETR) and risk/reward ratio into a structured
rating recommendation with conviction modifier and explanatory prose.

Default rating bands (configurable via rating_bands_config):
  BUY:         ETR >= +15%  AND  R/R >= 1.5
  OUTPERFORM:  ETR >= +5%   AND  R/R >= 1.2   (alias ADD)
  HOLD:        -5% <= ETR < +7%
  UNDERPERFORM: ETR < -5%  AND  R/R < 1.5     (alias REDUCE)
  SELL:        ETR < -15%  OR  (R/R < 0.8 AND ETR < 0)

Conviction modifier (high / medium / low) derived from dispersion + R/R.

Design ref: planning/2026-05-22-helpers-design-supplement.md §7.5
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
# Default band configuration
# ---------------------------------------------------------------------------

_DEFAULT_BANDS: dict[str, Any] = {
    "buy": {"etr_min": 0.15, "rr_min": 1.5},
    "outperform": {"etr_min": 0.05, "rr_min": 1.2},
    "hold": {"etr_min": -0.05, "etr_max": 0.07},
    "underperform": {"etr_max": -0.05, "rr_max": 1.5},
    "sell_etr": {"etr_max": -0.15},
    "sell_rr": {"rr_max": 0.8, "etr_max": 0.0},
}


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _resolve_rating(
    etr: float,
    rr: float,
    bands: dict[str, Any],
) -> str:
    """Evaluate bands in priority order; return the first match.

    Priority: SELL > BUY > OUTPERFORM > UNDERPERFORM > HOLD.
    SELL is checked first because a deeply negative ETR or broken R/R overrides
    any other condition.
    """
    sell_etr = bands.get("sell_etr", _DEFAULT_BANDS["sell_etr"])
    sell_rr = bands.get("sell_rr", _DEFAULT_BANDS["sell_rr"])
    buy = bands.get("buy", _DEFAULT_BANDS["buy"])
    outperform = bands.get("outperform", _DEFAULT_BANDS["outperform"])
    underperform = bands.get("underperform", _DEFAULT_BANDS["underperform"])
    # SELL
    if etr < sell_etr.get("etr_max", -0.15):
        return "SELL"
    if rr < sell_rr.get("rr_max", 0.8) and etr < sell_rr.get("etr_max", 0.0):
        return "SELL"

    # BUY
    if etr >= buy.get("etr_min", 0.15) and rr >= buy.get("rr_min", 1.5):
        return "BUY"

    # OUTPERFORM (ADD)
    if etr >= outperform.get("etr_min", 0.05) and rr >= outperform.get("rr_min", 1.2):
        return "OUTPERFORM"

    # UNDERPERFORM (REDUCE)
    if etr < underperform.get("etr_max", -0.05) and rr < underperform.get("rr_max", 1.5):
        return "UNDERPERFORM"

    # HOLD — default catch-all in the ETR range
    return "HOLD"


def _conviction(
    conviction_score: float,
    rr: float,
    dispersion_stdev: float | None,
    blended_target: float | None,
) -> str:
    """Derive conviction level.

    High:   conviction_score >= 0.65 AND R/R >= 2.0
    Low:    conviction_score < 0.35 OR R/R < 1.0 OR dispersion/PT > 0.15
    Medium: everything else.
    """
    # Relative dispersion check
    if dispersion_stdev is not None and blended_target is not None and blended_target > 0:
        cv = dispersion_stdev / blended_target
    else:
        cv = 0.0

    if conviction_score >= 0.65 and rr >= 2.0 and cv <= 0.15:
        return "high"
    if conviction_score < 0.35 or rr < 1.0 or cv > 0.15:
        return "low"
    return "medium"


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    expected_total_return_pct: float,
    risk_reward_ratio: float,
    conviction_score: float = 0.5,
    rating_bands_config: dict[str, Any] | None = None,
    dispersion_stdev: float | None = None,
    blended_target: float | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Assign a rating band and conviction modifier.

    Args:
        expected_total_return_pct: ETR from expected_total_return helper.
        risk_reward_ratio: R/R from risk_reward_calculator.
        conviction_score: Analyst confidence [0, 1]; default 0.5.
        rating_bands_config: Optional dict overriding default band thresholds.
        dispersion_stdev: Optional stddev from price_target_blender for conviction.
        blended_target: Optional blended PT for relative dispersion computation.
        data_as_of: ISO date.
        source_provenance: Citation IDs.

    Returns:
        dict with rating, conviction, expected_total_return_pct, risk_reward_ratio,
        conviction_score, why_this_rating, narrative, verifier_check, warnings.
    """
    if conviction_score < 0 or conviction_score > 1:
        raise ValueError(f"conviction_score must be in [0, 1]; got {conviction_score}.")
    if risk_reward_ratio < 0:
        raise ValueError(f"risk_reward_ratio must be non-negative; got {risk_reward_ratio}.")

    bands = rating_bands_config or _DEFAULT_BANDS
    rating = _resolve_rating(expected_total_return_pct, risk_reward_ratio, bands)
    conviction = _conviction(
        conviction_score, risk_reward_ratio, dispersion_stdev, blended_target
    )

    warnings: list[str] = []

    # Internal consistency checks (verifier hooks)
    if rating == "BUY" and expected_total_return_pct < 0:
        warnings.append(
            "BUY rating with negative ETR — band logic may have been overridden. "
            "Verify rating_bands_config."
        )
    if rating == "SELL" and expected_total_return_pct > 0.10:
        warnings.append(
            "SELL rating with ETR > +10% — check R/R condition that triggered SELL."
        )

    # Explanatory prose
    etr_str = f"{expected_total_return_pct:+.1%}"
    rr_str = f"{risk_reward_ratio:.1f}x"
    conv_str = f"{conviction_score:.2f}"

    why_map = {
        "BUY": (
            f"ETR {etr_str} exceeds +15% BUY threshold; "
            f"R/R {rr_str} clears 1.5x minimum; "
            f"conviction {conv_str}."
        ),
        "OUTPERFORM": (
            f"ETR {etr_str} in +5-15% outperform range; "
            f"R/R {rr_str} meets 1.2x threshold; "
            f"conviction {conv_str}."
        ),
        "HOLD": (
            f"ETR {etr_str} within -5% to +7% hold range; "
            f"risk/reward {rr_str} does not clear BUY bar; "
            f"conviction {conv_str}."
        ),
        "UNDERPERFORM": (
            f"ETR {etr_str} below -5% with R/R {rr_str} under 1.5x; "
            f"conviction {conv_str}."
        ),
        "SELL": (
            f"ETR {etr_str} triggers SELL; "
            f"R/R {rr_str}; conviction {conv_str}."
        ),
    }
    why_this_rating = why_map.get(rating, f"ETR {etr_str}, R/R {rr_str}.")

    narrative = (
        f"{rating}-rated ({conviction} conviction). "
        f"ETR {etr_str} over 12-month horizon. "
        f"R/R {rr_str}."
    )

    return {
        "rating": rating,
        "conviction": conviction,
        "expected_total_return_pct": expected_total_return_pct,
        "risk_reward_ratio": risk_reward_ratio,
        "conviction_score": conviction_score,
        "why_this_rating": why_this_rating,
        "alternative_ratings_considered": [],
        "narrative": narrative,
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
        name="rating_band_assigner",
        category=Category.DECISION,
        one_liner="Map ETR + R/R to BUY/OUTPERFORM/HOLD/UNDERPERFORM/SELL with conviction.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Translate expected total return (ETR) and risk/reward ratio into a structured "
            "rating recommendation (BUY/OUTPERFORM/HOLD/UNDERPERFORM/SELL) with a "
            "conviction modifier (high/medium/low) and an explanatory narrative."
        ),
        when_to_use=[
            "After expected_total_return and risk_reward_calculator to finalize the rating.",
            "When the report requires a formal rating with conviction level.",
            "When customising band thresholds via rating_bands_config for house style.",
        ],
        when_not_to_use=[
            "As a standalone tool without ETR and R/R from the other decision helpers.",
            "For portfolio-level rating aggregation — out of scope.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "expected_total_return_pct": HelperParam(
                type="float",
                description="ETR from expected_total_return helper (decimal, e.g. 0.18 = +18%).",
                required=True,
            ),
            "risk_reward_ratio": HelperParam(
                type="float",
                description="R/R ratio from risk_reward_calculator (upside / |downside|).",
                required=True,
            ),
            "conviction_score": HelperParam(
                type="float",
                default=0.5,
                description=(
                    "Analyst confidence [0, 1]; informed by dispersion, "
                    "DCF TV %, quality panels."
                ),
                required=False,
            ),
            "rating_bands_config": HelperParam(
                type="dict",
                default=None,
                description="Override default band thresholds. See skill doc for schema.",
                required=False,
            ),
            "dispersion_stdev": HelperParam(
                type="float",
                default=None,
                description="Stddev from price_target_blender for conviction computation.",
                required=False,
            ),
            "blended_target": HelperParam(
                type="float",
                default=None,
                description="Blended PT for relative dispersion (CV) in conviction computation.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="rating_assignment",
                type="rating_assignment",
                description=(
                    "rating, conviction, why_this_rating, narrative, "
                    "alternative_ratings_considered."
                ),
            ),
        ],
        produces_artifacts=["rating_assignment"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(
        path="skills/rating_band_assigner.md",
        estimated_tokens=900,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
