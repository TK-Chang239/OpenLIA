from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.exceptions import CapabilityError, LLMProviderError, TierNotConfiguredError
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportPhase,
    ReportSectionComplete,
    ReportSectionStart,
    ReportStart,
    ReportToolCall,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ModelTier,
    ProviderCredentials,
    ResolvedModel,
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
                    {"id": "thesis", "title": "Thesis", "instructions": "..."},
                    {"id": "risks", "title": "Risks", "instructions": "..."},
                ],
            }
        )
    )
    (root / "stock_initiation_style_guide.md").write_text("# Style\nProfessional tone.\n")
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


def _resolved() -> ResolvedModel:
    return ResolvedModel(
        provider_kind="fake",
        provider_id="p1",
        model_id="m1",
        model_ref="fake-1",
        tier=ModelTier.THINKING,
        credentials=ProviderCredentials(api_key="k", base_url=None),
        capabilities=Capabilities(streaming=True, tool_calling=True, structured_output=True),
        overrides={},
    )


class _Registry:
    def get_department_tier_override(self, department_id: str):
        return None

    def get_user_preference(self, user_id, tier):
        return None

    def get_tier_default(self, tier):
        return None

    def get_any_in_tier(self, tier):
        return None


def _always(resolved):
    def _r(*, department_id, user_id, registry, tier_override=None):
        return resolved

    return _r


def _raises(exc):
    def _r(*, department_id, user_id, registry, tier_override=None):
        raise exc

    return _r


async def _collect(it):
    return [e async for e in it]


async def test_report_run_emits_start_phases_and_complete(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    filled = {"title": "AAPL Initiation", "sections": [{"id": "overview", "body": "..."}]}
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(filled))]))
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    kinds = [type(e) for e in events]
    assert kinds[0] is ReportStart
    assert ReportPhase in kinds
    phases = [e.phase for e in events if isinstance(e, ReportPhase)]
    assert phases[:3] == ["fetching_data", "writing", "finalizing"]
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["title"] == "AAPL Initiation"


async def test_report_start_includes_section_titles_after_filter(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(filled))]))
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(
                mode="stock_initiation",
                user_input="AAPL",
                enabled_sections=["overview", "thesis"],
            ),
        )
    )
    start = events[0]
    assert isinstance(start, ReportStart)
    assert start.section_titles == ["Overview", "Thesis"]


async def test_report_tool_call_carries_call_id_through_to_event(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """NEW-5-02: ReportToolCall events carry the dispatcher's call_id so the
    FE can correlate them with the preceding report.tool_call.start."""
    call = ToolCall(id="c_42", name="stock_quote", arguments={"symbol": "AAPL"})
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("final_json", json.dumps(filled)),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"symbol": "AAPL"}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    tool_calls = [e for e in events if isinstance(e, ReportToolCall)]
    assert len(tool_calls) == 1
    assert tool_calls[0].call_id == "c_42"


async def test_report_tool_call_start_event_emitted_before_dispatch(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """NEW-5-03: report.tool_call.start fires before the tool runs so the FE
    can show progress while a long-running tool is in flight."""
    from openlia.llm.runtime.events import ReportToolCallStart

    call = ToolCall(id="c_42", name="stock_quote", arguments={"symbol": "AAPL"})
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("final_json", json.dumps(filled)),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    starts = [e for e in events if isinstance(e, ReportToolCallStart)]
    results = [e for e in events if isinstance(e, ReportToolCall)]
    assert len(starts) == 1
    assert starts[0].call_id == "c_42"
    assert starts[0].tool_name == "stock_quote"
    # Order: start before result.
    start_idx = events.index(starts[0])
    result_idx = events.index(results[0])
    assert start_idx < result_idx


async def test_report_tool_loop_emits_tool_events(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    filled = {"title": "x", "sections": []}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("final_json", json.dumps(filled)),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(
        manifest=manifest, results={"stock_quote": {"symbol": "AAPL", "price": 190}}
    )
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert any(isinstance(e, ReportToolCall) for e in events)


async def test_report_tier_not_configured_emits_report_error(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[]))
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_raises(TierNotConfiguredError("thinking")),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert events[-1].error_class == "TierNotConfiguredError"


async def test_report_capability_error_terminates(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    class _FailingProvider(FakeProvider):
        async def generate(self, request):
            raise CapabilityError("no structured output")

    provider = _FailingProvider()
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert events[-1].error_class == "CapabilityError"


async def test_two_round_tool_loop_uses_both_results(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    call_a = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    call_b = ToolCall(id="c2", name="stock_quote", arguments={"symbol": "MSFT"})
    filled = {"title": "AAPL Initiation", "sections": [{"id": "overview", "body": "..."}]}
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call_a]),
                ("tool_calls", [call_b]),
                ("final", ""),
                ("final_json", json.dumps(filled)),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 100}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    tool_call_events = [e for e in events if isinstance(e, ReportToolCall)]
    assert len(tool_call_events) == 2
    assert isinstance(events[-1], ReportComplete)


async def test_max_rounds_falls_through_to_writing(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    from openlia.llm.runtime.tools import MAX_TOOL_TURNS

    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    filled = {"title": "AAPL Initiation", "sections": [{"id": "overview", "body": "..."}]}
    turns: list[Any] = [("tool_calls", [call])] * MAX_TOOL_TURNS + [
        ("final_json", json.dumps(filled))
    ]
    provider = FakeProvider(script=FakeProviderScript(turns=turns))
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 100}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)


async def test_provider_error_in_report_tool_loop_emits_report_error(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    class _LoopErrorProvider(FakeProvider):
        async def generate(self, request):
            if self._turn_index >= 1:
                raise LLMProviderError("mid-loop failure")
            return await super().generate(request)

    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    provider = _LoopErrorProvider(script=FakeProviderScript(turns=[("tool_calls", [call])]))
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest, results={"stock_quote": {"price": 100}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert "mid-loop failure" in events[-1].message


async def test_report_cancellation_stops_yielding(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    call = ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"})
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final_json", "{}"),
            ]
        )
    )
    manifest = {
        "equity_research": {
            "stock_quote": {
                "name": "stock_quote",
                "description": "Quote",
                "parameters": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        }
    }
    data = FakeDataDispatcher(manifest=manifest)
    token = CancellationToken()
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    collected: list[Any] = []
    async for e in runner.run(
        department_id="equity_research",
        user_id="u_1",
        request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        cancel_token=token,
    ):
        collected.append(e)
        if isinstance(e, ReportToolCall):
            token.cancel()
    types = [type(e) for e in collected]
    assert ReportComplete not in types


async def test_report_emits_per_section_events(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """NEW-14-06 — runtime emits report.section.start/complete around the
    structured-output writing pass."""
    filled = {
        "title": "AAPL Initiation",
        "sections": [
            {"id": "overview", "blocks": [{"type": "text", "content": "..."}]},
            {"id": "thesis", "blocks": []},
        ],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(filled))]))
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_1",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(
                mode="stock_initiation",
                user_input="AAPL",
                enabled_sections=["overview", "thesis"],
            ),
        )
    )
    starts = [e for e in events if isinstance(e, ReportSectionStart)]
    completes = [e for e in events if isinstance(e, ReportSectionComplete)]
    assert [s.section_id for s in starts] == ["overview", "thesis"]
    assert all(s.total == 2 for s in starts)
    assert [c.section_id for c in completes] == ["overview", "thesis"]
    # Wire format includes the named events
    from openlia.llm.runtime.events import to_wire

    types = {to_wire(e)["type"] for e in events}
    assert "report.section.start" in types
    assert "report.section.complete" in types


async def test_report_forwards_section_topics_and_reference_portfolio(
    tmp_path: Path,
) -> None:
    """P1-04 — ReportRunner forwards section_topics + reference_portfolio
    fields from ReportRequest into the Jinja render context for the user
    prompt. End-to-end the captured LLMRequest user message includes the
    topic strings and holding tickers."""
    fwroot = tmp_path / "fw"
    fwroot.mkdir()
    (fwroot / "morning_briefing.json").write_text(
        json.dumps(
            {
                "title": "MB",
                "sections": [
                    {"id": "global_macro", "title": "Global Macro", "instructions": "..."},
                ],
            }
        )
    )
    (fwroot / "morning_briefing_style_guide.md").write_text("# Style\n")

    proots = tmp_path / "prompts"
    shared = proots / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("disc.\n")
    (proots / "morning_briefing.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              morning_briefing:
                user: |
                  topics:
                  {% if section_topics %}{% for sid, ts in section_topics.items() %}
                  - {{ sid }}: {% for t in ts %}{{ t.topic }} ({{ t.notes }}){% endfor %}
                  {% endfor %}{% endif %}
                  refs:
                  {% if reference_portfolio %}{% for h in reference_portfolio %}
                  - {{ h.ticker }} {{ h.name }}
                  {% endfor %}{% endif %}
            """
        )
    )

    filled = {"title": "MB", "sections": [{"id": "global_macro", "blocks": []}]}
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(filled))]))
    data = FakeDataDispatcher(manifest={"morning_briefing": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=proots),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_always(_resolved()),
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=fwroot,
        report_id_factory=lambda: "r_1",
    )
    request = ReportRequest(
        mode="morning_briefing",
        user_input="generate",
        enabled_sections=["global_macro"],
        section_topics={"global_macro": [{"topic": "War", "notes": "Russia-Ukraine"}]},
        reference_portfolio=[
            {"ticker": "AAPL", "name": "Apple"},
            {"ticker": "NVDA", "name": "Nvidia"},
        ],
    )
    await _collect(runner.run(department_id="morning_briefing", user_id="u_1", request=request))
    captured = provider.captured_requests[0]
    assert captured.messages, "expected at least one message"
    user_msg = captured.messages[0].content
    assert "War" in user_msg
    assert "Russia-Ukraine" in user_msg
    assert "AAPL" in user_msg
    assert "NVDA" in user_msg
