"""Smoke test for openlia_server.services.auth public API.

The plan re-exports its public surface from `services/auth/__init__.py` so
external callers can write `from openlia_server.services.auth import ...`.
This test freezes that contract.
"""

from __future__ import annotations


def test_public_api_imports() -> None:
    from openlia_server.services.auth import (
        AuthError,
        authenticate,
        change_password,
        consume_token,
        create_session,
        hash_password,
        hash_token,
        log_auth_event,
        register,
        request_reset,
        revoke_session,
        seed_signup_policy,
        validate_session,
    )

    assert callable(authenticate)
    assert callable(change_password)
    assert callable(consume_token)
    assert callable(create_session)
    assert callable(hash_password)
    assert callable(hash_token)
    assert callable(log_auth_event)
    assert callable(register)
    assert callable(request_reset)
    assert callable(revoke_session)
    assert callable(seed_signup_policy)
    assert callable(validate_session)
    assert issubclass(AuthError, Exception)
