"""Usage logging on SyncJsonLlmClient / SyncToolLlmClient.

These guard the diagnostic line that future PRs read to size
``max_tokens`` per stage from observed output, instead of guessing.
The contract: every LLM call emits one structured line carrying
``stage``, ``model``, token counts, the ``max_tokens`` ceiling, the
provider-reported ``finish_reason``, and a ``truncated`` flag derived
from the finish_reason vocab across providers.

Truncated calls must log at WARNING so they surface under default
filtering; non-truncated calls log at INFO so the stream is opt-in.
"""

from __future__ import annotations

import logging

import pytest
from openlia.llm.types import LLMRequest, LLMResponse, Message
from openlia_server.services.v2_stage_factory import (
    SyncJsonLlmClient,
    SyncToolLlmClient,
)


class _FakeProvider:
    """Minimal LLMProvider stand-in returning a canned response.

    Mirrors the duck-typed surface the stage clients touch: ``model``
    attribute + async ``generate(request) -> LLMResponse``.
    """

    def __init__(self, response: LLMResponse, *, model: str = "test-model") -> None:
        self._response = response
        self.model = model
        self.last_request: LLMRequest | None = None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        return self._response


def _response(
    *,
    text: str = '{"x": 1}',
    finish_reason: str = "stop",
    input_tokens: int = 120,
    output_tokens: int = 42,
    cached_input_tokens: int = 0,
    reasoning_output_tokens: int = 0,
) -> LLMResponse:
    return LLMResponse(
        text=text,
        finish_reason=finish_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached_input_tokens=cached_input_tokens,
        reasoning_output_tokens=reasoning_output_tokens,
    )


# ---------------------------------------------------------------------------
# SyncJsonLlmClient — normal + truncated
# ---------------------------------------------------------------------------


def test_json_client_logs_usage_line_with_stage(caplog: pytest.LogCaptureFixture) -> None:
    """A successful call emits a single structured log line at INFO
    carrying the fields we'll grep on to size max_tokens later."""
    provider = _FakeProvider(_response(output_tokens=42, input_tokens=120))
    client = SyncJsonLlmClient(provider, max_tokens=2048, temperature=0.3, stage="plan")

    with caplog.at_level(logging.INFO, logger="openlia_server.services.v2_stage_factory"):
        client.call(system="sys", user={"k": "v"})

    usage_lines = [r for r in caplog.records if "llm_usage" in r.getMessage()]
    assert len(usage_lines) == 1
    msg = usage_lines[0].getMessage()
    assert "stage=plan" in msg
    assert "model=test-model" in msg
    assert "in=120" in msg
    assert "out=42" in msg
    assert "max=2048" in msg
    assert "truncated=False" in msg
    assert "finish=stop" in msg
    assert usage_lines[0].levelno == logging.INFO


@pytest.mark.parametrize(
    "finish_reason",
    [
        "length",  # OpenAI chat completions, OpenAI compat, OpenRouter, Ollama
        "max_tokens",  # Anthropic
        "MAX_TOKENS",  # Gemini (upper-case)
        "incomplete",  # OpenAI Responses (status=incomplete when budget hit)
    ],
)
def test_json_client_marks_truncated_across_provider_vocab(
    finish_reason: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Truncation detection must span every adapter's finish_reason vocab.
    Without all four, ceilings sized from logs would under-count
    truncations on whichever provider got missed."""
    provider = _FakeProvider(_response(finish_reason=finish_reason, output_tokens=2048))
    client = SyncJsonLlmClient(provider, max_tokens=2048, temperature=0.3, stage="plan")

    with caplog.at_level(logging.WARNING, logger="openlia_server.services.v2_stage_factory"):
        client.call(system="sys", user={"k": "v"})

    usage_lines = [r for r in caplog.records if "llm_usage" in r.getMessage()]
    assert len(usage_lines) == 1
    assert "truncated=True" in usage_lines[0].getMessage()
    assert usage_lines[0].levelno == logging.WARNING


def test_json_client_logs_cached_input_tokens(caplog: pytest.LogCaptureFixture) -> None:
    """Prompt-cache hits affect cost more than raw input tokens; the log
    line carries cached_input_tokens so cost analysis is downstream of
    the same observation pass."""
    provider = _FakeProvider(_response(input_tokens=120, cached_input_tokens=80))
    client = SyncJsonLlmClient(provider, max_tokens=2048, temperature=0.3, stage="write")

    with caplog.at_level(logging.INFO, logger="openlia_server.services.v2_stage_factory"):
        client.call(system="sys", user={"k": "v"})

    msg = next(r.getMessage() for r in caplog.records if "llm_usage" in r.getMessage())
    assert "cached=80" in msg


# ---------------------------------------------------------------------------
# SyncToolLlmClient — tool-use turn logging
# ---------------------------------------------------------------------------


def test_tool_client_logs_usage_line_with_stage(caplog: pytest.LogCaptureFixture) -> None:
    """RESEARCH runs a multi-turn tool loop; each turn must emit the
    same usage line so we can size ``OPENLIA_V2_3_RESEARCH_MAX_TOKENS``
    from the longest observed turn, not from the whole-loop total."""
    provider = _FakeProvider(_response(output_tokens=900, input_tokens=4500))
    client = SyncToolLlmClient(provider, max_tokens=8192, temperature=0.3, stage="research")

    with caplog.at_level(logging.INFO, logger="openlia_server.services.v2_stage_factory"):
        client.send(system="sys", messages=[Message(role="user", content="hi")], tools=[])

    usage_lines = [r for r in caplog.records if "llm_usage" in r.getMessage()]
    assert len(usage_lines) == 1
    msg = usage_lines[0].getMessage()
    assert "stage=research" in msg
    assert "out=900" in msg
    assert "max=8192" in msg
    assert "truncated=False" in msg


def test_tool_client_marks_truncated_on_length(caplog: pytest.LogCaptureFixture) -> None:
    """A tool-loop turn that truncates leaves tool_calls / final text
    incomplete and breaks the researcher's state machine — the truncated
    flag is how operators correlate downstream RESEARCH failures with
    the ceiling that caused them."""
    provider = _FakeProvider(_response(finish_reason="length", output_tokens=8192))
    client = SyncToolLlmClient(provider, max_tokens=8192, temperature=0.3, stage="research")

    with caplog.at_level(logging.WARNING, logger="openlia_server.services.v2_stage_factory"):
        client.send(system="sys", messages=[Message(role="user", content="hi")], tools=[])

    usage_lines = [r for r in caplog.records if "llm_usage" in r.getMessage()]
    assert len(usage_lines) == 1
    assert "truncated=True" in usage_lines[0].getMessage()
    assert usage_lines[0].levelno == logging.WARNING


# ---------------------------------------------------------------------------
# Reasoning effort plumbing + telemetry
# ---------------------------------------------------------------------------


def test_json_client_forwards_reasoning_effort_to_request() -> None:
    """When constructed with a reasoning_effort, the value must appear on
    the LLMRequest the provider receives. v2_3_wiring relies on this to
    deliver per-stage reasoning to the adapter layer."""
    from openlia.llm.types import ReasoningEffort

    provider = _FakeProvider(_response())
    client = SyncJsonLlmClient(
        provider,
        max_tokens=16_384,
        stage="plan",
        reasoning_effort=ReasoningEffort.HIGH,
    )
    client.call(system="sys", user={"k": "v"})
    assert provider.last_request is not None
    assert provider.last_request.reasoning_effort is ReasoningEffort.HIGH


def test_json_client_defaults_reasoning_effort_to_none() -> None:
    """Default construction (no reasoning_effort) must send None so the
    adapter does not emit the provider-specific thinking block."""
    provider = _FakeProvider(_response())
    client = SyncJsonLlmClient(provider, max_tokens=2048, stage="plan")
    client.call(system="sys", user={"k": "v"})
    assert provider.last_request is not None
    assert provider.last_request.reasoning_effort is None


def test_tool_client_forwards_reasoning_effort_to_request() -> None:
    from openlia.llm.types import ReasoningEffort

    provider = _FakeProvider(_response())
    client = SyncToolLlmClient(
        provider,
        max_tokens=16_384,
        stage="research",
        reasoning_effort=ReasoningEffort.MEDIUM,
    )
    client.send(system="sys", messages=[Message(role="user", content="hi")], tools=[])
    assert provider.last_request is not None
    assert provider.last_request.reasoning_effort is ReasoningEffort.MEDIUM


def test_log_line_carries_reasoning_out(caplog: pytest.LogCaptureFixture) -> None:
    """The usage log surfaces the reasoning-token portion of the output
    separately from visible-text tokens so the sized-from-data pass can
    size visible-output and thinking headroom independently."""
    provider = _FakeProvider(_response(output_tokens=1200, reasoning_output_tokens=900))
    client = SyncJsonLlmClient(provider, max_tokens=16_384, stage="synthesize")

    with caplog.at_level(logging.INFO, logger="openlia_server.services.v2_stage_factory"):
        client.call(system="sys", user={"k": "v"})

    msg = next(r.getMessage() for r in caplog.records if "llm_usage" in r.getMessage())
    assert "out=1200" in msg
    assert "reasoning_out=900" in msg


def test_log_line_reasoning_out_zero_when_not_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Most calls have no thinking — the log still carries reasoning_out=0
    so a fixed grep / parser does not need to special-case absence."""
    provider = _FakeProvider(_response(output_tokens=42))  # default reasoning_output_tokens=0
    client = SyncJsonLlmClient(provider, max_tokens=2048, stage="plan")

    with caplog.at_level(logging.INFO, logger="openlia_server.services.v2_stage_factory"):
        client.call(system="sys", user={"k": "v"})

    msg = next(r.getMessage() for r in caplog.records if "llm_usage" in r.getMessage())
    assert "reasoning_out=0" in msg
