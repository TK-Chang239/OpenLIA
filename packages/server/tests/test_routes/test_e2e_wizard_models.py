"""NEW-4-38: End-to-end wizard Step 3 -> DB round-trip.

Drives the wizard through `/setup/models` and asserts the persisted
llm_providers + llm_models rows plus the wired slot_defaults entries.
"""

from __future__ import annotations

from openlia.departments import get_registered_department_ids
from openlia.llm.system_roles import SYSTEM_ROLE_IDS
from openlia_server.db.models.config import LLMModel, LLMProvider, LLMSlotDefault


def test_wizard_models_post_persists_models_and_slot_defaults(
    wizard_personal_client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")

    # Bootstrap wizard cookie via /setup/mode.
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})

    dept_ids = get_registered_department_ids()
    role_ids = list(SYSTEM_ROLE_IDS)
    payload = {
        "models": [
            {
                "provider_kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ref": "llama3.1:70b",
                "display_name": "Llama 3.1 70B",
            },
            {
                "provider_kind": "ollama",
                "base_url": "http://localhost:11434",
                "model_ref": "llama3.1:8b",
                "display_name": "Llama 3.1 8B",
            },
        ],
        "department_defaults": {dept_id: "llama3.1:70b" for dept_id in dept_ids},
        "system_role_defaults": {role_id: "llama3.1:8b" for role_id in role_ids},
    }
    resp = wizard_personal_client.post("/setup/models", json=payload)
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    providers = db_session.query(LLMProvider).all()
    models = db_session.query(LLMModel).all()
    assert len(providers) == 1  # single (kind, api_key, base_url, env) tuple
    assert len(models) == 2
    refs = {m.model_ref for m in models}
    assert refs == {"llama3.1:70b", "llama3.1:8b"}

    # Slot defaults are wired for every department + system role we sent.
    slot_rows = db_session.query(LLMSlotDefault).all()
    by_slot = {(r.slot_kind, r.slot_id): r.model_id for r in slot_rows}
    model_by_ref = {m.model_ref: m.id for m in models}
    for dept_id in dept_ids:
        assert by_slot[("department", dept_id)] == model_by_ref["llama3.1:70b"]
    for role_id in role_ids:
        assert by_slot[("system_role", role_id)] == model_by_ref["llama3.1:8b"]
