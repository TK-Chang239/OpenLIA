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

    # Firecrawl covers four needs: three world-order series plus
    # interest_revenue (which neither EODHD nor FMP exposes).
    assert len(rows) == 4

    need_ids = {r.need_id for r in rows}
    assert need_ids == {
        "usd_fx_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_holdings",
        "interest_revenue",
    }

    for row in rows:
        assert row.department_id == "macro_research"
        assert row.connector_id == connector.id
        assert row.access_mode == "python_lib"
        assert "need_id" in row.spec


# ---------------------------------------------------------------------------
# alternative-template install: replace existing (dept, need) ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_builtin_runs_canary_and_marks_failed_on_canary_error(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """list_tools succeeding isn't enough — for some MCP servers (FMP)
    list_tools works unauthenticated. The canary call exercises an
    authenticated tool with a sample argument so a wrong api_key flips
    status to FAILED at install time, not at first dashboard request.
    """
    from openlia_server.services import connectors_service as cs

    _stub_validate_ok(monkeypatch)

    # Pretend the FMP canary call (`quote` with sample args) raises.
    async def _fake_canary(*args, **kwargs):
        raise RuntimeError("401 Unauthorized")

    monkeypatch.setattr(cs, "_run_canary_call", _fake_canary)

    connector = await install_builtin(db_session, template_id="fmp", api_key="bad-key")
    assert connector.status == ConnectorStatus.FAILED.value
    assert "401" in (connector.last_error or "")


@pytest.mark.asyncio
async def test_install_builtin_replaces_specs_for_overlapping_needs(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """EODHD and FMP are alternative providers — both claim
    (macro_research, stock_quote). UNIQUE(dept, need) on
    runner_callable_specs forbids two rows for the same key. Installing
    the second should transfer ownership of overlapping needs to the
    new connector (replace) rather than raising IntegrityError.

    EODHD's non-overlapping specs (gdp_yoy, cpi_yoy, debt_gdp,
    cpi_core_yoy, pmi, social_posts) must remain on the EODHD connector.
    """
    from openlia_server.services import connectors_service as cs

    _stub_validate_ok(monkeypatch)

    # Skip the live canary call so the test focuses on replace-semantics
    # rather than re-testing canary behavior (covered by the test above).
    async def _noop_canary(**kwargs):
        return None

    monkeypatch.setattr(cs, "_run_canary_call", _noop_canary)

    eodhd = await install_builtin(db_session, template_id="eodhd", api_key="eodhd-k")
    fmp = await install_builtin(db_session, template_id="fmp", api_key="fmp-k")

    # Both connector rows persist.
    assert eodhd.id != fmp.id
    assert eodhd.status == ConnectorStatus.VALIDATED.value
    assert fmp.status == ConnectorStatus.VALIDATED.value

    rows = db_session.query(RunnerCallableSpec).all()
    by_need = {r.need_id: r for r in rows}

    # FMP claims stock_quote, cpi_yoy, gdp_yoy — all transferred from EODHD.
    fmp_owned = {"stock_quote", "cpi_yoy", "gdp_yoy"}
    for need in fmp_owned:
        assert by_need[need].connector_id == fmp.id, (
            f"{need!r} should be owned by FMP after install"
        )

    # EODHD's non-overlapping specs remain.
    eodhd_only = {"debt_gdp", "cpi_core_yoy", "pmi", "social_posts"}
    for need in eodhd_only:
        assert by_need[need].connector_id == eodhd.id, (
            f"{need!r} should still be owned by EODHD after FMP install"
        )


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
