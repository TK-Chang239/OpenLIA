from __future__ import annotations

from openlia_server.cli import app
from openlia_server.db.models.auth import AuthEvent
from openlia_server.db.models.infrastructure import ConfigStore
from sqlalchemy import select


class TestLockoutEnable:
    def test_defaults_on_no_row_means_noop(self, cli_runner, company_mode, cli_engine, cli_session):
        result = cli_runner.invoke(app, ["admin", "lockout", "enable"])
        assert result.exit_code == 0, result.output
        assert "Lockout enabled" in result.output
        row = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "auth.lockout.enabled")
        ).scalar_one_or_none()
        assert row is not None
        assert row.value == {"enabled": True}
        events = (
            cli_session.execute(
                select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        assert events[0].event_metadata["new"] is True
        assert events[0].event_metadata["source"] == "cli"
        assert events[0].actor_user_id is None

    def test_already_enabled_is_noop_no_event(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        cli_session.add(ConfigStore(key="auth.lockout.enabled", value={"enabled": True}))
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "lockout", "enable"])
        assert result.exit_code == 0
        assert "Lockout enabled" in result.output
        events = (
            cli_session.execute(
                select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
            )
            .scalars()
            .all()
        )
        assert events == []


class TestLockoutDisable:
    def test_disables_and_warns_about_locked_accounts(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        cli_session.add(ConfigStore(key="auth.lockout.enabled", value={"enabled": True}))
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "lockout", "disable"])
        assert result.exit_code == 0
        assert "Lockout disabled" in result.output
        assert "openlia admin unlock" in result.output
        cli_session.expire_all()
        row = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "auth.lockout.enabled")
        ).scalar_one()
        assert row.value == {"enabled": False}
        event = cli_session.execute(
            select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
        ).scalar_one()
        assert event.event_metadata["old"] is True
        assert event.event_metadata["new"] is False


class TestLockoutStatus:
    def test_prints_state_and_last_change(self, cli_runner, company_mode, cli_engine):
        cli_runner.invoke(app, ["admin", "lockout", "disable"])
        result = cli_runner.invoke(app, ["admin", "lockout", "status"])
        assert result.exit_code == 0
        assert "Lockout: disabled" in result.output
        assert "actor: cli" in result.output

    def test_fresh_install_reports_enabled_default(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "lockout", "status"])
        assert result.exit_code == 0
        assert "Lockout: enabled" in result.output
        assert "Last changed: never" in result.output
