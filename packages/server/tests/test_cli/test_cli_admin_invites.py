from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.cli import app
from openlia_server.db.models.auth import SignupInvite
from sqlalchemy import select


class TestCreateInvite:
    def test_defaults(self, cli_runner, company_mode, cli_engine, cli_session):
        result = cli_runner.invoke(app, ["admin", "create-invite"])
        assert result.exit_code == 0, result.output
        out = result.output
        assert "Invite created." in out
        assert "URL:" in out
        row = cli_session.execute(select(SignupInvite)).scalar_one()
        assert row.expires_at is None
        assert row.max_uses is None
        assert row.label is None
        assert row.token in out

    def test_with_label_max_uses_and_expires(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        result = cli_runner.invoke(
            app,
            [
                "admin",
                "create-invite",
                "--label",
                "Engineering team",
                "--max-uses",
                "10",
                "--expires",
                "7d",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Label:    Engineering team" in result.output
        assert "Max uses: 10" in result.output
        row = cli_session.execute(select(SignupInvite)).scalar_one()
        assert row.label == "Engineering team"
        assert row.max_uses == 10
        assert row.expires_at is not None
        delta = row.expires_at - datetime.now(UTC)
        assert timedelta(days=7) - timedelta(seconds=60) <= delta
        assert delta <= timedelta(days=7) + timedelta(seconds=60)

    def test_invalid_duration_exits_1(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "create-invite", "--expires", "not-a-duration"])
        assert result.exit_code == 1
        assert "Invalid duration" in result.output


class TestListInvites:
    def test_groups_active_expired_revoked_exhausted(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        now = datetime.now(UTC)
        active = SignupInvite(
            id="inv_1",
            token="abc123def456abcdef",
            token_hash="hash_1",
            label="Engineering",
            max_uses=10,
            use_count=3,
            expires_at=now + timedelta(days=6),
        )
        exhausted = SignupInvite(
            id="inv_2",
            token="mno345pqr678abcdef",
            token_hash="hash_2",
            label=None,
            max_uses=1,
            use_count=1,
            expires_at=None,
        )
        expired = SignupInvite(
            id="inv_3",
            token="xyz789abc012abcdef",
            token_hash="hash_3",
            label="old",
            max_uses=None,
            use_count=2,
            expires_at=now - timedelta(days=1),
        )
        revoked = SignupInvite(
            id="inv_4",
            token="rev000000000abcdef",
            token_hash="hash_4",
            label="gone",
            max_uses=None,
            use_count=0,
            expires_at=None,
            revoked_at=now,
        )
        cli_session.add_all([active, exhausted, expired, revoked])
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "list-invites"])
        assert result.exit_code == 0, result.output
        out = result.output

        assert "abc123def456" in out
        assert "mno345pqr678" in out
        assert "xyz789abc012" in out
        assert "rev000000000" in out

        assert "abc123def456abcdef" not in out  # only first 12 chars shown

        def row_for(prefix: str) -> str:
            return next(line for line in out.splitlines() if prefix in line)

        assert "3/10" in row_for("abc123def456")
        assert "1/1" in row_for("mno345pqr678")
        assert "unlimited" in row_for("xyz789abc012")
        assert "active" in row_for("abc123def456")
        assert "exhausted" in row_for("mno345pqr678")
        assert "expired" in row_for("xyz789abc012")
        assert "revoked" in row_for("rev000000000")


class TestRevokeInvite:
    def test_by_full_token(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="inv_x",
            token="abc123def456fullxyz",
            token_hash="hash_x",
            label="Q2",
            max_uses=None,
            use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", invite.token])
        assert result.exit_code == 0
        assert "Invite revoked" in result.output
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, "inv_x").revoked_at is not None

    def test_by_prefix(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="inv_p",
            token="abc123def456fullxyz",
            token_hash="hash_p",
            label="Q3",
            max_uses=None,
            use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "abc123def456"])
        assert result.exit_code == 0
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, "inv_p").revoked_at is not None

    def test_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "doesnotexist"])
        assert result.exit_code == 2

    def test_ambiguous_prefix_exits_1(self, cli_runner, company_mode, cli_engine, cli_session):
        cli_session.add_all(
            [
                SignupInvite(
                    id="inv_a",
                    token="samepref_aaaaaaaaa",
                    token_hash="hash_a",
                    label=None,
                    max_uses=None,
                    use_count=0,
                ),
                SignupInvite(
                    id="inv_b",
                    token="samepref_bbbbbbbbb",
                    token_hash="hash_b",
                    label=None,
                    max_uses=None,
                    use_count=0,
                ),
            ]
        )
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "samepref"])
        assert result.exit_code == 1
        assert "multiple" in result.output.lower()
