from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.cli import app
from openlia_server.db.models.auth import Session as AuthSession
from openlia_server.db.models.auth import User
from sqlalchemy import select


@pytest.fixture
def expired_sessions(cli_session):
    now = datetime.now(UTC)
    user = User(
        id="u_1",
        email="u@e.com",
        display_name="u",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    cli_session.add(user)
    cli_session.flush()
    for i in range(3):
        cli_session.add(
            AuthSession(
                id=f"s_{i}",
                user_id="u_1",
                token_hash=f"h_{i}",
                last_seen_at=now - timedelta(days=20),
                expires_at=now - timedelta(days=15),
            )
        )
    cli_session.add(
        AuthSession(
            id="s_fresh",
            user_id="u_1",
            token_hash="h_fresh",
            last_seen_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    cli_session.commit()


class TestMaintenance:
    def test_real_run_deletes_expired(self, cli_runner, cli_engine, cli_session, expired_sessions):
        result = cli_runner.invoke(app, ["maintenance"])
        assert result.exit_code == 0, result.output
        assert "sessions:" in result.output
        assert "deleted 3 expired rows" in result.output
        cli_session.expire_all()
        remaining = cli_session.execute(select(AuthSession)).scalars().all()
        assert {s.id for s in remaining} == {"s_fresh"}

    def test_dry_run_does_not_delete(self, cli_runner, cli_engine, cli_session, expired_sessions):
        result = cli_runner.invoke(app, ["maintenance", "--dry-run"])
        assert result.exit_code == 0, result.output
        for line in [line for line in result.output.splitlines() if line.strip()]:
            assert line.startswith("[dry-run]")
        cli_session.expire_all()
        remaining = cli_session.execute(select(AuthSession)).scalars().all()
        assert len(remaining) == 4

    def test_fresh_database_reports_all_zeros(self, cli_runner, cli_engine):
        result = cli_runner.invoke(app, ["maintenance"])
        assert result.exit_code == 0
        assert "deleted 0" in result.output or "0 expired" in result.output
