"""Local-filesystem storage backend for chat attachments.

Files live under ``$OPENLIA_ATTACHMENTS_DIR`` (default
``$OPENLIA_HOME/attachments``). Each file is given a server-generated UUID
filename with the original extension preserved (so downstream mime sniffers
keep working). Files are sharded by the first two hex chars of the UUID to
keep any single directory small even with many uploads.

The contract is the only public surface: ``save`` returns an opaque
``storage_path`` that ``read`` and ``unlink`` consume. Callers must never
construct paths themselves.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from openlia_server.db.bootstrap import openlia_home

DEFAULT_SUBDIR = "attachments"


def configured_root() -> Path:
    """Resolve and ensure the storage root directory exists."""
    env_dir = os.environ.get("OPENLIA_ATTACHMENTS_DIR")
    root = Path(env_dir) if env_dir else openlia_home() / DEFAULT_SUBDIR
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    return root


def save(content: bytes, *, original_filename: str) -> str:
    """Write ``content`` to a server-generated path. Returns the absolute path.

    ``original_filename`` is used only to derive the file extension; its body
    is discarded so a malicious client cannot influence the on-disk path.
    """
    extension = _safe_extension(original_filename)
    file_id = uuid.uuid4().hex
    shard = file_id[:2]
    target_dir = configured_root() / shard
    target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = target_dir / f"{file_id}{extension}"
    target.write_bytes(content)
    return str(target)


def read(storage_path: str) -> bytes:
    """Read the bytes back. Raises ``FileNotFoundError`` if missing."""
    return Path(storage_path).read_bytes()


def unlink(storage_path: str) -> None:
    """Remove the file. Idempotent — silent if already gone."""
    Path(storage_path).unlink(missing_ok=True)


def _safe_extension(original_filename: str) -> str:
    """Strip everything but the (lowercased) extension. Empty if none."""
    name = Path(original_filename).name  # drops directory components
    suffix = Path(name).suffix.lower()
    if not suffix or any(ch in suffix for ch in ("/", "\\", "..")):
        return ""
    return suffix
