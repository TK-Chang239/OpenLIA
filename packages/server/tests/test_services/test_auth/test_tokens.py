"""Tests for services.auth.tokens — opaque token generation + hashing."""

from __future__ import annotations

from openlia_server.services.auth import tokens


class TestGenerateToken:
    def test_length_is_urlsafe_base64_of_32_bytes(self):
        token = tokens.generate_opaque_token()
        assert 42 <= len(token) <= 43
        assert token.replace("-", "").replace("_", "").isalnum()

    def test_tokens_are_unique(self):
        seen = {tokens.generate_opaque_token() for _ in range(100)}
        assert len(seen) == 100

    def test_hash_is_hex_sha256(self):
        h = tokens.hash_token("abc")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_deterministic(self):
        assert tokens.hash_token("abc") == tokens.hash_token("abc")

    def test_hash_different_for_different_input(self):
        assert tokens.hash_token("abc") != tokens.hash_token("abd")
