"""statement_integrity_bundle — Composite financial-statement integrity panel.

Registered name (18-list): "statement_integrity_bundle"
Also documented as: "statement_integrity_panel" (design doc alias; both names
appear in the module docstring per schema-and-skills §6).

Aggregates four sub-panels:
  1. altman_z_variants       — bankruptcy/distress risk (supplement §8)
  2. beneish_m_score         — earnings manipulation detection (helpers-design §4.18)
  3. cross_statement_validation  — IS/BS/CFS coherence (PR 2.5)
  4. one_time_item_identification — non-recurring item intensity (PR 2.5)

Output:
  composite_statement_integrity_score : int 0-100 (higher = better integrity)
  component_scores : dict with per-sub-panel 0-100 score
  top_concerns : list of the most important integrity signals
  classification : "high_integrity" | "moderate_integrity" | "low_integrity"
  warnings : aggregated from sub-panels

Skill doc: skills/statement_integrity_bundle.md
This helper is on the 18-list (schema-and-skills §6 #15).
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

# Component weights (must sum to 1.0)
_WEIGHTS = {
    "altman_z": 0.25,
    "beneish": 0.30,
    "cross_statement": 0.25,
    "one_time_items": 0.20,
}


def _score_altman(altman_output: dict[str, Any] | None) -> tuple[float, list[str]]:
    """Convert Altman Z classification to 0-100 integrity score (higher = better).

    safe -> 90; gray -> 55; distress -> 15; missing -> 50 (neutral).
    """
    concerns: list[str] = []
    if altman_output is None:
        return 50.0, concerns

    # Handle "all" variant output (list)
    if "variants" in altman_output:
        # Use worst classification across variants
        classifications = [
            v.get("classification") for v in altman_output["variants"] if "classification" in v
        ]
        if not classifications:
            return 50.0, concerns
        if "distress" in classifications:
            classification = "distress"
        elif "gray" in classifications:
            classification = "gray"
        else:
            classification = "safe"
        z_score = None
    else:
        classification = altman_output.get("classification", "")
        z_score = altman_output.get("z_score")

    score_map = {"safe": 90.0, "gray": 55.0, "distress": 15.0}
    score = score_map.get(classification, 50.0)

    if classification == "distress":
        concerns.append(
            f"Altman Z in distress zone (score {z_score})"
            if z_score
            else "Altman Z in distress zone"
        )
    elif classification == "gray":
        concerns.append(
            f"Altman Z in gray zone (score {z_score})" if z_score else "Altman Z in gray zone"
        )

    return score, concerns


def _score_beneish(beneish_output: dict[str, Any] | None) -> tuple[float, list[str]]:
    """Convert Beneish classification to 0-100 integrity score.

    no_signal -> 85; likely_manipulator -> 15; missing -> 50 (neutral).
    """
    concerns: list[str] = []
    if beneish_output is None:
        return 50.0, concerns

    classification = beneish_output.get("classification", "")
    m_score = beneish_output.get("m_score")

    if classification == "likely_manipulator":
        score = 15.0
        concerns.append(
            f"Beneish M-score {m_score:.3f} signals likely manipulation (threshold -1.78)"
            if m_score is not None
            else "Beneish M-score signals likely manipulation"
        )
    elif classification == "no_signal":
        score = 85.0
    else:
        score = 50.0

    return score, concerns


def _score_cross_statement(csv_output: dict[str, Any] | None) -> tuple[float, list[str]]:
    """Score cross-statement validation output.

    No flags -> 90; 1 flag -> 65; 2+ flags -> 30.
    """
    concerns: list[str] = []
    if csv_output is None:
        return 50.0, concerns

    # cross_statement_validation outputs a list of checks with pass/fail
    checks = csv_output.get("checks", [])
    flag_count = sum(1 for c in checks if not c.get("passed", True))

    if flag_count == 0:
        return 90.0, concerns
    elif flag_count == 1:
        concerns.append("Cross-statement: 1 coherence flag detected")
        return 65.0, concerns
    else:
        concerns.append(f"Cross-statement: {flag_count} coherence flags detected")
        return 30.0, concerns


def _score_one_time_items(oti_output: dict[str, Any] | None) -> tuple[float, list[str]]:
    """Score one-time item intensity.

    Based on pct_of_net_income (absolute). < 5% -> 90; 5-20% -> 65; > 20% -> 30.
    """
    concerns: list[str] = []
    if oti_output is None:
        return 50.0, concerns

    pct = oti_output.get("pct_of_net_income")
    if pct is None:
        return 50.0, concerns

    abs_pct = abs(pct)
    if abs_pct < 5.0:
        return 90.0, concerns
    elif abs_pct < 20.0:
        concerns.append(f"One-time items {abs_pct:.1f}% of net income — moderate distortion")
        return 65.0, concerns
    else:
        concerns.append(f"One-time items {abs_pct:.1f}% of net income — high distortion")
        return 30.0, concerns


def _classify_composite(score: float) -> str:
    if score >= 75:
        return "high_integrity"
    elif score >= 50:
        return "moderate_integrity"
    else:
        return "low_integrity"


def execute(
    altman_z_output: dict[str, Any] | None = None,
    beneish_m_output: dict[str, Any] | None = None,
    cross_statement_output: dict[str, Any] | None = None,
    one_time_item_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute composite statement integrity score from 4 sub-panels.

    Composes altman_z_variants, beneish_m_score, cross_statement_validation,
    and one_time_item_identification into a unified 0-100 integrity score
    (higher = better integrity). Any sub-panel may be None (scored as neutral 50).

    Args:
        altman_z_output: Output from altman_z_variants helper.
        beneish_m_output: Output from beneish_m_score helper.
        cross_statement_output: Output from cross_statement_validation helper.
        one_time_item_output: Output from one_time_item_identification helper.

    Returns:
        Dict with composite_score, component_scores, classification,
        top_concerns (up to 4), and aggregated warnings.
    """
    altman_score, altman_concerns = _score_altman(altman_z_output)
    beneish_score, beneish_concerns = _score_beneish(beneish_m_output)
    cross_score, cross_concerns = _score_cross_statement(cross_statement_output)
    oti_score, oti_concerns = _score_one_time_items(one_time_item_output)

    component_scores = {
        "altman_z": round(altman_score, 1),
        "beneish": round(beneish_score, 1),
        "cross_statement": round(cross_score, 1),
        "one_time_items": round(oti_score, 1),
    }

    composite = sum(component_scores[k] * _WEIGHTS[k] for k in _WEIGHTS)
    composite = round(composite, 1)

    classification = _classify_composite(composite)

    # Aggregate and deduplicate concerns
    all_concerns = altman_concerns + beneish_concerns + cross_concerns + oti_concerns

    # Collect warnings from sub-panels
    aggregated_warnings: list[str] = []
    for output, label in [
        (altman_z_output, "altman_z"),
        (beneish_m_output, "beneish"),
        (cross_statement_output, "cross_statement"),
        (one_time_item_output, "one_time_items"),
    ]:
        if output is not None:
            for w in output.get("warnings", []):
                aggregated_warnings.append(f"[{label}] {w}")

    return {
        "composite_statement_integrity_score": composite,
        "classification": classification,
        "component_scores": component_scores,
        "component_weights": _WEIGHTS,
        "top_concerns": all_concerns[:4],
        "warnings": aggregated_warnings,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="statement_integrity_bundle",
        category=Category.STATEMENT_INTEGRITY,
        one_liner="Composite statement integrity: Altman + Beneish + cross-stmt + one-time items.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compose altman_z_variants, beneish_m_score, cross_statement_validation, "
            "and one_time_item_identification into a single 0-100 statement integrity score "
            "(higher = better). Provides a unified view of bankruptcy risk, earnings manipulation "
            "signals, balance-sheet coherence, and non-recurring item distortion. "
            "Also documented as 'statement_integrity_panel' in the supplement."
        ),
        when_to_use=[
            "Top-level integrity summary section in an initiation or update report.",
            "Pre-screening for accounting risk before deep forensic analysis.",
            "When any individual sub-panel has already been run and aggregation is needed.",
        ],
        when_not_to_use=[
            "For individual signal detail — call the constituent helper directly.",
            "Banks or insurers — Altman Z is not applicable; Beneish is unreliable for financials.",
            "Pre-revenue companies — Altman Z and Beneish both require two full periods.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "altman_z_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output from altman_z_variants. "
                    "If None, Altman component scored as neutral (50)."
                ),
            ),
            "beneish_m_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output from beneish_m_score. "
                    "If None, Beneish component scored as neutral (50)."
                ),
            ),
            "cross_statement_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output from cross_statement_validation. "
                    "If None, cross-statement component scored as neutral (50)."
                ),
            ),
            "one_time_item_output": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Output from one_time_item_identification. "
                    "If None, one-time item component scored as neutral (50)."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="statement_integrity_bundle_output",
                type="statement_integrity_bundle_output",
                description=(
                    "composite_statement_integrity_score (0-100, higher = better), "
                    "classification (high_integrity / moderate_integrity / low_integrity), "
                    "component_scores (per sub-panel), top_concerns (up to 4), warnings."
                ),
            ),
        ],
        produces_artifacts=["statement_integrity_bundle_output"],
        consumes_artifacts=[
            "altman_z_variants_output",
            "beneish_m_score_output",
            "cross_statement_validation_output",
            "one_time_item_output",
        ],
    ),
    skill_doc=SkillDocRef(
        path="skills/statement_integrity_bundle.md",
        estimated_tokens=1800,
    ),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
