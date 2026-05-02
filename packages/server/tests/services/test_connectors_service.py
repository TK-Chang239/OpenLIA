"""Tests for install_builtin in connectors_service."""

from __future__ import annotations

import pytest
from openlia.connectors.types import ConnectorStatus
from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.services import connectors_service
from openlia_server.services.connectors_service import ValidationOk, install_builtin
from sqlalchemy.orm import Session


def _stub_validate_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch _validate_launch to always return ValidationOk(tools=[], python_callables=[])."""

    async def _ok(launch, secrets):
        return ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _ok)


# ---------------------------------------------------------------------------
# test 1: unknown template raises KeyError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_builtin_unknown_template_raises(db_session: Session) -> None:
    with pytest.raises(KeyError, match="bogus-template-xyz"):
        await install_builtin(db_session, template_id="bogus-template-xyz", api_key="k")


# ---------------------------------------------------------------------------
# test 2: creates connector with modes derived from template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_builtin_creates_connector_with_modes_from_template(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_validate_ok(monkeypatch)

    connector = await install_builtin(db_session, template_id="firecrawl", api_key="fc-test-key")

    assert isinstance(connector, Connector)
    assert connector.provider_id == "firecrawl"
    assert connector.display_name == "Firecrawl"
    assert connector.source == "built_in"
    assert connector.status == ConnectorStatus.VALIDATED.value
    assert connector.secrets == {"FIRECRAWL_API_KEY": "fc-test-key"}

    # Launch spec must have the two modes from FIRECRAWL_TEMPLATE
    modes = connector.launch["modes"]
    kinds = {m["kind"] for m in modes}
    assert "remote_mcp" in kinds
    assert "cli_mcp" in kinds


# ---------------------------------------------------------------------------
# test 3: runner_specs rows written for macro_research needs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_builtin_inserts_runner_callable_specs_for_runner_needs(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_validate_ok(monkeypatch)

    connector = await install_builtin(db_session, template_id="firecrawl", api_key="fc-test-key")

    rows = (
        db_session.query(RunnerCallableSpec)
        .filter(RunnerCallableSpec.connector_id == connector.id)
        .all()
    )

    # Firecrawl has 3 runner_specs (world-order needs)
    assert len(rows) == 3

    need_ids = {r.need_id for r in rows}
    assert need_ids == {"usd_fx_reserve_share", "cb_gold_purchases", "foreign_treasury_holdings"}

    for row in rows:
        assert row.department_id == "macro_research"
        assert row.connector_id == connector.id
        assert row.access_mode == "python_lib"
        assert "need_id" in row.spec


# ---------------------------------------------------------------------------
# test 4: template with no runner_specs inserts no rows
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_builtin_template_with_no_runner_specs_inserts_no_specs(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_validate_ok(monkeypatch)

    connector = await install_builtin(db_session, template_id="x", api_key="x-test-key")

    rows = (
        db_session.query(RunnerCallableSpec)
        .filter(RunnerCallableSpec.connector_id == connector.id)
        .all()
    )
    assert len(rows) == 0
