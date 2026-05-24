"""Provider-agnostic LLM-backed ClarifierClient.

This module stays free of OpenAI / Anthropic SDK imports. It depends only
on a callable with the shape::

    json_call(system: str, user: dict | str) -> dict

The wiring layer (server `app.py`) chooses the provider — e.g.
`SyncJsonLlmClient` over the existing `OpenAIRouter` adapter — and passes
in `.call`. That keeps the core package portable and lets tests swap in a
plain function fake.

Prompt + JSON-shape contract:
- The system prompt asks for ONE of two top-level shapes — `proceed` or
  `needs_input` — discriminated by ``outcome``.
- Up to `MAX_CLARIFY_QUESTIONS` (3) questions in `needs_input`; the prompt
  documents the bar for asking (would a wrong default misdirect the
  pipeline?) so the gate stays cheap.
- Pydantic validates the shape on the way in; bad JSON is wrapped in a
  RuntimeError that names the offending fragment so failures are
  debuggable.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter, ValidationError

from ..schemas import (
    MAX_CLARIFY_QUESTIONS,
    ClarifyNeedsInput,
    ClarifyProceed,
    ClarifyResult,
)
from .clarifier import ClarifierClient, ClarifierRequest

log = logging.getLogger(__name__)

# A duck-typed JSON callable. Matches the shape of
# `openlia_server.services.v2_stage_factory.SyncJsonLlmClient.call`.
JsonCall = Callable[..., dict[str, Any]]


_CLARIFY_RESULT_ADAPTER: TypeAdapter[ClarifyResult] = TypeAdapter(ClarifyResult)


SYSTEM_PROMPT = f"""You are the CLARIFY stage of an equity-research report
pipeline. You will receive the user's request, the tickers, and a short
description of the template the report will follow.

Read the prompt and the template. Decide whether anything genuinely
needs clarifying before the pipeline runs. If nothing does, proceed —
no questions invented for their own sake. If something does, ask it.

There is no quota and no expected number of questions. Zero is the
right answer whenever the prompt + template are coherent enough to
write a good report from. Do not ask hypothetical or "nice to know"
questions just because you could think of them.

Asking is only appropriate when the user wrote something that leaves
the pipeline genuinely unable to pick between materially different
reports, AND a one-line answer would resolve it. Most well-formed
prompts ("Update on AAPL", "Initiation on NVDA focused on AI infra
margins", "Sector study of the lithium miners") do not require any
clarification.

If you do ask, cap at {MAX_CLARIFY_QUESTIONS} and only ask what you
actually need.

Return EXACTLY one JSON object matching ONE of these shapes:

Proceed (the typical case — nothing needs clarifying):
{{
  "outcome": "proceed",
  "assumptions": ["concrete assumption 1", "concrete assumption 2"]
}}

NeedsInput (only when a question genuinely blocks a good report):
{{
  "outcome": "needs_input",
  "questions": [
    {{
      "id": "short_snake_case_id",
      "question": "Question phrased for the user (one sentence).",
      "why_blocking": "How a different answer would change THIS report.",
      "default": "Reasonable fallback if the user skips."
    }}
  ]
}}

Rules:
- "outcome" MUST be "proceed" or "needs_input" (exact strings).
- Every question MUST include `id`, `question`, `why_blocking`, `default`.
- Assumptions in `proceed` describe what you locked in for the user
  (e.g. "horizon: 12 months", "focus: valuation") — concrete, not
  generic boilerplate. They are not required; an empty list is fine
  when the prompt was fully self-describing.
- Output JSON only. No prose, no markdown fences.
""".strip()


# One-line shape sketch per built-in template. Fed to the LLM as
# `template.shape` so it knows what kind of report it's clarifying for
# (a morning_brief needs vastly different questions than an
# initiation). Kept short — the planner generates the actual section
# list later; CLARIFY only needs to know the report's character.
_BUILTIN_TEMPLATE_SHAPES: dict[str, str] = {
    "initiation": (
        "Comprehensive initiation: business overview, financial profile, "
        "competitive position, valuation (DCF + comps), risks, recommendation. "
        "Long-form, written for someone who has not covered the name before."
    ),
    "update": (
        "Targeted update on a name already covered: what changed since last "
        "look, updated financials, refreshed valuation, revised stance. "
        "Assumes prior context."
    ),
    "sector_research": (
        "Sector / thematic deep-dive: industry dynamics, key players, "
        "winners and losers, top picks. Comps and cross-company comparison "
        "are central."
    ),
    "morning_brief": (
        "Short morning note: headline news, market read, immediate "
        "implications. Concise — bullet-density over prose."
    ),
    "earnings_review": (
        "Earnings print review: beat/miss vs consensus, segment trends, "
        "guidance, key questions answered/raised. Anchored to the most "
        "recent quarter."
    ),
}


def _to_user_payload(request: ClarifierRequest) -> dict[str, Any]:
    shape = _BUILTIN_TEMPLATE_SHAPES.get(
        request.report_type.value,
        "Unspecified template — treat as a general equity-research report.",
    )
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "tickers": request.tickers,
        "template": {
            "id": request.report_type.value,
            "shape": shape,
        },
    }


class LLMClarifierClient(ClarifierClient):
    """Adapts a JSON-call LLM into a `ClarifierClient`.

    The `json_call` argument is intentionally a plain callable so the core
    stays free of provider SDKs; in production it is
    `SyncJsonLlmClient.call` bound to an `OpenAIRouter` (or any other
    provider).
    """

    def __init__(self, json_call: JsonCall) -> None:
        self._json_call = json_call

    def clarify(self, request: ClarifierRequest) -> ClarifyResult:
        # Time + log every LLM call so we can verify CLARIFY actually
        # round-tripped to the model (a sub-millisecond duration would
        # mean the call was short-circuited; a few-second duration is
        # the expected shape for a small JSON completion).
        prompt_chars = len(request.raw_prompt or "")
        log.info(
            "CLARIFY: calling LLM (prompt_chars=%d, report_type=%s, tickers=%s)",
            prompt_chars,
            request.report_type.value,
            request.tickers,
        )
        t0 = time.monotonic()
        raw = self._json_call(system=SYSTEM_PROMPT, user=_to_user_payload(request))
        elapsed_ms = (time.monotonic() - t0) * 1000.0
        outcome = raw.get("outcome") if isinstance(raw, dict) else None
        question_count = (
            len(raw.get("questions") or [])
            if isinstance(raw, dict) and outcome == "needs_input"
            else 0
        )
        log.info(
            "CLARIFY: LLM responded in %.0fms (outcome=%s, questions=%d)",
            elapsed_ms,
            outcome,
            question_count,
        )
        try:
            return _CLARIFY_RESULT_ADAPTER.validate_python(raw)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            log.warning(
                "CLARIFY: validation failed, asking LLM to repair. First error: %s",
                errors[0] if errors else "<none>",
            )
            repair_user = {
                "original_request": _to_user_payload(request),
                "your_previous_output": raw,
                "validation_errors": errors,
                "instruction": (
                    "Your previous JSON output failed schema validation. "
                    "Re-emit the FULL corrected JSON object addressing the "
                    "errors above. Output JSON only, no prose."
                ),
            }
            raw_retry = self._json_call(system=SYSTEM_PROMPT, user=repair_user)
            try:
                return _CLARIFY_RESULT_ADAPTER.validate_python(raw_retry)
            except ValidationError as exc2:
                fragment = json.dumps(raw_retry, default=str)[:300]
                raise RuntimeError(
                    f"CLARIFY LLM returned malformed JSON for ClarifyResult after repair: "
                    f"{exc2.errors(include_url=False)}; head={fragment!r}"
                ) from exc2


__all__ = [
    "SYSTEM_PROMPT",
    "ClarifyNeedsInput",
    "ClarifyProceed",
    "LLMClarifierClient",
]
