"""Slice 8 — LLM-backed extract_fn factory.

The slice-6 extractor takes an injected ``extract_fn``. This module
ships the production-shaped one: it builds an LLMRequest from a chat
transcript, asks the model for structured JSON, and parses the result
into ProposalSpec dicts that ``extract_proposals_from_session``
understands.

Tests use a recording fake client so we can assert on the request shape
without a live model. Real adapter wiring (which client to pick from
user prefs) lands in slice 13 alongside the Secretary integration.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

from openlia.llm.types import LLMRequest, LLMResponse
from openlia_server.db.models.content import ChatMessage
from openlia_server.services import graph_extraction_llm


@dataclass
class _RecordingClient:
    canned_text: str
    last_request: LLMRequest | None = None

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        return LLMResponse(
            text=self.canned_text,
            finish_reason="stop",
            input_tokens=0,
            output_tokens=0,
        )


def _msg(role: str, content: str, idx: int) -> ChatMessage:
    return ChatMessage(
        id=f"m-{idx}",
        session_id="s-1",
        role=role,
        content=content,
        created_at=datetime.now(UTC),
    )


def test_extract_fn_returns_parsed_proposal_specs() -> None:
    canned = json.dumps(
        {
            "proposals": [
                {
                    "kind": "user_construct",
                    "payload": {
                        "construct_kind": "position",
                        "statement": "Long NVDA on services-margin thesis",
                        "entity_kind": "ticker",
                        "entity_value": "NVDA",
                        "source_excerpt": "I'm long NVDA",
                    },
                },
                {
                    "kind": "mention",
                    "payload": {
                        "entity_kind": "ticker",
                        "entity_value": "AMD",
                        "artifact_kind": "session",
                        "artifact_id": "s-1",
                    },
                },
            ]
        }
    )
    client = _RecordingClient(canned_text=canned)

    extract_fn = graph_extraction_llm.make_extract_fn(client)
    out = extract_fn(
        [
            _msg("user", "I'm long NVDA, watching AMD", 1),
            _msg("assistant", "Noted.", 2),
        ]
    )

    assert len(out) == 2
    assert out[0]["kind"] == "user_construct"
    assert out[0]["payload"]["entity_value"] == "NVDA"
    assert out[1]["kind"] == "mention"
    assert out[1]["payload"]["entity_value"] == "AMD"


def test_extract_fn_includes_transcript_in_request() -> None:
    """The model can only spot user beliefs that are visible in its
    input. The factory must put the transcript into the request — not
    just a system prompt — or the LLM is just hallucinating."""
    client = _RecordingClient(canned_text='{"proposals": []}')
    extract_fn = graph_extraction_llm.make_extract_fn(client)

    extract_fn(
        [
            _msg("user", "Im long NVDA", 1),
            _msg("assistant", "Noted.", 2),
        ]
    )

    assert client.last_request is not None
    rendered = "".join(m.content for m in client.last_request.messages)
    assert "long NVDA" in rendered
    # System prompt directs the model to emit JSON proposals.
    assert client.last_request.system is not None
    assert "proposal" in client.last_request.system.lower()


def test_extract_fn_skips_malformed_entries() -> None:
    """The LLM occasionally returns entries missing required fields. The
    factory drops those rather than poisoning the proposal queue with
    invalid payloads."""
    canned = json.dumps(
        {
            "proposals": [
                {"kind": "user_construct"},  # missing payload
                {"kind": "junk", "payload": {}},  # unknown kind
                {
                    "kind": "user_construct",
                    "payload": {
                        "construct_kind": "thesis",
                        "statement": "ok",
                        "entity_kind": "ticker",
                        "entity_value": "NVDA",
                    },
                },
            ]
        }
    )
    client = _RecordingClient(canned_text=canned)
    extract_fn = graph_extraction_llm.make_extract_fn(client)

    out = extract_fn([_msg("user", "x", 1)])

    assert len(out) == 1
    assert out[0]["payload"]["statement"] == "ok"
