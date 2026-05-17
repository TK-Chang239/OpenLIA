"""Every LLM call the subagent runner makes must emit an llm.call.done
trace event carrying cached_input_tokens, matching the contract the
classic ReportRunner now follows."""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_client import SECTION_DRAFT_TOOL_NAME
from openlia.llm.runtime.subagent_runner import (
    PLAN_REPORT_TOOL_NAME,
    SubagentReportRunner,
)
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel, ToolCall


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(
            streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192
        ),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan via plan_report. {{ user_input }} {{ style_guide }} {{ framework_summary }}
              stock_initiation:
                user: |
                  Topic: {{ user_input }}
            """
        )
    )
    return root


@pytest.fixture
def frameworks_root(tmp_path: Path) -> Path:
    root = tmp_path / "frameworks"
    root.mkdir()
    (root / "stock_initiation.json").write_text(
        json.dumps(
            {
                "title": "Stock Initiation",
                "sections": [
                    {"id": "company_overview", "title": "Overview", "instructions": "..."}
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


@pytest.mark.asyncio
async def test_runner_emits_cached_input_tokens_for_every_llm_call(
    prompts_root: Path, frameworks_root: Path
) -> None:
    plan_args = {
        "company_thesis": "thesis",
        "cross_section_themes": ["t1", "t2"],
        "sections": [
            {
                "section_id": "company_overview",
                "title": "Overview",
                "narrative_goal": "g",
                "key_questions": ["q1", "q2", "q3"],
                "target_depth": "standard",
                "word_budget": 200,
                "data_paths": [],
                "cross_refs": [],
            }
        ],
    }
    draft = {
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": " ".join(["w"] * 200)}],
        "citations_used": ["c1"],
        "word_count": 200,
        "open_questions": [],
    }
    editor = {
        "cover": {"title": "X", "subtitle": "Y", "tagline": "Z"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Final body."}],
            }
        ],
    }

    flagship = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=plan_args)],
                ),
                ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=editor)]),
            ]
        )
    )
    subagent = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="s0", name=SECTION_DRAFT_TOOL_NAME, arguments=draft)]),
            ]
        )
    )

    traces: list[tuple[str, str, dict | None]] = []

    def recorder(cat: str, msg: str, payload: dict | None) -> None:
        traces.append((cat, msg, payload))

    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: flagship,
        subagent_provider_factory=lambda r: subagent,
        report_id_factory=lambda: "r_tel",
        frameworks_root=frameworks_root,
        trace=recorder,
    )
    async for _ in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        pass

    done_events = [t for t in traces if t[0] == "llm.call.done"]
    # 3 LLM calls: planning + 1 subagent + 1 editor.
    assert len(done_events) == 3
    for _, _, payload in done_events:
        assert payload is not None
        assert "cached_input_tokens" in payload
