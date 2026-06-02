"""Event types + emitter contract for streaming v3 runs.

Phase 3b-backend lets a single run publish progress events to any
number of subscribers. The runner accepts an ``EventEmitter`` and
sprinkles ``emit(...)`` calls at the meaningful state transitions;
the server-side broker fans events out to one or more SSE
subscribers (typically just the one client watching the run).

Event taxonomy mirrors the spec § "Frontend events":

  - run.started        run_id, subject, template_id, language
  - tool.called        turn, tool_name, args_summary
  - tool.completed     turn, tool_name, source_id, summary, ok
  - section.written    section_id, title, char_count
  - chart.emitted      chart_id, chart_type, title
  - run.completed      report_id, section_count, chart_count, citation_count
  - run.failed         report_id, error, partial_sections_written
  - run.cancelled      report_id, partial_sections_written

The taxonomy stays small on purpose — adding 20 event types invites
the same "every nuance must be modelled" creep that bloated v2.3. If
a consumer needs finer signal it can poll the DB after run.completed
lands.

CancelToken is in this module too because event flow and cancellation
are the same shape of cross-cutting concern: both flow through the
runner from the route layer.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

# Sentinel poked into the queue when a run completes so the
# subscriber's async generator can break out of its receive loop
# without polling for a done flag. ``object()`` gives a unique
# identity that can't be confused with a real Event.
_BROKER_DONE = object()


@dataclass(frozen=True)
class Event:
    """One streamed event with a stable serialization shape."""

    type: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp.isoformat(),
        }


class EventEmitter(Protocol):
    """Minimum surface the runner consumes. Implementations can
    publish to a broker, append to a list (tests), or no-op."""

    def emit(self, event_type: str, payload: dict[str, Any]) -> None: ...


class NullEmitter:
    """Drop every event. Default for callers that don't subscribe."""

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        return None


class ListEmitter:
    """Append every event to an in-memory list. Used by tests."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append(Event(type=event_type, payload=dict(payload)))


class CancelToken:
    """Cooperative cancel flag the runner polls between turns.

    Cancellation is cooperative — the runner exits at the next safe
    point (turn boundary or pre-tool-dispatch), so a single in-flight
    tool call (an EODHD fetch, a model turn) may finish before the
    cancel takes effect. Partial work persists either way.
    """

    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def cancelled(self) -> bool:
        return self._cancelled


class EventBroker:
    """In-memory pub-sub keyed by ``report_id``.

    Lives on ``app.state.v3_event_broker``. One publisher per run
    (the runner's emitter); usually one subscriber (the SSE
    endpoint). Multiple subscribers are supported — useful when a
    frontend reconnects and the original socket hasn't been GC'd.

    Buffering: events that arrive before the first subscribe call
    are NOT replayed. Subscribers see only events emitted while
    they are connected. The route layer mitigates this by reading
    the persisted ``ReportV3.status`` on subscribe and surfacing it
    as the first message — so a client that connects late knows
    the terminal state without needing to replay every tool call.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue]] = {}

    def publish(self, report_id: str, event: Event) -> None:
        for queue in list(self._subscribers.get(report_id, [])):
            queue.put_nowait(event)

    def finish(self, report_id: str) -> None:
        """Signal subscribers that no more events will arrive."""
        for queue in list(self._subscribers.get(report_id, [])):
            queue.put_nowait(_BROKER_DONE)

    @asynccontextmanager
    async def subscribe(self, report_id: str) -> AsyncIterator[asyncio.Queue]:
        """Context-managed subscription — yields the receive queue.

        Use:

            async with broker.subscribe(report_id) as queue:
                while True:
                    item = await queue.get()
                    if item is _BROKER_DONE: break
                    yield item

        Bookkeeping ensures the subscription is removed when the
        caller exits, including on cancellation.
        """
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(report_id, []).append(queue)
        try:
            yield queue
        finally:
            subs = self._subscribers.get(report_id, [])
            if queue in subs:
                subs.remove(queue)
            if not subs:
                self._subscribers.pop(report_id, None)


def is_finish_sentinel(item: object) -> bool:
    """True when the dequeued item marks the end of a stream.

    Exposes the module-private sentinel so SSE consumers don't have
    to import the sentinel itself.
    """
    return item is _BROKER_DONE


@dataclass
class BrokerEmitter:
    """Adapter that turns ``EventEmitter.emit`` calls into broker publishes."""

    broker: EventBroker
    report_id: str

    def emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self.broker.publish(
            self.report_id,
            Event(type=event_type, payload=dict(payload)),
        )
