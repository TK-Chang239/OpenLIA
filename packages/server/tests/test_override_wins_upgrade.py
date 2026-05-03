"""Phase 11: catalog reinstall / upgrade must not clobber user overrides.

When a user has manually resolved (resolution_mode != 'catalog'), a
later catalog install or `sync_template_specs` MUST:
  1. Preserve the override row.
  2. Record the would-be new template spec in
     `pending_default_change` so the admin panel can surface a
     non-blocking "pending default change" notice.
A `revert_to_default` action consumes the pending blob and swaps in
the catalog spec.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from openlia.connectors.types import Category
from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.services.template_upgrade import (
    apply_template_with_override_protection,
    revert_to_default,
)
from sqlalchemy.orm import Session


def _make_connector(db_session: Session, *, provider_id: str) -> Connector:
    conn = Connector(
        id=str(uuid4()),
        provider_id=provider_id,
        display_name=provider_id,
        source="built_in",
        category=Category.FINANCIAL.value,
        launch={"modes": []},
        secrets={},
        cached_tools=[],
        status="validated",
    )
    db_session.add(conn)
    db_session.commit()
    return conn


def _user_override_row(db_session: Session, *, connector_id: str) -> RunnerCallableSpec:
    row = RunnerCallableSpec(
        id=str(uuid4()),
        department_id="macro_research",
        need_id="stock_quote",
        connector_id=connector_id,
        access_mode="remote_mcp",
        spec={"tool_name": "user_picked_quote"},
        resolution_mode="manual_endpoint",
        manually_overridden=True,
        last_smoke_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_install_does_not_overwrite_existing_user_override(
    db_session: Session,
) -> None:
    conn = _make_connector(db_session, provider_id="fmp")
    user_row = _user_override_row(db_session, connector_id=conn.id)
    new_template_spec = {"tool_name": "quote", "constants": {"endpoint": "quote"}}
    apply_template_with_override_protection(
        db_session,
        connector_id=conn.id,
        department_id="macro_research",
        need_id="stock_quote",
        template_spec=new_template_spec,
        access_mode="remote_mcp",
    )
    db_session.refresh(user_row)
    # Override row preserved.
    assert user_row.spec == {"tool_name": "user_picked_quote"}
    assert user_row.resolution_mode == "manual_endpoint"


def test_upgrade_records_pending_default_change_when_override_exists(
    db_session: Session,
) -> None:
    conn = _make_connector(db_session, provider_id="fmp")
    user_row = _user_override_row(db_session, connector_id=conn.id)
    new_template_spec = {"tool_name": "quote_v2"}
    apply_template_with_override_protection(
        db_session,
        connector_id=conn.id,
        department_id="macro_research",
        need_id="stock_quote",
        template_spec=new_template_spec,
        access_mode="remote_mcp",
    )
    db_session.refresh(user_row)
    pending = user_row.pending_default_change
    assert pending is not None
    assert pending["spec"] == {"tool_name": "quote_v2"}


def test_revert_to_default_swaps_override_for_template_spec(
    db_session: Session,
) -> None:
    conn = _make_connector(db_session, provider_id="fmp")
    user_row = _user_override_row(db_session, connector_id=conn.id)
    new_template_spec = {"tool_name": "quote_v2"}
    apply_template_with_override_protection(
        db_session,
        connector_id=conn.id,
        department_id="macro_research",
        need_id="stock_quote",
        template_spec=new_template_spec,
        access_mode="remote_mcp",
    )
    revert_to_default(
        db_session,
        department_id="macro_research",
        need_id="stock_quote",
    )
    db_session.refresh(user_row)
    assert user_row.spec == {"tool_name": "quote_v2"}
    assert user_row.resolution_mode == "catalog"
    assert user_row.pending_default_change is None
    assert user_row.manually_overridden is False


def test_install_overwrites_when_no_override_exists(
    db_session: Session,
) -> None:
    """No override → catalog install proceeds normally."""
    conn = _make_connector(db_session, provider_id="fmp")
    new_template_spec = {"tool_name": "quote"}
    apply_template_with_override_protection(
        db_session,
        connector_id=conn.id,
        department_id="macro_research",
        need_id="stock_quote",
        template_spec=new_template_spec,
        access_mode="remote_mcp",
    )
    rows = (
        db_session.query(RunnerCallableSpec)
        .filter(
            RunnerCallableSpec.department_id == "macro_research",
            RunnerCallableSpec.need_id == "stock_quote",
        )
        .all()
    )
    assert len(rows) == 1
    assert rows[0].spec == {"tool_name": "quote"}
    assert rows[0].resolution_mode == "catalog"
