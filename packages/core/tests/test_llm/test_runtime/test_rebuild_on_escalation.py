"""PR2.3 — verify that ToolDispatcher.build() is only called once initially and
then only when a `request_additional_tools` escalation actually occurred.

Strategy: wrap ToolDispatcher.build() with a spy that counts invocations,
then drive a minimal 3-turn tool loop through ReportRunner:

  turn 0 — LLM returns a normal tool call (stock_quote)  → no rebuild
  turn 1 — LLM returns request_additional_tools          → rebuild (1 extra call)
  turn 2 — LLM returns no tool calls                     → loop exits

Expected build() call count = 2: one initial build before the loop, one
rebuild after the escalation in turn 1.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _empty_skill_registry(tmp_path: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
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


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


async def test_build_called_once_initial_and_once_on_escalation(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
) -> None:
    """build() should be invoked exactly twice: once before the loop and once
    after the turn that contained request_additional_tools."""

    # Turn 0: normal tool call — no escalation
    normal_call = ToolCall(id="c0", name="stock_quote", arguments={"symbol": "AAPL"})
    # Turn 1: escalation tool call
    escalation_call = ToolCall(
        id="c1",
        name="request_additional_tools",
        arguments={"reason": "need more data", "category_hint": None},
    )
    # Turn 2: submit_report to end the data-fetch loop
    submit_payload = {"cover": {"title": "AAPL"}, "sections": []}
    submit_call = ToolCall(id="c2", name="submit_report", arguments=submit_payload)

    script = FakeProviderScript(
        turns=[
            ("tool_calls", [normal_call]),  # loop turn 0 — normal call, no rebuild
            ("tool_calls", [escalation_call]),  # loop turn 1 — escalation, triggers rebuild
            ("final", ""),  # loop turn 2 — no tool calls, breaks loop
            ("tool_calls", [submit_call]),  # writing turn — forced submit_report
        ]
    )
    provider = FakeProvider(script=script)

    data = FakeDataDispatcher(
        manifest={
            "equity_research": {
                "stock_quote": {
                    "name": "stock_quote",
                    "description": "Real-time stock quote.",
                    "parameters": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                },
            }
        }
    )
    dispatcher = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )

    build_call_count = 0
    original_build = dispatcher.build

    async def spy_build(department_id: str, **kwargs: Any) -> Any:
        nonlocal build_call_count
        build_call_count += 1
        return await original_build(department_id, **kwargs)

    dispatcher.build = spy_build  # type: ignore[method-assign]

    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=dispatcher,
        resolve=_always(_resolved()),
        registry=object(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_rebuild_test",
    )

    [
        e
        async for e in runner.run(
            department_id="equity_research",
            user_id="u1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    ]

    # Loop ran 3 turns (normal_call, escalation_call, empty → break), so:
    #   build #1 — initial, before the loop
    #   build #2 — after turn 1 (escalation)
    # No build after turn 0 (normal call) and no build after turn 2 (loop broke).
    assert build_call_count == 2, f"Expected build() called exactly 2 times, got {build_call_count}"
