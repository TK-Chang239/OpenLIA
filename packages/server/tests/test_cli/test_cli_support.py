from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
import typer
from openlia_server import _cli_support as support


class TestParseDuration:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("30m", timedelta(minutes=30)),
            ("24h", timedelta(hours=24)),
            ("7d", timedelta(days=7)),
            ("2w", timedelta(weeks=2)),
        ],
    )
    def test_happy_paths(self, raw: str, expected: timedelta) -> None:
        assert support.parse_duration(raw) == expected

    @pytest.mark.parametrize("raw", ["", "7", "7x", "d7", "-3d", "abc", "7dd"])
    def test_invalid_raises(self, raw: str) -> None:
        with pytest.raises(ValueError):
            support.parse_duration(raw)


class TestFormatTable:
    def test_pads_each_column_to_widest_value(self) -> None:
        out = support.format_table(
            headers=["A", "Long"],
            rows=[["x", "yy"], ["zzz", "q"]],
        )
        lines = out.splitlines()
        assert len(lines) == 3
        # Column widths: A=3 (zzz), Long=4 (header)
        assert lines[0] == "A    Long"
        assert lines[1] == "x    yy  "
        assert lines[2] == "zzz  q   "

    def test_empty_rows_returns_header_only(self) -> None:
        out = support.format_table(headers=["H"], rows=[])
        assert out == "H"


class TestEchoError:
    def test_prefixes_error_and_writes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        support.echo_error("nope")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error: nope\n"


class TestRequireCompany:
    def test_personal_mode_exits_1(self, personal_mode) -> None:
        with pytest.raises(typer.Exit) as exc:
            support.require_company()
        assert exc.value.exit_code == 1

    def test_company_mode_returns(self, company_mode) -> None:
        support.require_company()  # no raise


class TestBuildSession:
    def test_uses_explicit_db_url(self, tmp_path, monkeypatch) -> None:
        from openlia_server.db import session as session_mod
        from openlia_server.db.base import Base

        monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
        session_mod.dispose_engine()
        url = f"sqlite:///{tmp_path}/explicit.db"
        session = support.build_session(url)
        Base.metadata.create_all(session.get_bind())
        session.close()
        session_mod.dispose_engine()

    def test_falls_back_to_resolve_db_url(self, tmp_path, monkeypatch) -> None:
        from openlia_server.db import session as session_mod

        session_mod.dispose_engine()
        monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/env.db")
        session = support.build_session(None)
        assert str(session.get_bind().url).endswith("env.db")
        session.close()
        session_mod.dispose_engine()


class TestLogCliEvent:
    def test_emits_with_source_cli_and_null_actor(self, cli_session) -> None:

        from openlia_server.db.models.auth import AuthEvent, User

        user = User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(user)
        cli_session.commit()

        support.log_cli_event(
            cli_session,
            event_type="user_disabled",
            user_id=user.id,
            metadata={"note": "ran from terminal"},
        )
        rows = cli_session.query(AuthEvent).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.event_type == "user_disabled"
        assert row.user_id == user.id
        assert row.actor_user_id is None
        assert row.event_metadata == {"note": "ran from terminal", "source": "cli"}

    def test_metadata_source_cannot_be_overridden_by_caller(self, cli_session) -> None:
        support.log_cli_event(
            cli_session, event_type="user_disabled", metadata={"source": "script"}
        )
        from openlia_server.db.models.auth import AuthEvent

        row = cli_session.query(AuthEvent).one()
        assert row.event_metadata["source"] == "cli"


class TestRenderStartupBanner:
    def test_canonical_lines_in_order_with_sqlite_shortening(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
        out = support.render_startup_banner(
            version="0.1.0",
            mode="personal",
            db_url="sqlite:////home/u/.openlia/openlia.db",
            host="127.0.0.1",
            port=8000,
            scheduler_enabled=True,
            wizard_pending=False,
        )
        lines = out.splitlines()
        assert lines == [
            "OpenLIA v0.1.0",
            "Mode:      personal",
            "Database:  ~/.openlia/openlia.db",
            "Listening: http://127.0.0.1:8000",
            "Scheduler: enabled",
        ]

    def test_strips_query_params_and_keeps_absolute_when_outside_home(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
        out = support.render_startup_banner(
            version="0.1.0",
            mode="company",
            db_url="sqlite:////var/lib/openlia/openlia.db?check_same_thread=0",
            host="0.0.0.0",
            port=8000,
            scheduler_enabled=False,
            wizard_pending=False,
        )
        lines = out.splitlines()
        assert lines[1] == "Mode:      company"
        assert lines[2] == "Database:  /var/lib/openlia/openlia.db"
        assert lines[3] == "Listening: http://0.0.0.0:8000"
        assert lines[4] == "Scheduler: disabled"

    def test_wizard_pending_appends_extra_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
        out = support.render_startup_banner(
            version="0.1.0",
            mode="personal",
            db_url="sqlite:////home/u/.openlia/openlia.db",
            host="127.0.0.1",
            port=8000,
            scheduler_enabled=True,
            wizard_pending=True,
        )
        lines = out.splitlines()
        assert len(lines) == 6
        assert lines[5] == "Setup wizard: pending -- open the URL above to configure."

    def test_wizard_off_omits_extra_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: Path("/home/u")))
        out = support.render_startup_banner(
            version="0.1.0",
            mode="personal",
            db_url="sqlite:////home/u/.openlia/openlia.db",
            host="127.0.0.1",
            port=8000,
            scheduler_enabled=True,
            wizard_pending=False,
        )
        assert "Setup wizard" not in out
        assert len(out.splitlines()) == 5

    def test_non_sqlite_url_passes_through_minus_query(self) -> None:
        out = support.render_startup_banner(
            version="0.1.0",
            mode="company",
            db_url="postgresql://user:pw@host/db?sslmode=require",
            host="0.0.0.0",
            port=8000,
            scheduler_enabled=True,
            wizard_pending=False,
        )
        assert "Database:  postgresql://user:pw@host/db" in out
        assert "sslmode" not in out
