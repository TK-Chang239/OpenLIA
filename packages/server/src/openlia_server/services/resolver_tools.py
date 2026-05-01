"""Sandboxed filesystem tools the agentic adapter LLM uses to navigate
locally-cloned connector repos.

The orchestrator passes `connector_root` per call. The LLM supplies the
relative path. All resolution happens under `connector_root`; escapes
raise `ResolverToolError`.
"""

from __future__ import annotations

import os
from pathlib import Path


class ResolverToolError(Exception):
    """Raised when a resolver tool call cannot be served safely."""


def _resolve_under_root(connector_root: Path, path: str) -> Path:
    """Resolve `path` relative to `connector_root`, rejecting any escape.

    Rejects absolute paths, parent traversals, and symlinks pointing outside
    the root. The returned path is fully resolved (symlinks followed).
    """
    if Path(path).is_absolute():
        raise ResolverToolError(f"absolute path not allowed: {path!r}")
    root_resolved = connector_root.resolve(strict=True)
    candidate = (connector_root / path).resolve(strict=True)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ResolverToolError(f"path {path!r} resolves outside connector root") from exc
    return candidate


def list_directory(connector_root: Path, path: str) -> list[dict]:
    target = _resolve_under_root(connector_root, path)
    entries: list[dict] = []
    for entry in os.scandir(target):
        kind = "dir" if entry.is_dir(follow_symlinks=False) else "file"
        entries.append({"name": entry.name, "type": kind})
    return entries


def read_file(connector_root: Path, path: str, max_bytes: int = 200_000) -> str:
    target = _resolve_under_root(connector_root, path)
    if not target.is_file():
        raise ResolverToolError(f"not a regular file: {path!r}")
    raw = target.read_bytes()
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="replace")
    head = raw[:max_bytes].decode("utf-8", errors="replace")
    return f"{head}\n\n... [truncated at {max_bytes} bytes; full file is {len(raw)} bytes]"
