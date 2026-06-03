"""End-to-end test for ``mr_dash_run_service.run_to_cache``.

Drives the REAL ``report_dash_mr`` engine via an injected fake adapter
(no mocking of ``Runner``): a scripted ``LLMProvider`` replays two turns —
``classify_debt_cycle`` then ``emit_dashboard`` with a complete
``DebtCycleData`` payload — and the assertions confirm the typed payload
lands in one ``mr_dashboard_cache`` row. A second test scripts a run that
ends without ``emit_dashboard`` and confirms ``run_to_cache`` fails loud
and writes no row.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.report_dash_mr import LLMSession
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    ToolCall,
)
from openlia.llm.types import TestResult as ConnTestResult
from openlia_server.db.models.dashboard import MrDashboardCache
from openlia_server.services.mr_dash_run_service import run_to_cache


@dataclass
class _FakeProvider(LLMProvider):
    """Replay a pre-scripted list of ``LLMResponse``s on successive calls.

    Minimal shape copied from
    ``packages/core/tests/runtime/report_dash_mr/_fakes.py`` so the server
    test can drive the real engine loop without any network/SDK call.
    """

    scripted_responses: list[LLMResponse] = field(default_factory=list)
    _cursor: int = 0

    def __init__(self, *, scripted_responses: list[LLMResponse]) -> None:
        super().__init__(
            credentials=ProviderCredentials(api_key="fake", base_url=None, env_var_name=None),
            model="fake-model",
            capabilities=Capabilities(web_search_native=True),
        )
        self.scripted_responses = list(scripted_responses)
        self._cursor = 0

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.model, display_name=self.model)]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if self._cursor >= len(self.scripted_responses):
            raise RuntimeError("fake script exhausted; extend the script")
        response = self.scripted_responses[self._cursor]
        self._cursor += 1
        return response

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError

    async def test_connection(self, model: str) -> ConnTestResult:
        return ConnTestResult(ok=True, latency_ms=0, error_class=None, error_msg=None)


def _tool_call(name: str, arguments: dict) -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[ToolCall(id=f"call_{name}", name=name, arguments=arguments)],
    )


def _text(text: str) -> LLMResponse:
    return LLMResponse(
        text=text,
        finish_reason="stop",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[],
    )


def _complete_debt_cycle_payload() -> dict:
    """A complete, valid DebtCycleData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads.py and
    the core engine test.
    """
    return {
        "header": {
            "title": "Debt Cycle",
            "subtitle": "June 2026 · Dalio",
            "pills": [{"tone": "red", "label": "Late Plateau"}],
        },
        "cardSummary": "Debt burden critical; monetary space narrowing.",
        "scorecard": {
            "rows": [
                {
                    "name": "Govt debt / GDP",
                    "sub": "Q1 2026",
                    "current": "125.0%",
                    "currentTone": "red",
                    "currentMeta": "IMF",
                    "threshold": "> 120%",
                    "status": "Critical",
                    "statusTone": "red",
                    "fillPct": 95,
                    "fillTone": "red",
                }
            ]
        },
        "phaseBox": {
            "title": "Late Plateau",
            "body": "One red, multiple amber indicators.",
            "tone": "red",
        },
        "analogPair": {
            "analog": {"title": "1968-80", "body": "Stagflationary debt plateau."},
            "timeToConstraint": {"title": "3-7y", "body": "Window to the constraint."},
        },
        "policySpace": {
            "cards": [
                {
                    "label": "Rate cut headroom",
                    "value": "~470bps",
                    "valueTone": "amber",
                    "unit": "to neutral",
                    "note": "Real yields low.",
                }
            ]
        },
        "assetThesis": {
            "gold": {"title": "Gold", "body": "Debasement hedge."},
            "longBond": {"title": "Long bond", "body": "Vulnerable to fiscal dominance."},
        },
        "watchlist": {
            "rows": [{"tone": "red", "name": "Debt spiral", "body": "Interest/revenue rising."}]
        },
        "verdict": {
            "title": "Synthesis",
            "body": "Late-cycle debt dynamics with narrowing monetary space.",
            "tone": "red",
        },
        "sources": "IMF, BEA, FRED, ICE",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _fake_session(script: list[LLMResponse]) -> LLMSession:
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(_FakeProvider(scripted_responses=script))
    return session


def test_run_to_cache_writes_payload(db_session, make_user):
    user = make_user()
    payload = _complete_debt_cycle_payload()
    session = _fake_session(
        [
            _tool_call(
                "classify_debt_cycle",
                {
                    "debt_gdp": 125.0,
                    "interest_revenue": 18.0,
                    "tips_real_yield": 0.3,
                    "dxy": 97.0,
                },
            ),
            _tool_call("emit_dashboard", {"payload": payload}),
        ]
    )

    slug = asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            dashboard_slug="debt_cycle",
            session=session,
        )
    )

    assert slug == "debt_cycle"
    row = (
        db_session.query(MrDashboardCache).filter_by(user_id=user.id, dashboard="debt_cycle").one()
    )
    assert "phaseBox" in row.payload_json
    assert row.provenance == "live"
    assert row.model_ref == "claude-sonnet-4-6"


def test_run_to_cache_upserts_in_place(db_session, make_user):
    """A second run for the same (user, dashboard) updates the existing
    row rather than inserting a duplicate (unique constraint guarantees
    one row per dashboard per user)."""
    user = make_user()
    payload = _complete_debt_cycle_payload()

    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            dashboard_slug="debt_cycle",
            session=_fake_session([_tool_call("emit_dashboard", {"payload": payload})]),
        )
    )
    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            dashboard_slug="debt_cycle",
            session=_fake_session([_tool_call("emit_dashboard", {"payload": payload})]),
        )
    )

    rows = (
        db_session.query(MrDashboardCache).filter_by(user_id=user.id, dashboard="debt_cycle").all()
    )
    assert len(rows) == 1


def test_run_to_cache_fails_loud_without_emit(db_session, make_user):
    """A run that ends without calling emit_dashboard raises and writes
    no cache row."""
    user = make_user()
    session = _fake_session([_text("I am done, but I never emitted a dashboard.")])

    import pytest

    with pytest.raises(RuntimeError, match="did not complete"):
        asyncio.run(
            run_to_cache(
                db_session,
                user_id=user.id,
                dashboard_slug="debt_cycle",
                session=session,
            )
        )

    rows = (
        db_session.query(MrDashboardCache).filter_by(user_id=user.id, dashboard="debt_cycle").all()
    )
    assert rows == []
