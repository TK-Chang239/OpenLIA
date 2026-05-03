from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SkillManifest(BaseModel):
    name: str
    display_name: str | None = None
    description: str
    version: str = "0.0.0"
    departments: list[str]
    author: str | None = None
    # Plan 2 fields, parsed but unused in Plan 1:
    mcp: dict | None = None
    tools: list[dict] | None = None
    requires_secrets: list[dict] | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not SKILL_ID_RE.match(v):
            raise ValueError(f"invalid skill id: {v!r}")
        return v

    @field_validator("departments")
    @classmethod
    def _validate_departments(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("departments must be non-empty (or ['*'] for global)")
        return v


@dataclass(frozen=True)
class InstalledSkill:
    manifest: SkillManifest
    body: str
    scope: Literal["system", "user"]
    user_id: str | None
    enabled: bool
    installed_at: datetime
    source: str
