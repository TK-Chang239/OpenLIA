from __future__ import annotations

import pytest
from openlia_server.db import crypto


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
