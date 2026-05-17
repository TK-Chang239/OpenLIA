"""SubagentReportRunner must write a ReportContextBundle to disk
immediately before yielding ReportComplete. If the write fails (disk
full, permissions), the runner emits a warning trace and still yields
ReportComplete — the report itself is valid."""
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript

from openlia.llm.runtime.events import ReportComplete
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report_context_bundle import load_bundle
from openlia.llm.runtime.subagent_client import SECTION_DRAFT_TOOL_NAME
from openlia.llm.runtime.editor_client import EDITOR_TOOL_NAME
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
        provider_kind="fake", provider_id="p1", model_id="m1", model_ref="fake-1",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True, max_output_tokens=8192),
        overrides={},
    )


def _resolve(*, department_id, user_id, registry, role="flagship", model_id_override=None):
    return _resolved()


@pytest.fixture
def prompts_root(tmp_path: Path) -> Path:
    root = tmp_path / "prompts"
    (root / "shared").mkdir(parents=True)
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
                Plan {{ user_input }} via plan_report. {{ style_guide }} {{ framework_summary }}
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
    (root / "stock_initiation.json").write_text(json.dumps({
        "title": "Stock Initiation",
        "sections": [{"id": "company_overview", "title": "Overview", "instructions": "..."}]
    }))
    (root / "stock_initiation_style_guide.md").write_text("# Style\n")
    return root


def _plan_args() -> dict:
    return {
        "company_thesis": "thesis",
        "cross_section_themes": ["t1", "t2"],
        "sections": [{
            "section_id": "company_overview", "title": "Overview",
            "narrative_goal": "g", "key_questions": ["q1", "q2", "q3"],
            "target_depth": "standard", "word_budget": 200,
            "data_paths": [], "cross_refs": [],
        }],
    }


def _draft_args(content: str) -> dict:
    return {
        "section_id": "company_overview",
        "blocks": [{"type": "text", "content": content}],
        "citations_used": ["c1"], "word_count": len(content.split()), "open_questions": [],
    }


def _editor_args() -> dict:
    return {
        "cover": {"title": "MSFT", "subtitle": "Initiation", "tagline": "Constructive"},
        "sections": [{"id": "company_overview", "title": "Overview",
                      "blocks": [{"type": "text", "content": "Final body."}]}],
    }


@pytest.mark.asyncio
async def test_runner_writes_bundle_to_specified_dir(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    flagship = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_plan_args())]),
        ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())]),
    ]))
    subagent = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="s0", name=SECTION_DRAFT_TOOL_NAME,
                                 arguments=_draft_args(" ".join(["w"] * 200)))]),
    ]))
    bundle_dir = tmp_path / "bundles"
    runner = SubagentReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve, registry=object(),
        flagship_provider_factory=lambda r: flagship,
        subagent_provider_factory=lambda r: subagent,
        report_id_factory=lambda: "r_bundle",
        frameworks_root=frameworks_root,
        bundle_dir=bundle_dir,
    )
    events = []
    async for ev in runner.run(
        department_id="equity_research", user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
    ):
        events.append(ev)
    assert any(isinstance(e, ReportComplete) for e in events)
    bundle_path = bundle_dir / "r_bundle.json.gz"
    assert bundle_path.exists(), "bundle file should be written next to the report"
    loaded = load_bundle(bundle_path)
    assert loaded.plan.company_thesis == "thesis"
    assert loaded.section_drafts[0].section_id == "company_overview"


@pytest.mark.asyncio
async def test_runner_continues_when_bundle_write_fails(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """If persist_bundle raises (disk full, permission error), the runner
    emits a warning trace and still yields ReportComplete."""
    flagship = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="p0", name=PLAN_REPORT_TOOL_NAME, arguments=_plan_args())]),
        ("tool_calls", [ToolCall(id="e0", name=EDITOR_TOOL_NAME, arguments=_editor_args())]),
    ]))
    subagent = FakeProvider(script=FakeProviderScript(turns=[
        ("tool_calls", [ToolCall(id="s0", name=SECTION_DRAFT_TOOL_NAME,
                                 arguments=_draft_args(" ".join(["w"] * 200)))]),
    ]))
    bundle_dir = tmp_path / "readonly"
    bundle_dir.mkdir()
    bundle_dir.chmod(0o400)  # read-only -> mkdir of subdir works but write fails
    try:
        traces: list[tuple[str, str, dict | None]] = []
        runner = SubagentReportRunner(
            prompts=PromptLoader(root=prompts_root),
            tools=ToolDispatcher(
                data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
                web_search=WebSearchResolution(False, None, None),
            ),
            resolve=_resolve, registry=object(),
            flagship_provider_factory=lambda r: flagship,
            subagent_provider_factory=lambda r: subagent,
            report_id_factory=lambda: "r_fail",
            frameworks_root=frameworks_root,
            bundle_dir=bundle_dir / "nested",  # nested dir under read-only parent -> mkdir fails
            trace=lambda c, m, p: traces.append((c, m, p)),
        )
        events = []
        async for ev in runner.run(
            department_id="equity_research", user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="MSFT"),
        ):
            events.append(ev)
        assert any(isinstance(e, ReportComplete) for e in events), \
            "ReportComplete must still fire even when bundle write fails"
        assert any(c == "report.warning.bundle_persist_failed" for c, _, _ in traces), \
            "warning event must be recorded"
    finally:
        bundle_dir.chmod(0o755)
