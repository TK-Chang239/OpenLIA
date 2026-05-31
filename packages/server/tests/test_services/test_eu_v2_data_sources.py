# packages/server/tests/test_services/test_eu_v2_data_sources.py
from datetime import UTC, datetime

from openlia_server.db.models.auth import User
from openlia_server.db.models.connectors import Connector
from openlia_server.services import eu_v2_data_sources, eu_v2_settings


def _set_model(db, *, provider_kind, model):
    eu_v2_settings.update_settings(
        db,
        user_id="local",
        provider_kind=provider_kind,
        model=model,
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=["eodhd"],
        web_search_enabled=True,
    )


def test_financial_available_with_env(monkeypatch, db_session):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is True
    assert ds.financial.provider_label == "EODHD"
    assert ds.earnings_calendar.available is True
    assert ds.financial.unavailable_reason is None


def test_financial_unavailable_without_eodhd(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is False
    assert ds.financial.provider_label is None
    assert ds.financial.unavailable_reason == "eodhd_unconfigured"
    assert ds.earnings_calendar.unavailable_reason == "eodhd_unconfigured"


def test_financial_available_via_connector(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db"},
            status="validated",
        )
    )
    db_session.commit()
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is True


def test_web_search_follows_model_capability(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    yes = eu_v2_data_sources.compute_data_sources(
        db_session,
        user_id="local",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    assert yes.web_search.available is True
    assert yes.web_search.provider_label == "claude-sonnet-4-6"
    no = eu_v2_data_sources.compute_data_sources(
        db_session,
        user_id="local",
        provider_kind="anthropic",
        model="claude-haiku-4-5-20251001",
    )
    assert no.web_search.available is False
    assert no.web_search.unavailable_reason == "model_no_web_search"


def test_other_connectors_excludes_eodhd_lists_rest(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add_all(
        [
            Connector(
                id="c-eodhd",
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={},
                secrets={},
                status="validated",
            ),
            Connector(
                id="c-fmp",
                provider_id="fmp",
                source="built_in",
                category="financial",
                launch={},
                secrets={},
                status="validated",
                display_name="FMP",
            ),
            Connector(
                id="c-news",
                provider_id="newsapi_ai",
                source="built_in",
                category="news",
                launch={},
                secrets={},
                status="pending",
                display_name="News",
            ),
        ]
    )
    db_session.commit()
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    names = {c.display_name for c in ds.other_connectors}
    assert names == {"FMP"}  # eodhd excluded; pending news excluded


def test_web_search_uses_persisted_model_without_override(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    now = datetime.now(UTC)
    db_session.add(
        User(
            id="local",
            email="local@test.example",
            display_name="local",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.flush()
    _set_model(db_session, provider_kind="anthropic", model="claude-haiku-4-5-20251001")
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.web_search.available is False
    assert ds.web_search.unavailable_reason == "model_no_web_search"
