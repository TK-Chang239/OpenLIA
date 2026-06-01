"""First-run database bootstrap for `openlia serve` and the CLI.

Responsibilities (in order):

1. Ensure `$OPENLIA_HOME` (default `~/.openlia/`) exists.
2. Configure the SQLAlchemy engine against the resolved DB URL.
3. Run Alembic `upgrade head` (no-op if already at head).
4. Seed the synthetic local user (idempotent).
5. Seed the `config_store` with `wizard.completed=false` and
   `system.instance_id` (idempotent).

Out of scope here: seeding `signup_policy`. That row is owned by the setup
wizard's completion handler (`services.wizard.finalize`) and the Plan 10
invite flow; Plan 1a deliberately does not reach into `services.auth` from
this module to keep the layering contract intact. See
`planning/specs/systems/database-design.md` §3 `signup_policy` and the Plan
1a fix plan P0-1a-04 for history.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from alembic import command as _alembic_command
from alembic.config import Config as _AlembicConfig

DEFAULT_DB_FILENAME = "openlia.db"
OPENLIA_DIR_NAME = ".openlia"


def openlia_home() -> Path:
    env_home = os.environ.get("OPENLIA_HOME")
    if env_home:
        return Path(env_home)
    return Path(os.path.expanduser("~")) / OPENLIA_DIR_NAME


def ensure_openlia_dir() -> Path:
    path = openlia_home()
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    return path


def resolve_db_url() -> str:
    env = os.environ.get("OPENLIA_DB_URL")
    if env:
        return _expand_sqlite_url(env)

    db_path = openlia_home() / DEFAULT_DB_FILENAME
    return f"sqlite:///{db_path}"


def _expand_sqlite_url(url: str) -> str:
    if not url.startswith("sqlite:///"):
        return url
    raw_path = url[len("sqlite:///") :]
    expanded = os.path.expanduser(raw_path)
    return f"sqlite:///{expanded}"


LOCAL_USER_ID = "local"
LOCAL_USER_EMAIL = "local@openlia.local"
LOCAL_USER_DISPLAY_NAME = "Local"

_ALEMBIC_INI_PATH = Path(__file__).resolve().parents[3] / "alembic.ini"


def bootstrap() -> None:
    """Run the Plan 1a startup sequence (see module docstring)."""
    from openlia_server.db import secrets_crypto as _secrets_crypto
    from openlia_server.db import session as _session_mod

    ensure_openlia_dir()
    _secrets_crypto.ensure_key_available()

    url = resolve_db_url()
    _session_mod.configure_engine(url)

    _run_alembic_upgrade(url)
    _seed_local_user()
    _seed_config_store()


def _run_alembic_upgrade(url: str) -> None:
    cfg = _AlembicConfig(str(_ALEMBIC_INI_PATH))
    cfg.set_main_option("sqlalchemy.url", url)
    # `script_location` is set via `%(here)s` in alembic.ini, so no override
    # is needed here — both the CLI and this in-process runner resolve to the
    # same migrations directory.
    _alembic_command.upgrade(cfg, "head")


def _seed_local_user() -> None:
    from openlia_server.db import session as _session_mod
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
    from openlia_server.db import session as _session_mod
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
