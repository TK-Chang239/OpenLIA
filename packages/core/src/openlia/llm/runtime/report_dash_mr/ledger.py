"""Append-only citation ledger for v3 runs.

Every tool call appends one entry; the ledger assigns the stable
``source_id`` the model uses to cite the result. Source ids follow the
pattern ``<prefix>_<N>`` where prefix is derived from the tool name
(``web_search`` -> ``web``, ``get_fundamentals`` -> ``eodhd``,
``run_dcf`` -> ``dcf``) and N is a per-prefix monotonic counter
starting at 1.

The ledger is intentionally simple — in-memory, single-run scope, no
persistence concerns. Phase 2 mirrors the ledger contents into the
``ToolCallLog`` SQL table at flush time.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .schemas import CitationLogEntry

# Maps tool name -> source_id prefix. Unknown tools fall back to
# their tool name itself (lowercased, non-alphanumeric chars stripped) so we
# never silently lose provenance attribution. Lowercasing keeps the source_id
# matchable by the citation regex (``[a-z0-9_]+``) shared across the
# write_section validator, the display-index assigner, and the rewriter:
# connector tools carry uppercase names (e.g. ``alphavantage__TOOL_CALL``)
# that would otherwise render as raw, unresolved ``[^...]`` markers.
_TOOL_PREFIX_MAP: dict[str, str] = {
    "web_search": "web",
    "get_quotes": "eodhd",
    "get_historical_prices": "eodhd",
    "get_news": "eodhd",
    "get_economic_calendar": "eodhd",
    "get_macro_indicators": "eodhd",
    "run_dcf": "dcf",
    "run_comps": "comps",
    "run_sensitivity": "sens",
    "code_execution": "code",
}


def _prefix_for(tool_name: str) -> str:
    if tool_name in _TOOL_PREFIX_MAP:
        return _TOOL_PREFIX_MAP[tool_name]
    sanitized = "".join(ch for ch in tool_name.lower() if ch.isalnum() or ch == "_")
    return sanitized or "tool"


class CitationLedger:
    """In-memory append-only ledger of tool-call provenance.

    Use ``append`` to record one tool call and receive the assigned
    ``source_id``; pass that id back to the model in the tool result so
    it knows what to cite. Lookup is by ``source_id``; iteration
    preserves append order.
    """

    def __init__(self) -> None:
        self._entries: list[CitationLogEntry] = []
        self._counters: dict[str, int] = {}

    def append(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result_summary: str = "",
        provenance: dict[str, Any] | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        wall_time_ms: int = 0,
    ) -> CitationLogEntry:
        """Record one tool call. Returns the entry with its assigned id."""
        prefix = _prefix_for(tool_name)
        next_n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = next_n
        entry = CitationLogEntry(
            source_id=f"{prefix}_{next_n}",
            tool_name=tool_name,
            arguments=arguments or {},
            result_summary=result_summary,
            provenance=provenance or {},
            timestamp=datetime.now(UTC),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            wall_time_ms=wall_time_ms,
        )
        self._entries.append(entry)
        return entry

    def seed(
        self,
        entries: list[CitationLogEntry] | list[dict[str, Any]],
    ) -> None:
        """Pre-populate the ledger with prior entries (revise mode).

        Accepts either ``CitationLogEntry`` objects or plain dicts
        with ``source_id`` / ``tool_name`` / ``provenance`` keys.
        Updates ``_counters`` so future ``append`` calls keep
        numbering monotonically per prefix — no collisions with
        prior source_ids.
        """
        for raw in entries:
            entry = (
                raw
                if isinstance(raw, CitationLogEntry)
                else CitationLogEntry.model_validate(
                    {
                        "source_id": raw["source_id"],
                        "tool_name": raw["tool_name"],
                        "arguments": raw.get("arguments", {}),
                        "result_summary": raw.get("result_summary", ""),
                        "provenance": raw.get("provenance", {}),
                        "timestamp": raw.get("timestamp", datetime.now(UTC)),
                        "input_tokens": raw.get("input_tokens", 0),
                        "output_tokens": raw.get("output_tokens", 0),
                        "wall_time_ms": raw.get("wall_time_ms", 0),
                    }
                )
            )
            self._entries.append(entry)
            # Bump counters so the next auto-assigned id doesn't
            # collide with the prior prefix_N.
            sid = entry.source_id
            if "_" in sid:
                prefix, suffix = sid.rsplit("_", 1)
                try:
                    n = int(suffix)
                    self._counters[prefix] = max(self._counters.get(prefix, 0), n)
                except ValueError:
                    pass

    def lookup(self, source_id: str) -> CitationLogEntry | None:
        for entry in self._entries:
            if entry.source_id == source_id:
                return entry
        return None

    def all(self) -> list[CitationLogEntry]:
        return list(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
