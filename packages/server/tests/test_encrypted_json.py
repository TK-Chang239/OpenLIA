"""Tests for the EncryptedJSON TypeDecorator (bind/result round-trip)."""
from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from openlia_server.db import secrets_crypto as sc
from openlia_server.db.base import EncryptedJSON


@pytest.fixture(autouse=True)
def _key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_bind_produces_ciphertext_not_plaintext():
    col = EncryptedJSON()
    stored = col.process_bind_param({"API_KEY": "super-secret-value"}, dialect=None)
    assert isinstance(stored, str)
    assert "super-secret-value" not in stored
    assert "API_KEY" not in stored


def test_result_decrypts_back_to_dict():
    col = EncryptedJSON()
    stored = col.process_bind_param({"K": "v"}, dialect=None)
    assert col.process_result_value(stored, dialect=None) == {"K": "v"}


def test_none_binds_none_and_reads_empty_dict():
    col = EncryptedJSON()
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) == {}
    assert col.process_result_value("", dialect=None) == {}


def test_result_tolerates_legacy_plaintext_json():
    col = EncryptedJSON()
    legacy = json.dumps({"OLD": "plaintext"})
    assert col.process_result_value(legacy, dialect=None) == {"OLD": "plaintext"}


def test_result_with_wrong_key_raises_decrypt_error(monkeypatch):
    col = EncryptedJSON()
    stored = col.process_bind_param({"K": "v"}, dialect=None)
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    sc.reset_cache()
    with pytest.raises(sc.SecretDecryptError):
        col.process_result_value(stored, dialect=None)
