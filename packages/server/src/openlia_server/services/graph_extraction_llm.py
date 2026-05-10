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


SYSTEM_PROMPT = """You are an extractor that reads a chat transcript and
identifies durable user beliefs and entity mentions worth remembering
across sessions. Be conservative — only extract statements that would
matter again in a future conversation.

Return JSON with this exact shape:

{
  "proposals": [
    {
      "kind": "user_construct",
      "payload": {
        "construct_kind": "position" | "thesis" | "concern" | "watchlist_item",
        "statement": "<short canonical phrasing>",
        "entity_kind": "ticker" | "sector" | "theme" | "macro_regime",
        "entity_value": "<symbol or label>",
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

Rules:
- Skip casual mentions; require an explicit user belief or position for
  user_construct.
- Use uppercase tickers; emit each distinct ticker only once as a
  mention per session.
- If nothing rises to that bar, return {"proposals": []}.
- Output JSON only — no preamble, no commentary.
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
            required = {"construct_kind", "statement", "entity_kind", "entity_value"}
            if required.issubset(payload):
                out.append({"kind": kind, "payload": payload})
        elif kind == "mention":
            required = {"entity_kind", "entity_value", "artifact_kind", "artifact_id"}
            if required.issubset(payload):
                out.append({"kind": kind, "payload": payload})
    return out
