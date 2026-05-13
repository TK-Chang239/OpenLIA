"""Phase 1a P1-1a-01 — verify spec-mandated CHECK constraints are present
and rejecting at the DB level."""

from __future__ import annotations

import pytest
from openlia_server.db.base import Base
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def test_named_check_constraints_present() -> None:
    """Each of the conservative-slice CHECKs is registered on Base.metadata."""
    import openlia_server.db.models.register_all  # noqa: F401

    # Naming convention is `ck_%(table_name)s_%(constraint_name)s`.
    expected: dict[str, set[str]] = {
        "users": {"ck_users_failed_login_attempts_nonneg"},
        "signup_policy": {"ck_signup_policy_mode_enum"},
        "wizard_state": {"ck_wizard_state_status_enum"},
        "llm_slot_defaults": {"ck_llm_slot_defaults_slot_kind"},
    }
    for table_name, want in expected.items():
        constraints = Base.metadata.tables[table_name].constraints
        names = {c.name for c in constraints if c.name}
        assert want.issubset(names), f"{table_name} missing CHECK names: want={want}, have={names}"


def test_signup_policy_mode_rejects_unknown(create_tables, db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO signup_policy (id, mode, allowed_email_domains, updated_at) "
                "VALUES (1, 'wide_open', '[]', datetime('now'))"
            )
        )
        db_session.flush()


def test_wizard_state_status_rejects_unknown(create_tables, db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO wizard_state (id, status, current_step, completed_steps, "
                "step_data) VALUES (1, 'oops', 'mode', '[]', '{}')"
            )
        )
        db_session.flush()


def test_users_failed_login_rejects_negative(create_tables, db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO users (id, email, display_name, is_admin, is_disabled, "
                "must_change_password, failed_login_attempts, created_at, updated_at) "
                "VALUES ('u-neg', 'n@x', 'N', 0, 0, 0, -1, datetime('now'), datetime('now'))"
            )
        )
        db_session.flush()


def test_llm_slot_defaults_slot_kind_rejects_unknown(create_tables, db_session: Session) -> None:
    db_session.execute(
        text(
            "INSERT INTO llm_providers (id, kind, label, is_enabled, created_at, updated_at) "
            "VALUES ('p1', 'openai', 'OAI', 1, datetime('now'), datetime('now'))"
        )
    )
    db_session.execute(
        text(
            "INSERT INTO llm_models (id, provider_id, model_ref, display_name, "
            "is_enabled, created_at, updated_at) "
            "VALUES ('m1', 'p1', 'gpt-x', 'X', 1, "
            "datetime('now'), datetime('now'))"
        )
    )
    db_session.flush()
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO llm_slot_defaults (slot_kind, slot_id, model_id, updated_at) "
                "VALUES ('bogus', 'secretary', 'm1', datetime('now'))"
            )
        )
        db_session.flush()
