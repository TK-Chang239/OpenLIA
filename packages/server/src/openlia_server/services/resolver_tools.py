"""Sandboxed filesystem tools the agentic adapter LLM uses to navigate
locally-cloned connector repos.

The orchestrator passes `connector_root` per call. The LLM supplies the
relative path. All resolution happens under `connector_root`; escapes
raise `ResolverToolError`.
"""

from __future__ import annotations

import os
import re
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
    try:
        root_resolved = connector_root.resolve(strict=True)
        candidate = (connector_root / path).resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ResolverToolError(f"path not found: {path!r}") from exc
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise ResolverToolError(f"path {path!r} resolves outside connector root") from exc
    return candidate


def _within_grounding(
    rel_path: str,
    grounding_paths: list[str] | None,
    *,
    is_dir: bool,
) -> bool:
    """Decide whether `rel_path` is reachable under the user's grounding scope.

    A directory is reachable if any allowed path is inside it (so the LLM can
    navigate down from the root) or if it sits inside an allowed directory.
    A file is reachable only if it equals an allowed file or is a descendant
    of an allowed directory.
    """
    if not grounding_paths:
        return True
    norm = "" if rel_path in (".", "") else rel_path.replace("\\", "/").strip("/")
    for raw in grounding_paths:
        allowed = raw.replace("\\", "/").strip("/")
        if not allowed:
            continue
        if norm == allowed:
            return True
        # rel_path is a descendant of the allowed entry
        if norm.startswith(allowed + "/"):
            return True
        # rel_path is an ancestor of the allowed entry (only meaningful for
        # directory listings, so the LLM can walk down from the root)
        if is_dir and (norm == "" or allowed.startswith(norm + "/")):
            return True
    return False


def list_directory(
    connector_root: Path,
    path: str,
    *,
    grounding_paths: list[str] | None = None,
) -> list[dict]:
    target = _resolve_under_root(connector_root, path)
    rel = "" if path in (".", "") else path.replace("\\", "/").strip("/")
    if not _within_grounding(rel, grounding_paths, is_dir=True):
        raise ResolverToolError(
            f"path {path!r} is outside the connector's grounding_paths"
        )
    entries: list[dict] = []
    for entry in os.scandir(target):
        entry_rel = (rel + "/" + entry.name).strip("/")
        is_dir = entry.is_dir(follow_symlinks=False)
        if not _within_grounding(entry_rel, grounding_paths, is_dir=is_dir):
            continue
        entries.append(
            {"name": entry.name, "type": "dir" if is_dir else "file"}
        )
    return entries


def read_file(
    connector_root: Path,
    path: str,
    *,
    grounding_paths: list[str] | None = None,
    max_bytes: int = 200_000,
) -> str:
    target = _resolve_under_root(connector_root, path)
    if not target.is_file():
        raise ResolverToolError(f"not a regular file: {path!r}")
    rel = path.replace("\\", "/").strip("/")
    if not _within_grounding(rel, grounding_paths, is_dir=False):
        raise ResolverToolError(
            f"path {path!r} is outside the connector's grounding_paths"
        )
    raw = target.read_bytes()
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="replace")
    head = raw[:max_bytes].decode("utf-8", errors="replace")
    return f"{head}\n\n... [truncated at {max_bytes} bytes; full file is {len(raw)} bytes]"


def search_files(
    connector_root: Path,
    pattern: str,
    glob: str = "**/*",
    *,
    grounding_paths: list[str] | None = None,
    max_results: int = 200,
) -> list[dict]:
    root = connector_root.resolve(strict=True)
    try:
        regex = re.compile(pattern)
    except re.error as exc:
        raise ResolverToolError(f"invalid pattern {pattern!r}: {exc}") from exc

    # Choose the bases to glob from. If grounding_paths is set, walk each
    # explicitly-allowed entry instead of the whole repo.
    bases: list[Path] = [root]
    if grounding_paths:
        bases = []
        for raw in grounding_paths:
            allowed = raw.replace("\\", "/").strip("/")
            if not allowed:
                continue
            sub = (root / allowed).resolve(strict=False)
            try:
                sub.relative_to(root)
            except ValueError:
                continue
            if sub.exists():
                bases.append(sub)

    matches: list[dict] = []
    for base in bases:
        if len(matches) >= max_results:
            break
        # If the allowed entry is a single file, match it directly; else glob.
        candidates: list[Path]
        if base.is_file():
            candidates = [base]
        else:
            candidates = sorted(base.glob(glob))
        for candidate in candidates:
            if len(matches) >= max_results:
                break
            if not candidate.is_file():
                continue
            try:
                text = candidate.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = candidate.relative_to(root).as_posix()
            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append({"path": rel, "line_number": lineno, "line": line})
                    if len(matches) >= max_results:
                        break
    return matches
