from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.cli import app
from openlia_server.db.models.auth import SignupInvite
from openlia_server.services.auth import tokens as tokens_service
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
        url_line = next(line for line in out.splitlines() if line.startswith("URL:"))
        raw_token = url_line.split("invite=", 1)[1].strip()
        assert raw_token
        assert row.token_hash == tokens_service.hash_token(raw_token)
        assert row.id in out

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
            id="aaaa1111-0000-0000-0000-000000000001",
            token_hash="hash_1",
            label="Engineering",
            max_uses=10,
            use_count=3,
            expires_at=now + timedelta(days=6),
        )
        exhausted = SignupInvite(
            id="bbbb2222-0000-0000-0000-000000000002",
            token_hash="hash_2",
            label=None,
            max_uses=1,
            use_count=1,
            expires_at=None,
        )
        expired = SignupInvite(
            id="cccc3333-0000-0000-0000-000000000003",
            token_hash="hash_3",
            label="old",
            max_uses=None,
            use_count=2,
            expires_at=now - timedelta(days=1),
        )
        revoked = SignupInvite(
            id="dddd4444-0000-0000-0000-000000000004",
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

        assert "aaaa1111" in out
        assert "bbbb2222" in out
        assert "cccc3333" in out
        assert "dddd4444" in out

        # Only first 8 chars of ID are shown.
        assert active.id not in out

        def row_for(prefix: str) -> str:
            return next(line for line in out.splitlines() if prefix in line)

        assert "3/10" in row_for("aaaa1111")
        assert "1/1" in row_for("bbbb2222")
        assert "unlimited" in row_for("cccc3333")
        assert "active" in row_for("aaaa1111")
        assert "exhausted" in row_for("bbbb2222")
        assert "expired" in row_for("cccc3333")
        assert "revoked" in row_for("dddd4444")


class TestRevokeInvite:
    def test_by_full_id(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="fullxxxx-0000-0000-0000-000000000001",
            token_hash="hash_x",
            label="Q2",
            max_uses=None,
            use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", invite.id])
        assert result.exit_code == 0
        assert "Invite revoked" in result.output
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, invite.id).revoked_at is not None

    def test_by_prefix(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="prefixaa-0000-0000-0000-000000000002",
            token_hash="hash_p",
            label="Q3",
            max_uses=None,
            use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "prefixaa"])
        assert result.exit_code == 0
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, invite.id).revoked_at is not None

    def test_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "doesnotexist"])
        assert result.exit_code == 2

    def test_ambiguous_prefix_exits_1(self, cli_runner, company_mode, cli_engine, cli_session):
        cli_session.add_all(
            [
                SignupInvite(
                    id="sameaaaa-0000-0000-0000-000000000003",
                    token_hash="hash_a",
                    label=None,
                    max_uses=None,
                    use_count=0,
                ),
                SignupInvite(
                    id="samebbbb-0000-0000-0000-000000000004",
                    token_hash="hash_b",
                    label=None,
                    max_uses=None,
                    use_count=0,
                ),
            ]
        )
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "same"])
        assert result.exit_code == 1
        assert "multiple" in result.output.lower()
