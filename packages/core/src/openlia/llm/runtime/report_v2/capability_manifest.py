"""Capability manifest — single source of truth for engine version + feature surface.

Both the clarifier prompt construction and the template loader read from this
module. See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §3.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class SupportedCapability(BaseModel):
    id: str
    summary: str = ""


class UnsupportedCapability(BaseModel):
    id: str
    summary: str = ""
    detect_in_prompt: list[str] = Field(default_factory=list)
    detect_in_template_keys: list[str] = Field(default_factory=list)
    planned_in: str | None = None
    user_message: str


class CacheSourceToggle(BaseModel):
    enabled: bool = True


class CacheConfig(BaseModel):
    enabled: bool = True
    transcripts: CacheSourceToggle = Field(default_factory=CacheSourceToggle)
    investor_day: CacheSourceToggle = Field(default_factory=CacheSourceToggle)
    default_force_refresh: bool = False


class CapabilityManifest(BaseModel):
    engine_version: str
    dev_mode: bool
    supported: list[SupportedCapability]
    unsupported: list[UnsupportedCapability]
    known_template_keys: list[str]
    cache: CacheConfig

    def unsupported_by_template_key(self) -> dict[str, UnsupportedCapability]:
        """Map each reserved template-frontmatter key to the capability that owns it."""
        out: dict[str, UnsupportedCapability] = {}
        for u in self.unsupported:
            for k in u.detect_in_template_keys:
                out[k] = u
        return out


_DEFAULT_PATH = Path(__file__).parent / "capabilities.yaml"


@lru_cache(maxsize=8)
def load_manifest(path: Path | None = None) -> CapabilityManifest:
    p = path or _DEFAULT_PATH
    with p.open() as f:
        data: Any = yaml.safe_load(f)
    return CapabilityManifest.model_validate(data)


def clear_manifest_cache() -> None:
    load_manifest.cache_clear()
