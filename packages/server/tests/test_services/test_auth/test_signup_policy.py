"""Tests for services.auth.signup_policy — seeding + policy enforcement."""

from __future__ import annotations

import pytest
from openlia_server.db.models.auth import SignupPolicy
from openlia_server.services.auth import signup_policy
from openlia_server.services.auth.errors import AuthError
from sqlalchemy import select


def test_seed_personal_mode(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="personal")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.mode == "closed"


def test_seed_company_mode(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.mode == "invite_only"


def test_seed_is_idempotent(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    signup_policy.seed_signup_policy(db_session, mode_flag="personal")
    rows = list(db_session.execute(select(SignupPolicy)).scalars())
    assert len(rows) == 1
    assert rows[0].mode == "invite_only"


def test_check_email_allowed_no_restrictions(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    signup_policy.check_email_allowed(db_session, "anyone@any.tld")


def test_check_email_allowed_allowlist(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    row.allowed_email_domains = ["company.com"]
    db_session.commit()

    signup_policy.check_email_allowed(db_session, "ok@company.com")
    with pytest.raises(AuthError):
        signup_policy.check_email_allowed(db_session, "not@other.com")


def test_get_policy_returns_none_if_missing(db_session):
    assert signup_policy.get_policy(db_session) is None


def test_assert_registration_open_fails_closed_when_missing(db_session):
    with pytest.raises(signup_policy.SignupClosedError):
        signup_policy.assert_registration_open(db_session)
