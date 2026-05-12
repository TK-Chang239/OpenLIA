from __future__ import annotations

from pathlib import Path

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import ErTemplate
from openlia_server.services.equity_research_config import EquityResearchConfigService
from openlia_server.services.equity_research_templates import (
    EquityResearchTemplateService,
    TemplateValidationError,
)

LONG_TEXT = ("Equity research template body. " * 30).strip()


@pytest.fixture(autouse=True)
def _storage_dir(tmp_path, monkeypatch):
    """Route attachment_storage writes into a fresh tmp dir per test."""
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "attachments"))


@pytest.fixture
def user(db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.add(User(id="u2", email="u2@example.com", display_name="u2"))
    db_session.add(User(id="admin", email="admin@example.com", display_name="admin", is_admin=True))
    db_session.commit()
    return "u1"


def _upload(
    svc: EquityResearchTemplateService,
    *,
    user_id: str,
    owner_scope: str = "user",
    name="my",
    modes=None,
) -> str:
    dto = svc.upload(
        actor_user_id=user_id,
        owner_scope=owner_scope,  # type: ignore[arg-type]
        content=LONG_TEXT.encode("utf-8"),
        filename="x.md",
        mime_type="text/markdown",
        name=name,
        compatible_modes=modes or ["stock_initiation"],
    )
    return dto.id


def test_upload_persists_extracted_text_and_estimates_tokens(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    dto = svc.upload(
        actor_user_id=user,
        owner_scope="user",
        content=LONG_TEXT.encode("utf-8"),
        filename="my_template.md",
        mime_type="text/markdown",
        name=None,
        compatible_modes=["stock_initiation", "stock_update"],
    )
    assert dto.owner_scope == "user"
    assert dto.owner_user_id == user
    assert dto.name == "my_template"  # filename-derived
    assert dto.compatible_modes == ("stock_initiation", "stock_update")
    assert dto.char_count == len(LONG_TEXT)
    assert dto.estimated_tokens > 0
    row = db_session.get(ErTemplate, dto.id)
    assert row is not None
    assert row.extracted_text == LONG_TEXT
    assert Path(row.storage_path).exists()


def test_upload_rejects_below_min_chars(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    with pytest.raises(TemplateValidationError):
        svc.upload(
            actor_user_id=user,
            owner_scope="user",
            content=b"too short",
            filename="x.md",
            mime_type="text/markdown",
            name=None,
            compatible_modes=["stock_initiation"],
        )


def test_upload_rejects_unsupported_mime(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    with pytest.raises(TemplateValidationError):
        svc.upload(
            actor_user_id=user,
            owner_scope="user",
            content=LONG_TEXT.encode("utf-8"),
            filename="x.bin",
            mime_type="application/octet-stream",
            name=None,
            compatible_modes=["stock_initiation"],
        )


def test_upload_rejects_unknown_mode(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    with pytest.raises(TemplateValidationError):
        svc.upload(
            actor_user_id=user,
            owner_scope="user",
            content=LONG_TEXT.encode("utf-8"),
            filename="x.md",
            mime_type="text/markdown",
            name=None,
            compatible_modes=["bogus"],
        )


def test_list_visible_includes_globals_and_own(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    _upload(svc, user_id=user)
    _upload(svc, user_id="admin", owner_scope="global", name="firm-wide")
    _upload(svc, user_id="u2", owner_scope="user", name="other-user")
    visible = svc.list_visible(user)
    names = {t.name for t in visible}
    assert "my" in names and "firm-wide" in names
    assert "other-user" not in names


def test_get_for_user_blocks_other_users_private_templates(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    other_id = _upload(svc, user_id="u2", owner_scope="user")
    assert svc.get_for_user(user, other_id) is None


def test_update_metadata_changes_name_and_modes(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    tid = _upload(svc, user_id=user)
    dto = svc.update_metadata(
        template_id=tid,
        name="renamed",
        compatible_modes=["stock_update", "sector_research"],
    )
    assert dto.name == "renamed"
    assert dto.compatible_modes == ("stock_update", "sector_research")


def test_delete_cascades_to_selection(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    cfg_svc = EquityResearchConfigService(db_session)
    tid = _upload(svc, user_id=user)
    cfg_svc.get_config(user)  # ensure row exists
    cfg_svc.update_config(
        user,
        selected_template_id_by_mode={"stock_initiation": tid},
    )
    db_session.commit()
    svc.delete(tid)
    cfg = cfg_svc.get_config(user)
    assert cfg.selected_template_id_by_mode["stock_initiation"] == "default"


def test_delete_unlinks_storage_file(db_session, user):
    svc = EquityResearchTemplateService(db_session)
    tid = _upload(svc, user_id=user)
    row = db_session.get(ErTemplate, tid)
    path = row.storage_path
    assert Path(path).exists()
    svc.delete(tid)
    assert not Path(path).exists()


def test_resolve_active_returns_template_branch(db_session, user):
    tsvc = EquityResearchTemplateService(db_session)
    cfg_svc = EquityResearchConfigService(db_session)
    tid = _upload(tsvc, user_id=user, name="custom")
    cfg_svc.get_config(user)
    cfg_svc.update_config(user, selected_template_id_by_mode={"stock_initiation": tid})
    db_session.commit()
    cfg = cfg_svc.get_config(user)
    active = cfg_svc.resolve_active(cfg, mode="stock_initiation", user_id=user)
    assert active.template_id == tid
    assert active.template_name == "custom"
    assert active.template_text == LONG_TEXT
    assert active.enabled_section_ids == ()


def test_resolve_active_ignores_other_users_private_template(db_session, user):
    tsvc = EquityResearchTemplateService(db_session)
    cfg_svc = EquityResearchConfigService(db_session)
    other_tid = _upload(tsvc, user_id="u2", owner_scope="user")
    cfg_svc.get_config(user)
    cfg_svc.update_config(user, selected_template_id_by_mode={"stock_initiation": other_tid})
    db_session.commit()
    cfg = cfg_svc.get_config(user)
    active = cfg_svc.resolve_active(cfg, mode="stock_initiation", user_id=user)
    assert active.template_text is None
    assert active.template_id is None
