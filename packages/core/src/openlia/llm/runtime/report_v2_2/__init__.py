"""report_v2_2 — foundation package for the v2.2 equity research runtime.

Public surface: schema sub-models, enums, verifier issue model, ArtifactType
registry, helper registry, section plan, materialization, drafter prompt, and verifier.
Imports from this package are stable after PR 0.1 merges; downstream helpers bind
against these contracts.
"""

from .artifact_types import ArtifactType, ArtifactTypeRegistry
from .drafter_prompt import build_drafter_prompt
from .enums import Category, Fidelity, VerifierIssueType
from .materialize import (
    MaterializationError,
    MaterializedReport,
    MaterializedSection,
    PlanResolutionError,
    RenderedArtifact,
    materialize,
    materialize_section,
    register_projector,
    register_renderer,
    resolve_section_plan,
)
from .planner import (
    HelperInvocation,
    HelperSelection,
    Planner,
    PlannerOutput,
    sections_from_spec,
)
from .schema import (
    DirectoryEntry,
    HelperExample,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
)
from .section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)
from .sector_router import route_to_sector_template
from .template_defaults import SEED_DEFAULTS, load_template_defaults
from .tools.library_helpers import RegisteredHelper, list_helpers
from .verifier import Verifier
from .verifier_models import VerifierIssue

__all__ = [
    "SEED_DEFAULTS",
    "ArtifactType",
    "ArtifactTypeRegistry",
    "Category",
    "DirectoryEntry",
    "Fidelity",
    "HelperExample",
    "HelperInvocation",
    "HelperOutput",
    "HelperParam",
    "HelperSchema",
    "HelperSelection",
    "MaterializationError",
    "MaterializedReport",
    "MaterializedSection",
    "MechanicalContract",
    "PlanResolutionError",
    "Planner",
    "PlannerOutput",
    "PlannerOverrides",
    "RegisteredHelper",
    "RenderedArtifact",
    "ReportSectionPlan",
    "SectionArtifactRef",
    "SectionPlan",
    "SectionPlanOverride",
    "SelectionGuidance",
    "SkillDocRef",
    "Verifier",
    "VerifierIssue",
    "VerifierIssueType",
    "build_drafter_prompt",
    "list_helpers",
    "load_template_defaults",
    "materialize",
    "materialize_section",
    "register_projector",
    "register_renderer",
    "resolve_section_plan",
    "route_to_sector_template",
    "sections_from_spec",
]
