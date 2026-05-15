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
