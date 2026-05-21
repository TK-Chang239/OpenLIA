from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

IssueType = Literal[
    # structural
    "block_shape",
    "tombstone",
    "year_slip",
    # citation
    "citation_missing",
    "citation_unresolved",
    "citation_orphaned",
    # coverage
    "artifact_missing",
    "content_too_sparse",
    "directive_unmet",
    # quality
    "factual_inconsistency",
    "numeric_inconsistency",
    "incoherent_prose",
    # artifact-build
    "required_param_unresolvable",
    "helper_unavailable",
]


class VerifierIssue(BaseModel):
    issue_type: IssueType
    section_id: str | None = None
    severity: Literal["blocker", "warning"]
    evidence: str
    suggested_fix: str | None = None
    detector: Literal["deterministic", "llm"]
