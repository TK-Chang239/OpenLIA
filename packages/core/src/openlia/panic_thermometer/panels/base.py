"""Shared shapes for Panic Thermometer panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PanelContextBuildResult:
    """Output of a panel's context-builder.

    scalars: keys consumed by `EvaluationContext.scalars` (booleans, survey
        readings, days_elapsed, matched_phrase, etc.).
    raw_series: keys consumed by `EvaluationContext.raw_series` — named arrays of
        historical numeric values, oldest first.
    warnings: human-readable notes surfaced to the UI (stale data, etc.).
    """

    scalars: dict[str, Any]
    raw_series: dict[str, list[float]]
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class PanelBase(Protocol):
    """Structural protocol every PT panel satisfies.

    Panels are stateless — they do not hold user config. The runner passes
    the user's panel config and raw adapter payloads at call time.
    """

    panel_id: str
    required_requirements: tuple[str, ...]
    optional_requirements: tuple[str, ...]
    default_ruleset: dict[str, Any]

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        """Turn raw adapter payloads into engine inputs."""
        ...
