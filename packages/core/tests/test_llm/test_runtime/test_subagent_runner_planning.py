from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.events import ReportError, ReportPhase
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_runner import (
    PLAN_REPORT_TOOL_NAME,
    SubagentReportRunner,
)
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)


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
    (root / "shared" / "output_discipline.yaml.j2").write_text("")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan for {{ user_input }} via plan_report.
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
                    {
                        "id": "company_overview",
                        "title": "Overview",
                        "instructions": "...",
                    }
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


def _valid_plan_args() -> dict:
    return {
        "company_thesis": "MSFT thesis.",
        "cross_section_themes": ["t1", "t2"],
        "sections": [
            {
                "section_id": "company_overview",
                "title": "Overview",
                "narrative_goal": "Frame the business.",
                "key_questions": ["q1", "q2", "q3"],
                "target_depth": "standard",
                "word_budget": 200,
                "data_paths": [],
                "cross_refs": [],
            }
        ],
    }


@pytest.mark.asyncio
async def test_planning_phase_emits_phase_event_and_validates_plan(
    prompts_root: Path, frameworks_root: Path
) -> None:
    plan_call = ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_valid_plan_args())
    provider = FakeProvider(script=FakeProviderScript(turns=[("tool_calls", [plan_call])]))
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,  # unused here
        report_id_factory=lambda: "r_plan",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
        # Stop after planning phase to focus this test.
        if len(events) >= 3:
            break
    types = [type(e).__name__ for e in events]
    assert types[0] == "ReportStart"
    assert any(isinstance(e, ReportPhase) and e.phase == "planning" for e in events)


@pytest.mark.asyncio
async def test_planning_invalid_then_repair_succeeds(
    prompts_root: Path, frameworks_root: Path
) -> None:
    bad = {"company_thesis": "", "cross_section_themes": [], "sections": []}
    good = ToolCall(id="p1", name=PLAN_REPORT_TOOL_NAME, arguments=_valid_plan_args())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [good]),
            ]
        )
    )
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,
        report_id_factory=lambda: "r_repair",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
        if len(events) >= 3:
            break
    # Two calls to the provider (initial + 1 repair).
    assert len(provider.captured_requests) >= 2


@pytest.mark.asyncio
async def test_planning_invalid_twice_emits_report_error(
    prompts_root: Path, frameworks_root: Path
) -> None:
    bad = {"company_thesis": "", "cross_section_themes": [], "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
                ("tool_calls", [ToolCall(id="p1", name=PLAN_REPORT_TOOL_NAME, arguments=bad)]),
            ]
        )
    )
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=object(),
        flagship_provider_factory=lambda r: provider,
        subagent_provider_factory=lambda r: provider,
        report_id_factory=lambda: "r_abort",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
    assert any(isinstance(e, ReportError) for e in events)
