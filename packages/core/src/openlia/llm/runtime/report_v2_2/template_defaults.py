"""Template defaults resolver: three-source fidelity merge.

Per artifact-injection §4.  Three sources in ascending precedence:
  1. Artifact-type default (from artifact_types.yaml, e.g. FULL for DCF outputs)
  2. Template-section override (from section_plan_defaults.yaml shipped with each template)
  3. Per-run planner override (from PlannerOutput.planner_overrides)

The resolver lives in materialize.py as resolve_section_plan().  This module
re-exports it so callers can import from a single stable location without
duplicating logic.

Additionally it provides:
  - load_template_defaults(template_id, root) — loads and parses a
    section_plan_defaults.yaml for a given template.
  - SEED_DEFAULTS — the in-process fallback for stock_initiation_v2 when
    no defaults YAML is present on disk (test-safe).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .enums import Fidelity
from .materialize import resolve_section_plan  # re-export; logic lives there
from .section_plan import (
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
)

__all__ = [
    "SEED_DEFAULTS",
    "load_template_defaults",
    "resolve_section_plan",
]

# ---------------------------------------------------------------------------
# Seed defaults (stock_initiation_v2) — matches artifact-injection §4.1 example
# ---------------------------------------------------------------------------

SEED_DEFAULTS = ReportSectionPlan(
    template_id="stock_initiation_v2",
    sections=[
        SectionPlan(
            section_id="executive_summary",
            title="Executive Summary",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_base_valuation", fidelity=Fidelity.HEADLINE),
                SectionArtifactRef(artifact_id="peer_multiple_panel", fidelity=Fidelity.HEADLINE),
                SectionArtifactRef(
                    artifact_id="price_target_consensus", fidelity=Fidelity.HEADLINE
                ),
            ],
        ),
        SectionPlan(
            section_id="investment_thesis",
            title="Investment Thesis",
            artifacts=[
                SectionArtifactRef(artifact_id="business_quality_panel", fidelity=Fidelity.SUMMARY),
                SectionArtifactRef(artifact_id="growth_drivers", fidelity=Fidelity.SUMMARY),
            ],
        ),
        SectionPlan(
            section_id="valuation_dcf",
            title="Discounted Cash Flow Valuation",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_base_valuation", fidelity=Fidelity.FULL),
                SectionArtifactRef(artifact_id="sensitivity_grid", fidelity=Fidelity.FULL),
                SectionArtifactRef(artifact_id="cost_of_capital_panel", fidelity=Fidelity.SUMMARY),
            ],
        ),
        SectionPlan(
            section_id="valuation_comps",
            title="Relative Valuation",
            artifacts=[
                SectionArtifactRef(artifact_id="peer_multiple_panel", fidelity=Fidelity.FULL),
                SectionArtifactRef(
                    artifact_id="historical_multiple_trends", fidelity=Fidelity.SUMMARY
                ),
                SectionArtifactRef(artifact_id="football_field_chart", fidelity=Fidelity.FULL),
            ],
        ),
    ],
)


# ---------------------------------------------------------------------------
# YAML loader
# ---------------------------------------------------------------------------


def _parse_section_plan_yaml(data: dict[str, Any]) -> ReportSectionPlan:
    """Parse a section_plan_defaults.yaml dict into ReportSectionPlan.

    Raises ValidationError on schema mismatch; raises KeyError on missing
    required keys.
    """
    template_id: str = data["template_id"]
    sections_raw: list[dict[str, Any]] = data.get("sections", [])
    sections: list[SectionPlan] = []
    for s in sections_raw:
        artifacts: list[SectionArtifactRef] = []
        for a in s.get("artifacts", []):
            # Accept dict shorthand: {artifact_id: ..., fidelity: ...}
            if isinstance(a, dict):
                artifacts.append(
                    SectionArtifactRef(
                        artifact_id=a["artifact_id"],
                        fidelity=Fidelity(a["fidelity"]),
                        note=a.get("note"),
                    )
                )
        sections.append(
            SectionPlan(
                section_id=s["section_id"],
                title=s["title"],
                artifacts=artifacts,
                drafter_brief=s.get("drafter_brief"),
            )
        )
    return ReportSectionPlan(template_id=template_id, sections=sections)


def load_template_defaults(
    template_id: str,
    root: Path | None = None,
) -> ReportSectionPlan:
    """Load section_plan_defaults.yaml for the given template_id.

    Search order:
      1. <root>/templates/<template_id>/section_plan_defaults.yaml
      2. SEED_DEFAULTS in-memory fallback (stock_initiation_v2 only)

    Args:
        template_id: e.g. "stock_initiation_v2"
        root: filesystem root to search; defaults to this file's package root.

    Raises:
        FileNotFoundError: if no YAML found and template_id != "stock_initiation_v2".
        ValidationError: if YAML is malformed.
    """
    if root is None:
        # Default: packages/core/src/openlia/llm/runtime/report_v2_2/templates/
        root = Path(__file__).parent / "templates"

    candidate = root / template_id / "section_plan_defaults.yaml"
    if candidate.exists():
        raw_data = yaml.safe_load(candidate.read_text()) or {}
        if not isinstance(raw_data, dict):
            raise ValueError(f"section_plan_defaults.yaml for {template_id!r} must be a mapping")
        return _parse_section_plan_yaml(raw_data)

    # Fallback: return the in-process seed defaults for stock_initiation_v2.
    if template_id == "stock_initiation_v2":
        return SEED_DEFAULTS

    raise FileNotFoundError(
        f"No section_plan_defaults.yaml found for template {template_id!r} "
        f"at {candidate}. "
        "Either add the file or register a SEED_DEFAULTS entry."
    )
