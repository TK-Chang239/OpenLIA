"""Tests for db.crypto — AES-256-GCM key loading and column encryption."""

from __future__ import annotations

import base64
import stat

import pytest
from openlia_server.db import crypto


@pytest.fixture(autouse=True)
def _reset_key_cache():
    """Ensure every test starts with a fresh module-level key cache."""
    crypto._reset_cached_key()
    yield
    crypto._reset_cached_key()


class TestLoadSecretKey:
    def test_env_var_preferred_over_file(self, tmp_path, monkeypatch):
        raw = b"\x01" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        key_file = tmp_path / "secret.key"
        key_file.write_bytes(base64.b64encode(b"\x02" * 32))
        key_file.chmod(0o600)

        assert crypto.load_secret_key() == raw

    def test_env_var_rejects_wrong_length(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(b"short").decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        with pytest.raises(crypto.SecretKeyError, match="32 bytes"):
            crypto.load_secret_key()

    def test_file_fallback_generates_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        tmp_path.chmod(0o700)

        key = crypto.load_secret_key()
        assert len(key) == 32

        key_file = tmp_path / "secret.key"
        assert key_file.exists()
        mode = stat.S_IMODE(key_file.stat().st_mode)
        assert mode == 0o600

    def test_file_fallback_rejects_loose_permissions(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        tmp_path.chmod(0o700)
        key_file = tmp_path / "secret.key"
        key_file.write_bytes(base64.b64encode(b"\x03" * 32))
        key_file.chmod(0o644)

        with pytest.raises(crypto.SecretKeyError, match="0600"):
            crypto.load_secret_key()

    def test_cached_after_first_call(self, tmp_path, monkeypatch):
        raw = b"\x04" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

        first = crypto.load_secret_key()
        monkeypatch.delenv("OPENLIA_SECRET_KEY")
        second = crypto.load_secret_key()
        assert first is second


class TestEncryptDecrypt:
    @pytest.fixture
    def setup_key(self, tmp_path, monkeypatch):
        import base64

        raw = b"\x09" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

    def test_roundtrip(self, setup_key):
        row_id = "llm-provider-abc"
        plaintext = "sk-example-api-key"
        ciphertext = crypto.encrypt_for_row(row_id, plaintext)
        assert ciphertext != plaintext
        assert crypto.decrypt_for_row(row_id, ciphertext) == plaintext

    def test_ciphertext_is_base64(self, setup_key):
        import base64

        ciphertext = crypto.encrypt_for_row("id-1", "secret")
        raw = base64.b64decode(ciphertext, validate=True)
        assert len(raw) >= 12 + 16

    def test_different_nonces_each_call(self, setup_key):
        ct1 = crypto.encrypt_for_row("id-1", "same plaintext")
        ct2 = crypto.encrypt_for_row("id-1", "same plaintext")
        assert ct1 != ct2

    def test_aad_binds_to_row_id(self, setup_key):
        ciphertext = crypto.encrypt_for_row("correct-row", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_for_row("different-row", ciphertext)

    def test_tampered_ciphertext_rejected(self, setup_key):
        import base64

        ciphertext = crypto.encrypt_for_row("id-1", "hello")
        raw = bytearray(base64.b64decode(ciphertext))
        raw[-1] ^= 0x01
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_for_row("id-1", tampered)

    def test_empty_plaintext_roundtrips(self, setup_key):
        assert crypto.decrypt_for_row("id-1", crypto.encrypt_for_row("id-1", "")) == ""
