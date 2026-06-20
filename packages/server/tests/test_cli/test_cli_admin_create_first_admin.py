from __future__ import annotations

from openlia_server.cli import app
from openlia_server.db.models.auth import SignupPolicy, User
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.services.auth import passwords
from sqlalchemy import select

VALID_PW = "correct-horse-battery"  # >= 12 chars


class TestAdminGuard:
    def test_personal_mode_rejects(self, cli_runner, personal_mode, cli_engine):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "a@b.com",
                "--display-name",
                "A",
                "--password",
                VALID_PW,
            ],
        )
        assert result.exit_code == 1
        assert "admin commands require company mode" in result.output


class TestCreateFirstAdmin:
    def test_creates_admin(self, cli_runner, company_mode, cli_engine, cli_session):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "admin@demo.com",
                "--display-name",
                "Demo Admin",
                "--password",
                VALID_PW,
            ],
        )
        assert result.exit_code == 0, result.output
        assert "admin@demo.com" in result.output
        user = cli_session.execute(select(User).where(User.email == "admin@demo.com")).scalar_one()
        assert user.is_admin is True
        assert user.is_disabled is False
        assert passwords.verify_password(user.password_hash, VALID_PW) is True

    def test_finalizes_setup(self, cli_runner, company_mode, cli_engine, cli_session):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "admin@demo.com",
                "--display-name",
                "Demo Admin",
                "--password",
                VALID_PW,
            ],
        )
        assert result.exit_code == 0, result.output
        # Wizard marked complete so the SPA stops redirecting to /setup.
        completed = cli_session.get(ConfigStore, "wizard.completed")
        assert completed is not None and str(completed.value).lower() == "true"
        # Company-mode signup policy seeded so invite registration works.
        policy = cli_session.get(SignupPolicy, 1)
        assert policy is not None and policy.mode == "invite_only"

    def test_rejects_when_admin_exists(self, cli_runner, company_mode, cli_engine, cli_session):
        existing = User(
            id="u_existing",
            email="boss@demo.com",
            display_name="Boss",
            password_hash="hash",
            is_admin=True,
            is_disabled=False,
        )
        cli_session.add(existing)
        cli_session.commit()
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "second@demo.com",
                "--display-name",
                "Second",
                "--password",
                VALID_PW,
            ],
        )
        assert result.exit_code == 1
        assert "already exists" in result.output
        assert (
            cli_session.execute(
                select(User).where(User.email == "second@demo.com")
            ).scalar_one_or_none()
            is None
        )

    def test_rejects_short_password(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "a@b.com",
                "--display-name",
                "A",
                "--password",
                "short",
            ],
        )
        assert result.exit_code == 1
        assert "password" in result.output.lower()

    def test_rejects_invalid_email(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-first-admin",
                "--email",
                "not-an-email",
                "--display-name",
                "A",
                "--password",
                VALID_PW,
            ],
        )
        assert result.exit_code == 1
        assert "email" in result.output.lower()

    def test_prompts_for_password_when_omitted(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        result = cli_runner.invoke(
            app,
            ["admin", "create-first-admin", "--email", "prompt@demo.com", "--display-name", "P"],
            input=f"{VALID_PW}\n{VALID_PW}\n",
        )
        assert result.exit_code == 0, result.output
        user = cli_session.execute(select(User).where(User.email == "prompt@demo.com")).scalar_one()
        assert passwords.verify_password(user.password_hash, VALID_PW) is True
