"""Env-gated smoke test for the v2.3 CLARIFY stage against a real model.

Gated on:
    SMOKE=1                          enables the smoke suite
    OPENAI_API_KEY                   real OpenAI key
    OPENLIA_V2_3_CLARIFY_MODEL       model id (default to a cheap mini)

By default ``uv run pytest`` skips this file. To run:

    SMOKE=1 OPENAI_API_KEY=sk-... OPENLIA_V2_3_CLARIFY_MODEL=gpt-5.4-mini \
        uv run pytest packages/core/tests/test_smoke_v2_3.py -v

Cost shape: one ``LLMClarifierClient.clarify()`` call per test against
the real model. With a mini-tier model the suite costs under a cent.
"""

from __future__ import annotations

import os
import uuid

import pytest

_SMOKE_ON = os.environ.get("SMOKE", "").strip() == "1"
_HAS_OPENAI = bool(os.environ.get("OPENAI_API_KEY", "").strip())
_HAS_CLARIFY_MODEL = bool(os.environ.get("OPENLIA_V2_3_CLARIFY_MODEL", "").strip())

pytestmark = pytest.mark.skipif(
    not (_SMOKE_ON and _HAS_OPENAI and _HAS_CLARIFY_MODEL),
    reason=("Set SMOKE=1 + OPENAI_API_KEY + OPENLIA_V2_3_CLARIFY_MODEL to run v2.3 smoke tests."),
)


def _build_real_clarifier():
    """Build an LLMClarifierClient bound to a live OpenAI provider."""
    import asyncio
    import json
    import re

    from openlia.llm.adapters import build_adapter
    from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
    from openlia.llm.types import (
        Capabilities,
        LLMRequest,
        Message,
        ProviderCredentials,
        ResponseFormat,
    )

    provider = build_adapter(
        kind="openai",
        credentials=ProviderCredentials(
            api_key=os.environ["OPENAI_API_KEY"],
            base_url=os.environ.get("OPENAI_BASE_URL"),
            env_var_name="OPENAI_API_KEY",
        ),
        model=os.environ["OPENLIA_V2_3_CLARIFY_MODEL"],
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=1024,
        ),
    )
    fence_re = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)

    def _json_call(*, system: str | None, user) -> dict:
        text_user = user if isinstance(user, str) else json.dumps(user, default=str)
        request = LLMRequest(
            messages=[Message(role="user", content=text_user)],
            system=(system or "")
            + "\n\nReturn ONLY a single JSON object. No prose, no markdown fences.",
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=1024,
            temperature=0.2,
        )
        response = asyncio.run(provider.generate(request))
        text = (response.text or "").strip()
        match = fence_re.match(text)
        if match is not None:
            text = match.group(1).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            first = text.find("{")
            last = text.rfind("}")
            if first == -1 or last <= first:
                raise
            return json.loads(text[first : last + 1])

    return LLMClarifierClient(_json_call)


def test_clarifier_proceeds_on_clear_prompt() -> None:
    """A specific prompt + ticker should let the clarifier emit
    ``outcome=proceed`` with at least one stated assumption."""
    from openlia.llm.runtime.report_v2_3.clients.clarifier import ClarifierRequest
    from openlia.llm.runtime.report_v2_3.schemas import (
        ClarifyProceed,
        Language,
        ReportType,
    )
    from openlia.llm.runtime.report_v2_3.templates import get_builtin

    clarifier = _build_real_clarifier()
    result = clarifier.clarify(
        ClarifierRequest(
            raw_prompt=(
                "Write a 12-month initiation report on NVDA targeted at a "
                "PM, with a DCF and competitive overview."
            ),
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
            template=get_builtin(ReportType.INITIATION),
        )
    )
    assert isinstance(result, ClarifyProceed), (
        f"Expected proceed for a specific prompt; got {type(result).__name__}"
    )
    # A real clarifier should state at least one assumption (audience,
    # horizon, valuation method, etc.) — but we don't pin exact strings.
    assert len(result.assumptions) >= 1


def test_clarifier_runs_through_runner_and_persists_state() -> None:
    """Drive the real clarifier through ReportRunner and confirm a
    ClarifyProceed result lets the pipeline walk on through the
    remaining NoOp stages to COMPLETE.
    """
    from openlia.llm.runtime.report_v2_3.runner import ReportRunner
    from openlia.llm.runtime.report_v2_3.schemas import Language, ReportType, RunStatus
    from openlia.llm.runtime.report_v2_3.slots import V23Slot
    from openlia.llm.runtime.report_v2_3.stages import (
        PIPELINE_ORDER,
        ClarifyStage,
        NoOpStage,
        RealAssembleStage,
        StageContext,
    )
    from openlia.llm.runtime.report_v2_3.state import ReportState

    clarifier = _build_real_clarifier()
    stages = {slot: NoOpStage(slot) for slot in PIPELINE_ORDER}
    stages[V23Slot.CLARIFY] = ClarifyStage(clarifier)
    runner = ReportRunner(
        stages=stages,
        assemble=RealAssembleStage(),
        ctx=StageContext(clients={}, tools={}, extras={}),
    )

    state = ReportState(
        run_id=str(uuid.uuid4()),
        user_id="smoke",
        raw_prompt=(
            "Write a 12-month initiation report on NVDA targeted at a PM. "
            "Include a DCF and competitive overview."
        ),
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )

    state = runner.start(state)

    # The all-NoOp downstream + RealAssembleStage gracefully no-ops
    # when state is incomplete (per its design), so this completes.
    assert state.status == RunStatus.COMPLETE, (
        f"Expected COMPLETE; got {state.status} (last_error={state.last_error!r})"
    )
