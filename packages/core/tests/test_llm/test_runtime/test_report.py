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
    def _r(*, department_id, user_id, registry, tier_override=None, model_id_override=None):
        return resolved

    return _r


def _raises(exc):
    def _r(*, department_id, user_id, registry, tier_override=None, model_id_override=None):
        raise exc

    return _r


async def _collect(it):
    return [e async for e in it]


async def test_report_run_reads_schema_from_submit_report_tool_use(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    payload = {
        "cover": {"title": "AAPL Initiation"},
        "sections": [{"id": "overview", "blocks": []}],
    }
    submit_call = ToolCall(id="t1", name="submit_report", arguments=payload)
    provider = FakeProvider(script=FakeProviderScript(turns=[("tool_calls", [submit_call])]))
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
        report_id_factory=lambda: "r_submit",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["cover"] == {"title": "AAPL Initiation"}
    assert events[-1].schema["sections"] == [{"id": "overview", "blocks": []}]


async def test_report_run_writing_turn_forces_submit_report_tool_choice(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    payload = {"cover": {"title": "X"}, "sections": []}
    submit_call = ToolCall(id="t1", name="submit_report", arguments=payload)
    provider = FakeProvider(script=FakeProviderScript(turns=[("tool_calls", [submit_call])]))
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
        report_id_factory=lambda: "r_choice",
    )
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    writing_request = provider.captured_requests[-1]
    assert writing_request.tool_choice is not None
    tool_names = [t.name for t in (writing_request.tools or [])]
    assert "submit_report" in tool_names
    assert any(
        writing_request.tool_choice.get(k) == v
        for k, v in [
            ("name", "submit_report"),
            ("function", {"name": "submit_report"}),
        ]
    ) or "submit_report" in str(writing_request.tool_choice)


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


async def test_report_run_injects_current_date_and_has_tools(
    tmp_path: Path, frameworks_root: Path
) -> None:
    prompts_root = tmp_path / "prompts2"
    shared = prompts_root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (prompts_root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  date={{ current_date }} long={{ current_date_long }} tools={{ has_tools }}
            """
        )
    )

    captured: dict[str, Any] = {}

    class _CaptureProvider(FakeProvider):
        async def generate(self, request):  # type: ignore[override]
            captured["user_msg"] = request.messages[-1].content
            return await super().generate(request)

    provider = _CaptureProvider(
        script=FakeProviderScript(turns=[("final_json", json.dumps({"title": "x"}))])
    )
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
        report_id_factory=lambda: "r_date",
    )
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    msg = captured["user_msg"]
    assert "date=" in msg
    assert "long=" in msg
    assert "tools=False" in msg or "tools=True" in msg
    import re as _re

    assert _re.search(r"date=\d{4}-\d{2}-\d{2}", msg)


async def test_report_run_normalizes_top_level_meta_fields(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    drifted = {
        "report_metadata": {"date": "2026-05-05"},
        "schema_version": "wrong",
        "department": "wrong",
        "cover": {"title": "x"},
        "sections": [{"id": "overview", "blocks": []}],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(drifted))]))
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
        report_id_factory=lambda: "r_norm",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    schema = events[-1].schema
    assert schema["schema_version"] == "2.0"
    assert schema["department"] == "equity_research"
    assert "generated_at" in schema
    assert "report_metadata" not in schema
    assert schema["cover"] == {"title": "x"}
    assert schema["sections"] == [{"id": "overview", "blocks": []}]


async def test_report_run_unwraps_nested_payload(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    nested = {"report": {"cover": {"title": "x"}, "sections": []}}
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(nested))]))
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
        report_id_factory=lambda: "r_nest",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["cover"] == {"title": "x"}


async def test_report_run_coerces_numeric_cover_metric_values(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    drifted = {
        "cover": {
            "title": "x",
            "key_metrics": [
                {"label": "S&P 500", "value": 5680.42, "delta": -0.78},
                {"label": "VIX", "value": 14},
            ],
        },
        "rail": {
            "quick_stats": [
                {"label": "Date", "value": 20260505},
            ],
        },
        "sections": [],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(drifted))]))
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
        report_id_factory=lambda: "r_metric_cover",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    cover = events[-1].schema["cover"]
    assert cover["key_metrics"][0]["value"] == "5680.42"
    assert cover["key_metrics"][0]["delta"] == "-0.78"
    assert cover["key_metrics"][1]["value"] == "14"
    rail = events[-1].schema["rail"]
    assert rail["quick_stats"][0]["value"] == "20260505"


async def test_report_run_coerces_numeric_metric_cards_in_sections(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    drifted = {
        "cover": {"title": "x"},
        "sections": [
            {
                "id": "global_macro",
                "title": "Global Macro",
                "blocks": [
                    {
                        "type": "metric_cards",
                        "metrics": [
                            {"label": "CPI", "value": 0.4, "delta": 0.1},
                        ],
                    },
                    {
                        "type": "group",
                        "columns": 2,
                        "blocks": [
                            {
                                "type": "metric_cards",
                                "metrics": [{"label": "WTI", "value": 78.4}],
                            },
                        ],
                    },
                ],
            }
        ],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(drifted))]))
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
        report_id_factory=lambda: "r_metric_section",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    section = events[-1].schema["sections"][0]
    assert section["blocks"][0]["metrics"][0]["value"] == "0.4"
    assert section["blocks"][0]["metrics"][0]["delta"] == "0.1"
    assert section["blocks"][1]["blocks"][0]["metrics"][0]["value"] == "78.4"


async def test_report_run_preserves_string_and_none_metric_values(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    mixed = {
        "cover": {
            "title": "x",
            "key_metrics": [
                {"label": "S&P 500", "value": "5,680.42", "delta": "+0.78%"},
                {"label": "VIX", "value": 14.2, "delta": None},
            ],
        },
        "sections": [],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(mixed))]))
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
        report_id_factory=lambda: "r_metric_mixed",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    metrics = events[-1].schema["cover"]["key_metrics"]
    assert metrics[0]["value"] == "5,680.42"
    assert metrics[0]["delta"] == "+0.78%"
    assert metrics[1]["value"] == "14.2"
    assert metrics[1]["delta"] is None


async def test_report_runner_output_validates_against_strict_schema(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    from openlia.reports.validator import validate_report_payload

    drifted = {
        "cover": {
            "title": "Morning Briefing",
            "subtitle": "Tuesday, May 5, 2026",
            "tagline": "Risk-on overnight.",
            "key_metrics": [
                {"label": "S&P 500", "value": 5680.42, "delta": "+0.78%"},
            ],
            "stats_panel": [
                {"label": "VIX", "value": 14.2},
            ],
        },
        "sections": [
            {
                "id": "executive_summary",
                "title": "Executive Summary",
                "blocks": [{"type": "text", "content": "Markets up overnight."}],
            }
        ],
    }
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", json.dumps(drifted))]))
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
        report_id_factory=lambda: "r_validate",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    validate_report_payload(events[-1].schema)


async def test_report_run_strips_markdown_fence_around_final_json(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    filled = {"title": "AAPL Initiation", "sections": []}
    fenced = "```json\n" + json.dumps(filled) + "\n```"
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", fenced)]))
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
        report_id_factory=lambda: "r_fence",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["title"] == "AAPL Initiation"


async def test_report_run_extracts_json_from_prose_prefix(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    filled = {"title": "AAPL Initiation", "sections": []}
    prosed = "Here is the briefing:\n\n" + json.dumps(filled) + "\n\nLet me know."
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", prosed)]))
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
        report_id_factory=lambda: "r_prose",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportComplete)
    assert events[-1].schema["title"] == "AAPL Initiation"


async def test_report_run_emits_output_limit_reached_on_truncation(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    class _LengthCapProvider(FakeProvider):
        async def generate(self, request):  # type: ignore[override]
            self.captured_requests.append(request)
            from openlia.llm.types import LLMResponse

            return LLMResponse(
                text="",
                finish_reason="length",
                input_tokens=10,
                output_tokens=request.max_tokens,
                tool_calls=[],
            )

    provider = _LengthCapProvider(script=FakeProviderScript(turns=[]))
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
        report_id_factory=lambda: "r_trunc",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert events[-1].error_class == "OutputLimitReached"
    assert "output limit" in events[-1].message.lower()


async def test_report_run_emits_error_with_preview_when_no_json(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    provider = FakeProvider(script=FakeProviderScript(turns=[("final_json", "I cannot do that.")]))
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
        report_id_factory=lambda: "r_bad",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    assert isinstance(events[-1], ReportError)
    assert "submit_report" in events[-1].message
    assert "I cannot do that." in events[-1].message


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


async def test_report_replays_assistant_tool_calls_and_tool_call_id(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """Regression: after a tool turn the next provider request must contain
    (a) the assistant message with the original tool_calls, and
    (b) tool-result messages whose tool_call_id matches the originating
    tool call. OpenRouter passes tool_call_id through as Anthropic's
    tool_use_id, which Anthropic rejects (regex ^[a-zA-Z0-9_-]+$) when
    empty or missing."""
    call = ToolCall(id="c_99", name="stock_quote", arguments={"symbol": "AAPL"})
    submit_call = ToolCall(
        id="t_submit",
        name="submit_report",
        arguments={
            "cover": {"title": "x"},
            "sections": [{"id": "overview", "blocks": []}],
        },
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [call]),
                ("final", ""),
                ("tool_calls", [submit_call]),
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
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    # Second turn must include user, assistant(tool_calls), tool(result).
    assert len(provider.captured_requests) >= 2
    second = provider.captured_requests[1]
    assistant_msgs = [m for m in second.messages if m.role == "assistant"]
    assert assistant_msgs, "assistant tool-call message must be replayed"
    assert any(any(tc.id == "c_99" for tc in m.tool_calls) for m in assistant_msgs), (
        "assistant message must carry the original tool_calls"
    )
    tool_msgs = [m for m in second.messages if m.role == "tool"]
    assert tool_msgs, "tool-result message must be present"
    assert all(m.tool_call_id for m in tool_msgs), (
        "every tool-result message must carry tool_call_id (Anthropic's "
        "tool_use_id regex rejects empty strings)"
    )
    assert any(m.tool_call_id == "c_99" for m in tool_msgs)


async def test_report_run_uses_user_template_branch_when_provided(
    tmp_path: Path, frameworks_root: Path
) -> None:
    """When ReportRequest carries user_template_text, the runner renders the
    user_template prompt slot, skips the framework JSON, and emits no
    pre-emptive ReportSectionStart events."""
    prompts_root = tmp_path / "prompts_template"
    shared = prompts_root / "shared"
    shared.mkdir(parents=True)
    (shared / "output_discipline.yaml.j2").write_text("discipline.\n")
    (prompts_root / "equity_research.yaml").write_text(
        dedent(
            """\
            report:
              system: |
                Style: {{ style_guide }}
              stock_initiation:
                user: |
                  default framework path; should NOT be used.
              user_template:
                user: |
                  USE_TEMPLATE name={{ template_name }} mode={{ mode_label }}
                  ticker={{ user_input }} length={{ length }}
                  ---
                  {{ user_template_text }}
                  ---
            """
        )
    )

    captured: dict[str, Any] = {}

    class _CaptureProvider(FakeProvider):
        async def generate(self, request):  # type: ignore[override]
            captured["user_msg"] = request.messages[-1].content
            return await super().generate(request)

    filled = {"title": "X", "sections": [{"id": "s1", "title": "S1", "blocks": []}]}
    provider = _CaptureProvider(
        script=FakeProviderScript(turns=[("final_json", json.dumps(filled))])
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
        report_id_factory=lambda: "r_t",
    )

    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(
                mode="stock_initiation",
                user_input="AAPL",
                user_template_text="MY CUSTOM TEMPLATE BODY",
                user_template_name="V1",
            ),
        )
    )

    msg = captured["user_msg"]
    assert "USE_TEMPLATE name=V1" in msg
    assert "ticker=AAPL" in msg
    assert "MY CUSTOM TEMPLATE BODY" in msg
    assert "default framework path" not in msg

    # The user-template branch suppresses framework-derived section starts;
    # only the LLM-output sections produce ReportSectionComplete events.
    start = next(e for e in events if isinstance(e, ReportStart))
    assert start.section_titles == []
    section_starts = [e for e in events if isinstance(e, ReportSectionStart)]
    assert section_starts == []
