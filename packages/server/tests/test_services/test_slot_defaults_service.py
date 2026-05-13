from __future__ import annotations

import pytest
from openlia_server.services.slot_defaults import (
    InvalidSlotError,
    SlotDefaultsService,
    delete_slot_default,
    get_slot_default_model_id,
    list_slot_defaults,
    set_slot_default,
)


def test_set_then_get_department_slot(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=model.id)
    assert get_slot_default_model_id(db_session, "department", "secretary") == model.id


def test_set_then_get_system_role_slot(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(db_session, slot_kind="system_role", slot_id="ai_review", model_id=model.id)
    assert get_slot_default_model_id(db_session, "system_role", "ai_review") == model.id


def test_set_overwrites_existing(db_session, llm_model_factory):
    m1 = llm_model_factory()
    m2 = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m1.id)
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m2.id)
    assert get_slot_default_model_id(db_session, "department", "secretary") == m2.id


def test_invalid_slot_kind_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(db_session, slot_kind="bogus", slot_id="x", model_id=model.id)


def test_invalid_department_slot_id_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(
            db_session,
            slot_kind="department",
            slot_id="not_a_dept",
            model_id=model.id,
        )


def test_invalid_system_role_slot_id_raises(db_session, llm_model_factory):
    model = llm_model_factory()
    with pytest.raises(InvalidSlotError):
        set_slot_default(db_session, slot_kind="system_role", slot_id="ghost", model_id=model.id)


def test_delete_removes_row(db_session, llm_model_factory):
    model = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=model.id)
    delete_slot_default(db_session, slot_kind="department", slot_id="secretary")
    assert get_slot_default_model_id(db_session, "department", "secretary") is None


def test_list_returns_all_defaults(db_session, llm_model_factory):
    m1 = llm_model_factory()
    m2 = llm_model_factory()
    set_slot_default(db_session, slot_kind="department", slot_id="secretary", model_id=m1.id)
    set_slot_default(db_session, slot_kind="system_role", slot_id="ai_review", model_id=m2.id)
    rows = list_slot_defaults(db_session)
    assert len(rows) == 2
    by_kv = {(r.slot_kind, r.slot_id): r.model_id for r in rows}
    assert by_kv == {
        ("department", "secretary"): m1.id,
        ("system_role", "ai_review"): m2.id,
    }


def test_service_class_wraps_functions(db_session, llm_model_factory):
    model = llm_model_factory()
    svc = SlotDefaultsService(db_session)
    svc.set("department", "secretary", model.id)
    assert svc.get("department", "secretary") == model.id
    rows = svc.list_all()
    assert len(rows) == 1
    svc.delete("department", "secretary")
    assert svc.get("department", "secretary") is None
