# packages/server/tests/test_services/test_eu_v2_settings.py
from openlia_server.services.eu_v2_settings import get_settings, update_settings


def test_get_returns_defaults_when_no_row(db_session):
    dto = get_settings(db_session, user_id="u-1")
    assert dto.financial_enabled is True
    assert dto.calendar_enabled is True
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
        financial_enabled=False,
        calendar_enabled=True,
        web_search_enabled=True,
    )
    assert dto.web_search_enabled is True
    assert dto.length == "elaborative"
    # round-trips
    again = get_settings(db_session, user_id="u-1")
    assert again.financial_enabled is False
    assert again.reasoning_effort == "medium"
