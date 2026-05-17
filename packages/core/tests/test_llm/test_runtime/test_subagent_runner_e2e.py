from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
from openlia.llm.runtime.events import ReportComplete, ReportPhase, ReportSectionComplete
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.subagent_client import SECTION_DRAFT_TOOL_NAME
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
    (root / "shared" / "section_subagent_role.yaml.j2").write_text("ROLE")
    (root / "shared" / "editor_role.yaml.j2").write_text("EDITOR")
    (root / "shared" / "report_schema_strictness.yaml.j2").write_text("STRICT")
    (root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              subagent_planning: |
                Plan {{ user_input }}. style={{ style_guide }} fw={{ framework_summary }}
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


def _plan_args() -> dict:
    return {
        "company_thesis": "MSFT thesis.",
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


def _section_draft_args(content: str) -> dict:
    return {
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": content}],
        "citations_used": ["c1"],
        "word_count": len(content.split()),
        "open_questions": [],
    }


def _editor_args() -> dict:
    return {
        "cover": {"title": "MSFT", "subtitle": "Initiation", "tagline": "Constructive"},
        "sections": [
            {
                "id": "company_overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Final body."}],
            }
        ],
    }


@pytest.mark.asyncio
async def test_runner_end_to_end_happy_path(prompts_root: Path, frameworks_root: Path) -> None:
    flagship = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_plan_args())],
                ),
                (
                    "tool_calls",
                    [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())],
                ),
            ]
        )
    )
    subagent = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [
                        ToolCall(
                            id="s0",
                            name=SECTION_DRAFT_TOOL_NAME,
                            arguments=_section_draft_args(" ".join(["w"] * 200)),
                        )
                    ],
                ),
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
        flagship_provider_factory=lambda r: flagship,
        subagent_provider_factory=lambda r: subagent,
        report_id_factory=lambda: "r_e2e",
        frameworks_root=frameworks_root,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)

    types = [type(e).__name__ for e in events]
    assert "ReportStart" in types
    assert "ReportComplete" in types
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert phases == ["planning", "eager_fetch", "section_drafting", "editing"]
    section_done = [e for e in events if isinstance(e, ReportSectionComplete)]
    assert len(section_done) == 1
    assert section_done[0].section_id == "company_overview"
    final = [e for e in events if isinstance(e, ReportComplete)][-1]
    assert final.schema["cover"]["title"] == "MSFT"
    assert final.schema["department"] == "equity_research"
