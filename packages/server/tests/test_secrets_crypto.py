"""Tests for connector secret key resolution + Fernet encrypt/decrypt."""
from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from openlia_server.db import secrets_crypto as sc


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    # Isolate every test: clean env + a temp OPENLIA_HOME + fresh cipher cache.
    monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
    monkeypatch.delenv("OPENLIA_MODE", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_round_trip_with_env_key(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    token = sc.encrypt("hello")
    assert token != "hello"
    assert sc.decrypt(token) == "hello"


def test_personal_mode_autogenerates_key_file(tmp_path):
    # No env key, default (personal) mode -> a key file is created chmod 600.
    token = sc.encrypt("secret")
    key_file = tmp_path / sc.KEY_FILENAME
    assert key_file.exists()
    assert (key_file.stat().st_mode & 0o777) == 0o600
    assert sc.decrypt(token) == "secret"


def test_company_mode_without_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    with pytest.raises(sc.SecretKeyMissingError):
        sc.ensure_key_available()


def test_invalid_env_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "not-a-valid-fernet-key")
    with pytest.raises(sc.SecretKeyInvalidError):
        sc.ensure_key_available()


def test_decrypt_with_wrong_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    token = sc.encrypt("hello")
    # Swap to a different key and try to decrypt the old token.
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    sc.reset_cache()
    with pytest.raises(sc.SecretDecryptError):
        sc.decrypt(token)
