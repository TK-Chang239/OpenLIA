"""Tests for the EU v2 run service (request build + async start + persist).

``build_run_request`` is exercised against seeded settings + the
builtin ``eu_default`` template. ``start_run_async`` is driven with a
fake ``LLMSession`` (a scripted ``FakeLLMProvider`` adapter) so the
runner's tool-use loop completes deterministically with every connector
off and a null transports bundle — no network, no SDK.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from openlia.llm.runtime.report_eu import (
    EuDataTransports,
    EventBroker,
    LLMSession,
    is_finish_sentinel,
)
from openlia.llm.runtime.report_eu.default_template import build_default_template
from openlia_server.db.models.report_eu import (
    ReportEu,
    ReportEuSection,
    ReportEuTemplate,
)
from openlia_server.services import eu_v2_run_service as svc
from openlia_server.services.eu_v2_settings import update_settings
from sqlalchemy import select

# Pull the report_eu FakeLLMProvider helpers from the core test tree.
_CORE_TESTS = Path(__file__).resolve().parents[3] / "core" / "tests"
sys.path.insert(0, str(_CORE_TESTS))
from runtime.report_eu._fakes import (  # noqa: E402
    FakeLLMProvider,
    script_tool_calls,
)


def _seed_eu_default(db) -> None:
    """Insert the eu_default builtin row, mirroring what the migration does."""
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportEuTemplate(
            id=spec.template_id,
            user_id=None,
            name=spec.name,
            is_builtin=True,
            template_spec_json=json.loads(spec.model_dump_json()),
            source_markdown=None,
            source_doc_blob=None,
            source_doc_mime=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db.flush()


@pytest.fixture
def db_session_with_seed(db_session, monkeypatch):
    # Make EODHD availability deterministic instead of depending on an
    # ambient env key (which only happens to be present when the whole
    # suite runs). Tests that need EODHD *absent* delenv it themselves.
    monkeypatch.setenv("EODHD_API_KEY", "test-eodhd-key")
    _seed_eu_default(db_session)
    return db_session


def test_build_run_request_uses_settings_and_trigger(db_session_with_seed):
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=True,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="scheduled",
        fiscal_period="Q3 FY26",
        report_date="2026-06-15",
        release_timing="post_market",
        eps_estimate="2.50",
        revenue_estimate=None,
    )
    assert req.provider_kind == "anthropic"
    # eodhd provider enabled with EODHD available -> eodhd provider on
    assert req.enabled_connectors.eodhd is True
    assert req.enabled_connectors.web_search is True
    assert req.trigger_context.fiscal_period == "Q3 FY26"
    assert req.template.template_id == "eu_default"
    assert req.subject == "MSFT.US Q3 FY26 earnings"


def test_build_run_request_subject_falls_back_to_ticker(db_session_with_seed):
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort="high",
        enabled_provider_ids=["eodhd"],
        web_search_enabled=False,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.subject == "MSFT.US earnings"
    assert req.reasoning_effort is not None
    assert req.reasoning_effort.value == "high"


def test_build_run_request_resolves_selected_instructions(db_session_with_seed):
    from openlia_server.services import eu_v2_instructions_service

    profile = eu_v2_instructions_service.create_instructions_from_upload(
        db=db_session_with_seed,
        user_id="u-1",
        name="My methodology",
        body_text="Lead with the surprise. Quantify everything.",
    )
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
        instructions_id=profile.id,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.instructions == "Lead with the surprise. Quantify everything."


def test_build_run_request_instructions_none_when_unset(db_session_with_seed):
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.instructions is None


def test_build_run_request_freeform_with_instructions(db_session_with_seed):
    from openlia_server.services import eu_v2_instructions_service

    profile = eu_v2_instructions_service.create_instructions_from_upload(
        db=db_session_with_seed,
        user_id="u-1",
        name="Freeform methodology",
        body_text="Write whatever structure best fits the print.",
    )
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id=svc.EU_FREEFORM_TEMPLATE_ID,
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
        instructions_id=profile.id,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.template.template_id == svc.EU_FREEFORM_TEMPLATE_ID
    assert req.template.sections == []
    assert req.instructions == "Write whatever structure best fits the print."


def test_build_run_request_freeform_without_instructions_raises(db_session_with_seed):
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id=svc.EU_FREEFORM_TEMPLATE_ID,
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
        instructions_id=None,
    )
    with pytest.raises(svc.EmptyBriefError):
        svc.build_run_request(
            db_session_with_seed,
            user_id="u-1",
            ticker="MSFT.US",
            trigger_kind="on_demand",
            fiscal_period=None,
            report_date=None,
            release_timing=None,
            eps_estimate=None,
            revenue_estimate=None,
        )


def _fake_session() -> tuple[LLMSession, FakeLLMProvider]:
    """A real LLMSession with a scripted fake adapter attached.

    Scripts: write all 8 eu_default sections (connectors off, so no
    data tools), then finalize.
    """
    section_ids = [s.id for s in build_default_template().sections]
    script = [
        script_tool_calls(("write_section", {"section_id": sid, "markdown": f"{sid} body."}))
        for sid in section_ids
    ]
    script.append(script_tool_calls(("finalize", {})))
    fake = FakeLLMProvider(scripted_responses=script)
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    session.attach_adapter(fake)
    return session, fake


def _null_transports() -> EuDataTransports:
    def _raise(*_a: object, **_k: object) -> object:
        raise RuntimeError("not configured")

    return EuDataTransports(
        fundamentals=_raise, prices=_raise, news=_raise, earnings_calendar=_raise
    )


@pytest.mark.asyncio
async def test_start_run_async_completes_and_persists(db_session_with_seed, db_session_factory):
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
    )
    request = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period="Q3 FY26",
        report_date="2026-06-15",
        release_timing="post_market",
        eps_estimate=None,
        revenue_estimate=None,
    )

    session, _fake = _fake_session()
    broker = EventBroker()
    cancel_registry: dict = {}

    report_id = svc.start_run_async(
        db_session_with_seed,
        user_id="u-1",
        request=request,
        broker=broker,
        cancel_registry=cancel_registry,
        session_factory=db_session_factory,
        trigger_kind="on_demand",
        transports=_null_transports(),
        session=session,
    )
    db_session_with_seed.commit()

    # The background task runs on the same event loop; let it complete.
    for _ in range(200):
        if not svc._BACKGROUND_TASKS:
            break
        await asyncio.sleep(0.01)

    with db_session_factory() as check:
        row = check.get(ReportEu, report_id)
        assert row is not None
        assert row.status == "completed"
        assert row.ticker == "MSFT.US"
        assert row.trigger_kind == "on_demand"
        assert row.fiscal_date == "2026-06-15"
        assert row.completed_at is not None

        sections = list(
            check.scalars(select(ReportEuSection).where(ReportEuSection.report_id == report_id))
        )
        assert len(sections) == 8


@pytest.mark.asyncio
async def test_start_run_async_emits_run_failed_when_engine_raises(
    db_session_with_seed, db_session_factory
):
    """A mid-run engine exception (e.g. an httpx ReadError on the LLM call)
    must publish a terminal ``run.failed`` event — not just close the
    stream — so the SSE client resolves instead of spinning on the
    generating UI forever."""
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=[],
        web_search_enabled=False,
    )
    request = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )

    session, _fake = _fake_session()

    async def _boom(**_kwargs: object) -> object:
        raise RuntimeError("ReadError: connection reset mid-stream")

    session.generate = _boom  # type: ignore[method-assign]

    broker = EventBroker()
    cancel_registry: dict = {}

    report_id = svc.start_run_async(
        db_session_with_seed,
        user_id="u-1",
        request=request,
        broker=broker,
        cancel_registry=cancel_registry,
        session_factory=db_session_factory,
        trigger_kind="on_demand",
        transports=_null_transports(),
        session=session,
    )
    db_session_with_seed.commit()

    # Subscribe registers synchronously (before the bg task's first await),
    # so no run-start race: we see every event up to the finish sentinel.
    event_types: list[str] = []
    async with broker.subscribe(report_id) as queue:
        while True:
            item = await asyncio.wait_for(queue.get(), timeout=5)
            if is_finish_sentinel(item):
                break
            event_types.append(item.type)

    assert "run.failed" in event_types

    with db_session_factory() as check:
        row = check.get(ReportEu, report_id)
        assert row is not None
        assert row.status == "failed"
        assert "ReadError" in (row.error_message or "")


def test_build_run_request_gates_financial_off_without_eodhd(monkeypatch, db_session_with_seed):
    from openlia_server.db.models.auth import User
    from openlia_server.services import eu_v2_run_service, eu_v2_settings

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    now = datetime.now(UTC)
    if db_session_with_seed.get(User, "local") is None:
        db_session_with_seed.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                password_hash=None,
                is_admin=True,
                is_disabled=False,
                created_at=now,
                updated_at=now,
            )
        )
        db_session_with_seed.flush()
    eu_v2_settings.update_settings(
        db_session_with_seed,
        user_id="local",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=True,
    )
    req = eu_v2_run_service.build_run_request(
        db_session_with_seed,
        user_id="local",
        ticker="AAPL.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.enabled_connectors.eodhd is False
    assert req.enabled_connectors.web_search is True


def test_build_run_request_gates_web_search_off_for_incapable_model(
    monkeypatch, db_session_with_seed
):
    from openlia_server.db.models.auth import User
    from openlia_server.services import eu_v2_run_service, eu_v2_settings

    monkeypatch.setenv("EODHD_API_KEY", "k")
    now = datetime.now(UTC)
    if db_session_with_seed.get(User, "local") is None:
        db_session_with_seed.add(
            User(
                id="local",
                email="local@openlia.local",
                display_name="Local",
                password_hash=None,
                is_admin=True,
                is_disabled=False,
                created_at=now,
                updated_at=now,
            )
        )
        db_session_with_seed.flush()
    eu_v2_settings.update_settings(
        db_session_with_seed,
        user_id="local",
        provider_kind="anthropic",
        model="claude-haiku-4-5-20251001",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=True,
    )
    req = eu_v2_run_service.build_run_request(
        db_session_with_seed,
        user_id="local",
        ticker="AAPL.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert req.enabled_connectors.eodhd is True
    assert req.enabled_connectors.web_search is False


def _seed_connector(
    db,
    *,
    cid: str,
    provider_id: str,
    status: str = "validated",
) -> None:
    """Insert a routable built-in connector row (mirrors dispatcher tests)."""
    from openlia_server.db.models.connectors import Connector

    db.add(
        Connector(
            id=cid,
            provider_id=provider_id,
            display_name=provider_id,
            source="built_in",
            category="financial",
            status=status,
            launch={"modes": [{"kind": "remote_mcp", "url": "https://x.test", "headers": {}}]},
            secrets={},
            cached_tools=[
                {
                    "name": "quote",
                    "description": "x",
                    "input_schema": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                }
            ],
        )
    )
    db.commit()


def test_build_run_request_drops_provider_without_validated_connector(db_session_with_seed):
    """A settings-enabled provider with no validated connector row silently drops."""
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd", "ghost"],
        web_search_enabled=False,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    # eodhd stays (curated path); ghost has no validated connector -> dropped.
    assert set(req.enabled_connectors.provider_ids) == {"eodhd"}


def test_build_run_request_keeps_validated_connector_provider(db_session_with_seed):
    _seed_connector(db_session_with_seed, cid="c-newsapi", provider_id="newsapi_ai")
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["newsapi_ai", "ghost"],
        web_search_enabled=False,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert set(req.enabled_connectors.provider_ids) == {"newsapi_ai"}


def test_build_run_request_drops_unvalidated_connector_provider(db_session_with_seed):
    _seed_connector(
        db_session_with_seed, cid="c-newsapi", provider_id="newsapi_ai", status="failed"
    )
    update_settings(
        db_session_with_seed,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["newsapi_ai"],
        web_search_enabled=False,
    )
    req = svc.build_run_request(
        db_session_with_seed,
        user_id="u-1",
        ticker="MSFT.US",
        trigger_kind="on_demand",
        fiscal_period=None,
        report_date=None,
        release_timing=None,
        eps_estimate=None,
        revenue_estimate=None,
    )
    assert set(req.enabled_connectors.provider_ids) == set()


def test_build_eu_dispatcher_routes_validated_non_eodhd(db_session):
    _seed_connector(db_session, cid="c-eodhd", provider_id="eodhd")
    _seed_connector(db_session, cid="c-newsapi", provider_id="newsapi_ai")
    dispatcher = svc.build_eu_dispatcher(
        db_session, enabled_provider_ids=frozenset({"eodhd", "newsapi_ai"})
    )
    assert dispatcher is not None
    names = {c["name"] for c in dispatcher.candidate_tools()}
    assert "newsapi_ai__quote" in names
    # EODHD is always blocked from the dispatcher (served by the curated
    # path), even when enabled — so its tools are never enumerated here.
    assert not any(n.startswith("eodhd__") for n in names)


def test_build_eu_dispatcher_blocks_disabled_provider(db_session):
    _seed_connector(db_session, cid="c-eodhd", provider_id="eodhd")
    _seed_connector(db_session, cid="c-newsapi", provider_id="newsapi_ai")
    dispatcher = svc.build_eu_dispatcher(db_session, enabled_provider_ids=frozenset({"newsapi_ai"}))
    assert dispatcher is not None
    names = {c["name"] for c in dispatcher.candidate_tools()}
    assert "newsapi_ai__quote" in names
    assert not any(n.startswith("eodhd__") for n in names)


def test_build_eu_dispatcher_none_when_only_eodhd_enabled(db_session):
    _seed_connector(db_session, cid="c-eodhd", provider_id="eodhd")
    dispatcher = svc.build_eu_dispatcher(db_session, enabled_provider_ids=frozenset({"eodhd"}))
    assert dispatcher is None


def test_build_eu_dispatcher_none_when_no_enabled_non_eodhd(db_session):
    _seed_connector(db_session, cid="c-newsapi", provider_id="newsapi_ai")
    dispatcher = svc.build_eu_dispatcher(db_session, enabled_provider_ids=frozenset({"eodhd"}))
    assert dispatcher is None


def test_get_run_loads_row_with_children(db_session_with_seed):
    from datetime import UTC, datetime

    from openlia_server.db.models.report_eu import ReportEu, ReportEuSection

    rid = "rid-load-1"
    db_session_with_seed.add(
        ReportEu(
            id=rid, user_id="u-1", subject="AAPL earnings", ticker="AAPL",
            trigger_kind="on_demand", fiscal_date=None, template_id="eu_default",
            language="en", length="normal", provider_kind="anthropic",
            model="claude-sonnet-4-6", status="completed", error_message=None,
            created_at=datetime.now(UTC), completed_at=datetime.now(UTC),
            cover_json=None, reasoning_effort=None,
        )
    )
    db_session_with_seed.add(
        ReportEuSection(
            report_id=rid, section_id="quick_take", section_index=0,
            title="Quick Take", markdown="Body.", version=1,
        )
    )
    db_session_with_seed.flush()

    row, sections, charts, citations = svc.get_run(
        db=db_session_with_seed, user_id="u-1", report_id=rid
    )
    assert row.id == rid
    assert [s.section_id for s in sections] == ["quick_take"]
    assert charts == []
    assert citations == []


def test_get_run_missing_raises(db_session_with_seed):
    import pytest as _pytest
    with _pytest.raises(svc.ReportNotFoundError):
        svc.get_run(db=db_session_with_seed, user_id="u-1", report_id="nope")


def test_cleanup_orphaned_running_rows(db_session):
    """Stuck 'running' rows flipped to 'failed'; completed rows untouched."""
    now = datetime.now(UTC)

    running_row = ReportEu(
        id="r-running",
        user_id="u-1",
        subject="AAPL earnings",
        ticker="AAPL",
        trigger_kind="on_demand",
        fiscal_date=None,
        template_id="eu_default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="running",
        error_message=None,
        created_at=now,
        completed_at=None,
        cover_json=None,
        reasoning_effort=None,
    )
    completed_row = ReportEu(
        id="r-completed",
        user_id="u-1",
        subject="MSFT earnings",
        ticker="MSFT",
        trigger_kind="on_demand",
        fiscal_date=None,
        template_id="eu_default",
        language="en",
        length="normal",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        status="completed",
        error_message=None,
        created_at=now,
        completed_at=now,
        cover_json=None,
        reasoning_effort=None,
    )
    db_session.add(running_row)
    db_session.add(completed_row)
    db_session.commit()

    count = svc.cleanup_orphaned_running_rows(db=db_session)

    assert count == 1
    db_session.expire_all()
    fixed = db_session.get(ReportEu, "r-running")
    assert fixed.status == "failed"
    assert fixed.error_message == "server restart - run did not complete"
    assert fixed.completed_at is not None

    untouched = db_session.get(ReportEu, "r-completed")
    assert untouched.status == "completed"
