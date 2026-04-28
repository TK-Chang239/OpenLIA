"""CLI tests for `openlia connectors list` and `openlia connectors validate`.

The validate path patches `revalidate_connector` so the test stays
focused on CLI plumbing (argument parsing, output formatting, exit
codes) and doesn't depend on a real transport at fire time.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia_server.cli import app
from openlia_server.db.models.connectors import Connector


def _seed_connector(
    cli_session,
    *,
    cid: str = "11111111-1111-1111-1111-111111111111",
    provider_id: str = "demo_provider",
    display_name: str = "Demo Provider",
    category: str = "financial",
    status: str = "validated",
) -> Connector:
    row = Connector(
        id=cid,
        provider_id=provider_id,
        display_name=display_name,
        source="built_in",
        category=category,
        launch={"modes": []},
        secrets={},
        status=status,
        validated_at=datetime.now(UTC) if status == "validated" else None,
    )
    cli_session.add(row)
    cli_session.commit()
    return row


class TestConnectorsList:
    def test_empty_db_prints_message(self, cli_runner, cli_engine):
        result = cli_runner.invoke(app, ["connectors", "list"])
        assert result.exit_code == 0, result.output
        assert "No connectors configured." in result.output

    def test_lists_rows(self, cli_runner, cli_engine, cli_session):
        _seed_connector(
            cli_session,
            cid="11111111-1111-1111-1111-111111111111",
            provider_id="prov_a",
            display_name="Prov A",
            category="financial",
            status="validated",
        )
        _seed_connector(
            cli_session,
            cid="22222222-2222-2222-2222-222222222222",
            provider_id="prov_b",
            display_name="Prov B",
            category="news",
            status="failed",
        )

        result = cli_runner.invoke(app, ["connectors", "list"])
        assert result.exit_code == 0, result.output
        assert "11111111-1111-1111-1111-111111111111" in result.output
        assert "prov_a" in result.output
        assert "Prov A" in result.output
        assert "[financial]" in result.output
        assert "validated" in result.output
        assert "22222222-2222-2222-2222-222222222222" in result.output
        assert "prov_b" in result.output
        assert "[news]" in result.output
        assert "failed" in result.output


class TestConnectorsValidate:
    def test_not_found_exits_1(self, cli_runner, cli_engine, monkeypatch):
        async def _stub(_session, _cid):
            return None

        monkeypatch.setattr(
            "openlia_server.cli.revalidate_connector",
            _stub,
        )

        result = cli_runner.invoke(app, ["connectors", "validate", "missing-id"])
        assert result.exit_code == 1
        assert "missing-id" in result.output
        assert "not found" in result.output

    def test_success_prints_status(self, cli_runner, cli_engine, cli_session, monkeypatch):
        row = _seed_connector(
            cli_session,
            cid="33333333-3333-3333-3333-333333333333",
            provider_id="prov_ok",
            status="validated",
        )

        async def _stub(_session, cid):
            assert cid == row.id
            return row

        monkeypatch.setattr(
            "openlia_server.cli.revalidate_connector",
            _stub,
        )

        result = cli_runner.invoke(app, ["connectors", "validate", row.id])
        assert result.exit_code == 0, result.output
        assert row.id in result.output
        assert "status=validated" in result.output

    def test_failed_prints_error(self, cli_runner, cli_engine, cli_session, monkeypatch):
        row = _seed_connector(
            cli_session,
            cid="44444444-4444-4444-4444-444444444444",
            provider_id="prov_bad",
            status="failed",
        )
        row.last_error = "boom: list_tools failed"
        cli_session.commit()

        async def _stub(_session, _cid):
            return row

        monkeypatch.setattr(
            "openlia_server.cli.revalidate_connector",
            _stub,
        )

        result = cli_runner.invoke(app, ["connectors", "validate", row.id])
        assert result.exit_code == 0, result.output
        assert "status=failed" in result.output
        assert "error: boom: list_tools failed" in result.output
