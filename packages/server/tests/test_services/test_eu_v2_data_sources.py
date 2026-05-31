# packages/server/tests/test_services/test_eu_v2_data_sources.py
from datetime import UTC, datetime

from openlia_server.db.models.auth import User
from openlia_server.db.models.connectors import Connector
from openlia_server.services import eu_v2_data_sources, eu_v2_settings


def _add_user(db):
    now = datetime.now(UTC)
    db.add(
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
    db.flush()


def _set_settings(db, *, provider_kind, model, enabled_provider_ids, web_search_enabled):
    eu_v2_settings.update_settings(
        db,
        user_id="local",
        provider_kind=provider_kind,
        model=model,
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=enabled_provider_ids,
        web_search_enabled=web_search_enabled,
    )


def _validated(provider_id, *, category, display_name):
    return Connector(
        id=f"c-{provider_id}",
        provider_id=provider_id,
        source="built_in",
        category=category,
        launch={},
        secrets={},
        status="validated",
        display_name=display_name,
    )


def _by_key(ds):
    return {s.key: s for s in ds.sources}


def test_dynamic_registry_driven_sources(monkeypatch, db_session):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    _add_user(db_session)
    db_session.add_all(
        [
            _validated("eodhd", category="financial", display_name="EODHD-row"),
            _validated("newsapi_ai", category="news", display_name="News API"),
            _validated("firecrawl", category="web_search", display_name="Firecrawl"),
            _validated("x", category="social", display_name="X"),
        ]
    )
    db_session.commit()
    _set_settings(
        db_session,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_provider_ids=["eodhd", "newsapi_ai"],
        web_search_enabled=True,
    )

    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    by_key = _by_key(ds)
    assert set(by_key) == {"eodhd", "newsapi_ai", "firecrawl", "x", "model_web_search"}

    eodhd = by_key["eodhd"]
    assert eodhd.display_name == "EODHD"
    assert eodhd.category == "financial"
    assert eodhd.routing == "curated"
    assert eodhd.available is True
    assert eodhd.enabled is True
    assert eodhd.unavailable_reason is None

    news = by_key["newsapi_ai"]
    assert news.routing == "dispatcher"
    assert news.available is True
    assert news.enabled is True
    assert news.category == "news"
    assert news.display_name == "News API"

    assert by_key["firecrawl"].routing == "dispatcher"
    assert by_key["firecrawl"].enabled is False
    assert by_key["x"].routing == "dispatcher"
    assert by_key["x"].enabled is False

    ws = by_key["model_web_search"]
    assert ws.display_name == "Web search"
    assert ws.category == "web_search"
    assert ws.routing == "model_native"
    assert ws.available is True
    assert ws.enabled is True
    assert ws.unavailable_reason is None


def test_removing_connector_drops_source(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _add_user(db_session)
    fmp = _validated("fmp", category="financial", display_name="FMP")
    db_session.add(fmp)
    db_session.commit()

    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert "fmp" in _by_key(ds)

    db_session.delete(fmp)
    db_session.commit()
    ds2 = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert "fmp" not in _by_key(ds2)


def test_eodhd_unavailable_without_key(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _add_user(db_session)
    db_session.commit()
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    eodhd = _by_key(ds)["eodhd"]
    assert eodhd.available is False
    assert eodhd.unavailable_reason == "eodhd_unconfigured"


def test_eodhd_available_via_connector_secret(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _add_user(db_session)
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
    eodhd = _by_key(ds)["eodhd"]
    assert eodhd.available is True
    assert eodhd.unavailable_reason is None
    # eodhd surfaces only once, as the curated slot (not also dispatcher).
    keys = [s.key for s in ds.sources]
    assert keys.count("eodhd") == 1


def test_web_search_follows_model_capability_and_settings(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _add_user(db_session)
    db_session.commit()

    yes = eu_v2_data_sources.compute_data_sources(
        db_session,
        user_id="local",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    ws_yes = _by_key(yes)["model_web_search"]
    assert ws_yes.available is True

    no = eu_v2_data_sources.compute_data_sources(
        db_session,
        user_id="local",
        provider_kind="anthropic",
        model="claude-haiku-4-5-20251001",
    )
    ws_no = _by_key(no)["model_web_search"]
    assert ws_no.available is False
    assert ws_no.unavailable_reason == "model_no_web_search"


def test_web_search_enabled_from_persisted_settings(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    _add_user(db_session)
    db_session.flush()
    _set_settings(
        db_session,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_provider_ids=["eodhd"],
        web_search_enabled=False,
    )
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    ws = _by_key(ds)["model_web_search"]
    assert ws.available is True
    assert ws.enabled is False
