from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from openlia.llm.runtime.report_v2.schemas.verifier_issue import VerifierIssue

FinalResolution = Literal[
    "resolved",
    "persisted_degraded",
    "persisted_failed",
    "still_open",
]


class VerificationHistoryEntry(BaseModel):
    issue: VerifierIssue
    raised_at_round: int
    final_resolution: FinalResolution
    resolved_in_round: int | None = None


class VerificationHistory(BaseModel):
    entries: list[VerificationHistoryEntry] = Field(default_factory=list)
    total_issues_raised: int = 0
    resolved_on_first_retry: int = 0
    resolved_on_subsequent_retry: int = 0
    persisted_to_degraded: int = 0
    warnings_open: int = 0
