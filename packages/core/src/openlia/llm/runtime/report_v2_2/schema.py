from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from .enums import Category, VerifierIssueType


class HelperParam(BaseModel):
    """Per schema-and-skills §3.2."""

    type: str
    default: Any | None = None
    derivation: str | None = None
    description: str
    required: bool = True


class HelperOutput(BaseModel):
    """Documentation for the drafter; not used for shape validation.

    Per schema-and-skills §3.2: verifier does NOT read this — shape validation
    uses runtime Pydantic introspection on the helper's return type annotation.
    This field is explicitly documentation-only.
    """

    name: str
    type: str  # OutputType literal — kept as str to avoid import cycle
    description: str


class HelperExample(BaseModel):
    call: dict[str, Any]
    result_shape: str
    notes: str | None = None


class DirectoryEntry(BaseModel):
    """Tier L1.5 — always loaded. Per schema-and-skills §3.2."""

    name: str
    category: Category
    one_liner: str  # ~10-15 words; what it does at a glance


class SelectionGuidance(BaseModel):
    """Tier L2 — loaded when the planner picks helpers in this category.

    Per schema-and-skills §3.2.
    """

    purpose: str  # 1-2 sentences
    when_to_use: list[str]  # 2-4 bullets
    when_not_to_use: list[str]  # 2-4 bullets, with redirects to neighbors


class MechanicalContract(BaseModel):
    """Tier L2 — loaded with SelectionGuidance. Per schema-and-skills §3.2."""

    params: dict[str, HelperParam]
    outputs: list[HelperOutput]
    example: HelperExample | None = None
    produces_artifacts: list[str]  # ArtifactType IDs from artifact_types.yaml
    consumes_artifacts: list[str]  # ArtifactType IDs from artifact_types.yaml
    data_dependencies: list[str] = []  # e.g. ["eodhd.fundamentals"]


class SkillDocRef(BaseModel):
    """Tier L3 — pointer to skills/<name>.md, loaded on demand.

    Per schema-and-skills §3.2.
    """

    path: str  # e.g. "skills/dcf_engine.md"
    estimated_tokens: int  # planner uses this to budget L3 loads


class HelperSchema(BaseModel):
    """Universal helper contract for v2.2.

    Composes the four-tier contract per schema-and-skills §3.2.
    Each sub-model maps to exactly one projection tier.
    """

    version: str = "1.0"
    deprecated_at_version: str | None = None  # per execution-strategy locked decision #6
    directory: DirectoryEntry  # L1.5
    selection: SelectionGuidance  # L2 selection guidance
    contract: MechanicalContract  # L2 mechanical contract
    skill_doc: SkillDocRef | None = None  # L3; None for simple helpers
    verifier_hooks: list[VerifierIssueType] = []  # parent issue types this helper can emit
