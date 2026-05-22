from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .enums import VerifierIssueType


class VerifierIssue(BaseModel):
    """Per schema-and-skills §5.1."""

    type: VerifierIssueType  # closed parent enum (18 values)
    detail_code: str | None = None  # e.g. "tv_pct_high", "cet1_below_minimum"
    severity: Literal["blocking", "advisory"] = "blocking"
    helper: str  # helper name that emitted the issue
    detail: str  # human-readable message
