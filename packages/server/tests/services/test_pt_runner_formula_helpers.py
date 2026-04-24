import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner


@dataclass
class _FakeDispatcher:
    payloads: dict[tuple[str, str], Any]

    def fetch(
        self,
        *,
        requirement: str,
        panel_id: str,
        params: dict[str, Any],
    ) -> Any:
        return self.payloads.get((panel_id, requirement))


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


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="t@x",
        display_name="U",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_test_formula_reads_cache(db_session, user):
    PtConfigService(session_factory=lambda: db_session).get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    runner.compute_dashboard(user.id)

    result = runner.test_formula(user.id, "oil", "price > 50", params_override={})
    assert result.value is True
    assert result.resolved_values["price"] > 50


def test_preview_ruleset_reads_cache(db_session, user):
    PtConfigService(session_factory=lambda: db_session).get_or_create_for_user(user.id)
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    runner.compute_dashboard(user.id)

    preview = runner.preview_ruleset(
        user.id,
        "oil",
        {
            "rules": [
                {"status": "red", "formula": "price > 50", "label": "hit"},
                {"status": "green", "formula": "true", "label": "miss"},
            ],
            "params": {},
            "streak_condition": None,
        },
    )
    assert preview.status == "red"
    assert preview.label == "hit"


def test_test_formula_without_cache_raises(db_session, user):
    runner = PtRunner(
        session_factory=lambda: db_session,
        dispatcher=_dispatcher_with_oil_red(),
    )
    with pytest.raises(ValueError, match="no cached panel data"):
        runner.test_formula(user.id, "oil", "true", params_override={})
