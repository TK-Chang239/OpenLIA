"""NEW-4-38: End-to-end wizard Step 3 -> DB -> resolver round-trip.

Drives the wizard through `/setup/models` against an in-memory respx-mocked
Ollama backend, then asserts the persisted llm_providers + llm_models rows and
calls `resolve()` through `SQLModelRegistry`.
"""

from __future__ import annotations

from openlia.llm.resolver import resolve
from openlia.llm.types import ModelTier
from openlia_server.db.models.config import LLMModel, LLMProvider
from openlia_server.services.llm_registry import SQLModelRegistry


def test_wizard_models_post_persists_three_tiers_and_resolver_returns_thinking(
    wizard_personal_client, db_session, monkeypatch
) -> None:
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "0" * 43 + "=")

    # Bootstrap wizard cookie via /setup/mode.
    wizard_personal_client.post("/setup/mode", json={"mode": "personal"})

    payload = {
        "thinking": [
            {
                "provider": "ollama",
                "model": "llama3.1:70b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "everyday": [
            {
                "provider": "ollama",
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "quick": [
            {
                "provider": "ollama",
                "model": "qwen2.5:7b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
    }
    resp = wizard_personal_client.post("/setup/models", json=payload)
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    providers = db_session.query(LLMProvider).all()
    models = db_session.query(LLMModel).all()
    assert len(providers) == 3
    assert len(models) == 3
    refs = {m.model_ref for m in models}
    assert refs == {"llama3.1:70b", "llama3.1:8b", "qwen2.5:7b"}

    registry = SQLModelRegistry(db_session)
    resolved = resolve(
        department_id="equity_research",
        registry=registry,
        user_id=None,
    )
    assert resolved.tier == ModelTier.THINKING
    assert resolved.model_ref == "llama3.1:70b"
    assert resolved.provider_kind == "ollama"
