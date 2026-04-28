"""Verify Connector ORM model loads and round-trips."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from openlia_server.db.base import Base
from openlia_server.db.models import register_all  # noqa: F401  - side-effect register
from sqlalchemy import create_engine
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
