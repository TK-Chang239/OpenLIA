"""Singleton signup policy row + enforcement helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import SignupPolicy
from openlia_server.services.auth.errors import AuthError


class SignupClosedError(AuthError):
    code = "signup_closed"


class EmailDomainNotAllowedError(AuthError):
    code = "email_domain_not_allowed"


def seed_signup_policy(db: DBSession, *, mode_flag: Literal["personal", "company"]) -> None:
    """Insert the singleton row if absent. Idempotent — never overwrites."""
    existing = db.execute(select(SignupPolicy).where(SignupPolicy.id == 1)).scalar_one_or_none()
    if existing is not None:
        return

    policy_mode = "closed" if mode_flag == "personal" else "invite_only"
    db.add(
        SignupPolicy(
            id=1,
            mode=policy_mode,
            allowed_email_domains=[],
            updated_at=datetime.now(UTC),
        )
    )
    db.commit()


def get_policy(db: DBSession) -> SignupPolicy:
    row = db.execute(select(SignupPolicy).where(SignupPolicy.id == 1)).scalar_one_or_none()
    if row is None:
        raise RuntimeError("signup_policy row is missing; bootstrap did not run")
    return row


def check_email_allowed(db: DBSession, email: str) -> None:
    policy = get_policy(db)
    domains: list[str] = policy.allowed_email_domains or []
    if not domains:
        return
    _, _, domain = email.partition("@")
    if domain.lower() not in {d.lower() for d in domains}:
        raise EmailDomainNotAllowedError(f"Email domain '{domain}' is not in the allowlist.")


def assert_registration_open(db: DBSession) -> None:
    policy = get_policy(db)
    if policy.mode == "closed":
        raise SignupClosedError("Registration is closed.")
