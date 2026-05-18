from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from _fakes import FakeDataDispatcher, FakeProvider, FakeProviderScript
from openlia.llm.runtime.events import ReportComplete, ReportToolCall
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import (
    _SERVER_CONTROLLED_FIELDS,
    ReportRunner,
    _submit_report_input_schema,
    build_report_system_prompt,
)
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import (
    Capabilities,
    ProviderCredentials,
    ResolvedModel,
    ToolCall,
)
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry


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


def _resolve(*, department_id, user_id, registry, model_id_override=None):
    return _resolved()


class _Registry:
    pass


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
    (root / "stock_initiation_style_guide.md").write_text("# Style\nProfessional.\n")
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
            """
        )
    )
    return root


def _strict_valid_payload(*, title: str = "AAPL Initiation") -> dict[str, Any]:
    return {
        "cover": {
            "title": title,
            "subtitle": "Coverage initiation",
            "tagline": "Constructive on near-term setup",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "blocks": [
                    {"type": "text", "content": "Body."},
                ],
            }
        ],
    }


def _invalid_payload_with_drift() -> dict[str, Any]:
    """All three recurring violations in one payload."""
    return {
        "page_furniture": {"header": "h", "footer": "f"},
        "cover": {
            "title": "AAPL Initiation",
            "subtitle": "Coverage initiation",
            "tagline": "x",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "blocks": [
                    {
                        "type": "area_chart",
                        "title": "Revenue",
                        "series": [{"name": "rev", "data": [1, 2, 3]}],
                        "options": {"note": "FY24 estimate"},
                    },
                    {
                        "type": "table",
                        "title": "Comps",
                        "headers": ["Ticker", "Price"],
                        "rows": [{"Ticker": "AAPL", "Price": "200"}],
                    },
                ],
            }
        ],
    }


async def _collect(it):
    return [e async for e in it]


# ---------- Step 1 contract: tool schema strips server-controlled fields ----------


def test_submit_report_tool_schema_omits_page_furniture() -> None:
    schema = _submit_report_input_schema()
    props = schema.get("properties", {})
    assert "page_furniture" not in props
    for f in ("schema_version", "department", "generated_at"):
        assert f not in props
    assert "page_furniture" in _SERVER_CONTROLLED_FIELDS


# ---------- Step 2 contract: prompt carries schema-strictness guide ----------


def test_report_system_prompt_includes_schema_strictness_guide(tmp_path: Path) -> None:
    """Render the real equity_research report.system slot from the shipped
    prompts and assert it mentions the strict-schema constraints."""
    loader = PromptLoader()  # uses shipped prompts package
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        loader=loader,
    )
    assert "page_furniture" in rendered
    assert "height" in rendered and "show_legend" in rendered and "show_grid" in rendered
    assert "key" in rendered and "label" in rendered
    assert "extra" in rendered.lower() or "forbid" in rendered.lower()


def test_report_system_prompt_documents_chart_height_enum(tmp_path: Path) -> None:
    """Guards against the model emitting `height: 320` (pixel int) — schema
    requires the enum literal `small`/`medium`/`tall`. Without an explicit
    callout the model defaults to pixel ints, triggering a validation retry."""
    loader = PromptLoader()
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        loader=loader,
    )
    assert '"small"' in rendered and '"medium"' in rendered and '"tall"' in rendered
    lower = rendered.lower()
    assert "pixel" in lower or "integer" in lower


def test_runtime_finalize_submit_payload_rewrites_inline_citation_tuples() -> None:
    """The runtime finalization helper that ReportRunner calls after
    `submit_report` must rewrite inline citation tuples like
    `[Reuters, "Title", 2026-05-12, https://x.com]` into footnote markers
    `[1]` and populate `payload["citations"]`. Without this hook the raw
    tuples leak into the rendered report and the citations rail stays empty."""
    from datetime import UTC, datetime

    from openlia.llm.runtime.report import _finalize_submit_payload

    payload = {
        "cover": {
            "title": "Apple Q1 Initiation",
            "subtitle": "Hold",
            "tagline": "Solid quarter; valuation full.",
        },
        "sections": [
            {
                "id": "company_overview",
                "title": "Company Overview",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            "Apple beat Q1 estimates "
                            '[Reuters, "Apple Q1 beats", 2026-05-12, '
                            "https://reuters.com/business/apple-q1]."
                        ),
                    }
                ],
            }
        ],
    }

    finalized = _finalize_submit_payload(
        payload,
        department_id="equity_research",
        generated_at=datetime(2026, 5, 16, tzinfo=UTC),
        provider_citations=[],
        model_id="gpt-5.4",
        total_input_tokens=100,
        total_output_tokens=50,
        web_search_count=0,
    )

    text_block = finalized["sections"][0]["blocks"][0]
    assert "[1]" in text_block["content"]
    assert "Reuters" not in text_block["content"]
    assert "reuters.com" not in text_block["content"]
    assert len(finalized["citations"]) == 1
    assert finalized["citations"][0]["id"] == "1"
    assert finalized["citations"][0]["url"] == "https://reuters.com/business/apple-q1"


def test_report_system_prompt_marks_cache_breakpoint(tmp_path: Path) -> None:
    """The rendered report system prompt must embed the cache-breakpoint
    sentinel. Without it, the Anthropic adapter cannot split off a cached
    prefix, and the OpenAI auto-cache has no signal about where the
    stable boundary lies."""
    from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER

    loader = PromptLoader()
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="STYLE",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        search_budget=8,
        loader=loader,
    )
    assert CACHE_BREAKPOINT_MARKER in rendered


def test_report_system_prompt_static_prefix_excludes_per_turn_data(
    tmp_path: Path,
) -> None:
    """Everything above the cache breakpoint must be stable across
    sequential calls within (and ideally across) a report run. The
    current date, the long-form date, and the search budget all change
    between renders and therefore must sit BELOW the breakpoint marker."""
    from openlia.llm.adapters._content import split_at_cache_breakpoint

    loader = PromptLoader()
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="STYLE",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        search_budget=8,
        loader=loader,
    )
    static, dynamic = split_at_cache_breakpoint(rendered)
    assert dynamic is not None
    assert "2026-05-14" not in static
    assert "Thursday, May 14, 2026" not in static
    assert "May 14" not in static
    # search_budget number should not appear above the breakpoint.
    assert "budget of 8" not in static


def test_report_system_prompt_static_prefix_is_byte_stable_across_dates(
    tmp_path: Path,
) -> None:
    """Same department + style guide + skills set rendered with different
    dates / budgets must produce a byte-identical static prefix, so the
    same OpenAI/Anthropic cache slot can serve consecutive turns and even
    consecutive reports of the same mode."""
    from openlia.llm.adapters._content import split_at_cache_breakpoint

    loader = PromptLoader()
    a = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="STYLE",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        search_budget=8,
        loader=loader,
    )
    b = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="STYLE",
        available_category_hints=[],
        current_date="2027-11-22",
        current_date_long="Monday, November 22, 2027",
        search_budget=3,
        loader=loader,
    )
    static_a, _ = split_at_cache_breakpoint(a)
    static_b, _ = split_at_cache_breakpoint(b)
    assert static_a == static_b


def test_report_system_prompt_forbids_citations_and_meta_stats_under_rail(
    tmp_path: Path,
) -> None:
    """Guards against the model nesting `citations` or `meta_stats` under
    `rail`. Both live at the top level of ReportSchema; `meta_stats` is
    server-computed and must not be authored at all."""
    loader = PromptLoader()
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        loader=loader,
    )
    assert "citations" in rendered and "meta_stats" in rendered
    lower = rendered.lower()
    assert "top-level" in lower or "top level" in lower
    assert "rail" in lower


def test_report_system_prompt_anchors_current_date(tmp_path: Path) -> None:
    """Render the real equity_research report.system slot and assert the
    temporal anchor partial emits today's date + freshness discipline.

    Guards against regression where the runtime computes `current_date`
    but the rendered system prompt never references it, letting the model
    fall back to its training cutoff."""
    loader = PromptLoader()
    rendered = build_report_system_prompt(
        department_id="equity_research",
        user_id=None,
        registry=_empty_skill_registry(tmp_path),
        style_guide="",
        available_category_hints=[],
        current_date="2026-05-14",
        current_date_long="Thursday, May 14, 2026",
        loader=loader,
    )
    assert "Thursday, May 14, 2026" in rendered
    assert "2026-05-14" in rendered
    assert "training cutoff" in rendered.lower()
    assert "web_search" in rendered


# ---------- Cost guard: fetching-phase output token cap ----------


@pytest.mark.asyncio
async def test_fetching_turn_caps_max_output_tokens(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """Fetching turns must cap max_output_tokens to a small value
    (~2048) so a model that "gives up" calling tools can't burn the
    full ~16K output budget on inline prose. Observed in run
    r_f03c92dd8c30 turn 6: 13,151 output tokens with zero tool calls."""
    from openlia.llm.runtime.report import FETCHING_MAX_OUTPUT_TOKENS

    good_call = ToolCall(id="t_good", name="submit_report", arguments=_strict_valid_payload())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # fetching turn 0: ends loop
                ("tool_calls", [good_call]),  # writing turn: submit_report
            ]
        ),
        capabilities=Capabilities(
            streaming=True,
            tool_calling=True,
            structured_output=True,
            max_output_tokens=16_000,
        ),
    )

    def _resolve_high_max(*, department_id, user_id, registry, model_id_override=None):
        return dataclasses.replace(_resolved(), capabilities=provider.capabilities)

    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve_high_max,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_cap",
    )
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )

    fetching_request = provider.captured_requests[0]
    assert fetching_request.max_tokens == FETCHING_MAX_OUTPUT_TOKENS
    assert FETCHING_MAX_OUTPUT_TOKENS <= 2048


# ---------- Cost guard: request_additional_tools dropped after first call ----------


@pytest.mark.asyncio
async def test_request_additional_tools_dropped_after_first_call(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """Once the runtime has expanded the tool registry once, the
    request_additional_tools meta-tool must be absent from subsequent
    fetching turns. A second mid-loop call mutates the prefix bytes and
    invalidates the OpenAI/Anthropic prompt cache. Observed in run
    r_f03c92dd8c30: turn 5 called request_additional_tools again, and
    turn 6 dropped to 0% cache hit on 66K input tokens."""
    escalate_call = ToolCall(
        id="t_esc",
        name="request_additional_tools",
        arguments={"reason": "load tools"},
    )
    good_call = ToolCall(id="t_good", name="submit_report", arguments=_strict_valid_payload())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", [escalate_call]),  # fetching turn 0: escalate
                ("tool_calls", []),  # fetching turn 1: end loop
                ("tool_calls", [good_call]),  # writing turn: submit_report
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_drop",
    )
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )

    # Turn 0 (the escalation turn) must offer request_additional_tools.
    turn_0_tools = {t.name for t in (provider.captured_requests[0].tools or [])}
    assert "request_additional_tools" in turn_0_tools
    # Turn 1 (after escalation) must NOT offer it. Caches stay warm.
    turn_1_tools = {t.name for t in (provider.captured_requests[1].tools or [])}
    assert "request_additional_tools" not in turn_1_tools


# ---------- Step 3 contract: validation failure → repair turn with feedback ----------


@pytest.mark.asyncio
async def test_writing_loop_pushes_repair_feedback_on_validation_failure(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    bad_call = ToolCall(id="t_bad", name="submit_report", arguments=_invalid_payload_with_drift())
    good_call = ToolCall(id="t_good", name="submit_report", arguments=_strict_valid_payload())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # end fetching phase
                ("tool_calls", [bad_call]),
                ("tool_calls", [good_call]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_repair",
    )

    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )

    # A repair tool_result event was surfaced for submit_report.
    submit_results = [
        e for e in events if isinstance(e, ReportToolCall) and e.tool_name == "submit_report"
    ]
    assert submit_results, "expected a submit_report tool-result event for the failed turn"
    chip = submit_results[0].summary
    assert "validation_failed" in chip
    # Chip must name the first failing field path so operators can diagnose
    # repeated repair loops without server-side traces. The generic
    # `ReportValidationError` message is not enough on its own.
    assert "Report payload failed validation" not in chip

    # Final event is ReportComplete with the strict-valid payload (no coercion needed).
    final = events[-1]
    assert isinstance(final, ReportComplete)
    assert final.schema["cover"]["title"] == "AAPL Initiation"
    assert final.schema["department"] == "equity_research"
    # Server-controlled meta is stamped, page_furniture is absent.
    assert "page_furniture" not in final.schema
    assert final.schema["schema_version"] == "2.0"


@pytest.mark.asyncio
async def test_writing_loop_feeds_validation_errors_back_to_model(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """The repair turn must include a tool-message with structured errors so the
    model can self-correct rather than guessing."""
    bad_call = ToolCall(id="t_bad", name="submit_report", arguments=_invalid_payload_with_drift())
    good_call = ToolCall(id="t_good", name="submit_report", arguments=_strict_valid_payload())
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # end fetching phase
                ("tool_calls", [bad_call]),
                ("tool_calls", [good_call]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_feedback",
    )
    await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )

    # Second LLM request must include the repair tool-result message.
    second_request = provider.captured_requests[1]
    tool_msgs = [m for m in second_request.messages if m.role == "tool"]
    assert tool_msgs, "expected a tool-role repair message on the second writing turn"
    repair = json.loads(tool_msgs[-1].content)
    assert repair["ok"] is False
    assert repair["error"] == "validation_failed"
    assert isinstance(repair["errors"], list) and len(repair["errors"]) >= 1
    # Each error has a path, a message, and the offending input value/type so
    # operators can diagnose literal-mismatch drift without re-running.
    for err in repair["errors"]:
        assert "path" in err and "message" in err
        assert "input_value" in err and "input_type" in err
    assert "page_furniture" in repair["instruction"]


# ---------- Step 4 contract: strict-valid first try bypasses coercion ----------


@pytest.mark.asyncio
async def test_strict_valid_payload_passes_through_without_coercion(
    prompts_root: Path, frameworks_root: Path, tmp_path: Path
) -> None:
    """A first-try valid payload must not be silently rewritten by the
    coercion fallback. Use a chart with a title we'd be embarrassed to see
    suffixed by a folded `note`."""
    payload = _strict_valid_payload()
    payload["sections"][0]["blocks"].append(
        {
            "type": "line_chart",
            "title": "Revenue",
            "series": [{"name": "rev", "data": [1, 2, 3]}],
        }
    )
    submit_call = ToolCall(id="t1", name="submit_report", arguments=payload)
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # end fetching phase
                ("tool_calls", [submit_call]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_strict",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    final = events[-1]
    assert isinstance(final, ReportComplete)
    chart = final.schema["sections"][0]["blocks"][1]
    # Title is unchanged (no " — ..." suffix from coercion).
    assert chart["title"] == "Revenue"


# ---------- Step 4 contract: coercion fires only as last-resort fallback ----------


@pytest.mark.asyncio
async def test_coercion_fallback_runs_when_repair_turns_exhausted(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the model never produces a strict-valid payload, the runner should
    still emit ReportComplete after applying coercion. Drop MAX_WRITING_TURNS
    to keep the script short."""
    import openlia.llm.runtime.report as report_module

    monkeypatch.setattr(report_module, "MAX_WRITING_TURNS", 2)

    bad = ToolCall(id="t_bad", name="submit_report", arguments=_invalid_payload_with_drift())
    # Same invalid payload on every turn — model never repairs.
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # end fetching phase
                ("tool_calls", [bad]),
                ("tool_calls", [bad]),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_fallback",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    final = events[-1]
    assert isinstance(final, ReportComplete)
    # page_furniture stripped, server fields stamped.
    assert "page_furniture" not in final.schema
    assert final.schema["department"] == "equity_research"
    # Coercion converted string headers to {key,label} dicts and removed
    # the forbidden chart options.note key.
    table = final.schema["sections"][0]["blocks"][1]
    assert all(isinstance(h, dict) and "key" in h and "label" in h for h in table["headers"])
    chart = final.schema["sections"][0]["blocks"][0]
    assert "note" not in (chart.get("options") or {})


# ---------- Defect 2: fallback path must still merge provider citations + meta_stats ----------


@pytest.mark.asyncio
async def test_fallback_path_merges_provider_citations_and_stamps_meta_stats(
    prompts_root: Path,
    frameworks_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the model exhausts repair turns by repeatedly misplacing citations
    under rail (`rail.citations: Extra inputs are not permitted`), the
    fallback path must still:
      1. surface provider-emitted citations into `schema["citations"]`
         (the runner has been accumulating them via response.citations),
      2. stamp `meta_stats` server-side so sources_count/sections_count/
         model_id land in the persisted report.
    Without this, the user-visible report has empty footnotes and a
    blank meta panel — the exact regression seen in r_df2fad6a0961.
    """
    import openlia.llm.runtime.report as report_module
    from openlia.llm.types import Citation

    monkeypatch.setattr(report_module, "MAX_WRITING_TURNS", 2)

    rail_citations_payload: dict[str, Any] = {
        "cover": {
            "title": "AAPL Initiation",
            "subtitle": "Coverage initiation",
            "tagline": "x",
        },
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "blocks": [{"type": "text", "content": "Body."}],
            }
        ],
        "rail": {
            "verdict": {"stance": "hold", "rationale": "x"},
            "citations": [{"id": "1", "title": "misplaced"}],
        },
    }
    bad = ToolCall(id="t_bad", name="submit_report", arguments=rail_citations_payload)
    provider_cite = Citation(
        id="c-web-1",
        kind="web",
        url="https://example.com/aapl",
        title="AAPL coverage",
        source="example.com",
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                ("tool_calls", []),  # end fetching phase
                (
                    "tool_calls_with_searches",
                    {"tool_calls": [bad], "citations": (provider_cite,)},
                ),
                (
                    "tool_calls_with_searches",
                    {"tool_calls": [bad], "citations": (provider_cite,)},
                ),
            ]
        )
    )
    data = FakeDataDispatcher(manifest={"equity_research": {}})
    runner = ReportRunner(
        prompts=PromptLoader(root=prompts_root),
        tools=ToolDispatcher(
            data_dispatcher=data,
            web_search=WebSearchResolution(False, None, None),
        ),
        resolve=_resolve,
        registry=_Registry(),
        provider_factory=lambda r: provider,
        skill_registry=_empty_skill_registry(tmp_path),
        frameworks_root=frameworks_root,
        report_id_factory=lambda: "r_fallback_cites",
    )
    events = await _collect(
        runner.run(
            department_id="equity_research",
            user_id="u_1",
            request=ReportRequest(mode="stock_initiation", user_input="AAPL"),
        )
    )
    final = events[-1]
    assert isinstance(final, ReportComplete)
    # Provider citation surfaces at the root.
    cite_ids = {c.get("id") for c in final.schema.get("citations") or []}
    assert "c-web-1" in cite_ids, (
        f"provider citation lost in fallback path; got citations={final.schema.get('citations')}"
    )
    # Server-stamped meta_stats present with correct counts.
    meta = final.schema.get("meta_stats") or {}
    assert meta.get("sections_count") == 1
    assert meta.get("sources_count", 0) >= 1
    assert meta.get("model_id")


def test_inject_server_fields_hoists_rail_citations_to_root() -> None:
    """When the model puts citations under rail (a recurring drift even
    after explicit prompt guidance), strip them from rail and merge them
    into the root-level `citations` array so strict validation passes on
    the very first turn instead of burning the 8-turn repair budget."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from openlia.llm.runtime.report import _inject_server_fields

    payload = {
        "cover": {"title": "T", "subtitle": "S", "tagline": "x"},
        "sections": [{"id": "s", "title": "S", "blocks": []}],
        "rail": {
            "verdict": {"stance": "hold", "rationale": "x"},
            "citations": [{"id": "1", "title": "From rail"}],
            "meta_stats": {"sources_count": 99},  # also misplaced; should drop
        },
        "meta_stats": {"sources_count": 50},  # model should not emit; drop
    }
    out = _inject_server_fields(
        payload, department_id="equity_research", generated_at=_dt.now(_UTC)
    )
    assert "citations" not in out.get("rail", {})
    assert "meta_stats" not in out.get("rail", {})
    assert "meta_stats" not in out  # top-level model-authored copy dropped too
    root_cites = out.get("citations") or []
    assert any(c.get("id") == "1" and c.get("title") == "From rail" for c in root_cites)


def test_inject_server_fields_merges_rail_citations_with_existing_root() -> None:
    """If the model puts SOME citations at root and ALSO some under rail,
    hoist the rail ones in but keep root entries; deduplicate by id."""
    from datetime import UTC as _UTC
    from datetime import datetime as _dt

    from openlia.llm.runtime.report import _inject_server_fields

    payload = {
        "cover": {"title": "T", "subtitle": "S", "tagline": "x"},
        "sections": [{"id": "s", "title": "S", "blocks": []}],
        "citations": [{"id": "1", "title": "Root one"}],
        "rail": {
            "verdict": {"stance": "hold", "rationale": "x"},
            "citations": [
                {"id": "1", "title": "Same id — dropped (root wins)"},
                {"id": "2", "title": "New one — kept"},
            ],
        },
    }
    out = _inject_server_fields(
        payload, department_id="equity_research", generated_at=_dt.now(_UTC)
    )
    assert "citations" not in out.get("rail", {})
    by_id = {c["id"]: c for c in (out.get("citations") or [])}
    assert by_id["1"]["title"] == "Root one"  # root wins on id collision
    assert by_id["2"]["title"] == "New one — kept"
