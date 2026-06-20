# packages/core/tests/test_system_roles.py
from openlia.llm.system_roles import (
    SYSTEM_ROLE_IDS,
    SystemRole,
    get_system_role_label,
)


def test_system_role_ids_contains_locked_set():
    assert SYSTEM_ROLE_IDS == (
        "connector_agentic_resolver",
        "connector_spec_adapter",
        "graph_extraction",
        "graph_summarization",
    )


def test_system_role_enum_matches_ids():
    assert {r.value for r in SystemRole} == set(SYSTEM_ROLE_IDS)


def test_get_system_role_label_returns_human_string():
    assert get_system_role_label("graph_extraction") == "Graph memory extraction"


def test_get_system_role_label_unknown_raises():
    import pytest

    with pytest.raises(KeyError):
        get_system_role_label("not_a_role")
