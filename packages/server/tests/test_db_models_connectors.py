"""Verify Connector and ToolAllowlist ORM models load and round-trip."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.base import Base
from openlia_server.db.models import register_all  # noqa: F401  - side-effect register
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture()
def engine():
    eng = create_engine("sqlite:///:memory:")
    # SQLite needs FK enforcement enabled per-connection for cascade delete to fire.
    from sqlalchemy import event

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_connector_round_trip(engine):
    from openlia_server.db.models.connectors import Connector

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                credentials_ref="secret://eodhd/key",
                cached_tools=[{"name": "get_quote", "description": "...", "input_schema": {}}],
                status="validated",
                last_validated_at=datetime.now(UTC),
            )
        )
        s.commit()
        out = s.query(Connector).one()
        assert out.id == cid
        assert out.provider_id == "eodhd"
        assert out.cached_tools[0]["name"] == "get_quote"


def test_tool_allowlist_unique_constraint(engine):
    from openlia_server.db.models.connectors import Connector, ToolAllowlist

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            )
        )
        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",
                scoped_by="built_in_map",
            )
        )
        s.commit()

        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",
                scoped_by="built_in_map",
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()


def test_tool_allowlist_cascade_delete(engine):
    from openlia_server.db.models.connectors import Connector, ToolAllowlist

    cid = str(uuid.uuid4())
    with Session(engine) as s:
        s.add(
            Connector(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            )
        )
        s.add(
            ToolAllowlist(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="get_quote",
                scoped_by="built_in_map",
            )
        )
        s.commit()

        # Delete via ORM so cascade fires (raw table.delete() bypasses ORM cascade).
        s.delete(s.get(Connector, cid))
        s.commit()

        assert s.query(ToolAllowlist).count() == 0
