"""Per-connector grounding clone orchestration.

Owns the lifecycle of `<openlia_home>/connector_repos/<id>/`:
- `ensure_clone`: create the clone if it doesn't exist; no-op when present.
- `resync_clone`: blow away and recreate (use when the URL/revision changes
  or the user clicks Refresh).
- `path_for`: where the clone lives (or would live) for a given connector.

The agentic resolver reads files under that directory; this service is the
only thing that creates or removes it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from openlia_server.db.bootstrap import openlia_home
from openlia_server.db.models.connectors import Connector
from openlia_server.services.grounding_clone import (
    GroundingCloneError,
    clone_repo,
    delete_clone,
)

log = logging.getLogger(__name__)

_CLONES_DIR_NAME = "connector_repos"


def _clones_root() -> Path:
    """Where all connector clones live. Patched in tests."""
    return openlia_home() / _CLONES_DIR_NAME


def path_for(connector_id: str) -> Path:
    return _clones_root() / connector_id


def _set_failed(session: Session, conn: Connector, msg: str) -> None:
    conn.grounding_status = "failed"
    conn.grounding_fetched_at = datetime.now(UTC)
    conn.last_error = msg
    session.commit()


def ensure_clone(session: Session, *, connector_id: str) -> Path | None:
    """Clone the connector's grounding repo if not already present.

    Returns the local path on success, `None` when the connector has no
    grounding URL configured or the clone fails.
    """
    conn = session.get(Connector, connector_id)
    if conn is None:
        return None
    if not conn.source_repo_url:
        if conn.grounding_status != "none":
            conn.grounding_status = "none"
            session.commit()
        return None

    target = path_for(connector_id)
    if target.exists():
        if conn.grounding_status != "ready":
            conn.grounding_status = "ready"
            session.commit()
        return target

    target.parent.mkdir(parents=True, exist_ok=True)
    revision = conn.source_repo_revision or "main"
    try:
        sha = clone_repo(url=conn.source_repo_url, target=target, revision=revision)
    except GroundingCloneError as exc:
        log.warning("grounding clone failed for connector %s: %s", connector_id, exc)
        _set_failed(session, conn, str(exc))
        return None

    conn.cached_repo_commit_sha = sha
    conn.grounding_status = "ready"
    conn.grounding_fetched_at = datetime.now(UTC)
    session.commit()
    return target


def resync_clone(session: Session, *, connector_id: str) -> Path | None:
    """Drop any existing clone and re-clone from the connector's current URL."""
    target = path_for(connector_id)
    delete_clone(target)
    return ensure_clone(session, connector_id=connector_id)
