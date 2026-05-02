"""Phase 1 schema migration tests for the resolver redesign.

Covers:
- Round-trip of new columns on `runner_callable_specs`.
- `resolver_call_log` and `smoke_call_log` audit table round-trips.
- DB-level CHECK constraint on `resolution_mode`.
- Forward + backward migration cleanliness on a fresh DB.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

REPO_ROOT_SERVER = Path(__file__).resolve().parents[2]


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    merged = os.environ.copy()
    merged["OPENLIA_DB_URL"] = db_url
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


@pytest.fixture()
def engine():
    from openlia_server.db.base import Base
    from openlia_server.db.models import register_all  # noqa: F401

    eng = create_engine("sqlite:///:memory:")

    from sqlalchemy import event

    @event.listens_for(eng, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _make_connector(s: Session) -> str:
    from openlia_server.db.models.connectors import Connector

    cid = str(uuid.uuid4())
    s.add(
        Connector(
            id=cid,
            provider_id="fmp",
            display_name="FMP",
            source="built_in",
            category="financial",
            launch={"kind": "built_in", "template_id": "fmp"},
            secrets={"FMP_API_KEY": "k"},
        )
    )
    s.commit()
    return cid


def test_runner_callable_spec_new_columns_persist_and_load(engine) -> None:
    from openlia_server.db.models.connectors import RunnerCallableSpec

    with Session(engine) as s:
        cid = _make_connector(s)
        rid = str(uuid.uuid4())
        now = datetime.now(UTC)
        s.add(
            RunnerCallableSpec(
                id=rid,
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id=cid,
                access_mode="python_lib",
                spec={"tool_name": "fmp.macro.debt_gdp", "param_bindings": {}},
                resolution_mode="manual_endpoint",
                user_inputs={"endpoint": "fmp.macro.debt_gdp", "hint": ""},
                llm_warning=None,
                manually_overridden=True,
                last_smoke_at=now,
            )
        )
        s.commit()

        out = s.query(RunnerCallableSpec).one()
        assert out.id == rid
        assert out.resolution_mode == "manual_endpoint"
        assert out.user_inputs == {"endpoint": "fmp.macro.debt_gdp", "hint": ""}
        assert out.llm_warning is None
        assert out.manually_overridden is True
        assert out.last_smoke_at is not None


def test_resolver_call_log_round_trip(engine) -> None:
    from openlia_server.db.models.connectors import (
        ResolverCallLog,
        RunnerCallableSpec,
    )

    with Session(engine) as s:
        cid = _make_connector(s)
        rid = str(uuid.uuid4())
        s.add(
            RunnerCallableSpec(
                id=rid,
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id=cid,
                access_mode="python_lib",
                spec={},
                resolution_mode="catalog",
            )
        )
        s.commit()

        log_id = str(uuid.uuid4())
        s.add(
            ResolverCallLog(
                id=log_id,
                spec_id=rid,
                department_id="macro_research",
                need_id="debt_gdp",
                request={"endpoint": "fmp.macro.debt_gdp"},
                response={"spec": {}, "warning": None},
                status="success",
            )
        )
        s.commit()

        rows = s.query(ResolverCallLog).all()
        assert len(rows) == 1
        assert rows[0].spec_id == rid
        assert rows[0].status == "success"


def test_smoke_call_log_round_trip(engine) -> None:
    from openlia_server.db.models.connectors import (
        RunnerCallableSpec,
        SmokeCallLog,
    )

    with Session(engine) as s:
        cid = _make_connector(s)
        rid = str(uuid.uuid4())
        s.add(
            RunnerCallableSpec(
                id=rid,
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id=cid,
                access_mode="python_lib",
                spec={},
                resolution_mode="catalog",
            )
        )
        s.commit()

        log_id = str(uuid.uuid4())
        s.add(
            SmokeCallLog(
                id=log_id,
                spec_id=rid,
                args={"ticker": "AAPL"},
                status="success",
                attempt=1,
                error_class=None,
                error_message=None,
            )
        )
        s.commit()

        rows = s.query(SmokeCallLog).all()
        assert len(rows) == 1
        assert rows[0].status == "success"
        assert rows[0].attempt == 1


def test_resolution_mode_enum_rejects_unknown_value(engine) -> None:
    from openlia_server.db.models.connectors import RunnerCallableSpec

    with Session(engine) as s:
        cid = _make_connector(s)
        s.add(
            RunnerCallableSpec(
                id=str(uuid.uuid4()),
                department_id="macro_research",
                need_id="debt_gdp",
                connector_id=cid,
                access_mode="python_lib",
                spec={},
                resolution_mode="bogus_mode",
            )
        )
        with pytest.raises(IntegrityError):
            s.commit()


def test_phase1_migration_forward_and_back(tmp_path: Path) -> None:
    """Migration steps from prior head to the new head and reverses cleanly."""
    db_file = tmp_path / "phase1_step.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "20260501_0100_grounding_paths"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    assert "resolver_call_log" not in insp.get_table_names()
    assert "smoke_call_log" not in insp.get_table_names()
    rcs_cols = {c["name"] for c in insp.get_columns("runner_callable_specs")}
    assert "resolution_mode" not in rcs_cols
    assert "manually_overridden" not in rcs_cols
    engine.dispose()

    proc = _run_alembic(["upgrade", "head"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    assert "resolver_call_log" in insp.get_table_names()
    assert "smoke_call_log" in insp.get_table_names()
    rcs_cols = {c["name"] for c in insp.get_columns("runner_callable_specs")}
    for new_col in (
        "resolution_mode",
        "user_inputs",
        "llm_warning",
        "manually_overridden",
        "last_smoke_at",
    ):
        assert new_col in rcs_cols
    rc_idx = {idx["name"] for idx in insp.get_indexes("resolver_call_log")}
    sm_idx = {idx["name"] for idx in insp.get_indexes("smoke_call_log")}
    assert "ix_resolver_call_log_spec_created" in rc_idx
    assert "ix_smoke_call_log_spec_created" in sm_idx
    engine.dispose()

    proc = _run_alembic(["downgrade", "20260501_0100_grounding_paths"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    insp = inspect(engine)
    assert "resolver_call_log" not in insp.get_table_names()
    assert "smoke_call_log" not in insp.get_table_names()
    rcs_cols = {c["name"] for c in insp.get_columns("runner_callable_specs")}
    assert "resolution_mode" not in rcs_cols
    engine.dispose()


def test_default_resolution_mode_is_catalog_via_raw_insert(tmp_path: Path) -> None:
    """A row written without resolution_mode falls back to 'catalog' (server default)."""
    db_file = tmp_path / "phase1_default.db"
    db_url = f"sqlite:///{db_file}"

    proc = _run_alembic(["upgrade", "head"], db_url)
    assert proc.returncode == 0, proc.stderr

    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.execute(
            text(
                "INSERT INTO connectors (id, provider_id, display_name, source, category, "
                "launch, secrets, status, grounding_status, created_at) "
                "VALUES ('c1', 'fmp', 'FMP', 'built_in', 'financial', '{}', '{}', "
                "'pending', 'none', datetime('now'))"
            )
        )
        conn.execute(
            text(
                "INSERT INTO runner_callable_specs "
                "(id, department_id, need_id, connector_id, access_mode, spec, created_at) "
                "VALUES ('r1', 'macro_research', 'debt_gdp', 'c1', 'python_lib', '{}', "
                "datetime('now'))"
            )
        )
        mode = conn.execute(
            text("SELECT resolution_mode FROM runner_callable_specs WHERE id='r1'")
        ).scalar_one()
        manually = conn.execute(
            text("SELECT manually_overridden FROM runner_callable_specs WHERE id='r1'")
        ).scalar_one()
    engine.dispose()

    assert mode == "catalog"
    assert int(manually) == 0
