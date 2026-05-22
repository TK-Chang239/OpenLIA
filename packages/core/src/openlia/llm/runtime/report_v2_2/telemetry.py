"""Token-cost telemetry for the v2.2 equity research engine.

Captures per-call cost events at Stage 7a (materialization) and Stage 7b
(drafter LLM call). Each event is a frozen dataclass with a class-level TYPE
literal, matching the convention in runtime/events.py.

Wire-up:
  - materialize_section() / materialize() accept an optional TelemetryCollector
    and emit Stage7aMaterializeEvent per artifact rendered.
  - build_drafter_prompt() callers (Stage 7b) call record_drafter_call() on
    the same collector after each LLM response.

Usage::

    collector = TelemetryCollector()
    ms = materialize_section(plan, outputs, telemetry=collector)
    # ... LLM call ...
    collector.record_drafter_call(
        section_id="valuation_dcf",
        tokens_in=420, tokens_out=310, cached_tokens=200,
    )
    snapshot = collector.snapshot()
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Stage 7a — per-artifact materialization event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage7aMaterializeEvent:
    """Emitted once per rendered artifact in materialize_section() / materialize().

    Fields
    ------
    section_id : str
        The section that triggered this render.
    artifact_id : str
        Artifact being rendered (e.g. ``"dcf_base_valuation"``).
    helper_name : str
        The helper that produced this artifact (``"__materialization__"`` for
        default renders; the actual helper name if the artifact carries metadata).
    fidelity : str
        Fidelity level used: ``"headline"``, ``"summary"``, or ``"full"``.
    rendered_chars : int
        Character count of the rendered markdown string (before any truncation
        suffix). Used as a token-cost proxy (1 token ≈ 4 chars).
    was_truncated : bool
        True when the hard-cap was hit and ``[truncated]`` was appended.
    ts : str
        ISO-8601 UTC timestamp.
    """

    TYPE = "report_v2_2.stage7a.materialize"

    section_id: str
    artifact_id: str
    helper_name: str
    fidelity: str
    rendered_chars: int
    was_truncated: bool
    ts: str = field(default_factory=_utc_now_iso)


# ---------------------------------------------------------------------------
# Stage 7b — per-drafter-call LLM cost event
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage7bDrafterCallEvent:
    """Emitted once per Stage 7b LLM drafter call.

    Callers should populate ``tokens_in`` / ``tokens_out`` / ``cached_tokens``
    from the LLMResponse returned by the drafter. If the provider does not
    return cached-token counts, pass 0.

    Fields
    ------
    section_id : str
        Section being drafted.
    fidelity : str
        Highest fidelity artifact in this section's rendered artifacts.
        Proxies prompt complexity; empty string when section has no artifacts.
    tokens_in : int
        Prompt token count as reported by the LLM provider.
    tokens_out : int
        Completion token count as reported by the LLM provider.
    cached_tokens : int
        Prompt-cache hit tokens (Anthropic: ``cache_read_input_tokens``; others: 0).
    ts : str
        ISO-8601 UTC timestamp.
    """

    TYPE = "report_v2_2.stage7b.drafter_call"

    section_id: str
    fidelity: str
    tokens_in: int
    tokens_out: int
    cached_tokens: int
    ts: str = field(default_factory=_utc_now_iso)


# ---------------------------------------------------------------------------
# Collector — accumulates events, provides snapshot
# ---------------------------------------------------------------------------


class TelemetryCollector:
    """Accumulates Stage 7a/7b telemetry events for one report run.

    Thread-safety: not thread-safe; callers must serialize access or use one
    collector per section and merge via ``merge()``.
    """

    def __init__(self) -> None:
        self._events: list[Stage7aMaterializeEvent | Stage7bDrafterCallEvent] = []

    # -- recording ---------------------------------------------------------

    def record_materialize(
        self,
        *,
        section_id: str,
        artifact_id: str,
        helper_name: str,
        fidelity: str,
        rendered_chars: int,
        was_truncated: bool,
    ) -> None:
        """Record one Stage 7a render event. Called by materialize_section()."""
        evt = Stage7aMaterializeEvent(
            section_id=section_id,
            artifact_id=artifact_id,
            helper_name=helper_name,
            fidelity=fidelity,
            rendered_chars=rendered_chars,
            was_truncated=was_truncated,
        )
        self._events.append(evt)
        logger.debug(
            "stage7a.materialize section=%s artifact=%s fidelity=%s chars=%d truncated=%s",
            section_id,
            artifact_id,
            fidelity,
            rendered_chars,
            was_truncated,
        )

    def record_drafter_call(
        self,
        *,
        section_id: str,
        fidelity: str = "",
        tokens_in: int,
        tokens_out: int,
        cached_tokens: int = 0,
    ) -> None:
        """Record one Stage 7b drafter LLM call event."""
        evt = Stage7bDrafterCallEvent(
            section_id=section_id,
            fidelity=fidelity,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cached_tokens=cached_tokens,
        )
        self._events.append(evt)
        logger.debug(
            "stage7b.drafter_call section=%s fidelity=%s in=%d out=%d cached=%d",
            section_id,
            fidelity,
            tokens_in,
            tokens_out,
            cached_tokens,
        )

    # -- aggregation -------------------------------------------------------

    def events(self) -> list[Stage7aMaterializeEvent | Stage7bDrafterCallEvent]:
        """Return all recorded events in insertion order."""
        return list(self._events)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable aggregate summary.

        Structure::

            {
              "total_rendered_chars": int,
              "total_tokens_in": int,
              "total_tokens_out": int,
              "total_cached_tokens": int,
              "materialize_events": int,
              "drafter_call_events": int,
              "per_section": {
                "<section_id>": {
                  "rendered_chars": int,
                  "tokens_in": int,
                  "tokens_out": int,
                  "cached_tokens": int,
                  "artifact_count": int,
                  "truncated_count": int,
                }
              },
              "events": [ ... raw event dicts ... ],
            }
        """
        per_section: dict[str, dict[str, Any]] = {}

        def _s(sid: str) -> dict[str, Any]:
            if sid not in per_section:
                per_section[sid] = {
                    "rendered_chars": 0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "cached_tokens": 0,
                    "artifact_count": 0,
                    "truncated_count": 0,
                }
            return per_section[sid]

        total_chars = 0
        total_in = 0
        total_out = 0
        total_cached = 0
        n_mat = 0
        n_draft = 0

        for evt in self._events:
            if isinstance(evt, Stage7aMaterializeEvent):
                n_mat += 1
                total_chars += evt.rendered_chars
                s = _s(evt.section_id)
                s["rendered_chars"] += evt.rendered_chars
                s["artifact_count"] += 1
                if evt.was_truncated:
                    s["truncated_count"] += 1
            elif isinstance(evt, Stage7bDrafterCallEvent):
                n_draft += 1
                total_in += evt.tokens_in
                total_out += evt.tokens_out
                total_cached += evt.cached_tokens
                s = _s(evt.section_id)
                s["tokens_in"] += evt.tokens_in
                s["tokens_out"] += evt.tokens_out
                s["cached_tokens"] += evt.cached_tokens

        return {
            "total_rendered_chars": total_chars,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_cached_tokens": total_cached,
            "materialize_events": n_mat,
            "drafter_call_events": n_draft,
            "per_section": per_section,
            "events": [asdict(e) for e in self._events],
        }

    def merge(self, other: TelemetryCollector) -> None:
        """Merge events from another collector into this one (in-place)."""
        self._events.extend(other._events)
