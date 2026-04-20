from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from openlia_server.cli import app
from openlia_server.db.models.auth import Session as AuthSession
from openlia_server.db.models.auth import User
from openlia_server.services.auth import passwords
from sqlalchemy import select


@pytest.fixture
def seed_users(cli_session):
    alice = User(
        id="u_alice",
        email="alice@company.com",
        display_name="Alice Chen",
        password_hash="hash",
        is_admin=True,
        is_disabled=False,
        last_login_at=datetime(2026, 4, 15, 9, 30, tzinfo=UTC),
    )
    bob = User(
        id="u_bob",
        email="bob@company.com",
        display_name="Bob Kim",
        password_hash="hash",
        is_admin=False,
        is_disabled=False,
    )
    carol = User(
        id="u_carol",
        email="carol@company.com",
        display_name="Carol Wu",
        password_hash="hash",
        is_admin=False,
        is_disabled=True,
    )
    cli_session.add_all([alice, bob, carol])
    cli_session.commit()
    return {"alice": alice, "bob": bob, "carol": carol}


class TestAdminGuard:
    def test_personal_mode_rejects(self, cli_runner, personal_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        assert result.exit_code == 1
        assert "admin commands require company mode" in result.output


class TestListUsers:
    def test_lists_all_users_with_columns(self, cli_runner, company_mode, cli_engine, seed_users):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "Email" in out and "Display Name" in out
        assert "alice@company.com" in out
        assert "bob@company.com" in out
        assert "carol@company.com" in out
        alice_row = next(line for line in out.splitlines() if "alice@" in line)
        assert "yes" in alice_row.split("alice@company.com")[1][:20]

    def test_disabled_filter(self, cli_runner, company_mode, cli_engine, seed_users):
        result = cli_runner.invoke(app, ["admin", "list-users", "--disabled"])
        assert result.exit_code == 0
        out = result.output
        assert "carol@company.com" in out
        assert "alice@company.com" not in out
        assert "bob@company.com" not in out

    def test_last_login_blank_when_null(self, cli_runner, company_mode, cli_engine, seed_users):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        bob_line = next(line for line in result.output.splitlines() if "bob@" in line)
        assert bob_line.rstrip().endswith("no")


class TestUnlock:
    def test_clears_lock_state(self, cli_runner, company_mode, cli_engine, cli_session):
        now = datetime.now(UTC)
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
            failed_login_attempts=5,
            locked_until=now + timedelta(minutes=10),
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "unlock", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Unlocked: alice@company.com" in result.output
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert refreshed.locked_until is None
        assert refreshed.failed_login_attempts == 0

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "unlock", "ghost@company.com"])
        assert result.exit_code == 2
        assert "not found" in result.output.lower()


class TestResetPassword:
    def test_with_password_flag_sets_must_change(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="original",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "alice@company.com", "--password", "NewStrongP@ssw0rd1"],
        )
        assert result.exit_code == 0, result.output
        assert "Password reset for alice@company.com" in result.output
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert refreshed.must_change_password is True
        assert refreshed.password_hash != "original"
        assert passwords.verify_password(refreshed.password_hash, "NewStrongP@ssw0rd1")

    def test_interactive_prompt_accepts_password(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="original",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "alice@company.com"],
            input="PromptStrongP@ss1\nPromptStrongP@ss1\n",
        )
        assert result.exit_code == 0, result.output
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert passwords.verify_password(refreshed.password_hash, "PromptStrongP@ss1")

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "ghost@company.com", "--password", "x" * 20],
        )
        assert result.exit_code == 2


class TestDisableUser:
    def test_disables_and_revokes_sessions(self, cli_runner, company_mode, cli_engine, cli_session):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        now = datetime.now(UTC)
        for i in range(3):
            cli_session.add(
                AuthSession(
                    id=f"s_{i}",
                    user_id="u_alice",
                    token_hash=f"th_{i}",
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "disable-user", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Disabled: alice@company.com" in result.output
        assert "3 sessions revoked" in result.output
        cli_session.expire_all()
        assert cli_session.get(User, "u_alice").is_disabled is True
        live_sessions = (
            cli_session.execute(
                select(AuthSession).where(
                    AuthSession.user_id == "u_alice", AuthSession.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        assert live_sessions == []

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "disable-user", "ghost@company.com"])
        assert result.exit_code == 2


class TestEnableUser:
    def test_enables(self, cli_runner, company_mode, cli_engine, cli_session):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=True,
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "enable-user", "alice@company.com"])
        assert result.exit_code == 0
        assert "Enabled: alice@company.com" in result.output
        cli_session.expire_all()
        assert cli_session.get(User, "u_alice").is_disabled is False

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "enable-user", "ghost@company.com"])
        assert result.exit_code == 2


class TestRevokeSessions:
    def test_revokes_all_sessions(self, cli_runner, company_mode, cli_engine, cli_session):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        now = datetime.now(UTC)
        for i in range(4):
            cli_session.add(
                AuthSession(
                    id=f"s_{i}",
                    user_id="u_alice",
                    token_hash=f"th_{i}",
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Revoked 4 sessions for alice@company.com" in result.output
        live = (
            cli_session.execute(
                select(AuthSession).where(
                    AuthSession.user_id == "u_alice", AuthSession.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        assert live == []

    def test_no_sessions_still_succeeds(self, cli_runner, company_mode, cli_engine, cli_session):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "alice@company.com"])
        assert result.exit_code == 0
        assert "Revoked 0 sessions" in result.output

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "ghost@company.com"])
        assert result.exit_code == 2
