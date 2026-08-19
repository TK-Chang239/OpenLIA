"""End-to-end test for ``rs_dash_run_service.run_to_cache``.

Drives the REAL ``report_dash_rs`` engine via an injected fake adapter
(no mocking of ``Runner``): a scripted ``LLMProvider`` replays turns —
``classify_retail_sentiment`` then ``emit_dashboard`` with a complete
``RetailSentimentData`` payload — and the assertions confirm the typed payload
lands in one ``rs_dashboard_cache`` row.

A second test seeds a prior cache row with an older sentiment_score and
confirms the new row's payload has a non-null ``momentum`` and
``trend_label == "improving"``.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.report_dash_rs import LLMSession
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
from openlia_server.db.models.dashboard import RsDashboardCache
from openlia_server.services.rs_dash_run_service import run_to_cache


@dataclass
class _FakeProvider(LLMProvider):
    """Replay a pre-scripted list of ``LLMResponse``s on successive calls."""

    scripted_responses: list[LLMResponse] = field(default_factory=list)
    _cursor: int = 0

    def __init__(self, *, scripted_responses: list[LLMResponse]) -> None:
        super().__init__(
            credentials=ProviderCredentials(api_key="fake", base_url=None, env_var_name=None),
            model="fake-model",
            capabilities=Capabilities(web_search_native=False),
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


def _complete_rs_payload(sentiment_score: float = 0.35) -> dict:
    """A complete, valid RetailSentimentData as a JSON-ready dict."""
    return {
        "subject": "AAPL",
        "sentiment_score": sentiment_score,
        "direction": "bullish",
        "buzz_level": "elevated",
        "buzz_note": "Steady chatter across WSB and StockTwits.",
        "bull_pct": 55.0,
        "bear_pct": 20.0,
        "narratives": ["AI integration hype", "strong earnings beat"],
        "signals": [],
        "evidence": [
            {
                "title": "AAPL AI push drives sentiment",
                "url": "https://example.com/aapl",
                "source": "StockTwits",
                "classification": "bullish",
                "published_at": "2026-06-04T00:00:00Z",
            }
        ],
        "narrative": "Retail traders broadly positive on AAPL.",
        "aggregated_sentiment": 0.40,
        "analyst_gap": 0.05,
        "captured_at": "2026-06-04T00:00:00Z",
        "provenance": "live",
    }


def _fake_session(script: list[LLMResponse]) -> LLMSession:
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(_FakeProvider(scripted_responses=script))
    return session


def test_run_to_cache_writes_payload(db_session, make_user):
    """Engine run writes one rs_dashboard_cache row with the emitted payload."""
    user = make_user()
    payload = _complete_rs_payload(sentiment_score=0.35)
    session = _fake_session(
        [
            _tool_call(
                "classify_retail_sentiment",
                {
                    "bullish": 55,
                    "bearish": 20,
                    "neutral": 25,
                    "buzz_level": "elevated",
                },
            ),
            _tool_call("emit_dashboard", {"payload": payload}),
        ]
    )

    ticker = asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            session=session,
        )
    )

    assert ticker == "AAPL"
    row = db_session.query(RsDashboardCache).filter_by(user_id=user.id, ticker="AAPL").one()
    stored = json.loads(row.payload_json)
    assert stored["sentiment_score"] == 0.35
    assert row.provenance == "live"
    assert row.model_ref == "claude-sonnet-4-6"


def test_run_to_cache_appends_rows(db_session, make_user):
    """Each run appends a new row; two runs produce two rows for (user, ticker)."""
    user = make_user()

    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            session=_fake_session(
                [_tool_call("emit_dashboard", {"payload": _complete_rs_payload(0.30)})]
            ),
        )
    )
    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            session=_fake_session(
                [_tool_call("emit_dashboard", {"payload": _complete_rs_payload(0.50)})]
            ),
        )
    )

    rows = (
        db_session.query(RsDashboardCache)
        .filter_by(user_id=user.id, ticker="AAPL")
        .order_by(RsDashboardCache.generated_at.asc())
        .all()
    )
    assert len(rows) == 2

    # Latest row should reflect the second run's score.
    latest = (
        db_session.query(RsDashboardCache)
        .filter_by(user_id=user.id, ticker="AAPL")
        .order_by(RsDashboardCache.generated_at.desc())
        .first()
    )
    assert latest is not None
    import json

    assert json.loads(latest.payload_json)["sentiment_score"] == 0.50


def test_run_to_cache_momentum_improving(db_session, make_user):
    """When a prior cache row exists with a lower score, the new payload
    carries a non-null momentum and trend_label == 'improving'."""
    user = make_user()

    # Seed a prior row with a lower sentiment_score.
    prior_payload = _complete_rs_payload(sentiment_score=0.10)
    db_session.add(
        RsDashboardCache(
            user_id=user.id,
            ticker="AAPL",
            payload_json=json.dumps(prior_payload),
            provenance="live",
            model_ref="claude-sonnet-4-6",
            generated_at=datetime.now(UTC),
        )
    )
    db_session.flush()

    # Run again with a higher score (+0.30 delta > 0.05 threshold => "improving").
    new_payload = _complete_rs_payload(sentiment_score=0.40)
    session = _fake_session(
        [
            _tool_call(
                "classify_retail_sentiment",
                {
                    "bullish": 65,
                    "bearish": 15,
                    "neutral": 20,
                    "buzz_level": "elevated",
                },
            ),
            _tool_call("emit_dashboard", {"payload": new_payload}),
        ]
    )

    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            session=session,
        )
    )

    # Two rows: the seeded prior + the new run.
    all_rows = db_session.query(RsDashboardCache).filter_by(user_id=user.id, ticker="AAPL").all()
    assert len(all_rows) == 2

    latest = (
        db_session.query(RsDashboardCache)
        .filter_by(user_id=user.id, ticker="AAPL")
        .order_by(RsDashboardCache.generated_at.desc())
        .first()
    )
    stored = json.loads(latest.payload_json)
    assert stored["momentum"] is not None
    assert stored["trend_label"] == "improving"


def test_run_to_cache_fails_loud_without_emit(db_session, make_user):
    """A run that ends without calling emit_dashboard raises and writes no row."""
    import pytest

    user = make_user()
    from openlia.llm.types import LLMResponse

    session = _fake_session(
        [
            LLMResponse(
                text="I am done but I never emitted.",
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
                tool_calls=[],
            )
        ]
    )

    with pytest.raises(RuntimeError, match="did not complete"):
        asyncio.run(
            run_to_cache(
                db_session,
                user_id=user.id,
                ticker="AAPL",
                session=session,
            )
        )

    rows = db_session.query(RsDashboardCache).filter_by(user_id=user.id, ticker="AAPL").all()
    assert rows == []


def test_resolve_enabled_connectors_honors_capability_override(db_session):
    """Gate must honor the same web_search_native override the session applies.

    A model that defaults web_search_native=False plus a user override enabling
    it must produce a gate with web_search=True, matching the session built by
    LLMSession.create in run_to_cache. Regression for the audit's 1.B.3 finding
    (gate used override-free capabilities_for, session honored the override).
    """
    from openlia_server.services import rs_dash_run_service
    from openlia_server.services.llm_providers import set_capability_override

    base = rs_dash_run_service._resolve_enabled_connectors(
        db_session, provider_kind="anthropic", model="claude-haiku-4-6"
    )
    assert base.web_search is False

    set_capability_override(
        db_session,
        provider_kind="anthropic",
        model="claude-haiku-4-6",
        override={"web_search_native": True},
    )
    gated = rs_dash_run_service._resolve_enabled_connectors(
        db_session, provider_kind="anthropic", model="claude-haiku-4-6"
    )
    assert gated.web_search is True


def test_dedupe_evidence_drops_syndicated_duplicate():
    """Same story emitted twice under different source strings (audit M1)."""
    from openlia_server.services.rs_dash_run_service import _dedupe_evidence

    items = [
        {
            "title": "Reddit Has Turned Bearish on Tesla and the Crowd Might Be Right",
            "url": "https://247wallst.com/a",
            "source": "24/7 Wall St.",
            "published_at": "2026-03-12",
            "classification": "bearish",
        },
        {
            "title": "Reddit Has Turned Bearish on Tesla and the Crowd Might Be Right",
            "url": "https://finance.yahoo.com/b",
            "source": "Yahoo Finance / 24/7 Wall St.",
            "published_at": "2026-03-12T09:00:00Z",
            "classification": "bearish",
        },
        {
            "title": "Vanda: retail investors buying the dip",
            "url": "https://barchart.com/c",
            "source": "Barchart",
            "published_at": "2026-08-14",
            "classification": "bullish",
        },
    ]
    out = _dedupe_evidence(items)
    assert len(out) == 2
    assert out[0]["source"] == "24/7 Wall St."
    assert out[1]["title"].startswith("Vanda")


def test_dedupe_evidence_keeps_same_title_on_different_dates():
    from openlia_server.services.rs_dash_run_service import _dedupe_evidence

    items = [
        {"title": "TSLA daily sentiment wrap", "published_at": "2026-08-14"},
        {"title": "TSLA daily sentiment wrap", "published_at": "2026-08-15"},
    ]
    assert len(_dedupe_evidence(items)) == 2


def test_citation_rows_maps_web_and_provider_entries():
    from dataclasses import dataclass, field

    from openlia_server.services.dash_citations import citation_rows

    @dataclass
    class _Entry:
        source_id: str
        tool_name: str
        provenance: dict = field(default_factory=dict)

    rows = citation_rows(
        [
            _Entry(
                "web_2",
                "web_search",
                {"type": "web", "url": "https://reuters.com/a", "title": "Reuters piece"},
            ),
            _Entry(
                "web_9",
                "web_search",
                {"type": "web", "url": "search://tsla sentiment", "title": "Search"},
            ),
            _Entry(
                "eodhd_1",
                "get_news",
                {"type": "data_provider", "provider": "EODHD", "endpoint": "news"},
            ),
        ]
    )
    assert rows[0] == {
        "source_id": "web_2",
        "title": "Reuters piece",
        "url": "https://reuters.com/a",
    }
    # search:// pseudo-URLs are not linkable.
    assert rows[1]["url"] is None
    assert rows[2] == {"source_id": "eodhd_1", "title": "EODHD news", "url": None}


def test_run_to_cache_attaches_citations(db_session, make_user):
    """The cached payload carries the run's citation ledger so the UI can
    link narrative markers (audit follow-up F3)."""
    user = make_user()
    payload = _complete_rs_payload(sentiment_score=0.1)
    session = _fake_session(
        [
            _tool_call(
                "classify_retail_sentiment",
                {"bullish": 40, "bearish": 30, "neutral": 30, "buzz_level": "low"},
            ),
            _tool_call("emit_dashboard", {"payload": payload}),
        ]
    )
    asyncio.run(
        run_to_cache(
            db_session,
            user_id=user.id,
            ticker="TSLA",
            session=session,
        )
    )
    row = db_session.query(RsDashboardCache).filter_by(user_id=user.id, ticker="TSLA").one()
    stored = json.loads(row.payload_json)
    assert "citations" in stored
    assert isinstance(stored["citations"], list)
