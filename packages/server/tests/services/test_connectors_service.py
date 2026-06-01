"""Tests for install_builtin in connectors_service."""

from __future__ import annotations

import pytest
from openlia.connectors.types import Category, ConnectorSource, ConnectorStatus
from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.services import connectors_service
from openlia_server.services.connectors_service import (
    DuplicateConnectorError,
    ValidationOk,
    create_connector,
    install_builtin,
)
from sqlalchemy.orm import Session


def _stub_validate_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch _validate_launch to always return ValidationOk(tools=[], python_callables=[])."""

    async def _ok(launch, secrets, *, tool_overrides=None):
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

    # Firecrawl covers five needs: three world-order series, interest_revenue
    # (which neither EODHD nor FMP exposes), and geopolitical_news as a
    # headline-source fallback for users without NewsAPI.ai.
    assert len(rows) == 5

    need_ids = {r.need_id for r in rows}
    assert need_ids == {
        "usd_fx_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_holdings",
        "interest_revenue",
        "geopolitical_news",
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


# ---------------------------------------------------------------------------
# sync_template_specs: re-sync runner specs against an existing built-in row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_template_specs_inserts_new_specs_added_to_template(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a template gains a new runner spec after the user already
    installed the connector, sync_template_specs must upsert the new
    spec rows in place — without forcing the user to delete and reinstall.
    """
    from dataclasses import replace

    from openlia.connectors.builtins.firecrawl import FIRECRAWL_TEMPLATE
    from openlia.connectors.types import CallableSpec

    _stub_validate_ok(monkeypatch)

    connector = await install_builtin(db_session, template_id="firecrawl", api_key="fc-key")
    initial = (
        db_session.query(RunnerCallableSpec)
        .filter(RunnerCallableSpec.connector_id == connector.id)
        .count()
    )
    assert initial == len(FIRECRAWL_TEMPLATE.runner_specs)

    # Simulate a future template upgrade: prepend a brand-new spec for
    # a need the original template did NOT cover, so we can prove the
    # upserted set strictly grew.
    new_spec = CallableSpec(
        need_id="cpi_yoy",  # MR need; not currently in firecrawl runner_specs
        access_mode="python_lib",
        method="Firecrawl.scrape",
        constants={"url": "https://example.invalid/"},
        result_path=("json", "x"),
        shape="float",
    )
    upgraded = replace(
        FIRECRAWL_TEMPLATE,
        runner_specs=(*FIRECRAWL_TEMPLATE.runner_specs, new_spec),
    )
    monkeypatch.setattr(
        connectors_service, "get_template", lambda tid: upgraded if tid == "firecrawl" else None
    )

    inserted = connectors_service.sync_template_specs(db_session, connector.id)
    assert inserted == len(upgraded.runner_specs)

    rows = (
        db_session.query(RunnerCallableSpec)
        .filter(RunnerCallableSpec.connector_id == connector.id)
        .all()
    )
    need_ids = {r.need_id for r in rows}
    assert "cpi_yoy" in need_ids
    assert len(rows) == len(upgraded.runner_specs)


@pytest.mark.asyncio
async def test_sync_template_specs_unknown_connector_raises(
    db_session: Session,
) -> None:
    with pytest.raises(KeyError, match="unknown connector"):
        connectors_service.sync_template_specs(db_session, "not-a-real-id")


@pytest.mark.asyncio
async def test_sync_template_specs_rejects_non_builtin_connector(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only built-in connectors map back to a template, so a custom
    connector cannot be re-synced this way."""
    from openlia.connectors.types import (
        ConnectorSource,
        ConnectorStatus,
    )
    from openlia_server.db.models.connectors import Connector

    custom = Connector(
        id="custom-1",
        provider_id="my-custom-provider",
        display_name="Custom",
        source=ConnectorSource.REMOTE_MCP.value,
        category="financial",
        launch={"modes": [{"kind": "remote_mcp", "url": "https://x", "headers": {}}]},
        secrets={},
        cached_tools=[],
        status=ConnectorStatus.VALIDATED.value,
    )
    db_session.add(custom)
    db_session.commit()

    with pytest.raises(KeyError, match="not built-in"):
        connectors_service.sync_template_specs(db_session, "custom-1")


# ---------------------------------------------------------------------------
# duplicate-install guard: same (provider_id, source) is rejected
# ---------------------------------------------------------------------------


def _firecrawl_remote_launch() -> dict:
    return {
        "modes": [
            {
                "kind": "remote_mcp",
                "url": "https://mcp.firecrawl.dev/key/v2/mcp",
                "headers": {},
            }
        ]
    }


@pytest.mark.asyncio
async def test_create_connector_rejects_duplicate_provider_source(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_validate_ok(monkeypatch)

    first = await create_connector(
        db_session,
        provider_id="firecrawl",
        display_name="Firecrawl",
        source=ConnectorSource.REMOTE_MCP,
        category=Category.WEB_SEARCH,
        launch=_firecrawl_remote_launch(),
    )
    assert first.status == ConnectorStatus.VALIDATED.value

    with pytest.raises(DuplicateConnectorError) as exc:
        await create_connector(
            db_session,
            provider_id="firecrawl",
            display_name="Firecrawl",
            source=ConnectorSource.REMOTE_MCP,
            category=Category.WEB_SEARCH,
            launch=_firecrawl_remote_launch(),
        )

    assert exc.value.existing_id == first.id
    assert exc.value.provider_id == "firecrawl"
    assert exc.value.source == ConnectorSource.REMOTE_MCP.value

    rows = (
        db_session.query(Connector)
        .filter(
            Connector.provider_id == "firecrawl",
            Connector.source == ConnectorSource.REMOTE_MCP.value,
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].id == first.id


@pytest.mark.asyncio
async def test_create_connector_allows_same_provider_with_different_source(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """built_in install + a separately-managed remote_mcp install must coexist."""
    _stub_validate_ok(monkeypatch)

    builtin = await install_builtin(db_session, template_id="firecrawl", api_key="k")
    assert builtin.source == ConnectorSource.BUILT_IN.value

    sibling = await create_connector(
        db_session,
        provider_id="firecrawl",
        display_name="Firecrawl",
        source=ConnectorSource.REMOTE_MCP,
        category=Category.WEB_SEARCH,
        launch=_firecrawl_remote_launch(),
    )
    assert sibling.id != builtin.id


@pytest.mark.asyncio
async def test_install_builtin_rejects_second_install_of_same_template(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _stub_validate_ok(monkeypatch)

    first = await install_builtin(db_session, template_id="firecrawl", api_key="k1")

    with pytest.raises(DuplicateConnectorError) as exc:
        await install_builtin(db_session, template_id="firecrawl", api_key="k2")
    assert exc.value.existing_id == first.id

    rows = db_session.query(Connector).filter(Connector.provider_id == "firecrawl").all()
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# _validate_launch: require >= 1 tool for cli_mcp / remote_mcp
# ---------------------------------------------------------------------------


from openlia_server.services import connectors_service as cs  # noqa: E402


class _FakeTransport:
    def __init__(self, tools: list[dict]) -> None:
        self._tools = tools

    async def list_tools(self) -> list[dict]:
        return self._tools

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_validate_launch_fails_when_remote_mcp_returns_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cs, "_build_transport", lambda connector_id, mode, secrets: _FakeTransport([])
    )
    launch = {"modes": [{"kind": "remote_mcp", "url": "https://x/mcp", "headers": {}}]}
    result = await cs._validate_launch(launch, {})
    assert isinstance(result, cs.ValidationFailure)
    assert "no tools" in result.error.lower()


@pytest.mark.asyncio
async def test_validate_launch_passes_when_cli_mcp_returns_a_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = {"name": "quote", "description": "", "input_schema": {}}
    monkeypatch.setattr(
        cs, "_build_transport", lambda connector_id, mode, secrets: _FakeTransport([tool])
    )
    launch = {"modes": [{"kind": "cli_mcp", "argv": ["uvx", "srv"], "env_keys": []}]}
    result = await cs._validate_launch(launch, {})
    assert isinstance(result, cs.ValidationOk)
    assert result.tools == [tool]
