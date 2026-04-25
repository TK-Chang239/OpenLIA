# Phase 1A — Database Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the SQLite persistence layer so every Phase 2+ plan can open a session and read/write rows. Ships 22 of the 33 tables defined in `database-design.md` — every table that Plans 2–5 need (auth + LLM/data/search config + chat/reports/portfolio + wizard/config_store) — plus the engine, Alembic machinery, startup bootstrap, and auto-migrate.

**Architecture:** SQLAlchemy 2.x declarative models grouped by category under `openlia_server/db/models/`. One hand-written baseline Alembic migration creates every table in this plan. `db/session.py` owns the engine factory, sessionmaker, and the WAL/PRAGMA connect listener. `db/bootstrap.py` owns `~/.openlia/` directory creation, DB URL resolution, and the startup sequence (auto-migrate → seed `local` user → seed `config_store`). The Typer `serve` command from Phase 0 calls `bootstrap()` before uvicorn starts. Plan 1B (future) adds the dashboard, scheduler, and notification tables as a second migration.

**Tech Stack:** SQLAlchemy 2.0+, Alembic 1.13+, sqlite3 (stdlib), Python 3.12. Tests use pytest with `tmp_path` and `monkeypatch` fixtures.

**Source spec:** `planning/specs/systems/database-design.md` (sections 1–6, 8, 9, plus the §7 infrastructure rows `wizard_state` and `config_store`). Sections 7 dashboard rows and the scheduler/notification tables are deferred to Plan 1B.

**Depends on:** Phase 0 (workspace scaffold, `openlia_server` package, Typer CLI).

**Unblocks:** Plan 2 (secrets encryption + auth primitives), Plan 3 (data providers), Plan 4 (LLM providers), Plan 5 (LLM runtime).

**Out of scope (handled elsewhere):**
- AES-256-GCM encryption of `api_key_encrypted` columns — Plan 2 writes the crypto module; this plan defines the columns as nullable `Text`.
- Argon2id password hashing — Plan 2; this plan defines `users.password_hash` as nullable `String(256)`.
- Dashboard/scheduler/notification tables — Plan 1B.
- Route handlers that read/write these tables — Plans 2+.
- Nightly maintenance sweep — Plan 6/7 (this plan does not install the pruner).

---

## File Structure

Files created in this plan:

```
openlia/
├── packages/
│   └── server/
│       ├── alembic.ini                                  # Alembic config, points at openlia_server.db.migrations
│       ├── pyproject.toml                               # +sqlalchemy, +alembic deps
│       └── src/openlia_server/
│           ├── cli.py                                   # MODIFIED — serve calls bootstrap()
│           └── db/
│               ├── __init__.py                          # Re-exports Base, engine, SessionLocal, bootstrap
│               ├── base.py                              # DeclarativeBase + TimestampMixin + naming convention
│               ├── session.py                           # engine factory, sessionmaker, WAL/PRAGMA listener
│               ├── bootstrap.py                         # ~/.openlia/ dir, DB URL resolution, auto-migrate, seed
│               ├── models/
│               │   ├── __init__.py                      # Re-exports every model
│               │   ├── auth.py                          # users, sessions, signup_invites, signup_policy,
│               │   │                                    #   password_reset_requests, auth_events
│               │   ├── config.py                        # llm_providers, llm_models, user_llm_preferences,
│               │   │                                    #   data_providers, data_provider_requirement_mapping,
│               │   │                                    #   web_search_providers
│               │   ├── content.py                       # chat_sessions, chat_messages, chat_attachments,
│               │   │                                    #   reports, report_versions, portfolio_holdings,
│               │   │                                    #   watchlists, watchlist_items
│               │   └── infrastructure.py                # wizard_state, config_store
│               └── migrations/
│                   ├── env.py                           # Hand-written env.py; uses Base.metadata
│                   ├── script.py.mako                   # Standard Alembic template
│                   └── versions/
│                       ├── .gitkeep
│                       └── 2026-04-16-1200_baseline.py  # The one migration this plan adds
└── packages/server/tests/
    ├── test_db/
    │   ├── __init__.py
    │   ├── conftest.py                                  # tmp-DB fixture, SessionLocal override
    │   ├── test_session.py                              # WAL + pragmas
    │   ├── test_bootstrap.py                            # dir creation, URL resolution, seed idempotency
    │   ├── test_models_auth.py                          # 6 auth tables
    │   ├── test_models_config.py                        # 6 config tables
    │   ├── test_models_content.py                       # 8 content tables
    │   ├── test_models_infrastructure.py                # 2 infrastructure tables
    │   └── test_migrations.py                           # upgrade/downgrade cleanly
    └── test_cli_bootstrap.py                            # `openlia serve` triggers bootstrap
```

Design rules:

- **One model file per database-design.md category** (auth, config, content, infrastructure). Matches the spec's §3/§4/§6/§7 groupings and keeps each file under ~400 lines.
- **`Base.metadata.naming_convention`** set once so migration index/constraint names are deterministic and portable (see `base.py` below).
- **Session/engine** built from a URL passed in — tests override by calling `configure_engine(url)` before work. Production code reads the URL from `bootstrap.resolve_db_url()`.
- **Alembic `env.py` imports `Base` from `openlia_server.db` and every model package** so `Base.metadata.tables` is fully populated before autogenerate or upgrade.

---

## Task 1: Add SQLAlchemy + Alembic to the server package

**Files:**
- Modify: `packages/server/pyproject.toml`

- [ ] **Step 1: Read the current pyproject**

Run:
```bash
cat packages/server/pyproject.toml
```
Expected: prints the file Phase 0 wrote (should contain `dependencies = ["openlia-core", "fastapi>=...", "typer>=...", "uvicorn[standard]>=..."]`).

- [ ] **Step 2: Add sqlalchemy + alembic to the dependencies array**

Edit `packages/server/pyproject.toml`. The `dependencies = [...]` array under `[project]` must include two new entries. After edit, the relevant slice must read:

```toml
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "typer>=0.12",
    "uvicorn[standard]>=0.34",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
]
```

Preserve every other line in the file exactly as Phase 0 wrote it.

- [ ] **Step 3: Sync the workspace**

Run:
```bash
uv sync --all-packages
```
Expected: `Resolved N packages`, `Installed M packages`. No errors. Both `sqlalchemy` and `alembic` must appear in the installed list (or be already present).

- [ ] **Step 4: Smoke-import both libraries**

Run:
```bash
uv run python -c "import sqlalchemy, alembic; print(sqlalchemy.__version__, alembic.__version__)"
```
Expected: prints `2.0.x 1.13.x` (version numbers may differ; no `ImportError`).

- [ ] **Step 5: Commit**

```bash
git add packages/server/pyproject.toml uv.lock
git commit -m "deps(server): add sqlalchemy 2.x + alembic for Phase 1A database layer"
```

---

## Task 2: Declarative Base + naming convention + timestamp mixin

**Files:**
- Create: `packages/server/src/openlia_server/db/__init__.py`
- Create: `packages/server/src/openlia_server/db/base.py`
- Create: `packages/server/tests/test_db/__init__.py`
- Create: `packages/server/tests/test_db/conftest.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/__init__.py` (empty file — package marker).

Create `packages/server/tests/test_db/conftest.py`:

```python
"""Shared pytest fixtures for DB tests.

Every test gets a temporary SQLite database in `tmp_path`. The fixture
rebinds the server's engine and sessionmaker so code under test uses the
temp DB without touching `~/.openlia/`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def db_url(db_path: Path) -> str:
    return f"sqlite:///{db_path}"


@pytest.fixture
def engine(db_url: str) -> Iterator[Engine]:
    from openlia_server.db import session as session_mod

    session_mod.configure_engine(db_url)
    yield session_mod.get_engine()
    session_mod.dispose_engine()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    from openlia_server.db import session as session_mod

    with session_mod.SessionLocal() as s:
        yield s
```

Now create `packages/server/tests/test_db/test_session.py` (stub — filled in Task 3, but the file must exist so pytest collects the package):

```python
"""Placeholder — real session tests land in Task 3."""
```

Add a first real test targeting `base.py`. Create a file for it — reuse `test_session.py` for now:

Append to `packages/server/tests/test_db/test_session.py`:

```python
from __future__ import annotations


def test_base_has_naming_convention() -> None:
    """Naming convention must be set on metadata so Alembic emits deterministic
    index/constraint names across SQLite and (future) Postgres."""
    from openlia_server.db.base import Base

    expected_keys = {"ix", "uq", "ck", "fk", "pk"}
    assert set(Base.metadata.naming_convention.keys()) == expected_keys


def test_timestamp_mixin_columns_present() -> None:
    """TimestampMixin must contribute created_at + updated_at to any model
    that inherits it."""
    from sqlalchemy import DateTime
    from sqlalchemy.orm import Mapped, mapped_column

    from openlia_server.db.base import Base, TimestampMixin

    class _Demo(Base, TimestampMixin):
        __tablename__ = "_demo"
        id: Mapped[int] = mapped_column(primary_key=True)

    cols = {c.name: c for c in _Demo.__table__.columns}
    assert "created_at" in cols
    assert "updated_at" in cols
    assert isinstance(cols["created_at"].type, DateTime)
    assert cols["created_at"].type.timezone is True
    assert cols["updated_at"].type.timezone is True
    assert cols["created_at"].nullable is False
    assert cols["updated_at"].nullable is False
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_session.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server.db'`.

- [ ] **Step 3: Create the `db` package with `base.py`**

Create `packages/server/src/openlia_server/db/__init__.py`:

```python
"""Persistence layer for the OpenLIA server.

This package owns the SQLAlchemy Base, engine, sessionmaker, and the
bootstrap routine that materializes `~/.openlia/` and runs Alembic.
"""

from openlia_server.db.base import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
```

Create `packages/server/src/openlia_server/db/base.py`:

```python
"""Declarative base and shared mixins for all SQLAlchemy models.

The naming convention below makes every implicit constraint name
deterministic. This matters because Alembic generates migration ops that
reference constraints by name — without a convention, SQLAlchemy invents
names at metadata-build time which can drift between releases.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Common base for every ORM model in the server."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """Adds `created_at` and `updated_at` timezone-aware timestamps.

    `created_at` is set by the DB on INSERT. `updated_at` is set on INSERT
    and refreshed on UPDATE by SQLAlchemy's `onupdate`.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_session.py -v
```
Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/__init__.py \
        packages/server/src/openlia_server/db/base.py \
        packages/server/tests/test_db/__init__.py \
        packages/server/tests/test_db/conftest.py \
        packages/server/tests/test_db/test_session.py
git commit -m "feat(db): add declarative Base + TimestampMixin with naming convention"
```

---

## Task 3: Engine factory, sessionmaker, and SQLite PRAGMA listener

**Files:**
- Create: `packages/server/src/openlia_server/db/session.py`
- Modify: `packages/server/tests/test_db/test_session.py`

- [ ] **Step 1: Extend the test file**

Replace the entire contents of `packages/server/tests/test_db/test_session.py` with:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine


def test_base_has_naming_convention() -> None:
    from openlia_server.db.base import Base

    assert set(Base.metadata.naming_convention.keys()) == {"ix", "uq", "ck", "fk", "pk"}


def test_timestamp_mixin_columns_present() -> None:
    from sqlalchemy import DateTime
    from sqlalchemy.orm import Mapped, mapped_column

    from openlia_server.db.base import Base, TimestampMixin

    class _Demo(Base, TimestampMixin):
        __tablename__ = "_demo"
        id: Mapped[int] = mapped_column(primary_key=True)

    cols = {c.name: c for c in _Demo.__table__.columns}
    assert isinstance(cols["created_at"].type, DateTime)
    assert cols["created_at"].type.timezone is True
    assert cols["updated_at"].type.timezone is True


def test_configure_engine_requires_url() -> None:
    from openlia_server.db import session as session_mod

    with pytest.raises(RuntimeError):
        session_mod.get_engine()


def test_configure_engine_creates_sqlite_engine(db_url: str) -> None:
    from openlia_server.db import session as session_mod

    session_mod.configure_engine(db_url)
    try:
        engine: Engine = session_mod.get_engine()
        assert engine.url.drivername == "sqlite"
    finally:
        session_mod.dispose_engine()


def test_sqlite_pragmas_applied(engine: Engine) -> None:
    """Every new connection must be WAL, foreign_keys=ON, synchronous=NORMAL,
    busy_timeout=5000."""
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL = 1
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000


def test_session_local_usable(engine: Engine) -> None:
    from openlia_server.db import session as session_mod

    with session_mod.SessionLocal() as s:
        assert s.execute(text("SELECT 1")).scalar() == 1


def test_dispose_engine_is_idempotent() -> None:
    from openlia_server.db import session as session_mod

    session_mod.dispose_engine()  # no-op when nothing configured
    session_mod.dispose_engine()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_session.py -v
```
Expected: FAIL — `openlia_server.db.session` does not exist yet.

- [ ] **Step 3: Implement `session.py`**

Create `packages/server/src/openlia_server/db/session.py`:

```python
"""Engine + sessionmaker management.

Configuration is explicit: call `configure_engine(url)` once at startup
(or per-test in fixtures). Subsequent calls to `get_engine()` and
`SessionLocal()` return the bound engine/session factory. `dispose_engine()`
tears everything down for clean test isolation.
"""

from __future__ import annotations

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def configure_engine(url: str, *, echo: bool = False) -> Engine:
    """Build and register the process-wide engine + session factory.

    Called by `bootstrap.bootstrap()` at server start and by test fixtures.
    Re-calling disposes the previous engine before creating a new one.
    """
    global _engine, _SessionFactory

    if _engine is not None:
        _engine.dispose()

    _engine = create_engine(
        url,
        echo=echo,
        future=True,
        # connect_args needed for multi-threaded access (FastAPI default).
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    _register_sqlite_pragmas(_engine)
    _SessionFactory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError(
            "Engine not configured. Call openlia_server.db.session.configure_engine(url) first."
        )
    return _engine


def SessionLocal() -> Session:  # noqa: N802 — conventional FastAPI name
    if _SessionFactory is None:
        raise RuntimeError(
            "Session factory not configured. Call configure_engine(url) first."
        )
    return _SessionFactory()


def dispose_engine() -> None:
    """Release the engine. Safe to call when nothing is configured."""
    global _engine, _SessionFactory

    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None


def _register_sqlite_pragmas(engine: Engine) -> None:
    """Attach a `connect` listener that sets the four required PRAGMAs on
    every new SQLite connection.

    Mirrors database-design.md § 2: journal_mode=WAL, synchronous=NORMAL,
    foreign_keys=ON, busy_timeout=5000.
    """
    if engine.url.drivername != "sqlite":
        return

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()
```

Update `packages/server/src/openlia_server/db/__init__.py` to re-export:

```python
"""Persistence layer for the OpenLIA server."""

from openlia_server.db.base import Base, TimestampMixin
from openlia_server.db.session import SessionLocal, configure_engine, dispose_engine, get_engine

__all__ = [
    "Base",
    "SessionLocal",
    "TimestampMixin",
    "configure_engine",
    "dispose_engine",
    "get_engine",
]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_session.py -v
```
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/session.py \
        packages/server/src/openlia_server/db/__init__.py \
        packages/server/tests/test_db/test_session.py
git commit -m "feat(db): engine factory + SessionLocal with SQLite WAL/PRAGMA listener"
```

---

## Task 4: Startup bootstrap — `~/.openlia/` dir + DB URL resolution

**Files:**
- Create: `packages/server/src/openlia_server/db/bootstrap.py`
- Create: `packages/server/tests/test_db/test_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_bootstrap.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_resolve_db_url_uses_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("OPENLIA_DB_URL", "sqlite:///tmp/explicit.db")
    assert bootstrap.resolve_db_url() == "sqlite:///tmp/explicit.db"


def test_resolve_db_url_defaults_to_home_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))

    expected = f"sqlite:///{tmp_path / '.openlia' / 'openlia.db'}"
    assert bootstrap.resolve_db_url() == expected


def test_ensure_openlia_dir_creates_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    path = bootstrap.ensure_openlia_dir()

    assert path == tmp_path / ".openlia"
    assert path.is_dir()


def test_ensure_openlia_dir_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    bootstrap.ensure_openlia_dir()
    bootstrap.ensure_openlia_dir()  # must not raise

    assert (tmp_path / ".openlia").is_dir()


def test_resolve_db_url_expands_tilde(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When OPENLIA_DB_URL contains ~, expand to the user's home directory."""
    from openlia_server.db import bootstrap

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", "sqlite:///~/custom.db")

    assert bootstrap.resolve_db_url() == f"sqlite:///{tmp_path / 'custom.db'}"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_bootstrap.py -v
```
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `bootstrap.py` (partial — path logic only)**

Create `packages/server/src/openlia_server/db/bootstrap.py`:

```python
"""Startup orchestration for the persistence layer.

Owns three concerns:
  1. Resolving the DB URL from env or the default `~/.openlia/openlia.db`.
  2. Materializing `~/.openlia/` on disk (for the SQLite file, uploads, and
     the secret-key file that Plan 2 will add).
  3. Running Alembic to head and seeding the synthetic `local` user plus
     a minimal `config_store` (added in Task 11 of this plan).

Callers: `openlia serve` (production) and test fixtures (never).
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_FILENAME = "openlia.db"
OPENLIA_DIR_NAME = ".openlia"


def openlia_home() -> Path:
    """Resolve `~/.openlia` respecting the current `HOME` env var."""
    return Path(os.path.expanduser("~")) / OPENLIA_DIR_NAME


def ensure_openlia_dir() -> Path:
    """Create `~/.openlia` (0700) if missing. Returns the directory path."""
    path = openlia_home()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def resolve_db_url() -> str:
    """Return the SQLAlchemy URL for the DB.

    Precedence:
      1. `OPENLIA_DB_URL` env var (tilde-expanded).
      2. `sqlite:///<openlia_home>/openlia.db`.
    """
    env = os.environ.get("OPENLIA_DB_URL")
    if env:
        return _expand_sqlite_url(env)

    db_path = openlia_home() / DEFAULT_DB_FILENAME
    return f"sqlite:///{db_path}"


def _expand_sqlite_url(url: str) -> str:
    """Expand `~` inside the path part of a `sqlite:///` URL."""
    if not url.startswith("sqlite:///"):
        return url
    raw_path = url[len("sqlite:///") :]
    expanded = os.path.expanduser(raw_path)
    return f"sqlite:///{expanded}"
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_bootstrap.py -v
```
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/bootstrap.py \
        packages/server/tests/test_db/test_bootstrap.py
git commit -m "feat(db): bootstrap helpers — openlia_home, ensure_dir, resolve_db_url"
```

---

## Task 5: Auth models (6 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/__init__.py`
- Create: `packages/server/src/openlia_server/db/models/auth.py`
- Create: `packages/server/tests/test_db/test_models_auth.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_auth.py`:

```python
"""Verifies the 6 auth tables in §3 of database-design.md:
  users, sessions, signup_invites, signup_policy, password_reset_requests, auth_events.

Every test uses Base.metadata.create_all against a tmp SQLite file — we are
not exercising Alembic here; Alembic's round-trip is tested in Task 10.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401 — registers models on Base.metadata

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_users_columns(create_tables, engine) -> None:
    from openlia_server.db.models.auth import User

    cols = {c.name: c for c in User.__table__.columns}
    expected = {
        "id", "email", "display_name", "password_hash", "is_admin", "is_disabled",
        "must_change_password", "created_at", "updated_at", "last_login_at",
        "failed_login_attempts", "locked_until",
    }
    assert set(cols.keys()) == expected
    assert cols["id"].primary_key
    assert cols["email"].unique is True
    assert cols["password_hash"].nullable is True
    assert cols["is_admin"].default.arg is False
    assert cols["failed_login_attempts"].default.arg == 0


def test_users_email_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id="u1", email="a@example.com", display_name="A"))
    db_session.add(User(id="u2", email="a@example.com", display_name="B"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_sessions_cascade_delete_on_user(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import Session as SessionModel, User

    u = User(id="u1", email="u1@example.com", display_name="U1")
    s = SessionModel(
        id="s1",
        user_id="u1",
        token_hash="a" * 64,
        last_seen_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=12),
    )
    db_session.add_all([u, s])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    assert db_session.execute(select(SessionModel)).scalar_one_or_none() is None


def test_auth_events_user_id_set_null_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import AuthEvent, User

    u = User(id="u1", email="u1@example.com", display_name="U1")
    ev = AuthEvent(id="e1", user_id="u1", event_type="login_success")
    db_session.add_all([u, ev])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    row = db_session.execute(select(AuthEvent)).scalar_one()
    assert row.user_id is None


def test_signup_invites_token_unique(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import SignupInvite

    db_session.add(SignupInvite(id="i1", token="tok-a"))
    db_session.add(SignupInvite(id="i2", token="tok-a"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_signup_policy_singleton_constraint(create_tables, db_session: Session) -> None:
    """CHECK (id = 1) — second row with a different id must be rejected."""
    from openlia_server.db.models.auth import SignupPolicy

    db_session.add(SignupPolicy(id=1, mode="closed"))
    db_session.commit()

    db_session.add(SignupPolicy(id=2, mode="invite_only"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_password_reset_requests_columns(create_tables) -> None:
    from openlia_server.db.models.auth import PasswordResetRequest

    cols = {c.name: c for c in PasswordResetRequest.__table__.columns}
    assert {"id", "user_id", "status", "requested_at", "requested_ip",
            "approved_by_user_id", "approved_at", "token_hash", "expires_at",
            "consumed_at"} <= set(cols.keys())
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_auth.py -v
```
Expected: FAIL — `openlia_server.db.models.auth` does not exist.

- [ ] **Step 3: Create the models package**

Create `packages/server/src/openlia_server/db/models/__init__.py`:

```python
"""SQLAlchemy models, grouped by database-design.md category.

Importing this package registers every model on Base.metadata, which is
what Alembic needs before running `upgrade head` or `autogenerate`.
"""

from openlia_server.db.models import auth, config, content, infrastructure  # noqa: F401

__all__ = ["auth", "config", "content", "infrastructure"]
```

(`config`, `content`, `infrastructure` submodules are created in Tasks 6-8 — this import will fail until then. Write the import anyway; Task 5 commits only `auth.py`, and the test file imports `openlia_server.db.models.auth` directly, bypassing this `__init__.py`.)

Actually — revise the plan: keep `__init__.py` minimal until all submodules exist. Write this placeholder now, fill it in Task 8:

```python
"""SQLAlchemy models, grouped by database-design.md category.

Each submodule below registers its models on Base.metadata. Importers
should `import openlia_server.db.models` — that loads every category so
`Base.metadata.tables` is complete.
"""
# Submodules registered as they are added. Full list completed in Task 8.
from openlia_server.db.models import auth  # noqa: F401

__all__ = ["auth"]
```

- [ ] **Step 4: Write the auth models**

Create `packages/server/src/openlia_server/db/models/auth.py`:

```python
"""Auth tables from database-design.md § 3.

Rows:
  users, sessions, signup_invites, signup_policy, password_reset_requests, auth_events.

Encryption/hashing notes:
  - password_hash is nullable `String(256)` — Plan 2 will populate it with
    Argon2id hashes. NULL for the personal-mode `local` row.
  - session.token_hash and password_reset.token_hash are SHA-256 hex
    (64 chars). Plan 2 wires up the hashing helpers.
  - signup_invite.token is stored in plaintext (bearer credential, looked
    up by value; protected by randomness + revocation).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_users_locked_until", "locked_until"),)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sessions_user_id", "user_id"),
        Index("ix_sessions_expires_at", "expires_at"),
    )


class SignupInvite(Base, TimestampMixin):
    __tablename__ = "signup_invites"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    # 2026-04-24 amendment: shipped as `token_hash` (SHA-256 hex of the opaque
    # bearer token). Raw token is handed to the creator once on issuance and
    # never persisted. Migration `2026-04-20-0001_add_signup_invites_token.py`
    # introduced `token_hash` alongside `token`; migration
    # `2026-04-22-2000_drop_signup_invite_raw_token.py` dropped the plaintext
    # `token` column. See `database-design.md` §3 `signup_invites` and §5
    # "Non-encrypted credential columns" for the final shape.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SignupPolicy(Base):
    """Singleton row (CHECK id = 1). Seeded by the wizard on completion."""

    __tablename__ = "signup_policy"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=False
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_email_domains: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=__import__("sqlalchemy").func.now(),
        onupdate=__import__("sqlalchemy").func.now(),
    )
    updated_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )
    requested_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approved_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_password_reset_requests_user_status", "user_id", "status"),
    )


class AuthEvent(Base):
    """Append-only audit log. No updated_at — rows are immutable."""

    __tablename__ = "auth_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=__import__("sqlalchemy").func.now()
    )

    __table_args__ = (
        Index("ix_auth_events_user_id_created_at", "user_id", "created_at"),
        Index("ix_auth_events_event_type_created_at", "event_type", "created_at"),
    )
```

Note: the `__import__("sqlalchemy").func.now()` pattern is a lint-free way to reference `func.now()` where we can't use the top-level `from sqlalchemy import func` import (keeps the module header strict). Alternative: just `from sqlalchemy import func` at top and use `func.now()`. Prefer that — cleaner. **Replace every `__import__("sqlalchemy").func.now()` occurrence with `func.now()`** and add `func` to the `from sqlalchemy import ...` line. The implementer should make this substitution when writing the file.

- [ ] **Step 5: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_auth.py -v
```
Expected: 7 tests pass.

- [ ] **Step 6: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/models/auth.py \
                  packages/server/src/openlia_server/db/models/__init__.py
uv run ruff format --check packages/server/src/openlia_server/db/models/
```
Expected: no findings. If format fails, run `uv run ruff format packages/server/src/openlia_server/db/models/`.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/src/openlia_server/db/models/auth.py \
        packages/server/tests/test_db/test_models_auth.py
git commit -m "feat(db): add 6 auth models (users, sessions, invites, policy, resets, events)"
```

---

## Task 6: Config models (6 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/config.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`
- Create: `packages/server/tests/test_db/test_models_config.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_config.py`:

```python
"""Verifies the 6 config tables in §4 of database-design.md:
  llm_providers, llm_models, user_llm_preferences,
  data_providers, data_provider_requirement_mapping, web_search_providers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401
    import openlia_server.db.models.config  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_llm_providers_columns(create_tables) -> None:
    from openlia_server.db.models.config import LLMProvider

    cols = {c.name for c in LLMProvider.__table__.columns}
    assert cols == {
        "id", "kind", "label", "api_key_encrypted", "env_var_name", "base_url",
        "extra_config", "is_enabled", "created_at", "updated_at", "created_by_user_id",
    }


def test_llm_models_tier_default_partial_unique(create_tables, db_session: Session) -> None:
    """At most one is_tier_default=true per tier (partial unique index)."""
    from openlia_server.db.models.config import LLMModel, LLMProvider

    p = LLMProvider(id="p1", kind="openai", label="p")
    db_session.add(p)
    db_session.commit()

    db_session.add(LLMModel(id="m1", provider_id="p1", tier="thinking",
                            model_ref="a", display_name="A", is_tier_default=True))
    db_session.commit()
    db_session.add(LLMModel(id="m2", provider_id="p1", tier="thinking",
                            model_ref="b", display_name="B", is_tier_default=True))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_user_llm_preferences_composite_pk(create_tables) -> None:
    from openlia_server.db.models.config import UserLLMPreference

    pk_cols = {c.name for c in UserLLMPreference.__table__.primary_key}
    assert pk_cols == {"user_id", "tier"}


def test_data_provider_requirement_mapping_composite_pk(create_tables) -> None:
    from openlia_server.db.models.config import DataProviderRequirementMapping

    pk_cols = {c.name for c in DataProviderRequirementMapping.__table__.primary_key}
    assert pk_cols == {"requirement_type", "provider_id"}


def test_web_search_providers_priority_default(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.config import WebSearchProvider

    p = WebSearchProvider(id="w1", kind="brave", label="Brave")
    db_session.add(p)
    db_session.commit()
    db_session.refresh(p)
    assert p.priority == 100
    assert p.is_enabled is True


def test_llm_model_provider_restrict_delete(create_tables, db_session: Session) -> None:
    """Deleting a provider with attached models must raise (ON DELETE RESTRICT)."""
    from openlia_server.db.models.config import LLMModel, LLMProvider

    p = LLMProvider(id="p1", kind="openai", label="p")
    m = LLMModel(id="m1", provider_id="p1", tier="thinking", model_ref="a", display_name="A")
    db_session.add_all([p, m])
    db_session.commit()

    db_session.delete(p)
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_config.py -v
```
Expected: FAIL — `openlia_server.db.models.config` does not exist.

- [ ] **Step 3: Write the config models**

Create `packages/server/src/openlia_server/db/models/config.py`:

```python
"""LLM + data + web search provider config tables (database-design.md § 4).

Rows:
  llm_providers, llm_models, user_llm_preferences,
  data_providers, data_provider_requirement_mapping, web_search_providers.

Column notes:
  - api_key_encrypted is `Text` holding base64(nonce(12) || ciphertext || tag(16)).
    Plan 2 installs the encryption helpers; this plan only defines the column.
  - llm_models has a partial unique index on `tier` filtered by
    is_tier_default=true (SQLite 3.8+ supports partial indexes natively).
  - llm_models.provider_id uses ondelete=RESTRICT so providers with attached
    models cannot be orphan-deleted.
  - user_llm_preferences and data_provider_requirement_mapping both use
    composite primary keys (no surrogate id column).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class LLMProvider(Base, TimestampMixin):
    __tablename__ = "llm_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_llm_providers_kind", "kind"),
        Index("ix_llm_providers_is_enabled", "is_enabled"),
    )


class LLMModel(Base, TimestampMixin):
    __tablename__ = "llm_models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_providers.id", ondelete="RESTRICT"), nullable=False
    )
    tier: Mapped[str] = mapped_column(String(16), nullable=False)
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    is_tier_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overrides: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_llm_models_tier_is_enabled", "tier", "is_enabled"),
        Index("ix_llm_models_provider_id", "provider_id"),
        Index(
            "uq_llm_models_tier_default",
            "tier",
            unique=True,
            sqlite_where=mapped_column("is_tier_default", Boolean).__clause_element__() == True,  # noqa: E712
        ),
    )
```

**Reviewer note on the partial index:** the `Index(..., sqlite_where=...)` form is the canonical SQLAlchemy 2.x way to express a partial unique index. The implementer should write it as:

```python
Index(
    "uq_llm_models_tier_default",
    "tier",
    unique=True,
    sqlite_where=text("is_tier_default = 1"),
)
```

(`from sqlalchemy import text` — simpler and doesn't invent throwaway columns). Use this form; the template above is illustrative only.

Continue `config.py`:

```python
class UserLLMPreference(Base):
    __tablename__ = "user_llm_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa_func_timestamp := None,  # placeholder
    )
```

**Correction:** the `placeholder` mapped_column is illustrative garbage — implementer should write this properly:

```python
class UserLLMPreference(Base):
    __tablename__ = "user_llm_preferences"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    tier: Mapped[str] = mapped_column(String(16), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

(import `DateTime` in this file's `from sqlalchemy import ...` line.)

Continue:

```python
class DataProvider(Base, TimestampMixin):
    __tablename__ = "data_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    extra_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_data_providers_kind", "kind"),
        Index("ix_data_providers_is_enabled", "is_enabled"),
    )


class DataProviderRequirementMapping(Base):
    __tablename__ = "data_provider_requirement_mapping"

    requirement_type: Mapped[str] = mapped_column(String(64), primary_key=True)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("data_providers.id", ondelete="CASCADE"), primary_key=True
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WebSearchProvider(Base, TimestampMixin):
    __tablename__ = "web_search_providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    env_var_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    __table_args__ = (
        Index("ix_web_search_providers_is_enabled_priority", "is_enabled", "priority"),
    )
```

Update `packages/server/src/openlia_server/db/models/__init__.py`:

```python
"""SQLAlchemy models, grouped by database-design.md category."""

from openlia_server.db.models import auth, config  # noqa: F401

__all__ = ["auth", "config"]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_config.py -v
```
Expected: 6 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/models/config.py
uv run ruff format --check packages/server/src/openlia_server/db/models/
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/config.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/test_db/test_models_config.py
git commit -m "feat(db): add 6 config models (llm/data/web-search providers + mappings)"
```

---

## Task 7: Content models (8 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/content.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`
- Create: `packages/server/tests/test_db/test_models_content.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_content.py`:

```python
"""Verifies the 8 content tables in §6 of database-design.md:
  chat_sessions, chat_messages, chat_attachments, reports, report_versions,
  portfolio_holdings, watchlists, watchlist_items.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.auth  # noqa: F401
    import openlia_server.db.models.config  # noqa: F401
    import openlia_server.db.models.content  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_chat_message_cascade_from_session(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import ChatMessage, ChatSession

    u = User(id="u1", email="u1@example.com", display_name="U1")
    cs = ChatSession(id="cs1", user_id="u1", department="secretary")
    msg = ChatMessage(id="m1", session_id="cs1", role="user", content="hi")
    db_session.add_all([u, cs, msg])
    db_session.commit()

    db_session.delete(cs)
    db_session.commit()
    assert db_session.execute(select(ChatMessage)).scalar_one_or_none() is None


def test_report_user_id_set_null_on_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1", user_id="u1", department="equity_research",
        report_type="stock_update", title="AAPL Update",
        content_markdown="# AAPL", content_structured={},
        model_ref="gpt-4o",
    )
    db_session.add_all([u, r])
    db_session.commit()

    db_session.delete(u)
    db_session.commit()

    row = db_session.execute(select(Report)).scalar_one()
    assert row.user_id is None


def test_report_version_unique_per_report(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report, ReportVersion

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1", user_id="u1", department="equity_research",
        report_type="stock_update", title="t",
        content_markdown="m", content_structured={}, model_ref="m",
    )
    v1 = ReportVersion(id="v1", report_id="r1", version_number=1,
                      content_markdown="m", content_structured={})
    v2 = ReportVersion(id="v2", report_id="r1", version_number=1,
                      content_markdown="m", content_structured={})
    db_session.add_all([u, r, v1, v2])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_portfolio_unique_user_ticker(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    u = User(id="u1", email="u1@example.com", display_name="U1")
    h1 = PortfolioHolding(id="h1", user_id="u1", ticker="AAPL")
    h2 = PortfolioHolding(id="h2", user_id="u1", ticker="AAPL")
    db_session.add_all([u, h1, h2])
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_item_composite_pk(create_tables) -> None:
    from openlia_server.db.models.content import WatchlistItem

    pk_cols = {c.name for c in WatchlistItem.__table__.primary_key}
    assert pk_cols == {"watchlist_id", "ticker"}


def test_chat_session_indexes(create_tables) -> None:
    from openlia_server.db.models.content import ChatSession

    idx_names = {i.name for i in ChatSession.__table__.indexes}
    assert "ix_chat_sessions_user_id_department" in idx_names
    assert "ix_chat_sessions_user_id_updated_at" in idx_names


def test_numeric_columns_use_decimal(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    u = User(id="u1", email="u1@example.com", display_name="U1")
    h = PortfolioHolding(
        id="h1", user_id="u1", ticker="AAPL",
        shares=Decimal("100.5"), cost_basis=Decimal("150.25"),
    )
    db_session.add_all([u, h])
    db_session.commit()
    db_session.refresh(h)
    assert h.shares == Decimal("100.5")


def test_tags_default_empty_list(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report

    u = User(id="u1", email="u1@example.com", display_name="U1")
    r = Report(
        id="r1", user_id="u1", department="equity_research",
        report_type="stock_update", title="t",
        content_markdown="m", content_structured={}, model_ref="m",
    )
    db_session.add_all([u, r])
    db_session.commit()
    db_session.refresh(r)
    assert r.tags == []
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_content.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the content models**

Create `packages/server/src/openlia_server/db/models/content.py`:

```python
"""Chat + reports + portfolio tables (database-design.md § 6).

Rows:
  chat_sessions, chat_messages, chat_attachments,
  reports, report_versions,
  portfolio_holdings, watchlists, watchlist_items.

Notes:
  - chat_messages is append-only (no updated_at).
  - reports.user_id uses SET NULL because reports outlive their author in
    company mode.
  - report_versions has a unique (report_id, version_number) constraint.
  - portfolio_holdings uses Numeric(18, 6) for shares and cost_basis — never
    Float for monetary values.
  - watchlist_items uses a composite PK (no surrogate id).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, TimestampMixin


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_chat_sessions_user_id_department", "user_id", "department"),
        Index("ix_chat_sessions_user_id_updated_at", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_chat_messages_session_id_created_at", "session_id", "created_at"),
    )


class ChatAttachment(Base):
    __tablename__ = "chat_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chat_messages.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (Index("ix_chat_attachments_message_id", "message_id"),)


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    department: Mapped[str] = mapped_column(String(32), nullable=False)
    report_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_structured: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    token_usage: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    generation_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_starred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        Index("ix_reports_user_id_department", "user_id", "department"),
        Index("ix_reports_user_id_created_at", "user_id", "created_at"),
        Index("ix_reports_subject", "subject"),
        Index("ix_reports_report_type", "report_type"),
    )


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    report_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_structured: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("report_id", "version_number", name="uq_report_versions_report_id_version_number"),
    )


class PortfolioHolding(Base):
    __tablename__ = "portfolio_holdings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    shares: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_portfolio_holdings_user_id_ticker"),
    )


class Watchlist(Base, TimestampMixin):
    __tablename__ = "watchlists"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_id_name"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    watchlist_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("watchlists.id", ondelete="CASCADE"), primary_key=True
    )
    ticker: Mapped[str] = mapped_column(String(16), primary_key=True)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

Update `packages/server/src/openlia_server/db/models/__init__.py`:

```python
"""SQLAlchemy models, grouped by database-design.md category."""

from openlia_server.db.models import auth, config, content  # noqa: F401

__all__ = ["auth", "config", "content"]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_content.py -v
```
Expected: 8 tests pass.

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/models/
uv run ruff format --check packages/server/src/openlia_server/db/models/
```
Expected: no findings.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/content.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/test_db/test_models_content.py
git commit -m "feat(db): add 8 content models (chat, reports, portfolio, watchlists)"
```

---

## Task 8: Infrastructure models (2 tables)

**Files:**
- Create: `packages/server/src/openlia_server/db/models/infrastructure.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`
- Create: `packages/server/tests/test_db/test_models_infrastructure.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_models_infrastructure.py`:

```python
"""Verifies the 2 infrastructure tables in §7 of database-design.md:
  wizard_state (singleton), config_store (KV escape hatch).
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    from openlia_server.db.base import Base
    import openlia_server.db.models.infrastructure  # noqa: F401

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_wizard_state_singleton(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import WizardState

    db_session.add(WizardState(id=1))
    db_session.commit()

    db_session.add(WizardState(id=2))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_wizard_state_defaults(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import WizardState

    w = WizardState(id=1)
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)

    assert w.status == "not_started"
    assert w.current_step == 1
    assert w.step_data == {}


def test_config_store_roundtrip(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    row = ConfigStore(key="wizard.completed", value=False)
    db_session.add(row)
    db_session.commit()

    db_session.refresh(row)
    assert row.value is False
    assert row.key == "wizard.completed"


def test_config_store_key_primary(create_tables) -> None:
    from openlia_server.db.models.infrastructure import ConfigStore

    pk_cols = {c.name for c in ConfigStore.__table__.primary_key}
    assert pk_cols == {"key"}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_infrastructure.py -v
```
Expected: FAIL — module does not exist.

- [ ] **Step 3: Write the infrastructure models**

Create `packages/server/src/openlia_server/db/models/infrastructure.py`:

```python
"""Setup wizard state + KV escape hatch (database-design.md § 7).

Rows:
  wizard_state — singleton, CHECK(id = 1).
  config_store — narrow KV with dotted keys (`wizard.completed`, ...).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class WizardState(Base):
    __tablename__ = "wizard_state"

    # 2026-04-24 amendment: shape finalized by Plan 10 (setup wizard). The
    # original Plan 1a shape (`current_step: Integer default=1`) was reshaped
    # by migration `2026-04-21-0001_reshape_wizard_state.py` to a String-valued
    # step slug plus `completed_steps` (JSON list) and `active_session_token`
    # (SHA-256 hex). Migration `2026-04-22-1800_drop_wizard_state_legacy_columns.py`
    # then removed the vestigial integer column. The listing below is the
    # Plan 1a baseline shape for historical reference; the as-shipped ORM lives
    # in `infrastructure.py` and matches Plan 10's final form. See
    # `database-design.md` §7 `wizard_state` for the authoritative columns.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_started")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    step_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (CheckConstraint("id = 1", name="singleton"),)


class ConfigStore(Base):
    __tablename__ = "config_store"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

Update `packages/server/src/openlia_server/db/models/__init__.py` to its final form:

```python
"""SQLAlchemy models for the server.

Importing this package registers every model on Base.metadata. Alembic's
`env.py` and the bootstrap routine rely on this side effect.
"""

from openlia_server.db.models import auth, config, content, infrastructure  # noqa: F401

__all__ = ["auth", "config", "content", "infrastructure"]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_models_infrastructure.py -v
```
Expected: 4 tests pass.

- [ ] **Step 5: Full model-layer regression**

Run the entire test_db suite to make sure no model file accidentally broke a prior one:
```bash
uv run pytest packages/server/tests/test_db/ -v
```
Expected: all tests pass (session + bootstrap + auth + config + content + infrastructure — roughly 32 tests).

- [ ] **Step 6: Ruff check full models package**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/
uv run ruff format --check packages/server/src/openlia_server/db/
```
Expected: no findings.

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/models/infrastructure.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/test_db/test_models_infrastructure.py
git commit -m "feat(db): add 2 infrastructure models (wizard_state, config_store)"
```

---

## Task 9: Alembic scaffold — env.py, script template, alembic.ini

**Files:**
- Create: `packages/server/alembic.ini`
- Create: `packages/server/src/openlia_server/db/migrations/env.py`
- Create: `packages/server/src/openlia_server/db/migrations/script.py.mako`
- Create: `packages/server/src/openlia_server/db/migrations/versions/.gitkeep`
- Create: `packages/server/tests/test_db/test_migrations.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_db/test_migrations.py`:

```python
"""Exercises Alembic scaffold + baseline migration.

The baseline migration itself is created in Task 10. Task 9's scaffold
test only asserts env.py can load without error."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def test_alembic_env_loads(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`alembic current` must not crash against an empty DB. It prints nothing
    when no migrations have run yet."""
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/empty.db")

    repo_root = Path(__file__).resolve().parents[3]  # packages/server
    result = subprocess.run(
        ["uv", "run", "alembic", "current"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}\nstdout: {result.stdout}"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: FAIL — `alembic.ini` / `env.py` missing, `alembic current` exits nonzero.

- [ ] **Step 3: Write `alembic.ini`**

Create `packages/server/alembic.ini`:

```ini
# Alembic configuration for the OpenLIA server package.
# Invoked from `packages/server/` — `script_location` is relative to this file.

[alembic]
script_location = src/openlia_server/db/migrations
prepend_sys_path = src
file_template = %%(year)d-%%(month).2d-%%(day).2d-%%(hour).2d%%(minute).2d_%%(slug)s
timezone = UTC
# sqlalchemy.url is read from env.py, not from here.
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 4: Write `env.py`**

Create `packages/server/src/openlia_server/db/migrations/env.py`:

```python
"""Alembic migration environment.

Reads the DB URL from `OPENLIA_DB_URL` (or the default from
`openlia_server.db.bootstrap.resolve_db_url()`) and binds metadata from
the server's models package.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from openlia_server.db import bootstrap
from openlia_server.db.base import Base
import openlia_server.db.models  # noqa: F401 — registers every model

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _db_url() -> str:
    return bootstrap.resolve_db_url()


def run_migrations_offline() -> None:
    url = _db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite-safe ALTER TABLE
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _db_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 5: Write `script.py.mako`**

Create `packages/server/src/openlia_server/db/migrations/script.py.mako`:

```python
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Create the empty versions directory**

```bash
mkdir -p packages/server/src/openlia_server/db/migrations/versions
touch packages/server/src/openlia_server/db/migrations/versions/.gitkeep
```

- [ ] **Step 7: Run the test to confirm `alembic current` works**

Run:
```bash
cd packages/server && uv run alembic current
```
Expected: prints nothing (no migrations applied), exit code 0.

Run from repo root:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: 1 test passes.

- [ ] **Step 8: Commit**

```bash
git add packages/server/alembic.ini \
        packages/server/src/openlia_server/db/migrations/env.py \
        packages/server/src/openlia_server/db/migrations/script.py.mako \
        packages/server/src/openlia_server/db/migrations/versions/.gitkeep \
        packages/server/tests/test_db/test_migrations.py
git commit -m "feat(db): Alembic scaffold — env.py, alembic.ini, script template"
```

---

## Task 10: Baseline migration — create all 22 tables

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-16-1200_baseline.py`
  (**2026-04-24 amendment:** shipped as `2026-04-18-1609_baseline.py` with Alembic revision ID `01526cb27f5e`. The file contents match this task's spec; only the timestamp in the filename differs. Every downstream migration's `down_revision` already points to `01526cb27f5e`, so renaming the file would be a churn-for-no-gain change. References to `2026-04-16-1200_baseline.py` elsewhere in this plan should be read as "the Plan 1a baseline migration, shipped at `2026-04-18-1609_baseline.py`".)
- Modify: `packages/server/tests/test_db/test_migrations.py`

- [ ] **Step 1: Extend the test**

Replace `packages/server/tests/test_db/test_migrations.py` contents:

```python
"""Alembic round-trip: upgrade to head, then downgrade to base.

If the baseline migration is correct, a temp DB should have zero tables
after `downgrade base` (other than Alembic's own `alembic_version`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect


REPO_ROOT_SERVER = Path(__file__).resolve().parents[3]  # packages/server
EXPECTED_TABLES = {
    # Auth (6)
    "users", "sessions", "signup_invites", "signup_policy",
    "password_reset_requests", "auth_events",
    # Config (6)
    "llm_providers", "llm_models", "user_llm_preferences",
    "data_providers", "data_provider_requirement_mapping", "web_search_providers",
    # Content (8)
    "chat_sessions", "chat_messages", "chat_attachments",
    "reports", "report_versions",
    "portfolio_holdings", "watchlists", "watchlist_items",
    # Infrastructure (2)
    "wizard_state", "config_store",
}


def _run_alembic(args: list[str], db_url: str) -> subprocess.CompletedProcess:
    env = {"OPENLIA_DB_URL": db_url}
    import os
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=REPO_ROOT_SERVER,
        capture_output=True,
        text=True,
        env=merged,
        check=False,
    )


def test_alembic_env_loads(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/empty.db"
    result = _run_alembic(["current"], db_url)
    assert result.returncode == 0, result.stderr


def test_baseline_upgrade_creates_all_tables(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/upgrade.db"
    result = _run_alembic(["upgrade", "head"], db_url)
    assert result.returncode == 0, result.stderr

    eng = create_engine(db_url)
    inspector = inspect(eng)
    actual = set(inspector.get_table_names()) - {"alembic_version"}
    assert actual == EXPECTED_TABLES, (
        f"Missing: {EXPECTED_TABLES - actual}\nExtra: {actual - EXPECTED_TABLES}"
    )


def test_baseline_downgrade_drops_all_tables(tmp_path: Path) -> None:
    db_url = f"sqlite:///{tmp_path}/downgrade.db"
    up = _run_alembic(["upgrade", "head"], db_url)
    assert up.returncode == 0, up.stderr
    down = _run_alembic(["downgrade", "base"], db_url)
    assert down.returncode == 0, down.stderr

    eng = create_engine(db_url)
    inspector = inspect(eng)
    remaining = set(inspector.get_table_names()) - {"alembic_version"}
    assert remaining == set()


def test_baseline_is_idempotent(tmp_path: Path) -> None:
    """`alembic upgrade head` run twice should not error."""
    db_url = f"sqlite:///{tmp_path}/twice.db"
    r1 = _run_alembic(["upgrade", "head"], db_url)
    assert r1.returncode == 0, r1.stderr
    r2 = _run_alembic(["upgrade", "head"], db_url)
    assert r2.returncode == 0, r2.stderr
```

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: `test_baseline_upgrade_creates_all_tables` fails (no migration yet).

- [ ] **Step 3: Generate the baseline migration via autogenerate**

From `packages/server/`:
```bash
cd packages/server && uv run alembic revision --autogenerate -m "baseline"
```
This writes `packages/server/src/openlia_server/db/migrations/versions/<timestamp>_baseline.py`.

If the generated filename already matches the pattern `YYYY-MM-DD-HHMM_baseline.py` (it should, because of `file_template` in `alembic.ini`), keep it. If not, rename to today's timestamp: `2026-04-16-1200_baseline.py`.

Open the generated file and inspect the `upgrade()` body. Alembic may miss:

- **Partial unique index on `llm_models`** — must be expressed as `op.create_index('uq_llm_models_tier_default', 'llm_models', ['tier'], unique=True, sqlite_where=sa.text('is_tier_default = 1'))`.
- **CheckConstraints named `singleton`** on `wizard_state` and `signup_policy` — autogenerate sometimes omits `name=` on inline CHECKs. Verify they survive the round-trip by reading the generated file. If missing, add them by hand to the `op.create_table` args:
  ```python
  sa.CheckConstraint('id = 1', name='singleton'),
  ```
- **Enum-like default values** — autogenerate preserves `default=` from the model, so no manual fix needed.

Edit the migration file to add a file-level docstring:

```python
"""Baseline — 22 tables (auth, config, content, infrastructure).

See database-design.md for the canonical schema. Sections covered:
  §3 Auth (6), §4 Config (6), §6 Content (8), §7 Infrastructure (2).

Deferred to a later migration (Plan 1B):
  §7 Dashboard (7) + §7 Scheduler/Notifications (4).
"""
```

- [ ] **Step 4: Run the tests**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_migrations.py -v
```
Expected: 4 tests pass (env loads, upgrade creates all tables, downgrade drops all, upgrade twice is idempotent).

If `test_baseline_upgrade_creates_all_tables` fails with "Missing: {'xxx'}", inspect the migration and add the missing create_table op. If it fails with "Extra: {'xxx'}", a stale model registration is leaking; rerun the test with `-p no:cacheprovider` to rule out stale imports.

- [ ] **Step 5: Ruff format the generated migration**

Autogenerate formatting is hit-or-miss. Run:
```bash
uv run ruff format packages/server/src/openlia_server/db/migrations/versions/
uv run ruff check packages/server/src/openlia_server/db/migrations/versions/
```
Expected: clean. The migration is code-generated so trailing-comma / line-length warnings may appear — fix them.

- [ ] **Step 6: Run the full test_db suite**

Run:
```bash
uv run pytest packages/server/tests/test_db/ -v
```
Expected: every test still passes (~36 tests including migrations).

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/ \
        packages/server/tests/test_db/test_migrations.py
git commit -m "feat(db): baseline migration creating all 22 Plan 1A tables"
```

---

## Task 11: Startup bootstrap — auto-migrate + personal-mode seed + config_store seed

**Files:**
- Modify: `packages/server/src/openlia_server/db/bootstrap.py`
- Modify: `packages/server/src/openlia_server/db/__init__.py`
- Modify: `packages/server/tests/test_db/test_bootstrap.py`

- [ ] **Step 1: Extend `test_bootstrap.py`**

Append to `packages/server/tests/test_db/test_bootstrap.py`:

```python
def test_bootstrap_creates_local_user(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bootstrap() must seed the synthetic `local` user for personal mode."""
    from openlia_server.db import bootstrap, session as session_mod
    from openlia_server.db.models.auth import User

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/bootstrap.db")

    bootstrap.bootstrap()

    with session_mod.SessionLocal() as s:
        local = s.get(User, "local")
        assert local is not None
        assert local.email == "local@openlia.local"
        assert local.is_admin is True
        assert local.password_hash is None
        assert local.display_name == "Local"

    session_mod.dispose_engine()


def test_bootstrap_is_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Running bootstrap() twice must not duplicate the local user or
    re-seed config_store with different values."""
    from openlia_server.db import bootstrap, session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.infrastructure import ConfigStore

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/idempotent.db")

    bootstrap.bootstrap()
    with session_mod.SessionLocal() as s:
        first_instance_id = s.get(ConfigStore, "system.instance_id").value
    session_mod.dispose_engine()

    bootstrap.bootstrap()
    with session_mod.SessionLocal() as s:
        count = s.query(User).filter_by(id="local").count()
        assert count == 1
        second_instance_id = s.get(ConfigStore, "system.instance_id").value
    session_mod.dispose_engine()

    assert first_instance_id == second_instance_id  # stable across restarts


def test_bootstrap_seeds_config_store(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """bootstrap() must seed wizard.completed=false and system.instance_id."""
    from openlia_server.db import bootstrap, session as session_mod
    from openlia_server.db.models.infrastructure import ConfigStore

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/configstore.db")

    bootstrap.bootstrap()

    with session_mod.SessionLocal() as s:
        wc = s.get(ConfigStore, "wizard.completed")
        assert wc is not None
        assert wc.value is False

        iid = s.get(ConfigStore, "system.instance_id")
        assert iid is not None
        assert isinstance(iid.value, str)
        assert len(iid.value) == 36  # UUID4 string length

    session_mod.dispose_engine()


def test_bootstrap_runs_migrations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Against an empty DB, bootstrap() must run Alembic to head before
    seeding, so the seed INSERTs succeed."""
    from openlia_server.db import bootstrap
    from sqlalchemy import create_engine, inspect

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/fresh.db")

    bootstrap.bootstrap()

    eng = create_engine(f"sqlite:///{tmp_path}/fresh.db")
    table_names = set(inspect(eng).get_table_names())
    assert "users" in table_names
    assert "alembic_version" in table_names
```

- [ ] **Step 2: Run the tests to confirm they fail**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_bootstrap.py -v
```
Expected: the 4 new tests fail — `bootstrap.bootstrap` does not exist yet.

- [ ] **Step 3: Extend `bootstrap.py`**

Append to `packages/server/src/openlia_server/db/bootstrap.py`:

```python
import uuid
from pathlib import Path as _Path

from alembic import command as _alembic_command
from alembic.config import Config as _AlembicConfig

from openlia_server.db import session as _session_mod

LOCAL_USER_ID = "local"
LOCAL_USER_EMAIL = "local@openlia.local"
LOCAL_USER_DISPLAY_NAME = "Local"

_ALEMBIC_INI_PATH = _Path(__file__).resolve().parents[3] / "alembic.ini"


def bootstrap() -> None:
    """Server startup sequence.

    Run once by `openlia serve` before uvicorn starts:
      1. Ensure `~/.openlia/` exists.
      2. Configure the engine against the resolved DB URL.
      3. Run Alembic `upgrade head` (no-op if already at head).
      4. Seed the synthetic `local` user (idempotent).
      5. Seed `config_store` with `wizard.completed=false` and
         `system.instance_id=<uuid4>` (idempotent; preserves existing values).
    """
    ensure_openlia_dir()

    url = resolve_db_url()
    _session_mod.configure_engine(url)

    _run_alembic_upgrade(url)
    _seed_local_user()
    _seed_config_store()


def _run_alembic_upgrade(url: str) -> None:
    cfg = _AlembicConfig(str(_ALEMBIC_INI_PATH))
    cfg.set_main_option("sqlalchemy.url", url)
    _alembic_command.upgrade(cfg, "head")


def _seed_local_user() -> None:
    from openlia_server.db.models.auth import User

    with _session_mod.SessionLocal() as s:
        existing = s.get(User, LOCAL_USER_ID)
        if existing is not None:
            return
        s.add(
            User(
                id=LOCAL_USER_ID,
                email=LOCAL_USER_EMAIL,
                display_name=LOCAL_USER_DISPLAY_NAME,
                password_hash=None,
                is_admin=True,
                is_disabled=False,
                must_change_password=False,
            )
        )
        s.commit()


def _seed_config_store() -> None:
    """Seed the minimum KV rows bootstrap needs. Preserves pre-existing
    rows so re-running doesn't stomp operator overrides."""
    from openlia_server.db.models.infrastructure import ConfigStore

    defaults: dict[str, object] = {
        "wizard.completed": False,
        "system.instance_id": str(uuid.uuid4()),
    }

    with _session_mod.SessionLocal() as s:
        for key, default_value in defaults.items():
            existing = s.get(ConfigStore, key)
            if existing is not None:
                continue
            s.add(ConfigStore(key=key, value=default_value))
        s.commit()
```

Update `packages/server/src/openlia_server/db/__init__.py` to re-export `bootstrap`:

```python
"""Persistence layer for the OpenLIA server."""

from openlia_server.db.base import Base, TimestampMixin
from openlia_server.db.bootstrap import bootstrap
from openlia_server.db.session import (
    SessionLocal,
    configure_engine,
    dispose_engine,
    get_engine,
)

__all__ = [
    "Base",
    "SessionLocal",
    "TimestampMixin",
    "bootstrap",
    "configure_engine",
    "dispose_engine",
    "get_engine",
]
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run:
```bash
uv run pytest packages/server/tests/test_db/test_bootstrap.py -v
```
Expected: all 9 tests pass (5 original + 4 new).

- [ ] **Step 5: Ruff check**

Run:
```bash
uv run ruff check packages/server/src/openlia_server/db/
uv run ruff format --check packages/server/src/openlia_server/db/
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/bootstrap.py \
        packages/server/src/openlia_server/db/__init__.py \
        packages/server/tests/test_db/test_bootstrap.py
git commit -m "feat(db): bootstrap runs Alembic + seeds local user + config_store keys"
```

---

## Task 12: Wire bootstrap into `openlia serve`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli_bootstrap.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli_bootstrap.py`:

```python
"""`openlia serve` must run bootstrap() before handing off to uvicorn.

We can't actually start uvicorn in a test, so we patch `uvicorn.run` and
assert the order of operations.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


def test_serve_calls_bootstrap_before_uvicorn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/cli.db")

    from openlia_server.cli import app

    runner = CliRunner()

    with patch("openlia_server.cli.bootstrap") as mock_bootstrap, \
         patch("openlia_server.cli.uvicorn.run") as mock_uvicorn:
        mock_bootstrap.return_value = None
        result = runner.invoke(app, ["serve"])

    assert result.exit_code == 0, result.output
    mock_bootstrap.assert_called_once()
    mock_uvicorn.assert_called_once()
    # Order check: bootstrap was called before uvicorn.run
    assert (
        mock_bootstrap.call_args_list[0].kwargs == {}
        and mock_bootstrap.call_count == 1
    )


def test_serve_fails_loudly_if_bootstrap_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/broken.db")

    from openlia_server.cli import app

    runner = CliRunner()
    with patch("openlia_server.cli.bootstrap", side_effect=RuntimeError("boom")), \
         patch("openlia_server.cli.uvicorn.run") as mock_uvicorn:
        result = runner.invoke(app, ["serve"])

    assert result.exit_code != 0
    assert "boom" in (result.output + str(result.exception))
    mock_uvicorn.assert_not_called()
```

Dependency note: `CliRunner` comes from `typer.testing`. No new package needed.

- [ ] **Step 2: Run the test to confirm it fails**

Run:
```bash
uv run pytest packages/server/tests/test_cli_bootstrap.py -v
```
Expected: FAIL — `openlia_server.cli.bootstrap` does not exist (cli.py hasn't imported it yet).

- [ ] **Step 3: Modify `cli.py`**

Read the current `packages/server/src/openlia_server/cli.py`, then update the `serve` body to call bootstrap first. The full file after edit:

```python
"""Typer CLI entry point. Registered as the `openlia` console script."""

import typer
import uvicorn

from openlia_server.db import bootstrap

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Force Typer into multi-command mode so `serve` shows as a named subcommand."""


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development)."),
) -> None:
    """Start the OpenLIA HTTP server.

    Runs DB bootstrap (directory + migrations + local-user seed) before
    handing off to uvicorn.
    """
    bootstrap()

    uvicorn.run(
        "openlia_server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def main() -> None:
    """Console-script entry point."""
    app()
```

- [ ] **Step 4: Run the test to confirm it passes**

Run:
```bash
uv run pytest packages/server/tests/test_cli_bootstrap.py -v
```
Expected: 2 tests pass.

- [ ] **Step 5: Regression — full suite green**

Run:
```bash
uv run pytest -v
```
Expected: all tests pass (Phase 0's 8 + Plan 1A's ~38 = ~46).

- [ ] **Step 6: Smoke test against a real temp DB**

Run:
```bash
OPENLIA_DB_URL="sqlite:///$(mktemp -d)/openlia.db" uv run openlia serve --port 18001 &
SERVER_PID=$!
sleep 2
curl -sf http://127.0.0.1:18001/health
kill $SERVER_PID
wait $SERVER_PID 2>/dev/null || true
```
Expected: `{"status":"ok"}` printed, no tracebacks. The server's startup log shows "alembic.runtime.migration" lines confirming migration ran.

- [ ] **Step 7: Ruff check**

Run:
```bash
uv run ruff check packages/server/
uv run ruff format --check packages/server/
```
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli_bootstrap.py
git commit -m "feat(server): serve runs db.bootstrap() before uvicorn"
```

---

## Task 13: Acceptance — full plan green, documentation updates

**Files:**
- Modify: `planning/implementation-plans/README.md` (status row for Plan 1A → Draft, file column filled).

- [ ] **Step 1: Run the full test suite**

Run:
```bash
uv run pytest -v
```
Expected: all pass (8 Phase 0 + 40+ Plan 1A).

- [ ] **Step 2: Run lint + format**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
```
Expected: clean.

- [ ] **Step 3: End-to-end acceptance check**

Run every piece in order:

```bash
# 1. Fresh DB from scratch
rm -rf /tmp/openlia-accept && mkdir /tmp/openlia-accept
export OPENLIA_DB_URL="sqlite:///tmp/openlia-accept/openlia.db"
export HOME=/tmp/openlia-accept

# 2. Bootstrap runs via serve
uv run openlia serve --port 18002 &
SERVER_PID=$!
sleep 2

# 3. /health returns 200
curl -sf http://127.0.0.1:18002/health
echo

# 4. DB has the expected tables
uv run python -c "
from sqlalchemy import create_engine, inspect
e = create_engine('${OPENLIA_DB_URL}')
tables = set(inspect(e).get_table_names()) - {'alembic_version'}
expected = {'users','sessions','signup_invites','signup_policy','password_reset_requests','auth_events','llm_providers','llm_models','user_llm_preferences','data_providers','data_provider_requirement_mapping','web_search_providers','chat_sessions','chat_messages','chat_attachments','reports','report_versions','portfolio_holdings','watchlists','watchlist_items','wizard_state','config_store'}
assert tables == expected, f'missing={expected-tables} extra={tables-expected}'
print(f'OK: {len(tables)} tables')
"

# 5. local user exists
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openlia_server.db.models.auth import User
e = create_engine('${OPENLIA_DB_URL}')
with Session(e) as s:
    u = s.get(User, 'local')
    assert u and u.is_admin and u.password_hash is None
    print(f'OK: local user id={u.id} admin={u.is_admin}')
"

# 6. config_store seeded
uv run python -c "
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from openlia_server.db.models.infrastructure import ConfigStore
e = create_engine('${OPENLIA_DB_URL}')
with Session(e) as s:
    wc = s.get(ConfigStore, 'wizard.completed').value
    iid = s.get(ConfigStore, 'system.instance_id').value
    assert wc is False and len(iid) == 36
    print(f'OK: wizard.completed={wc} instance_id={iid[:8]}...')
"

# 7. Restart and confirm idempotency
kill $SERVER_PID; wait $SERVER_PID 2>/dev/null || true
uv run openlia serve --port 18002 &
SERVER_PID=$!
sleep 2
curl -sf http://127.0.0.1:18002/health
echo
kill $SERVER_PID; wait $SERVER_PID 2>/dev/null || true

unset OPENLIA_DB_URL HOME
```

Expected output (in order):
- `{"status":"ok"}`
- `OK: 22 tables`
- `OK: local user id=local admin=True`
- `OK: wizard.completed=False instance_id=xxxxxxxx...`
- `{"status":"ok"}` (second time — proves idempotent restart)

If any line fails, stop and fix before continuing.

- [ ] **Step 4: Update the roadmap README**

Edit `planning/implementation-plans/README.md`.

In the status table, replace the Plan 1 row:
```
| 1 | 1 | Database baseline | Not started | — |
```
with two rows (Plan 1A done-when-executed, Plan 1B still to be written):
```
| 1A | 1 | Database baseline — infrastructure + auth/config/content/infra tables | Draft | `2026-04-16-phase-1a-database-baseline.md` |
| 1B | 1 | Database baseline — dashboards/scheduler/notifications tables | Not started | — |
```

Under "Phase 1 — Persistence foundation", replace the "### Plan 1 — Database baseline" section with:

```markdown
### Plan 1A — Database baseline (infrastructure + auth/config/content/infra)

- **Spec:** `planning/specs/systems/database-design.md` (sections 1–6, 8, 9, plus §7 rows `wizard_state` + `config_store`)
- **Scope:** SQLAlchemy 2.x models for 22 tables, Alembic baseline migration, `openlia_server/db/session.py` + engine factory with SQLite WAL mode, `~/.openlia/` bootstrap, DB path resolution (env override + default), auto-migrate on `openlia serve` startup, personal-mode `local` user seed, initial `config_store` seed.
- **Depends on:** Phase 0.
- **Unblocks:** Plans 2, 3, 4, 5.

### Plan 1B — Database baseline (dashboards/scheduler/notifications)

- **Spec:** `planning/specs/systems/database-design.md` (§7 dashboard + scheduler + notification rows).
- **Scope:** 11 remaining tables — `pt_user_configs`, `pt_presets`, `mr_dashboard_state`, `mr_assessment_cache`, `rs_user_config`, `rs_snapshots`, `fe_saved_formulas`, `mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications`. Second Alembic migration on top of Plan 1A's baseline. Seed shipped `pt_presets` library.
- **Depends on:** Plan 1A.
- **Unblocks:** Plan 6 (scheduling), Plan 8 (frontend notifications endpoint), Plans 17–20 (dashboards + formula engine).
```

- [ ] **Step 5: Commit**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plans): mark Plan 1A Draft, split 1A/1B rows, link plan file"
```

---

## Acceptance criteria

A reviewer should verify every box is checked:

- [ ] `uv sync --all-packages` clean.
- [ ] `uv run pytest -v` — all ~46 tests pass (Phase 0 + Plan 1A).
- [ ] `uv run ruff check .` clean.
- [ ] `uv run ruff format --check .` clean.
- [ ] `uv run openlia serve` launches, `/health` returns `{"status":"ok"}`.
- [ ] Against a fresh `OPENLIA_DB_URL`, post-serve DB has exactly 22 application tables + `alembic_version`.
- [ ] `users` has one row: `id='local'`, `is_admin=true`, `password_hash=None`, `email='local@openlia.local'`.
- [ ] `config_store` has `wizard.completed=false` and `system.instance_id=<uuid4>`.
- [ ] Restarting `openlia serve` against the same DB: no duplicate rows, `system.instance_id` unchanged.
- [ ] `cd packages/server && uv run alembic downgrade base && uv run alembic upgrade head` round-trips cleanly.
- [ ] SQLite PRAGMAs visible on a live connection: `journal_mode=wal`, `foreign_keys=1`, `synchronous=1`, `busy_timeout=5000`.
- [ ] CI workflow from Phase 0 still green (no updates needed for Plan 1A — `uv sync --all-packages` already picks up the new deps).

---

## Self-review notes (for the plan author)

**Spec coverage** — every §3, §4, §6, and §7-infrastructure row from `database-design.md` is implemented in Tasks 5–8. Deferred to 1B: §7 dashboard (7 tables) + scheduler/notification (4 tables). §5 (secrets) is represented by the column shapes only; encryption is Plan 2's job. §2 pragmas are verified in Task 3. §8 env vars: `OPENLIA_DB_URL` honored; `OPENLIA_SECRET_KEY` and the cookie/proxy vars are Plan 2 and beyond.

**Type consistency** — names used across tasks (`User`, `Session`, `SignupInvite`, `ChatSession`, `ChatMessage`, `Report`, etc.) are defined in the task that first introduces them and referenced by the same name in subsequent tasks. `bootstrap()` is the single public entry point.

**TDD discipline** — every task writes the failing test first, then the implementation, then re-runs the test. Commits are one-per-task.

**No placeholders** — every step contains actual code or an actual command. Two spots in Task 5 and Task 6 explicitly flag a pattern substitution for the implementer (`__import__("sqlalchemy").func.now()` → `func.now()` and the partial-index `sqlite_where=...` form); treat these as instructions, not as unfinished code.
