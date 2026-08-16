"""EU v2 scheduled sync must honor an installed EODHD connector.

``build_eu_v2_transports`` reads ``EODHD_API_KEY`` from env only, so the
scheduled weekly calendar sync used to ignore a validated EODHD key
installed through the Connectors UI. ``EuV2CalendarSyncerImpl`` now resolves
the key from the sync's DB session (env first, then connector) and threads
it into the transports factory, matching the live route's
``build_eu_v2_transports(api_key=resolve_eodhd_api_key(db))``.
"""

from __future__ import annotations

from openlia_server.services.eu_v2_scheduler_impl import EuV2CalendarSyncerImpl
from openlia_server.services.eu_v2_wiring import (
    build_eu_v2_transports,
    resolve_eodhd_api_key,
)


def test_sync_all_threads_resolved_key_into_transports_factory() -> None:
    """The key resolved from the session is passed to the transports factory."""
    seen: dict[str, object] = {}
    sentinel_session = object()

    def fake_key_resolver(session: object) -> str | None:
        seen["session"] = session
        return "db-connector-key"

    def fake_transports_factory(api_key: str | None) -> object | None:
        seen["api_key"] = api_key
        return None  # short-circuits sync_all before touching the calendar

    syncer = EuV2CalendarSyncerImpl(
        transports_factory=fake_transports_factory,
        key_resolver=fake_key_resolver,
    )

    count = syncer.sync_all(session=sentinel_session)

    assert seen["session"] is sentinel_session
    assert seen["api_key"] == "db-connector-key"
    assert count == 0  # None transports => skipped, but the key was threaded


def test_sync_all_reaches_calendar_when_transports_resolved() -> None:
    """A non-None transports (built from the resolved key) drives the sync."""
    calls: list[str] = []

    class _FakeTransports:
        def earnings_calendar(self, ticker: str) -> list:  # pragma: no cover - unused
            return []

    def fake_transports_factory(api_key: str | None) -> object | None:
        calls.append(f"factory:{api_key}")
        return _FakeTransports()

    # sync_all_watchlists needs a DB session; patch it out — we only assert the
    # resolved key reached the factory and produced live transports.
    import openlia_server.services.eu_v2_scheduler_impl as mod

    original = mod.sync_all_watchlists
    try:
        mod.sync_all_watchlists = lambda *a, **k: 3  # type: ignore[assignment]
        syncer = EuV2CalendarSyncerImpl(
            transports_factory=fake_transports_factory,
            key_resolver=lambda _s: "resolved-key",
        )
        count = syncer.sync_all(session=object())
    finally:
        mod.sync_all_watchlists = original

    assert calls == ["factory:resolved-key"]
    assert count == 3


def test_default_wiring_uses_connector_aware_resolver() -> None:
    """Production construction (no injection) uses the env+connector resolver.

    ``app.py`` builds ``EuV2CalendarSyncerImpl()`` with defaults, so the
    connector-aware behavior only ships if the defaults are the real
    resolver + factory.
    """
    syncer = EuV2CalendarSyncerImpl()
    assert syncer._key_resolver is resolve_eodhd_api_key
    assert syncer._transports_factory is build_eu_v2_transports
