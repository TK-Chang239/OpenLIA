"""Report runtime emits ReportWebSearchInvoked / ReportWebSearchCompleted
SSE events when an LLM turn surfaces native server-side web search
activity via ``LLMResponse.server_tool_calls`` + ``LLMResponse.citations``.

The report path uses ``provider.generate()`` per turn (not streaming),
so the runner inspects the unary response and emits the pair after the
fact. Each invoked/completed flows with the report_id, the originating
turn_idx, and the provider kind from the resolved model so the UI can
attribute the activity to the correct report and turn.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportWebSearchCompleted,
    ReportWebSearchInvoked,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    Citation,
    ProviderCredentials,
    ResolvedModel,
    ServerToolCall,
    ToolCall,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry

pytestmark = pytest.mark.asyncio


def _empty_skill_registry(tmp_path: Path) -> SkillRegistry:
    fs = FilesystemSkillStore(root=tmp_path)
    return SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))


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


def _resolved(provider_kind: str = "anthropic") -> ResolvedModel:
    return ResolvedModel(
        provider_kind=provider_kind,
        provider_id="p1",
        model_id="m1",
        model_ref="claude-sonnet-4-6",
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _Registry:
    pass


def _always(resolved):
    def _r(*, department_id, user_id, registry, model_id_override=None):
        return resolved

    return _r


async def _collect(it):
    return [e async for e in it]


async def test_server_tool_calls_emit_invoked_and_completed(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """A fetching turn whose LLMResponse carries one ServerToolCall and
    two Citations triggers exactly one ReportWebSearchInvoked (with the
    call's query) plus one ReportWebSearchCompleted (with the citation
    URLs aggregated)."""
    submit_payload = {
        "cover": {
            "title": "AAPL Initiation",
            "subtitle": "Coverage initiation",
            "tagline": "Constructive setup",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Body."}],
            }
        ],
    }
    submit_call = ToolCall(id="t_submit", name="submit_report", arguments=submit_payload)
    fetching_turn = {
        "tool_calls": [],
        "server_tool_calls": (
            ServerToolCall(
                name="web_search", arguments={"query": "AAPL recent news"}, turn_idx=0
            ),
        ),
        "citations": (
            Citation(
                id="c1",
                kind="web",
                url="https://reuters.com/aapl",
                title="Reuters",
                source="Anthropic Web Search",
            ),
            Citation(
                id="c2",
                kind="web",
                url="https://ft.com/aapl",
                title="FT",
                source="Anthropic Web Search",
            ),
        ),
    }
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls_with_searches", fetching_turn),
                ("tool_calls", [submit_call]),
            ]
        )
    )
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved(provider_kind="anthropic")),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_ws",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )

    invoked = [e for e in events if isinstance(e, ReportWebSearchInvoked)]
    completed = [e for e in events if isinstance(e, ReportWebSearchCompleted)]
    assert len(invoked) == 1
    assert invoked[0].query == "AAPL recent news"
    assert invoked[0].turn_idx == 0
    assert invoked[0].provider == "anthropic"
    assert invoked[0].report_id == "r_ws"

    assert len(completed) == 1
    assert completed[0].provider == "anthropic"
    assert completed[0].turn_idx == 0
    assert completed[0].n_results == 2
    assert completed[0].urls == ["https://reuters.com/aapl", "https://ft.com/aapl"]

    # Report still completes normally.
    assert any(isinstance(e, ReportComplete) for e in events)


async def test_turn_without_server_tool_calls_emits_no_web_search_events(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """Fetching turns with empty server_tool_calls produce zero
    ReportWebSearch* events — guards against phantom emissions for
    plain tool-calling turns."""
    submit_call = ToolCall(
        id="t",
        name="submit_report",
        arguments={
            "cover": {
                "title": "AAPL Initiation",
                "subtitle": "Coverage initiation",
                "tagline": "Constructive",
            },
            "sections": [
                {
                    "id": "overview",
                    "title": "Overview",
                    "blocks": [{"type": "text", "content": "Body."}],
                }
            ],
        },
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),
                ("tool_calls", [submit_call]),
            ]
        )
    )
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=FakeDataDispatcher(manifest={"equity_research": {}}),
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_clean",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert not any(
        isinstance(e, (ReportWebSearchInvoked, ReportWebSearchCompleted)) for e in events
    )
