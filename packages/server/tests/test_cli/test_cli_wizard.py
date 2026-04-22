from __future__ import annotations

from openlia_server.cli import app
from openlia_server.db.models.infrastructure import ConfigStore, WizardState
from sqlalchemy import select


class TestWizardReset:
    def test_yes_flag_skips_confirmation(self, cli_runner, cli_engine, cli_session):
        cli_session.add(WizardState(
            id=1,
            status="completed",
            current_step="done",
            completed_steps=["mode", "account", "models", "data_providers", "review"],
            active_session_token="old-token",
            mode="personal",
        ))
        cli_session.add(ConfigStore(key="wizard.completed", value=True))
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset", "--yes"])
        assert result.exit_code == 0, result.output
        assert "Wizard state reset" in result.output

        cli_session.expire_all()
        state = cli_session.execute(select(WizardState)).scalar_one()
        assert state.status == "not_started"
        assert state.current_step == "mode"
        assert state.completed_steps == []
        assert state.active_session_token is None
        assert state.mode is None
        wc = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "wizard.completed")
        ).scalar_one()
        assert wc.value is False

    def test_interactive_yes(self, cli_runner, cli_engine, cli_session):
        cli_session.add(WizardState(
            id=1,
            status="completed",
            current_step="done",
            completed_steps=["mode", "account", "models", "data_providers", "policy", "review"],
            active_session_token="old-token",
            mode="company",
        ))
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset"], input="y\n")
        assert result.exit_code == 0, result.output
        cli_session.expire_all()
        assert cli_session.execute(select(WizardState)).scalar_one().status == "not_started"

    def test_interactive_abort(self, cli_runner, cli_engine, cli_session):
        cli_session.add(WizardState(
            id=1,
            status="completed",
            current_step="done",
            completed_steps=["mode", "account", "models", "data_providers", "policy", "review"],
            active_session_token="old-token",
            mode="company",
        ))
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset"], input="n\n")
        assert result.exit_code == 1
        cli_session.expire_all()
        assert cli_session.execute(select(WizardState)).scalar_one().status == "completed"

    def test_works_without_existing_wizard_row(self, cli_runner, cli_engine, cli_session):
        assert cli_session.execute(select(WizardState)).scalar_one_or_none() is None
        result = cli_runner.invoke(app, ["wizard", "reset", "--yes"])
        assert result.exit_code == 0
        cli_session.expire_all()
        state = cli_session.execute(select(WizardState)).scalar_one()
        assert state.status == "not_started"
        assert state.current_step == "mode"
        assert state.completed_steps == []
        assert state.active_session_token is None
        assert state.mode is None
