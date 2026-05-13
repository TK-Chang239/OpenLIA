import pytest
from openlia_server.services.adapter_llm_client import (
    AdapterLlmNotConfigured,
    _resolve_provider_for_role,
)


def test_resolve_for_role_returns_provider(db_session, llm_model_factory):
    from openlia_server.services.slot_defaults import set_slot_default

    m = llm_model_factory()
    set_slot_default(
        db_session,
        slot_kind="system_role",
        slot_id="graph_extraction",
        model_id=m.id,
    )
    provider = _resolve_provider_for_role(db_session, "graph_extraction")
    assert provider is not None


def test_resolve_for_role_raises_when_unset(db_session):
    with pytest.raises(AdapterLlmNotConfigured) as ei:
        _resolve_provider_for_role(db_session, "graph_extraction")
    assert "graph_extraction" in str(ei.value)
