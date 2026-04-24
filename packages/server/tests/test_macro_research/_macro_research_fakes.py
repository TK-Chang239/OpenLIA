"""Shared fakes for MR tests. Uniquely named to avoid import-mode=importlib collisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class FakeDataProvider:
    """Return canned values keyed by requirement name."""

    values: dict[str, Any] = field(default_factory=dict)

    def fetch(self, *, requirement: str, **kwargs: Any) -> Any:
        return self.values.get(requirement)


@dataclass
class FakeLLMClient:
    """Record every call; return a scripted response."""

    scripted_response: dict[str, Any] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(self, *, prompt: str, **kwargs: Any) -> dict[str, Any]:
        self.calls.append({"prompt": prompt, **kwargs})
        return self.scripted_response


@dataclass
class FakeMRCacheStore:
    saved: list[dict[str, Any]] = field(default_factory=list)
    read_result: dict[str, Any] | None = None

    def save(self, *, session: Any, user_id: str, payload: dict[str, Any]) -> str:
        self.saved.append({"user_id": user_id, "payload": payload})
        return "cache-1"

    def read_latest(
        self, *, session: Any, user_id: str, dashboard: str, assessment_type: str
    ) -> dict[str, Any] | None:
        return self.read_result


@dataclass
class FakeReportStore:
    saved: list[dict[str, Any]] = field(default_factory=list)

    def save(self, *, session: Any, user_id: str, department: str, payload: dict[str, Any]) -> str:
        self.saved.append({"user_id": user_id, "department": department, "payload": payload})
        return "report-1"


def utcnow() -> datetime:
    return datetime.now(UTC)
