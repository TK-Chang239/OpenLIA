import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import DashboardPayload, PtRunner


@dataclass
class _FakeDispatcher:
    """Minimal stand-in for Plan 3 data adapter dispatcher."""

    payloads: dict[tuple[str, str], Any]

    def fetch(
        self,
        *,
        requirement: str,
        panel_id: str,
        params: dict[str, Any],
    ) -> Any:
        return self.payloads.get((panel_id, requirement))


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="r@x",
        display_name="U",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def _dispatcher_with_oil_red():
    history = [
        {
            "date": f"2026-03-{i:02d}",
            "open": 90.0,
            "high": 95.0,
            "low": 88.0,
            "close": 90.0 + i * 0.1,
            "volume": 0,
        }
        for i in range(1, 99)
    ]
    quote = {"price": 98.5, "previous_close": 97.9}
    return _FakeDispatcher(
        payloads={
            ("oil", "historical_prices"): history,
            ("oil", "stock_quote"): quote,
            ("inflation", "historical_prices"): [],
            ("inflation", "stock_quote"): None,
            ("inflation", "economic_events"): [],
            ("fed_language", "company_news"): [],
            ("fed_language", "economic_events"): [],
            ("wage_growth", "economic_events"): [],
            ("diplomacy", "company_news"): [],
        }
    )


def test_runner_returns_five_panels_and_composite(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg_svc.get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    payload = runner.compute_dashboard(user.id)
    assert isinstance(payload, DashboardPayload)
    assert set(payload.panels.keys()) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }
    assert payload.panels["oil"]["status"] in ("amber", "red", "dark_red")
    assert payload.composite["level"] in (
        "calm",
        "elevated",
        "high",
        "severe",
        "crisis",
    )


def test_runner_surfaces_series_params_and_full_scalars(db_session, user):
    # Phase B payload superset: the dashboard must carry the chart series
    # (raw_series), the effective thresholds (params), and the full panel
    # scalar readings (not a narrow whitelist) so the viewer can render real
    # data instead of the frozen static copy.
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg_svc.get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    payload = runner.compute_dashboard(user.id)

    oil = payload.panels["oil"]
    assert oil["raw_series"]["price"]  # non-empty price series feeds the chart
    assert oil["params"]["price_threshold"] == 85  # threshold for the UI

    # ``michigan_5y_missing`` is a panel scalar outside the old whitelist;
    # its presence proves the full scalar set is surfaced.
    inflation = payload.panels["inflation"]
    assert inflation["extras"]["michigan_5y_missing"] is True


def test_runner_disabled_panel_returns_disabled_status(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg = cfg_svc.get_or_create_for_user(user.id)
    pc = cfg.panel_config
    for entry in pc:
        if entry["panel_id"] == "oil":
            entry["enabled"] = False
    cfg_svc.update_config(user.id, panel_config=pc, composite_settings=cfg.composite_settings)

    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    payload = runner.compute_dashboard(user.id)
    assert payload.panels["oil"]["status"] == "disabled"


def test_level_transition_inserts_trigger_event(db_session, user):
    from openlia_server.db.models.dashboard import PtTriggerEvent
    from openlia_server.db.models.scheduler import UserNotification

    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg_svc.get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    runner.compute_dashboard(user.id)
    rows = db_session.query(PtTriggerEvent).filter_by(user_id=user.id).all()
    assert len(rows) == 1
    assert rows[0].level_from is None
    assert rows[0].level_to in {"calm", "elevated", "high", "severe", "crisis"}
    notifs = db_session.query(UserNotification).filter_by(user_id=user.id).all()
    assert any(n.type == "panic_level_change" for n in notifs)


def test_no_event_when_level_unchanged(db_session, user):
    from openlia_server.db.models.dashboard import PtTriggerEvent

    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg_svc.get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    runner.compute_dashboard(user.id)
    runner.compute_dashboard(user.id)
    rows = db_session.query(PtTriggerEvent).filter_by(user_id=user.id).all()
    assert len(rows) == 1


def test_runner_manual_override_short_circuits_rule_evaluation(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg = cfg_svc.get_or_create_for_user(user.id)
    for entry in cfg.panel_config:
        if entry["panel_id"] == "fed_language":
            entry["manual_override"] = {
                "status": "red",
                "note": "forced",
                "set_at": "2026-04-23T00:00:00Z",
            }
    cfg_svc.update_config(
        user.id,
        panel_config=cfg.panel_config,
        composite_settings=cfg.composite_settings,
    )
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    payload = runner.compute_dashboard(user.id)
    assert payload.panels["fed_language"]["status"] == "red"
    assert payload.panels["fed_language"]["label"].startswith("Manual override")
