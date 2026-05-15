"""Tests for the fetching-phase forced-escalation contract.

Background:
  Under the Phase B empty-starter-pack contract, the LLM enters the fetching
  loop with only `request_additional_tools`, `read_payload`, and (optionally)
  `web_search` exposed. If the model produces a text-only response on turn 0
  (e.g. a refusal saying "no data tools available"), the loop breaks
  immediately and the writing phase runs with no fetched data — yielding a
  report whose sections all say "no data available".

  To prevent that failure mode, the fetching loop forces the model to call
  `request_additional_tools` on turn 0. The 3-failure directive in
  `ToolDispatcher` provides graceful degradation if escalation truly yields
  nothing.

  These tests pin the contract:
    1. Fetching turn 0 carries provider-specific `tool_choice` forcing
       `request_additional_tools`.
    2. Subsequent fetching turns do NOT carry that constraint — the model
       may call data tools, escalate again, or exit naturally.
    3. The forcing is provider-specific (Anthropic, OpenAI/OpenRouter,
       Gemini shapes).
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio


_SUBMIT_PAYLOAD = {
    "cover": {
        "title": "AAPL",
        "subtitle": "Coverage initiation",
        "tagline": "Constructive setup",
    },
    "sections": [],
}


def _empty_skill_registry(tmp_path: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


def _resolved(provider_kind: str = "fake") -> ResolvedModel:
    return ResolvedModel(
        provider_kind=provider_kind,
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


def _always(resolved: ResolvedModel):
    def _r(
        *,
        department_id: str,
        user_id: str | None,
        registry: Any,
        model_id_override: str | None = None,
    ) -> ResolvedModel:
        return resolved

    return _r


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps(
            {
                "title": "Stock Initiation",
                "sections": [
                    {"id": "overview", "title": "Overview", "instructions": "..."},
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    shared = root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
                  Framework: {{ framework | tojson }}
            """
        )
    )
    return root


def _make_runner(
    provider: FakeProvider,
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    *,
    resolved: ResolvedModel | None = None,
    data: FakeDataDispatcher | None = None,
) -> ReportRunner:
    dispatcher = ToolDispatcher(
        data_dispatcher=data or FakeDataDispatcher(),
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    return ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=dispatcher,
        resolve=_always(resolved or _resolved()),
        registry=object(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_fetch_force_test",
    )


async def _collect(runner: ReportRunner) -> list[Any]:
    return [
        e
        async for e in runner.run(
            department_id="equity_research",
            user_id="u1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    ]


# ---------------------------------------------------------------------------
# Contract: fetching turn 0 forces request_additional_tools
# ---------------------------------------------------------------------------


async def test_fetching_turn_0_forces_request_additional_tools_anthropic(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Turn 0 of fetching phase must force the Anthropic-shaped tool_choice
    targeting request_additional_tools. This prevents the model from exiting
    the fetching loop with a text-only refusal before any data tool is
    discovered."""
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("final", ""),  # fetching turn 0 — no tool calls (model refusal)
            ("tool_calls", [submit_call]),  # writing turn 0 — submit forced by final-turn logic
        ]
    )
    provider = FakeProvider(script=script)
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("anthropic"),
    )
    await _collect(runner)

    fetch_req = provider.captured_requests[0]
    assert fetch_req.tool_choice == {"type": "tool", "name": "request_additional_tools"}


async def test_fetching_turn_0_forces_request_additional_tools_openai(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """OpenAI/OpenRouter shape: chat.completions function tool_choice."""
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("final", ""),
            ("tool_calls", [submit_call]),
        ]
    )
    provider = FakeProvider(script=script)
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("openai"),
    )
    await _collect(runner)

    fetch_req = provider.captured_requests[0]
    assert fetch_req.tool_choice == {
        "type": "function",
        "function": {"name": "request_additional_tools"},
    }


async def test_fetching_turn_0_forces_request_additional_tools_gemini(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Gemini shape: function_calling_config with ANY mode + allowed_function_names."""
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("final", ""),
            ("tool_calls", [submit_call]),
        ]
    )
    provider = FakeProvider(script=script)
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("gemini"),
    )
    await _collect(runner)

    fetch_req = provider.captured_requests[0]
    assert fetch_req.tool_choice == {
        "function_calling_config": {
            "mode": "ANY",
            "allowed_function_names": ["request_additional_tools"],
        }
    }


# ---------------------------------------------------------------------------
# Contract: only turn 0 is forced; later turns are unconstrained
# ---------------------------------------------------------------------------


async def test_fetching_later_turns_do_not_force_tool_choice(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """After turn 0, the model may freely call data tools, escalate again,
    web_search, or exit. Turn 1+ must NOT carry the forced tool_choice —
    otherwise the model is stuck calling request_additional_tools forever."""
    escalation_call = ToolCall(
        id="c0",
        name="request_additional_tools",
        arguments={"reason": "need NVDA financials", "category_hint": None},
    )
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("tool_calls", [escalation_call]),  # fetching turn 0 — forced escalation
            ("final", ""),  # fetching turn 1 — natural exit, MUST NOT be forced
            ("tool_calls", [submit_call]),  # writing turn 0 — submit
        ]
    )
    provider = FakeProvider(script=script)
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("anthropic"),
    )
    await _collect(runner)

    # Turn 0 forced
    assert provider.captured_requests[0].tool_choice == {
        "type": "tool",
        "name": "request_additional_tools",
    }
    # Turn 1 unconstrained
    assert provider.captured_requests[1].tool_choice is None


# ---------------------------------------------------------------------------
# Contract: forcing is provider-specific (no constraint for unknown kinds)
# ---------------------------------------------------------------------------


async def test_fetching_turn_0_unknown_provider_falls_back_to_openai_shape(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Unknown provider_kind falls back to the OpenAI-compatible chat.completions
    tool_choice shape — matching `_submit_report_tool_choice`'s contract."""
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("final", ""),
            ("tool_calls", [submit_call]),
        ]
    )
    provider = FakeProvider(script=script)
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("ollama"),
    )
    await _collect(runner)

    assert provider.captured_requests[0].tool_choice == {
        "type": "function",
        "function": {"name": "request_additional_tools"},
    }


# ---------------------------------------------------------------------------
# Contract: tools loaded via escalation are actually passed on next turn
# ---------------------------------------------------------------------------


async def test_escalated_tools_appear_in_next_fetching_turn(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """Regression guard: after `request_additional_tools` succeeds, the
    next fetching turn's LLMRequest tools must include the newly-added
    tool entries — so the model can actually call them."""
    escalation_call = ToolCall(
        id="c0",
        name="request_additional_tools",
        arguments={"reason": "fetch NVDA quote", "category_hint": None},
    )
    submit_call = ToolCall(id="w0", name="submit_report", arguments=_SUBMIT_PAYLOAD)
    script = FakeProviderScript(
        turns=[
            ("tool_calls", [escalation_call]),  # turn 0 — escalate
            ("final", ""),  # turn 1 — exit
            ("tool_calls", [submit_call]),  # writing — submit
        ]
    )
    provider = FakeProvider(script=script)

    # FakeDataDispatcher.expand_tools matches on reason verbatim.
    data = FakeDataDispatcher(
        results={
            "expand::fetch NVDA quote": [
                {
                    "name": "stock_quote",
                    "description": "Real-time stock quote.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                }
            ]
        }
    )
    runner = _make_runner(
        provider,
        prompts_root,
        frameworks_root,
        tmp_path,
        resolved=_resolved("anthropic"),
        data=data,
    )
    await _collect(runner)

    # Turn 1 request should carry the freshly-added stock_quote tool.
    turn_1_req = provider.captured_requests[1]
    tool_names = [t.name for t in (turn_1_req.tools or [])]
    assert "stock_quote" in tool_names, (
        f"Expected stock_quote in turn-1 tools after escalation; got {tool_names}"
    )
