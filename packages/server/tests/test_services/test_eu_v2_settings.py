# packages/server/tests/test_services/test_eu_v2_settings.py
from openlia_server.services.eu_v2_settings import get_settings, update_settings


def test_get_returns_defaults_when_no_row(db_session):
    dto = get_settings(db_session, user_id="u-1")
    assert dto.enabled_provider_ids == frozenset({"eodhd"})
    assert dto.web_search_enabled is False
    assert dto.length == "normal"


def test_update_persists_and_returns(db_session):
    dto = update_settings(
        db_session,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="elaborative",
        reasoning_effort="medium",
        enabled_provider_ids=["eodhd"],
        web_search_enabled=True,
    )
    assert dto.web_search_enabled is True
    assert dto.length == "elaborative"
    # round-trips
    again = get_settings(db_session, user_id="u-1")
    assert again.enabled_provider_ids == frozenset({"eodhd"})
    assert again.reasoning_effort == "medium"


def test_update_round_trips_enabled_provider_ids(db_session):
    update_settings(
        db_session,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids={"eodhd", "alpha"},
        web_search_enabled=False,
    )
    again = get_settings(db_session, user_id="u-1")
    assert again.enabled_provider_ids == frozenset({"alpha", "eodhd"})


def test_instructions_id_defaults_to_none_without_row(db_session):
    dto = get_settings(db_session, user_id="u-1")
    assert dto.instructions_id is None


def test_batch_enabled_defaults_false_without_row(db_session):
    dto = get_settings(db_session, user_id="nobody")
    assert dto.batch_enabled is False


def test_update_persists_batch_enabled(db_session):
    dto = update_settings(
        db_session,
        user_id="u-1",
        provider_kind="openai",
        model="gpt-5.4-2026-03-05",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=False,
        instructions_id=None,
        batch_enabled=True,
    )
    assert dto.batch_enabled is True
    again = get_settings(db_session, user_id="u-1")
    assert again.batch_enabled is True


def test_update_persists_instructions_id(db_session):
    update_settings(
        db_session,
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=False,
        instructions_id="abc123",
    )
    again = get_settings(db_session, user_id="u-1")
    assert again.instructions_id == "abc123"
