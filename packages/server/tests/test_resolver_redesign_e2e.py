"""Phase 12: end-to-end coverage of the manual-pick redesign.

Exercises every layer end-to-end without HTTP:
  - Phase 5 resolver (manual-pick)
  - Phase 6 validation gate
  - Phase 7 smoke pipeline (success + failure)
  - Phase 10 save flow + audit log persistence
  - Phase 11 override-wins template upgrade
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
import pytest
from openlia.connectors.types import Category
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
from openlia_server.services.template_upgrade import (
    apply_template_with_override_protection,
    revert_to_default,
)
from sqlalchemy.orm import Session


class _StubLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        return self._payload


class _OkTransport:
    def __init__(self, response: Any) -> None:
        self._response = response

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return self._response

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


class _AuthFailTransport:
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        req = httpx.Request("GET", "https://example.com")
        resp = httpx.Response(401, request=req)
        raise httpx.HTTPStatusError("401", request=req, response=resp)

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


def _connector(db_session: Session) -> Connector:
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
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
        status="validated",
    )
    db_session.add(conn)
    db_session.commit()
    return conn


def _llm_ok() -> _StubLlm:
    return _StubLlm(
        {
            "spec": {
                "param_bindings": {
                    "ticker": {"to_arg": "symbol", "transform": "upper"},
                },
                "constants": {},
            },
            "warning": None,
        }
    )


@pytest.mark.asyncio
async def test_e2e_happy_path(db_session: Session) -> None:
    conn = _connector(db_session)
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
        llm_client=_llm_ok(),
        transport_factory=lambda _: _OkTransport(150.0),
    )
    assert isinstance(result, SaveFlowSuccess)
    spec_row = result.spec
    assert spec_row.spec["tool_name"] == "quote"
    assert db_session.query(ResolverCallLog).count() == 1
    assert db_session.query(SmokeCallLog).count() == 1
    smoke = db_session.query(SmokeCallLog).one()
    assert smoke.status == "success"


@pytest.mark.asyncio
async def test_e2e_auth_failure_preserves_no_spec(db_session: Session) -> None:
    conn = _connector(db_session)
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
        llm_client=_llm_ok(),
        transport_factory=lambda _: _AuthFailTransport(),
    )
    assert isinstance(result, SaveFlowFailure)
    assert result.failure.status == "auth"
    assert db_session.query(RunnerCallableSpec).count() == 0
    smokes = db_session.query(SmokeCallLog).all()
    assert len(smokes) == 1
    assert smokes[0].status == "auth"


@pytest.mark.asyncio
async def test_e2e_override_path_preserves_user_pick_on_template_upgrade(
    db_session: Session,
) -> None:
    """End-to-end override-wins path:

    1. User saves a manual override.
    2. A subsequent catalog install for the same (dept, need) records a
       pending default change but does not clobber.
    3. Revert_to_default replaces the spec with the pending one.
    """
    conn = _connector(db_session)
    save_result = await save_user_picked_spec(
        session=db_session,
        connector=conn,
        department_id="macro_research",
        need_id="stock_quote",
        resolution_mode="manual_endpoint",
        user_picked_endpoint="quote",
        user_hint="user pick",
        websearch_url=None,
        manually_overridden=True,
        llm_client=_llm_ok(),
        transport_factory=lambda _: _OkTransport(150.0),
    )
    assert isinstance(save_result, SaveFlowSuccess)
    spec_row = save_result.spec
    assert spec_row.resolution_mode == "manual_endpoint"
    assert spec_row.manually_overridden is True

    # Catalog install attempts the same (dept, need) — must not clobber.
    apply_template_with_override_protection(
        db_session,
        connector_id=conn.id,
        department_id="macro_research",
        need_id="stock_quote",
        template_spec={"tool_name": "catalog_quote"},
        access_mode="remote_mcp",
    )
    db_session.refresh(spec_row)
    assert spec_row.spec["tool_name"] == "quote"
    assert spec_row.pending_default_change is not None
    assert spec_row.pending_default_change["spec"] == {"tool_name": "catalog_quote"}

    # Revert applies the pending default.
    revert_to_default(db_session, department_id="macro_research", need_id="stock_quote")
    db_session.refresh(spec_row)
    assert spec_row.spec == {"tool_name": "catalog_quote"}
    assert spec_row.resolution_mode == "catalog"
    assert spec_row.pending_default_change is None
    assert spec_row.manually_overridden is False
