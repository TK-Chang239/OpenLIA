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


class TestEncryptDecryptWithKey:
    def test_roundtrip(self) -> None:
        key = b"\x00" * 32
        ciphertext = crypto.encrypt_with_key(key, "row-1", "hello")
        assert crypto.decrypt_with_key(key, "row-1", ciphertext) == "hello"

    def test_different_keys_do_not_decrypt(self) -> None:
        key_a = b"\x00" * 32
        key_b = b"\xff" * 32
        ciphertext = crypto.encrypt_with_key(key_a, "row-1", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_with_key(key_b, "row-1", ciphertext)

    def test_aad_binds_to_row_id(self) -> None:
        key = b"\x00" * 32
        ciphertext = crypto.encrypt_with_key(key, "correct-row", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_with_key(key, "other-row", ciphertext)

    def test_fresh_nonce_each_call(self) -> None:
        key = b"\x00" * 32
        a = crypto.encrypt_with_key(key, "row", "same")
        b = crypto.encrypt_with_key(key, "row", "same")
        assert a != b

    def test_rejects_non_32_byte_key(self) -> None:
        short_key = b"\x00" * 16
        with pytest.raises(crypto.SecretKeyError):
            crypto.encrypt_with_key(short_key, "row", "hello")
        with pytest.raises(crypto.SecretKeyError):
            crypto.decrypt_with_key(short_key, "row", "ignored")


class TestRotateKeyCLI:
    """End-to-end round-trip across all three encrypted-key tables.

    Phase 2 fix-plan P2-02-03 — the rotation CLI was previously only covered
    in `test_cli_secrets.py::TestRotateKey`; this suite freezes the contract
    that *this* file (the natural home for crypto rotation tests) exercises
    the full LLMProvider/DataProvider/WebSearchProvider triple.
    """

    @pytest.fixture
    def seeded_rows(self, cli_session, cli_secret_key):
        old = cli_secret_key
        cli_session.add_all(
            [
                LLMProvider(
                    id="llm-1",
                    kind="openai",
                    label="OpenAI",
                    api_key_encrypted=crypto.encrypt_with_key(old, "llm-1", "sk-llm"),
                ),
                DataProvider(
                    id="data-1",
                    kind="eodhd",
                    label="EODHD",
                    api_key_encrypted=crypto.encrypt_with_key(old, "data-1", "eodhd"),
                ),
                WebSearchProvider(
                    id="ws-1",
                    kind="brave",
                    label="Brave",
                    api_key_encrypted=crypto.encrypt_with_key(old, "ws-1", "brave"),
                ),
            ]
        )
        cli_session.commit()

    def test_rotate_round_trip_all_three_tables(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_rows,
        monkeypatch,
    ):
        new_key = b"\x77" * 32
        new_key_b64 = base64.b64encode(new_key).decode()

        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", new_key_b64])
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.output

        # Decrypt every row with the new key.
        from openlia_server.db.session import SessionLocal

        with SessionLocal() as s:
            llm = s.execute(select(LLMProvider)).scalar_one()
            data = s.execute(select(DataProvider)).scalar_one()
            ws = s.execute(select(WebSearchProvider)).scalar_one()
            assert crypto.decrypt_with_key(new_key, "llm-1", llm.api_key_encrypted) == "sk-llm"
            assert crypto.decrypt_with_key(new_key, "data-1", data.api_key_encrypted) == "eodhd"
            assert crypto.decrypt_with_key(new_key, "ws-1", ws.api_key_encrypted) == "brave"

    def test_rotate_rejects_same_key(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_rows,
    ):
        same_b64 = base64.b64encode(cli_secret_key).decode()
        result = cli_runner.invoke(app, ["secrets", "rotate-key", "--new-key", same_b64])
        assert result.exit_code == 1
        assert "new key must differ from the current key" in result.output
