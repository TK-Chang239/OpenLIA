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
pipeline. You receive the user's free-form request, any tickers the
caller already pinned, and a short description of the template the
report will follow.

You have two jobs:

(1) IDENTIFY THE SUBJECT. The user may type the ticker outright
    ("Initiation on NVDA"), name the company instead ("Update on
    Nvidia's data-center business"), describe a sector ("the lithium
    miners"), or describe a theme ("AI infrastructure margins this
    cycle"). Extract every ticker the request implies into
    `inferred_tickers`. Use the exchange-suffix form the pipeline
    expects (e.g. "NVDA", "AAPL", "TSM" — bare US tickers; for
    non-US names use the EODHD form like "0700.HK", "005930.KS").
    If the request is genuinely topic-only and no specific tickers
    are implied, return `inferred_tickers: []` AND ask via
    `needs_input` what name/ticker the user wants the report anchored
    to — most v2.3 stages assume at least one subject ticker.

(2) DECIDE WHETHER TO ASK ANYTHING ELSE. If the prompt + template
    are coherent enough to write a good report from, proceed. Don't
    invent hypothetical "nice to know" questions. Ask only when a
    one-line answer would change which report you'd write.

If the caller already pinned `tickers` (non-empty), trust them and
mirror them into `inferred_tickers` verbatim — they came from the
user's explicit input upstream.

If you do ask, cap at {MAX_CLARIFY_QUESTIONS} and only ask what you
actually need.

Return EXACTLY one JSON object matching ONE of these shapes:

Proceed (the typical case — subject identified, nothing else needs clarifying):
{{
  "outcome": "proceed",
  "inferred_tickers": ["NVDA"],
  "assumptions": ["concrete assumption 1", "concrete assumption 2"]
}}

NeedsInput (when a question genuinely blocks a good report —
including the case where you couldn't identify the subject ticker):
{{
  "outcome": "needs_input",
  "questions": [
    {{
      "id": "ticker",
      "question": "Which ticker should this report cover?",
      "why_blocking": "Pipeline needs a subject ticker to fetch data and run valuation.",
      "default": "SPY"
    }}
  ]
}}

Rules:
- "outcome" MUST be "proceed" or "needs_input" (exact strings).
- `inferred_tickers` is REQUIRED in the `proceed` shape, even if
  empty (which should only happen on `needs_input`). Symbols only —
  no descriptions, no exchange names.
- Every question MUST include `id`, `question`, `why_blocking`, `default`.
  When the missing piece is the subject ticker, use id "ticker" so
  the runner knows to copy the answer into the run's ticker list.
- Assumptions in `proceed` describe what you locked in for the user
  (e.g. "horizon: 12 months", "focus: valuation") — concrete, not
  generic boilerplate. They are not required; an empty list is fine
  when the prompt was fully self-describing.
- Output JSON only. No prose, no markdown fences.
""".strip()


def _to_user_payload(request: ClarifierRequest) -> dict[str, Any]:
    return {
        "raw_prompt": request.raw_prompt,
        "language": request.language.value,
        "tickers": request.tickers,
        "template": {
            "id": request.report_type.value,
            "shape": request.template.shape_description,
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

    @staticmethod
    def _build_user_prompt(request: ClarifierRequest) -> str:
        """Serialize the user-side payload as the JSON string the LLM
        sees. Exposed so tests (and any future telemetry) can assert
        the prompt contains the template's shape_description."""
        return json.dumps(_to_user_payload(request), ensure_ascii=False, indent=2)

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
