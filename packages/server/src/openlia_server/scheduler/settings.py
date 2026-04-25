"""Environment-driven scheduler settings. All knobs are ops-level with
sensible defaults; none are stored in config_store."""

from __future__ import annotations

import os
from dataclasses import dataclass

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"invalid boolean: {raw!r}")


def _parse_int(raw: str | None, default: int, name: str) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}: cannot parse {raw!r} as int") from exc
    if value < 0:
        raise ValueError(f"{name}: must be >= 0, got {value}")
    return value


def _parse_optional_int(raw: str | None, name: str) -> int | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}: cannot parse {raw!r} as int") from exc
    if value <= 0:
        raise ValueError(f"{name}: must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class SchedulerSettings:
    enabled: bool
    misfire_grace_seconds: int = 21_600
    shutdown_grace_seconds: int = 30
    max_concurrent_jobs: int | None = None

    @classmethod
    def from_env(cls) -> SchedulerSettings:
        return cls(
            enabled=_parse_bool(os.getenv("OPENLIA_SCHEDULER_ENABLED"), default=True),
            misfire_grace_seconds=_parse_int(
                os.getenv("OPENLIA_SCHEDULER_MISFIRE_GRACE_SECONDS"),
                default=21_600,
                name="misfire_grace_seconds",
            ),
            shutdown_grace_seconds=_parse_int(
                os.getenv("OPENLIA_SCHEDULER_SHUTDOWN_GRACE_SECONDS"),
                default=30,
                name="shutdown_grace_seconds",
            ),
            max_concurrent_jobs=_parse_optional_int(
                os.getenv("OPENLIA_SCHEDULER_MAX_CONCURRENT_JOBS"),
                name="max_concurrent_jobs",
            ),
        )
