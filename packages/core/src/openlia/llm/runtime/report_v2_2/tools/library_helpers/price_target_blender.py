"""price_target_blender — weighted blend of per-methodology price targets.

Registered name: "price_target_blender"

Accepts a list of {name, value, weight, source_artifact_id} methodology targets
and produces a weighted-average blended price target with dispersion diagnostics.

Decision layer position: first helper. Output consumed by expected_total_return,
implied_upside_downside, rating_band_assigner, and football_field_chart.

Per locked decision #12: unweighted equal-weight mode (auto_weight="equal") is the
default when caller cannot supply reliable weights.

Design ref: planning/2026-05-22-helpers-design-supplement.md §7.1
"""

from __future__ import annotations

import datetime
import math
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

_WEIGHT_SUM_TOLERANCE = 0.01  # 1% rounding slack
_HIGH_DISPERSION_THRESHOLD = 0.50  # max-min > 50% of blended → high_dispersion flag
_DOMINANT_WEIGHT_THRESHOLD = 0.80  # weight > 80% → single-method warning


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _validate_and_normalise(
    items: list[dict[str, Any]],
    auto_weight: str,
) -> list[dict[str, Any]]:
    """Validate inputs; return list with resolved float weights.

    Drops items whose value is None; records reweight in each item's
    'dropped' key (False for retained, True for dropped).
    """
    if not items:
        raise ValueError("methodology_targets must be non-empty")

    # Partition live vs null
    live = [it for it in items if it.get("value") is not None]
    dropped = [it for it in items if it.get("value") is None]

    if not live:
        raise ValueError(
            "All methodology_targets have null values; cannot compute blended target."
        )

    # Resolve weights
    if auto_weight == "equal":
        n = len(live)
        weight_val = 1.0 / n
        for it in live:
            it["_resolved_weight"] = weight_val
    else:
        # Use provided weights; require they sum to ~1.0 after dropping nulls.
        for it in live:
            w = it.get("weight")
            if w is None:
                raise ValueError(
                    f"Methodology {it.get('name')!r}: weight is required "
                    "when auto_weight is not 'equal'."
                )
            if w < 0:
                raise ValueError(f"Methodology {it.get('name')!r}: weight must be non-negative.")
            it["_resolved_weight"] = float(w)

        raw_sum = sum(it["_resolved_weight"] for it in live)
        if abs(raw_sum - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(
                f"Weights sum to {raw_sum:.4f}; must equal 1.0 within ±{_WEIGHT_SUM_TOLERANCE}. "
                "Renormalize inputs or pass auto_weight='equal'."
            )
        # Renormalize to exactly 1.0 (absorb rounding)
        for it in live:
            it["_resolved_weight"] = it["_resolved_weight"] / raw_sum

    for it in dropped:
        it["_resolved_weight"] = 0.0

    return live, dropped


def _blended(live: list[dict[str, Any]]) -> float:
    return sum(it["_resolved_weight"] * float(it["value"]) for it in live)


def _dispersion(live: list[dict[str, Any]], blended_target: float) -> dict[str, Any]:
    values = [float(it["value"]) for it in live]
    min_v = min(values)
    max_v = max(values)
    n = len(values)
    stdev = math.sqrt(sum((v - blended_target) ** 2 for v in values) / n) if n > 1 else 0.0
    spread_pct = (max_v - min_v) / blended_target if blended_target != 0 else 0.0
    return {
        "min": min_v,
        "max": max_v,
        "stdev": stdev,
        "spread_pct_of_blended": spread_pct,
    }


def _confidence_score(stdev: float, blended_target: float) -> float:
    """Lower stddev → higher confidence. Score in [0, 1]."""
    if blended_target == 0:
        return 0.5
    cv = stdev / abs(blended_target)  # coefficient of variation
    # Linear decay: cv=0 → 1.0; cv=0.30+ → 0.0
    score = max(0.0, 1.0 - cv / 0.30)
    return round(score, 3)


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    methodology_targets: list[dict[str, Any]],
    auto_weight: str = "equal",
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Blend multiple per-methodology price targets into a single estimate.

    Args:
        methodology_targets: List of dicts, each with:
            - name (str): methodology label, e.g. "DCF perpetuity".
            - value (float | None): implied price target; None → dropped.
            - weight (float | None): fractional weight [0, 1]; required if
              auto_weight != 'equal'.
            - source_artifact_id (str | None): upstream artifact for provenance.
        auto_weight: "equal" (default) | "none" (use provided weights).
        data_as_of: ISO date for the computation.
        source_provenance: Upstream artifact citation IDs.

    Returns:
        dict with blended_target, method_breakdown, weight_audit,
        dispersion, confidence_score, warnings, narrative.
    """
    if auto_weight not in ("equal", "none"):
        raise ValueError(f"auto_weight must be 'equal' or 'none'; got {auto_weight!r}")

    live, dropped = _validate_and_normalise(
        [dict(it) for it in methodology_targets],
        auto_weight,
    )

    blended = _blended(live)
    disp = _dispersion(live, blended)
    conf = _confidence_score(disp["stdev"], blended)

    # Warnings
    warnings: list[str] = []
    reweighted = len(dropped) > 0
    if reweighted:
        dropped_names = [it.get("name", "?") for it in dropped]
        warnings.append(
            f"Dropped {len(dropped)} null-value method(s): {dropped_names}. "
            "Weights renormalized."
        )

    dominant = [it for it in live if it["_resolved_weight"] > _DOMINANT_WEIGHT_THRESHOLD]
    if dominant:
        warnings.append(
            f"Method {dominant[0].get('name')!r} carries weight "
            f"{dominant[0]['_resolved_weight']:.0%}. "
            "Single-method dominance — blender is structural overhead."
        )

    if disp["spread_pct_of_blended"] > _HIGH_DISPERSION_THRESHOLD:
        warnings.append(
            f"High dispersion: methods range ${disp['min']:.2f}-${disp['max']:.2f} "
            f"({disp['spread_pct_of_blended']:.0%} of blended). "
            "Investigate methodology assumptions."
        )

    method_breakdown = [
        {
            "name": it.get("name"),
            "value": float(it["value"]),
            "weight": it["_resolved_weight"],
            "source_artifact_id": it.get("source_artifact_id"),
            "weighted_contribution": it["_resolved_weight"] * float(it["value"]),
        }
        for it in live
    ]

    weight_sum = sum(it["_resolved_weight"] for it in live)
    weight_audit = {
        "sum": round(weight_sum, 6),
        "auto_weight_applied": auto_weight == "equal",
        "methods_dropped": len(dropped),
        "reweighted": reweighted,
    }

    # Narrative
    method_names = ", ".join(f"{it['name']} ({it['_resolved_weight']:.0%})" for it in live)
    narrative = (
        f"Blended price target ${blended:.2f} across {len(live)} method(s): {method_names}. "
        f"Range ${disp['min']:.2f}-${disp['max']:.2f} "
        f"({disp['spread_pct_of_blended']:.0%} spread). "
        f"Confidence score {conf:.2f} (stddev {disp['stdev']:.2f})."
    )
    if warnings:
        narrative += " " + " ".join(warnings)

    return {
        "blended_target": round(blended, 4),
        "method_breakdown": method_breakdown,
        "weight_audit": weight_audit,
        "dispersion": {
            "min": disp["min"],
            "max": disp["max"],
            "stdev": round(disp["stdev"], 4),
            "spread_pct_of_blended": round(disp["spread_pct_of_blended"], 4),
        },
        "confidence_score": conf,
        "warnings": warnings,
        "narrative": narrative,
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
        name="price_target_blender",
        category=Category.DECISION,
        one_liner="Blend per-methodology price targets into a weighted average with dispersion.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Combine multiple per-methodology price targets (DCF, DDM, comparables, SOTP) "
            "into a single blended price target with explicit weights, dispersion statistics, "
            "and a confidence score."
        ),
        when_to_use=[
            "After running DCF, DDM, and/or comparables helpers to produce a single PT.",
            "When analyst wants equal-weight blend of 2-5 methodology outputs.",
            "As input to expected_total_return and rating_band_assigner.",
        ],
        when_not_to_use=[
            "When only one methodology is available — return that value directly.",
            "For scenario weighting by probability — use scenario_weighting instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "methodology_targets": HelperParam(
                type="list[dict]",
                description=(
                    "List of {name, value, weight, source_artifact_id} dicts. "
                    "value may be None (dropped and reweighted). "
                    "weight required when auto_weight='none'."
                ),
                required=True,
            ),
            "auto_weight": HelperParam(
                type="str",
                default="equal",
                description="'equal' overrides all weights to 1/N. 'none' uses provided weights.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="price_target_blended",
                type="price_target_blended",
                description=(
                    "Blended target, method breakdown, weight audit, dispersion, "
                    "confidence_score, warnings, narrative."
                ),
            ),
        ],
        produces_artifacts=["price_target_blended"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(
        path="skills/price_target_blender.md",
        estimated_tokens=900,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, execute)
