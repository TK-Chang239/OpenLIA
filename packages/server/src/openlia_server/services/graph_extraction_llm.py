"""Production-shaped ``extract_fn`` factory (slice 8).

Builds an ``ExtractFn`` (the slice-6 callable interface) from any LLM
client conforming to the ``openlia.llm.types`` ``generate`` contract.
The returned callable:

1. Renders the chat transcript into an LLM-readable form.
2. Asks the model, in JSON-mode, what user constructs and entity
   mentions it observed.
3. Parses the response and drops malformed entries so the proposal
   queue (slice 6) stays clean.

The system prompt is conservative — bias toward *fewer* high-confidence
extractions, since each one becomes a row the user has to triage.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

from openlia.llm.types import LLMRequest, LLMResponse, Message, ResponseFormat

from openlia_server.db.models.content import ChatMessage
from openlia_server.services.graph_extraction import ExtractFn


class _ClientLike(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...


_VALID_CONSTRUCT_KINDS: frozenset[str] = frozenset(
    {"position", "thesis", "concern", "watchlist_item"}
)
_VALID_ENTITY_KINDS: frozenset[str] = frozenset({"ticker", "sector", "theme", "macro_regime"})


SYSTEM_PROMPT = """You extract durable user beliefs and entity mentions
from a chat transcript so a future session can reference them.

CRITICAL OUTPUT CONTRACT — read carefully:
- Your entire response MUST be a single JSON object.
- Any prose, preamble, code fences, or trailing commentary will be
  discarded as a protocol violation.
- If you are uncertain, prefer emitting fewer proposals. Empty is fine.

Schema:

{
  "proposals": [
    {
      "kind": "user_construct",
      "payload": {
        "construct_kind": "position" | "thesis" | "concern" | "watchlist_item",
        "statement": "<one short sentence stating the user's belief>",
        "entity_kind": "ticker" | "sector" | "theme" | "macro_regime",
        "entity_value": "<NVDA | semiconductors | ai-capex | risk-off>",
        "source_excerpt": "<verbatim line from the transcript>"
      }
    },
    {
      "kind": "mention",
      "payload": {
        "entity_kind": "ticker" | "sector" | "theme" | "macro_regime",
        "entity_value": "<symbol or label>",
        "artifact_kind": "session",
        "artifact_id": "<session id>"
      }
    }
  ]
}

Field rules (every rejected field drops the whole proposal):
- ``construct_kind`` MUST be one of: position, thesis, concern, watchlist_item.
- ``entity_kind`` MUST be one of: ticker, sector, theme, macro_regime.
- ``statement`` MUST be a complete sentence — not a fragment, not whitespace.
- ``entity_value`` MUST be non-empty. Tickers UPPERCASE. Sectors/themes/
  macro_regimes kebab-case (e.g. ``ai-capex``, not ``AI Capex``).
- Emit each distinct ticker at most once per session as a ``mention``.

Heuristics:
- ``position``: user states they own / are long / short something.
- ``thesis``: user states a directional view ("X will outperform because ...").
- ``concern``: user states a worry or downside they're tracking.
- ``watchlist_item``: user states they're watching / interested but not
  yet committed.

When in doubt, leave it out. The cost of a missed belief is one
unmemoried turn; the cost of a wrong belief is a permanently misshapen
user model.
"""


def make_extract_fn(client: _ClientLike) -> ExtractFn:
    def _extract(messages: list[ChatMessage]) -> list[dict[str, Any]]:
        transcript = "\n\n".join(f"[{m.role}] {m.content}" for m in messages)
        request = LLMRequest(
            messages=[Message(role="user", content=transcript)],
            system=SYSTEM_PROMPT,
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=2048,
            temperature=0.0,
        )
        response = client.generate(request)
        return _parse(response.text)

    return _extract


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _parse(text: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    raw = data.get("proposals", []) if isinstance(data, dict) else []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        payload = entry.get("payload")
        if not isinstance(payload, dict):
            continue
        if kind == "user_construct":
            if (
                payload.get("construct_kind") in _VALID_CONSTRUCT_KINDS
                and payload.get("entity_kind") in _VALID_ENTITY_KINDS
                and _nonempty_str(payload.get("statement"))
                and _nonempty_str(payload.get("entity_value"))
            ):
                out.append({"kind": kind, "payload": payload})
        elif kind == "mention":
            if (
                payload.get("entity_kind") in _VALID_ENTITY_KINDS
                and _nonempty_str(payload.get("entity_value"))
                and _nonempty_str(payload.get("artifact_kind"))
                and _nonempty_str(payload.get("artifact_id"))
            ):
                out.append({"kind": kind, "payload": payload})
    return out
