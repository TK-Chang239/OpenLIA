from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_FILENAME = "openlia.db"
OPENLIA_DIR_NAME = ".openlia"


def openlia_home() -> Path:
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
    raw_path = url[len("sqlite:///"):]
    expanded = os.path.expanduser(raw_path)
    return f"sqlite:///{expanded}"
