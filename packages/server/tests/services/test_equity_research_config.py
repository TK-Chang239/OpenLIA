import pytest
from openlia.reports.frameworks.loader import load_framework
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import ErUserConfig
from openlia_server.services.equity_research_config import (
    CustomSectionDTO,
    EquityResearchConfigService,
    ErConfigDTO,
)


@pytest.fixture
def user(db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    return "u1"


def test_get_config_creates_defaults_on_first_call(db_session, user):
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    assert isinstance(cfg, ErConfigDTO)
    assert cfg.report_mode == "stock_initiation"
    assert cfg.report_length == "normal"
    init_ids = {s["id"] for s in load_framework("stock_initiation")["sections"]}
    assert set(cfg.sections_by_mode["stock_initiation"]) == init_ids
    assert cfg.custom_sections_by_mode["stock_initiation"] == []
    assert cfg.custom_sections_by_mode["stock_update"] == []
    assert cfg.custom_sections_by_mode["sector_research"] == []


def test_get_config_idempotent(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    svc.get_config(user)
    assert db_session.query(ErUserConfig).count() == 1


def test_update_config_persists_mode_and_length(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(
        user,
        report_mode="stock_update",
        report_length="elaborative",
        sections_by_mode=None,
        custom_sections_by_mode=None,
    )
    assert updated.report_mode == "stock_update"
    assert updated.report_length == "elaborative"


def test_update_config_rejects_unknown_section_id(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    with pytest.raises(ValueError, match="unknown section"):
        svc.update_config(
            user,
            report_mode=None,
            report_length=None,
            sections_by_mode={"stock_update": ["does_not_exist"]},
            custom_sections_by_mode=None,
        )


def test_update_config_persists_custom_sections(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(
        user,
        report_mode=None,
        report_length=None,
        sections_by_mode=None,
        custom_sections_by_mode={
            "stock_update": [
                CustomSectionDTO(id="custom_esg_x1", title="ESG", description="note"),
            ],
            "stock_initiation": [],
            "sector_research": [],
        },
    )
    update_cs = updated.custom_sections_by_mode["stock_update"]
    assert len(update_cs) == 1
    assert update_cs[0].id == "custom_esg_x1"


def test_resolve_active_returns_sections_for_selected_mode(db_session, user):
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    active = svc.resolve_active(cfg, mode="stock_update")
    assert active.mode == "stock_update"
    assert active.report_length == "normal"
    expected_ids = {s["id"] for s in load_framework("stock_update")["sections"]}
    assert set(active.enabled_section_ids) == expected_ids
    assert active.custom_sections == ()


# ---------- Phase 5f: per-mode web_search budget overrides ----------


def test_get_config_defaults_web_search_budgets_by_mode_to_empty(db_session, user):
    """No row → defaults: no overrides recorded; ReportRunner falls back
    to the framework default."""
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    assert cfg.web_search_budgets_by_mode == {}


def test_update_config_persists_web_search_budgets_by_mode(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(
        user,
        web_search_budgets_by_mode={
            "stock_initiation": 12,
            "stock_update": 3,
        },
    )
    assert updated.web_search_budgets_by_mode == {
        "stock_initiation": 12,
        "stock_update": 3,
    }
    # Round-trip through DB.
    refreshed = svc.get_config(user)
    assert refreshed.web_search_budgets_by_mode == {
        "stock_initiation": 12,
        "stock_update": 3,
    }


def test_update_config_merges_web_search_budgets_partially(db_session, user):
    """A PUT that only sets one mode must leave the other modes' budgets
    intact — the patch is a merge, not a replacement."""
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    svc.update_config(
        user, web_search_budgets_by_mode={"stock_initiation": 10, "sector_research": 15}
    )
    svc.update_config(user, web_search_budgets_by_mode={"stock_update": 4})
    cfg = svc.get_config(user)
    assert cfg.web_search_budgets_by_mode == {
        "stock_initiation": 10,
        "sector_research": 15,
        "stock_update": 4,
    }


def test_update_config_rejects_unknown_mode_in_budget_map(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    with pytest.raises(ValueError, match="unknown mode"):
        svc.update_config(user, web_search_budgets_by_mode={"not_a_real_mode": 5})


def test_update_config_rejects_non_positive_budget(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    with pytest.raises(ValueError, match="positive"):
        svc.update_config(user, web_search_budgets_by_mode={"stock_initiation": 0})
    with pytest.raises(ValueError, match="positive"):
        svc.update_config(user, web_search_budgets_by_mode={"stock_initiation": -3})


def test_resolve_active_exposes_web_search_budget_for_mode(db_session, user):
    """The runner reads ``active.web_search_budget`` to populate
    ``ReportRequest.web_search_budget_override``. None when the user
    hasn't set one — runner then falls back to framework default."""
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    svc.update_config(user, web_search_budgets_by_mode={"stock_initiation": 7})

    cfg = svc.get_config(user)
    init_active = svc.resolve_active(cfg, mode="stock_initiation")
    assert init_active.web_search_budget == 7

    update_active = svc.resolve_active(cfg, mode="stock_update")
    assert update_active.web_search_budget is None


# ---------- report_reasoning_effort persistence (v2.3 extended thinking) ----------


def test_get_config_defaults_reasoning_effort_to_medium(db_session, user):
    """A fresh row materialises as 'medium' — the working default. Users
    can opt into 'off' explicitly for fast/cheap runs."""
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    assert cfg.report_reasoning_effort == "medium"


def test_update_config_persists_reasoning_effort(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(user, report_reasoning_effort="high")
    assert updated.report_reasoning_effort == "high"
    # Round-trip through the DB.
    refreshed = svc.get_config(user)
    assert refreshed.report_reasoning_effort == "high"


def test_update_config_accepts_each_valid_reasoning_value(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    for value in ("off", "medium", "high"):
        updated = svc.update_config(user, report_reasoning_effort=value)
        assert updated.report_reasoning_effort == value


def test_update_config_persists_off_unchanged(db_session, user):
    """'off' is a valid user-selectable state — it must round-trip
    through the DB unchanged, not get coerced to 'medium'."""
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(user, report_reasoning_effort="off")
    assert updated.report_reasoning_effort == "off"
    refreshed = svc.get_config(user)
    assert refreshed.report_reasoning_effort == "off"


def test_update_config_rejects_invalid_reasoning_effort(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    with pytest.raises(ValueError, match="reasoning_effort"):
        svc.update_config(user, report_reasoning_effort="extreme")  # type: ignore[arg-type]


def test_update_config_leaves_reasoning_effort_when_omitted(db_session, user):
    """PATCH semantics: omitting the field must not reset it."""
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    svc.update_config(user, report_reasoning_effort="high")
    svc.update_config(user, report_length="concise")
    cfg = svc.get_config(user)
    assert cfg.report_reasoning_effort == "high"
    assert cfg.report_length == "concise"
