"""Tests for the Phase 10 save-flow + audit log persistence.

`save_user_picked_spec` is the single entry point the resolve endpoint
calls. It runs the resolver LLM, runs smoke, persists logs in both
audit tables, and writes / preserves the RunnerCallableSpec row.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from openlia.connectors.types import Category, NeedParameter, RunnerNeed
from openlia_server.db.models.connectors import (
    Connector,
    ResolverCallLog,
    RunnerCallableSpec,
    SmokeCallLog,
)
from openlia_server.services.resolver_save_flow import (
    SaveFlowFailure,
    SaveFlowSuccess,
    save_user_picked_spec,
)
from openlia_server.services.smoke_service import SmokeResult
from sqlalchemy.orm import Session


class _StubLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls: int = 0

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        self.calls += 1
        return self._payload


class _StubTransport:
    def __init__(self, *, response: Any) -> None:
        self._response = response

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._response

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


_STOCK_QUOTE_NEED = RunnerNeed(
    id="stock_quote",
    description="Latest closing price for a ticker.",
    parameters=[
        NeedParameter(name="ticker", description="Ticker symbol", type="str", required=True)
    ],
    shape="float",
)


def _make_connector(db_session: Session) -> Connector:
    conn = Connector(
        id=str(uuid4()),
        provider_id="fmp",
        display_name="FMP",
        source="remote_mcp",
        category=Category.FINANCIAL.value,
        launch={"modes": []},
        secrets={},
        cached_tools=[
            {
                "name": "quote",
                "description": "quote tool",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "endpoint": {"type": "string"},
                    },
                },
            }
        ],
        status="validated",
    )
    db_session.add(conn)
    db_session.commit()
    return conn


@pytest.mark.asyncio
async def test_save_flow_persists_spec_and_log_rows_on_success(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "openlia_server.services.resolver_save_flow.load_needs",
        lambda dept_id: [_STOCK_QUOTE_NEED] if dept_id == "macro_research" else [],
    )
    conn = _make_connector(db_session)
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {
                    "ticker": {"to_arg": "symbol", "transform": None},
                },
                "constants": {"endpoint": "quote"},
            },
            "warning": None,
        }
    )
    transport = _StubTransport(response=123.45)
    result = await save_user_picked_spec(
        session=db_session,
        connector=conn,
        department_id="macro_research",
        need_id="stock_quote",
        resolution_mode="manual_endpoint",
        user_picked_endpoint="quote",
        user_hint=None,
        websearch_url=None,
        manually_overridden=False,
        llm_client=llm,
        transport_factory=lambda _c: transport,
    )
    assert isinstance(result, SaveFlowSuccess)
    assert result.spec.access_mode == "remote_mcp"
    assert result.spec.resolution_mode == "manual_endpoint"
    assert result.spec.last_smoke_at is not None

    # Both audit tables got rows.
    assert db_session.query(ResolverCallLog).count() == 1
    assert db_session.query(SmokeCallLog).count() == 1
    assert db_session.query(RunnerCallableSpec).count() == 1


@pytest.mark.asyncio
async def test_save_flow_blocks_persist_on_smoke_failure(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Smoke failure → no live RunnerCallableSpec row, but logs persist."""
    monkeypatch.setattr(
        "openlia_server.services.resolver_save_flow.load_needs",
        lambda dept_id: [_STOCK_QUOTE_NEED] if dept_id == "macro_research" else [],
    )
    conn = _make_connector(db_session)
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {
                    "ticker": {"to_arg": "symbol", "transform": None},
                },
                "constants": {"endpoint": "quote"},
            },
            "warning": None,
        }
    )
    import httpx

    class _AuthFailTransport:
        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            req = httpx.Request("GET", "https://example.com")
            resp = httpx.Response(401, request=req)
            raise httpx.HTTPStatusError("401", request=req, response=resp)

        async def list_tools(self) -> list[dict]:
            return []

        async def aclose(self) -> None:
            return None

    result = await save_user_picked_spec(
        session=db_session,
        connector=conn,
        department_id="macro_research",
        need_id="stock_quote",
        resolution_mode="manual_endpoint",
        user_picked_endpoint="quote",
        user_hint=None,
        websearch_url=None,
        manually_overridden=False,
        llm_client=llm,
        transport_factory=lambda _c: _AuthFailTransport(),
    )
    assert isinstance(result, SaveFlowFailure)
    assert result.failure.status == "auth"
    # No live RunnerCallableSpec row.
    assert db_session.query(RunnerCallableSpec).count() == 0
    # Smoke log captured the failure.
    smokes = db_session.query(SmokeCallLog).all()
    assert len(smokes) == 1
    assert smokes[0].status == "auth"


@pytest.mark.asyncio
async def test_save_flow_overrides_existing_spec_on_resave(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-saving for the same (dept, need) updates rather than duplicating."""
    monkeypatch.setattr(
        "openlia_server.services.resolver_save_flow.load_needs",
        lambda dept_id: [_STOCK_QUOTE_NEED] if dept_id == "macro_research" else [],
    )
    conn = _make_connector(db_session)
    llm = _StubLlm(
        {
            "spec": {"param_bindings": {}, "constants": {"endpoint": "quote"}},
            "warning": None,
        }
    )
    transport = _StubTransport(response=99.0)
    result1 = await save_user_picked_spec(
        session=db_session,
        connector=conn,
        department_id="macro_research",
        need_id="stock_quote",
        resolution_mode="manual_endpoint",
        user_picked_endpoint="quote",
        user_hint=None,
        websearch_url=None,
        manually_overridden=False,
        llm_client=llm,
        transport_factory=lambda _c: transport,
    )
    assert isinstance(result1, SaveFlowSuccess)
    spec_id_1 = result1.spec.id

    # Second save — same (dept, need) — should reuse the row.
    result2 = await save_user_picked_spec(
        session=db_session,
        connector=conn,
        department_id="macro_research",
        need_id="stock_quote",
        resolution_mode="manual_endpoint",
        user_picked_endpoint="quote",
        user_hint="adjusted",
        websearch_url=None,
        manually_overridden=True,
        llm_client=llm,
        transport_factory=lambda _c: transport,
    )
    assert isinstance(result2, SaveFlowSuccess)
    assert result2.spec.id == spec_id_1
    assert db_session.query(RunnerCallableSpec).count() == 1
    assert result2.spec.manually_overridden is True
    # Two resolver attempts and two smoke attempts.
    assert db_session.query(ResolverCallLog).count() == 2
    assert db_session.query(SmokeCallLog).count() == 2


def test_smoke_result_status_field_required() -> None:
    """Smoke failures carry the discriminator surfaced to the frontend."""
    r = SmokeResult(
        status="auth",
        attempts=1,
        error_class="X",
        error_message="msg",
        response_excerpt=None,
    )
    assert r.status == "auth"
