"""Dev-mode event bus for backend visibility.

Off by default. Enabled when ``OPENLIA_DEV_MODE`` is truthy. When
enabled, callers anywhere in the server can call :func:`record` to push
a structured event into:

  1. An in-process ring buffer (last ~500) for replay on connect.
  2. A JSONL file at ``~/.openlia/dev-events.jsonl`` for ``tail -f``.
  3. Every live ``asyncio.Queue`` subscriber (used by the SSE route).

When disabled, every public function short-circuits — zero overhead.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_RING_MAX = 500
_ring: deque[dict[str, Any]] = deque(maxlen=_RING_MAX)
_subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
_seq: int = 0
_log_path: Path | None = None


def _resolve_log_path() -> Path:
    """Pick the JSONL log path. Honors ``OPENLIA_DEV_EVENTS_LOG`` if set,
    otherwise defaults to ``~/.openlia/dev-events.jsonl``."""
    override = os.environ.get("OPENLIA_DEV_EVENTS_LOG")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".openlia" / "dev-events.jsonl"


def is_enabled() -> bool:
    raw = os.environ.get("OPENLIA_DEV_MODE", "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def reset_for_tests() -> None:
    """Clear ring + subscribers. Tests use this between cases."""
    global _seq, _log_path
    _ring.clear()
    _subscribers.clear()
    _seq = 0
    _log_path = None


def record(
    category: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    """Push a dev event. No-op when ``OPENLIA_DEV_MODE`` is unset.

    ``category`` is a short tag like ``"chat.request"`` or ``"chat.event"``.
    ``message`` is a one-line human summary. ``payload`` is an optional
    JSON-serializable dict for structured detail.
    """
    if not is_enabled():
        return
    global _seq, _log_path
    _seq += 1
    event: dict[str, Any] = {
        "seq": _seq,
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "category": category,
        "message": message,
        "payload": payload or {},
    }
    _ring.append(event)

    # Append to the JSONL log. Resolve+create the path lazily so tests
    # that reset between cases pick up env overrides.
    if _log_path is None:
        _log_path = _resolve_log_path()
        try:
            _log_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            log.warning("dev-events: could not prepare log dir", exc_info=True)
    try:
        with _log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        log.warning("dev-events: could not append to log", exc_info=True)

    # Fan out to live SSE subscribers. ``put_nowait`` to avoid blocking
    # the producer; if a subscriber's queue is full, drop oldest from
    # that subscriber's perspective (rare in practice for a small ring).
    for queue in list(_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(event)
            except Exception:
                pass


def snapshot() -> list[dict[str, Any]]:
    """Return a copy of the current ring buffer (oldest → newest)."""
    return list(_ring)


async def stream() -> AsyncIterator[dict[str, Any]]:
    """Async generator: yields the ring buffer first (replay), then every
    new event as it arrives. Caller is responsible for awaiting the
    iterator on a stream until the client disconnects.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=512)
    _subscribers.add(queue)
    try:
        for event in list(_ring):
            yield event
        while True:
            event = await queue.get()
            yield event
    finally:
        _subscribers.discard(queue)
