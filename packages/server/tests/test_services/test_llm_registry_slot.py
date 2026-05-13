from __future__ import annotations

from openlia_server.services.llm_registry import SQLModelRegistry


def test_get_department_slot_default_returns_row(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default

    m = llm_model_factory()
    set_slot_default(
        db_session, slot_kind="department", slot_id="secretary", model_id=m.id
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_department_slot_default("secretary")
    assert row is not None
    assert row.model_id == m.id


def test_get_system_role_default_returns_row(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default

    m = llm_model_factory()
    set_slot_default(
        db_session, slot_kind="system_role", slot_id="ai_review", model_id=m.id
    )
    reg = SQLModelRegistry(db_session)
    row = reg.get_system_role_default("ai_review")
    assert row is not None
    assert row.model_id == m.id


def test_registry_no_longer_exposes_tier_methods(db_session):
    reg = SQLModelRegistry(db_session)
    assert not hasattr(reg, "get_tier_default")
    assert not hasattr(reg, "get_any_in_tier")
    assert not hasattr(reg, "get_user_preference")
    assert not hasattr(reg, "get_department_tier_override")


def test_get_by_id_returns_row(db_session, llm_model_factory):
    m = llm_model_factory()
    reg = SQLModelRegistry(db_session)
    row = reg.get_by_id(m.id)
    assert row is not None
    assert row.model_id == m.id


def test_get_by_id_returns_none_for_unknown(db_session):
    reg = SQLModelRegistry(db_session)
    assert reg.get_by_id("does-not-exist") is None
