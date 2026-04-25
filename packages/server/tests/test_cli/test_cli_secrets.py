from __future__ import annotations

import base64

import pytest
from openlia_server.cli import app
from openlia_server.db import crypto
from openlia_server.db.models.config import (
    DataProvider,
    LLMProvider,
    WebSearchProvider,
)
from sqlalchemy import select


@pytest.fixture
def seeded_encrypted_rows(cli_session, cli_secret_key):
    """Insert one row per encrypted-column table, encrypted with the old key."""
    old_key = cli_secret_key
    llm = LLMProvider(
        id="llm_1",
        kind="openai",
        label="OpenAI",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "llm_1", "sk-llm-secret"),
    )
    data = DataProvider(
        id="data_1",
        kind="eodhd",
        label="EODHD",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "data_1", "eodhd-secret"),
    )
    ws = WebSearchProvider(
        id="ws_1",
        kind="brave",
        label="Brave",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "ws_1", "brave-secret"),
    )
    cli_session.add_all([llm, data, ws])
    cli_session.commit()
    return {"llm": llm, "data": data, "ws": ws}


class TestRotateKey:
    def test_rotates_using_env_key_path(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_encrypted_rows,
        monkeypatch,
    ):
        assert not (cli_home / "secret.key").exists()
        new_key = b"\x33" * 32
        new_key_b64 = base64.b64encode(new_key).decode()

        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", new_key_b64])
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.output
        assert "Update your OPENLIA_SECRET_KEY" in result.output
        assert new_key_b64 in result.output
        assert not (cli_home / "secret.key").exists()

        from openlia_server.db.session import SessionLocal

        s = SessionLocal()
        try:
            llm = s.execute(select(LLMProvider)).scalar_one()
            data = s.execute(select(DataProvider)).scalar_one()
            ws = s.execute(select(WebSearchProvider)).scalar_one()
            assert (
                crypto.decrypt_with_key(new_key, "llm_1", llm.api_key_encrypted) == "sk-llm-secret"
            )
            assert (
                crypto.decrypt_with_key(new_key, "data_1", data.api_key_encrypted) == "eodhd-secret"
            )
            assert crypto.decrypt_with_key(new_key, "ws_1", ws.api_key_encrypted) == "brave-secret"
        finally:
            s.close()

    def test_rotates_using_file_key_path(
        self,
        cli_runner,
        cli_engine,
        cli_home,
        seeded_encrypted_rows,
        monkeypatch,
    ):
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        old_key = b"\x22" * 32
        key_file = cli_home / "secret.key"
        key_file.write_bytes(base64.b64encode(old_key))
        key_file.chmod(0o600)

        from openlia_server.db import crypto as crypto_mod
        from openlia_server.db.session import SessionLocal

        s = SessionLocal()
        try:
            for row_id, Model, plaintext in [
                ("llm_1", LLMProvider, "sk-llm-secret"),
                ("data_1", DataProvider, "eodhd-secret"),
                ("ws_1", WebSearchProvider, "brave-secret"),
            ]:
                row = s.get(Model, row_id)
                row.api_key_encrypted = crypto_mod.encrypt_with_key(old_key, row_id, plaintext)
            s.commit()
        finally:
            s.close()
        crypto_mod._reset_cached_key()

        new_key = b"\x44" * 32
        new_key_b64 = base64.b64encode(new_key).decode()
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", new_key_b64])
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.output
        assert "New key written to" in result.output
        assert key_file.exists()
        assert oct(key_file.stat().st_mode & 0o777) == "0o600"
        new_on_disk = base64.b64decode(key_file.read_bytes(), validate=True)
        assert new_on_disk == new_key

    def test_refuses_if_database_locked(
        self, cli_runner, cli_engine, cli_secret_key, seeded_encrypted_rows, monkeypatch
    ):
        import sqlite3

        engine = cli_engine
        db_path = engine.url.database
        assert db_path is not None
        holder = sqlite3.connect(db_path, isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")

        new_key_b64 = base64.b64encode(b"\x55" * 32).decode()
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", new_key_b64])
        holder.close()

        assert result.exit_code == 1
        assert "stop the server before rotating keys" in result.output

    def test_invalid_new_key_exits_1(
        self, cli_runner, cli_engine, cli_secret_key, seeded_encrypted_rows
    ):
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", "not-valid-base64!"])
        assert result.exit_code == 1

    def test_no_encrypted_rows_reports_zero(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
    ):
        new_key_b64 = base64.b64encode(b"\x66" * 32).decode()
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", new_key_b64])
        assert result.exit_code == 0
        assert "0 values re-encrypted" in result.output

    def test_rotate_key_from_stdin(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_encrypted_rows,
        monkeypatch,
    ):
        new_key = b"\x88" * 32
        new_key_b64 = base64.b64encode(new_key).decode()
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--from-stdin"], input=new_key_b64 + "\n"
        )
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.output

        from openlia_server.db.session import SessionLocal

        with SessionLocal() as s:
            llm = s.execute(select(LLMProvider)).scalar_one()
            assert (
                crypto.decrypt_with_key(new_key, "llm_1", llm.api_key_encrypted) == "sk-llm-secret"
            )

    def test_rotate_key_from_stdin_empty(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_encrypted_rows,
    ):
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--from-stdin"], input="")
        assert result.exit_code == 1
        assert "no key read from stdin" in result.output

    def test_rotate_key_rejects_both_flags(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_encrypted_rows,
    ):
        new_key_b64 = base64.b64encode(b"\x99" * 32).decode()
        result = cli_runner.invoke(
            app,
            ["secrets", "rotate-key", "--new-key", new_key_b64, "--from-stdin"],
            input=new_key_b64 + "\n",
        )
        assert result.exit_code == 1
        assert "use either --new-key or --from-stdin" in result.output
