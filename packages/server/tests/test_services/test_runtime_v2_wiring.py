"""Plan 13 — chat runtime is wired with the v2 connector dispatcher,
the runtime tool router, and the routing-context loader so Secretary
(and every other chat dept) can actually call connector tools.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia_server.db.models.connectors import Connector
from sqlalchemy.orm import Session as DBSession


def _seed_validated_eodhd(session: DBSession) -> Connector:
    row = Connector(
        id="conn-eodhd-1",
        provider_id="eodhd",
        display_name="EODHD",
        source="remote_mcp",
        category="financial",
        status="validated",
        launch={
            "modes": [{"kind": "remote_mcp", "url": "https://example.test/mcp", "headers": {}}]
        },
        secrets={},
        cached_tools=[
            {
                "name": "get_quote",
                "description": "Latest quote.",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        ],
    )
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def _stub_router_factory(monkeypatch):
    """Stub the router-LLM factory so the test doesn't need a real model row."""
    from openlia_server.services import runtime as svc

    class _StubRouterClient:
        async def generate_json(self, *, prompt: str):
            return []

    monkeypatch.setattr(svc, "_build_router_llm_client", lambda db: _StubRouterClient())


def test_build_chat_runner_enables_v2_when_connectors_exist(
    db_session: DBSession, _stub_router_factory
) -> None:
    _seed_validated_eodhd(db_session)
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution

    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
    )
    assert runner._v2_routing_enabled() is True
    candidates: list[dict[str, Any]] = runner._dispatcher.candidate_tools()
    names = {c["name"] for c in candidates}
    assert "eodhd__get_quote" in names


def test_build_chat_runner_threads_disabled_connector_ids_to_dispatcher(
    db_session: DBSession, _stub_router_factory
) -> None:
    """The chat-input "Tools" toggle: connectors in the disabled list
    must be excluded from the dispatcher's chat-routing pool."""
    _seed_validated_eodhd(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
        disabled_connector_ids=("conn-eodhd-1",),
    )
    candidates = runner._dispatcher.candidate_tools()
    names = {c["name"] for c in candidates}
    assert not any(n.startswith("eodhd__") for n in names)


def test_build_report_runner_returns_waved_host_by_default(
    db_session: DBSession,
    monkeypatch,
) -> None:
    """V2 is default-on for equity_research since 2026-05-18. With the env
    var unset, _build_report_runner_with_registry must hand back a
    WavedReportRunnerHost — not the v1 ReportRunner. Regression guard for
    the routing bug where the call site required env=="true" while
    select_report_runner_class had already moved to default-on semantics.
    """
    from datetime import date

    monkeypatch.delenv("OPENLIA_REPORT_V2_ENABLED", raising=False)
    _seed_validated_eodhd(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_report_runner_with_registry
    from openlia_server.services.runtime_report_v2 import WavedReportRunnerHost

    registry = SQLModelRegistry(db_session)
    runner = _build_report_runner_with_registry(
        registry,
        web_search=WebSearchResolution(False, None, None),
        db=db_session,
        user_id="u1",
        department_id="equity_research",
        run_id="r_test",
        run_date=date.today(),
    )
    assert isinstance(runner, WavedReportRunnerHost)


def test_build_report_runner_threads_disabled_connector_ids_to_dispatcher(
    db_session: DBSession,
) -> None:
    """Report path parity with chat: connectors in the disabled list must
    not appear in the report runner's data dispatcher candidate tools."""
    from datetime import UTC, date, datetime  # noqa: F401

    _seed_validated_eodhd(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_report_runner_with_registry

    registry = SQLModelRegistry(db_session)
    runner = _build_report_runner_with_registry(
        registry,
        web_search=WebSearchResolution(False, None, None),
        db=db_session,
        user_id="u1",
        department_id="equity_research",
        run_id="r_test",
        run_date=date.today(),
        disabled_connector_ids=("conn-eodhd-1",),
    )
    # The dispatcher under the bridge is the connector dispatcher; its
    # candidate_tools must omit anything from the disabled connector.
    bridge = runner._tools._data
    candidate_names = {c["name"] for c in bridge.dispatcher.candidate_tools()}
    assert not any(n.startswith("eodhd__") for n in candidate_names)


def test_refreshing_report_runner_forwards_disabled_ids(monkeypatch) -> None:
    """RefreshingReportRunner.run must thread disabled_connector_ids and
    disabled_skill_ids down to _build_report_runner_with_registry and to
    the per-call ReportRunner.run."""
    from openlia_server.services import runtime as svc

    captured: dict = {}

    class _FakeReportRunner:
        async def run(self, **kwargs):
            captured["runner_kwargs"] = kwargs
            yield {"type": "report.start"}

    def _fake_build(
        registry,
        *,
        web_search,
        db,
        user_id,
        department_id,
        run_id,
        run_date,
        skill_registry=None,
        disabled_connector_ids=(),
        disabled_skill_ids=(),
    ):
        captured["build_kwargs"] = {
            "disabled_connector_ids": disabled_connector_ids,
            "disabled_skill_ids": disabled_skill_ids,
        }
        return _FakeReportRunner()

    monkeypatch.setattr(svc, "_build_report_runner_with_registry", _fake_build)

    class _NoopRegistry:
        def __init__(self, db) -> None:
            self.db = db

    monkeypatch.setattr(svc, "SQLModelRegistry", _NoopRegistry)

    from openlia.llm.exceptions import ModelNotConfiguredError

    def _raise_unconfigured(**_kwargs):
        raise ModelNotConfiguredError(slot_kind="department", slot_id="equity_research")

    monkeypatch.setattr(svc, "resolve", _raise_unconfigured)

    class _SpySession:
        def __init__(self) -> None:
            self.closed = False

        def commit(self) -> None:
            pass

        def close(self) -> None:
            self.closed = True

    import asyncio

    async def _drive() -> None:
        async for _ in svc.RefreshingReportRunner(_SpySession).run(
            department_id="equity_research",
            user_id="u1",
            request=object(),
            disabled_connector_ids=("c-foo",),
            disabled_skill_ids=("s-bar",),
        ):
            pass

    asyncio.run(_drive())

    assert captured["build_kwargs"]["disabled_connector_ids"] == ("c-foo",)
    assert captured["build_kwargs"]["disabled_skill_ids"] == ("s-bar",)
    assert captured["runner_kwargs"]["disabled_skill_ids"] == frozenset({"s-bar"})


def test_build_chat_runner_uses_routing_context_loader_from_core(
    db_session: DBSession, _stub_router_factory
) -> None:
    """The loader must read the dept's routing_context.md from the core
    package, not a stub path. Verify by loading secretary."""
    _seed_validated_eodhd(db_session)
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution

    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
    )
    body = runner._routing_context_loader("secretary")
    assert "Secretary" in body
    assert "routing context" in body.lower() or "what this department does" in body.lower()
