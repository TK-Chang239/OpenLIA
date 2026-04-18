"""Tests for services.auth.passwords — Argon2id hashing + dummy verify."""

from __future__ import annotations

import time

import pytest
from openlia_server.services.auth import passwords


class TestHashAndVerify:
    def test_hash_is_argon2id(self):
        hashed = passwords.hash_password("correct horse battery staple")
        assert hashed.startswith("$argon2id$")

    def test_verify_matches(self):
        hashed = passwords.hash_password("pw")
        assert passwords.verify_password(hashed, "pw") is True

    def test_verify_rejects_wrong_password(self):
        hashed = passwords.hash_password("pw")
        assert passwords.verify_password(hashed, "nope") is False

    def test_verify_rejects_none_hash(self):
        assert passwords.verify_password(None, "anything") is False

    def test_dummy_verify_returns_false_in_roughly_same_time(self):
        real_hash = passwords.hash_password("pw")
        t0 = time.perf_counter()
        passwords.verify_password(real_hash, "wrong")
        real_elapsed = time.perf_counter() - t0

        t0 = time.perf_counter()
        passwords.dummy_verify()
        dummy_elapsed = time.perf_counter() - t0
        assert 0.25 * real_elapsed < dummy_elapsed < 4.0 * real_elapsed


class TestPolicy:
    def test_min_length_default_8(self, monkeypatch):
        monkeypatch.delenv("OPENLIA_PASSWORD_MIN_LENGTH", raising=False)
        passwords.validate_password_policy("12345678")
        with pytest.raises(passwords.WeakPasswordError):
            passwords.validate_password_policy("short")

    def test_min_length_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENLIA_PASSWORD_MIN_LENGTH", "12")
        with pytest.raises(passwords.WeakPasswordError):
            passwords.validate_password_policy("eleven-char")
        passwords.validate_password_policy("twelve-chars")
