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

# A duck-typed JSON callable. Matches the shape of
# `openlia_server.services.v2_stage_factory.SyncJsonLlmClient.call`.
JsonCall = Callable[..., dict[str, Any]]


_CLARIFY_RESULT_ADAPTER: TypeAdapter[ClarifyResult] = TypeAdapter(ClarifyResult)


SYSTEM_PROMPT = f"""You are the CLARIFY stage of an equity-research report
pipeline. Your ONLY job is to decide whether the user's prompt is clear
enough for the pipeline to proceed, OR whether one to three blocking
questions must be answered first.

Bar for asking a question: "would a wrong default here send the whole
pipeline down the wrong path?" — NOT "could this be more specified?".
Asking is expensive (one round-trip with the user); silently defaulting
the wrong way is more expensive. When in doubt, proceed and surface the
defaults you assumed.

Limits:
- At most {MAX_CLARIFY_QUESTIONS} questions in needs_input. Need more than
  {MAX_CLARIFY_QUESTIONS}? Choose a default report shape and proceed
  instead — that means the prompt is too vague to interrogate around.

Return EXACTLY one JSON object matching ONE of these shapes:

Proceed:
{{
  "outcome": "proceed",
  "assumptions": ["audience: PM", "horizon: 12 months", "report type: initiation"]
}}

NeedsInput:
{{
  "outcome": "needs_input",
  "questions": [
    {{
      "id": "horizon",
      "question": "What investment horizon should the report target?",
      "why_blocking": "Drives DCF projection length and growth assumptions.",
      "default": "12 months"
    }}
  ]
}}

Rules:
- "outcome" MUST be "proceed" or "needs_input" (exact strings).
- Every question MUST include `id`, `question`, `why_blocking`, `default`.
- Assumptions in `proceed` should be visible (e.g. "audience: PM"); they
  flow into the thesis and let the user see what the pipeline locked in.
- Output JSON only. No prose, no markdown fences.
""".strip()


def _to_user_payload(request: ClarifierRequest) -> dict[str, Any]:
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "report_type": request.report_type.value,
        "tickers": request.tickers,
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
        raw = self._json_call(system=SYSTEM_PROMPT, user=_to_user_payload(request))
        try:
            return _CLARIFY_RESULT_ADAPTER.validate_python(raw)
        except ValidationError as exc:
            fragment = json.dumps(raw, default=str)[:300]
            raise RuntimeError(
                f"CLARIFY LLM returned malformed JSON for ClarifyResult: "
                f"{exc.errors(include_url=False)}; head={fragment!r}"
            ) from exc


__all__ = [
    "SYSTEM_PROMPT",
    "ClarifyNeedsInput",
    "ClarifyProceed",
    "LLMClarifierClient",
]
