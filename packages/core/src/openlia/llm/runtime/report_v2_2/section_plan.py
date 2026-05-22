"""SectionPlan schema for Stage 7a materialization.

Per artifact-injection §3: the hand-off contract from Stage 5 planner into Stage 7a.
ReportSectionPlan is the single boundary object; Stage 6 only needs to ensure every
artifact_id referenced is in its output map.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .enums import Fidelity


class SectionArtifactRef(BaseModel):
    """Reference to one artifact within a section, with requested fidelity.

    Per artifact-injection §3.
    """

    artifact_id: str  # must exist in Stage 6 output map
    fidelity: Fidelity  # requested level for THIS section
    note: str | None = None  # optional planner annotation; ignored by renderer


class SectionPlan(BaseModel):
    """Plan for one template section.

    Per artifact-injection §3.
    """

    section_id: str  # e.g. "valuation_dcf"
    title: str  # e.g. "Discounted Cash Flow Valuation"
    artifacts: list[SectionArtifactRef]
    drafter_brief: str | None = None  # 1-2 sentences guiding the drafter for this section


class ReportSectionPlan(BaseModel):
    """Full report-level section plan: one per run, output of resolve_section_plan.

    Per artifact-injection §3. Drafter renders sections in list order.
    """

    template_id: str  # e.g. "stock_initiation_v2"
    sections: list[SectionPlan]  # ordered; drafter renders in this order
    overrides_applied: list[str] = []  # audit trail: which planner overrides were applied


class SectionPlanOverride(BaseModel):
    """A delta emitted by the Stage 5 planner to mutate the template default.

    Per artifact-injection §4.2.
    """

    section_id: str
    operation: Literal["add", "remove", "change_fidelity", "add_brief"]
    artifact_id: str | None = None  # required for add / remove / change_fidelity
    fidelity: Fidelity | None = None  # required for add / change_fidelity
    drafter_brief: str | None = None  # required for add_brief


class PlannerOverrides(BaseModel):
    """Container for all planner-emitted overrides for one run.

    Per artifact-injection §4.2.
    """

    template_id: str
    overrides: list[SectionPlanOverride]
    rationale: str  # planner's stated reason; preserved in run trace for audit
