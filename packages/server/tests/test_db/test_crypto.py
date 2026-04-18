"""Tests for db.crypto — AES-256-GCM key loading and column encryption."""
from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

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
