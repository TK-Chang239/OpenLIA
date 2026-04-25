"""Public API for the auth service package.

Re-exports the surface documented in
`planning/implementation-plans/2026-04-16-phase-2-auth-and-secrets.md`.
Internal callers may still reach into the submodules directly; this module
exists so external importers (CLI, future Phase 7 helpers, etc.) can write
`from openlia_server.services.auth import authenticate, ...` per the plan.
"""

from __future__ import annotations

from openlia_server.services.auth.errors import AuthError
from openlia_server.services.auth.events import log_auth_event
from openlia_server.services.auth.login import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticatedUser,
    InvalidCredentialsError,
    authenticate,
)
from openlia_server.services.auth.password_reset import (
    TokenExpiredError,
    TokenInvalidError,
    admin_direct_reset,
    approve_request,
    change_password,
    consume_token,
    reject_request,
    request_reset,
)
from openlia_server.services.auth.passwords import (
    WeakPasswordError,
    dummy_verify,
    hash_password,
    validate_password_policy,
    verify_password,
)
from openlia_server.services.auth.registration import (
    InviteInvalidError,
    InviteRequiredError,
    RegistrationFailedError,
    normalize_email,
    register,
)
from openlia_server.services.auth.sessions import (
    NON_PERSISTENT_TTL,
    PERSISTENT_TTL,
    CreatedSession,
    ValidatedSession,
    create_session,
    prune_expired,
    revoke_all_sessions,
    revoke_session,
    validate_session,
)
from openlia_server.services.auth.signup_policy import (
    EmailDomainNotAllowedError,
    SignupClosedError,
    assert_registration_open,
    check_email_allowed,
    get_policy,
    seed_signup_policy,
)
from openlia_server.services.auth.tokens import generate_opaque_token, hash_token

__all__ = [
    "NON_PERSISTENT_TTL",
    "PERSISTENT_TTL",
    "AccountDisabledError",
    "AccountLockedError",
    "AuthError",
    "AuthenticatedUser",
    "CreatedSession",
    "EmailDomainNotAllowedError",
    "InvalidCredentialsError",
    "InviteInvalidError",
    "InviteRequiredError",
    "RegistrationFailedError",
    "SignupClosedError",
    "TokenExpiredError",
    "TokenInvalidError",
    "ValidatedSession",
    "WeakPasswordError",
    "admin_direct_reset",
    "approve_request",
    "assert_registration_open",
    "authenticate",
    "change_password",
    "check_email_allowed",
    "consume_token",
    "create_session",
    "dummy_verify",
    "generate_opaque_token",
    "get_policy",
    "hash_password",
    "hash_token",
    "log_auth_event",
    "normalize_email",
    "prune_expired",
    "register",
    "reject_request",
    "request_reset",
    "revoke_all_sessions",
    "revoke_session",
    "seed_signup_policy",
    "validate_password_policy",
    "validate_session",
    "verify_password",
]
