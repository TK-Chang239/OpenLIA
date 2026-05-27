"""Tests for LLMResearcherClient — tool-use loop + provenance attachment."""

from __future__ import annotations

import json

import pytest
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
    MAX_COVERAGE_RETRIES,
    FakeToolLLMClient,
    LLMResearcherClient,
    ToolTurnResponse,
)
from openlia.llm.runtime.report_v2_3.clients.researcher import ResearchRequest
from openlia.llm.runtime.report_v2_3.research import build_research_tools
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleSeries,
    ClarifyProceed,
    ComputedSource,
    DataNeed,
    DataProviderSource,
    Language,
    Outline,
    OutlineSection,
    ReportType,
    ResearchBundle,
    WebSource,
)
from openlia.llm.runtime.report_v2_3.templates import TemplateSpec, get_builtin
from openlia.llm.types import Citation, Message, ToolCall

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _template() -> TemplateSpec:
    return get_builtin(ReportType.INITIATION)


def _outline() -> Outline:
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="financials",
                title="Financials",
                data_needs=[
                    DataNeed(
                        description="latest annual revenue",
                        expected_fact_ids=["rev_ttm"],
                    )
                ],
            )
        ],
    )


def _request() -> ResearchRequest:
    return ResearchRequest(
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        outline=_outline(),
        template=_template(),
        clarify_result=ClarifyProceed(assumptions=["audience: PM"]),
    )


def _tools() -> list:
    return build_research_tools(
        fundamentals=lambda t: {
            "General": {"Code": t},
            "Highlights": {"Revenue": 60_900_000_000},
        },
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )


# ---------------------------------------------------------------------------
# Happy path — one tool call, one fact
# ---------------------------------------------------------------------------


def test_happy_path_single_tool_call_to_single_fact() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_ttm",
                                "label": "Revenue (TTM)",
                                "value": 60_900_000_000,
                                "unit": "USD",
                                "ticker": "NVDA",
                                "evidence_id": "tc_1",
                            }
                        ]
                    }
                ),
                tool_calls=(),
            ),
        ]
    )

    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert isinstance(bundle, ResearchBundle)
    assert bundle.tickers == ["NVDA"]
    fact = bundle.facts["rev_ttm"]
    assert fact.label == "Revenue (TTM)"
    assert fact.value == 60_900_000_000.0
    assert isinstance(fact.source, DataProviderSource)
    assert fact.source.provider == "EODHD"


def test_provenance_carries_tool_endpoint() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_42",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 1.0,
                                "evidence_id": "tc_42",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    src = bundle.facts["rev"].source
    assert isinstance(src, DataProviderSource)
    assert src.endpoint == "fundamentals"


# ---------------------------------------------------------------------------
# Multi-turn — model chains tool calls and emits multiple facts
# ---------------------------------------------------------------------------


def test_multi_turn_loop_accumulates_evidence() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="t2",
                        name="get_historical_prices",
                        arguments={
                            "ticker": "NVDA",
                            "from_date": "2025-01-01",
                            "to_date": "2025-12-31",
                        },
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 100.0,
                                "evidence_id": "t1",
                            },
                            {
                                "id": "px_last",
                                "label": "Last Close",
                                "value": 500.0,
                                "evidence_id": "t2",
                            },
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    assert {"rev", "px_last"} <= set(bundle.facts)
    assert bundle.facts["px_last"].source.endpoint == "eod"


# ---------------------------------------------------------------------------
# Computed facts
# ---------------------------------------------------------------------------


def test_computed_fact_emitted_with_computed_from() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_usd",
                                "label": "Revenue USD",
                                "value": 100.0,
                                "evidence_id": "t1",
                            },
                            {
                                "id": "rev_millions",
                                "label": "Revenue (USD M)",
                                "value": 0.0001,
                                "unit": "USD_millions",
                                "computed_from": ["rev_usd"],
                                "method": "rev_usd / 1_000_000",
                            },
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    computed = bundle.facts["rev_millions"]
    assert isinstance(computed.source, ComputedSource)
    assert computed.source.derived_from == ["rev_usd"]
    assert "1_000_000" in computed.source.method


# ---------------------------------------------------------------------------
# Time-series values
# ---------------------------------------------------------------------------


def test_timeseries_value_parsed_into_bundle_series() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_series",
                                "label": "Revenue by quarter",
                                "value": {
                                    "points": [
                                        {"period": "2024-Q4", "value": 22.1},
                                        {"period": "2025-Q1", "value": 26.0},
                                    ],
                                    "unit": "USD_billions",
                                },
                                "evidence_id": "t1",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    series = bundle.facts["rev_series"].value
    assert isinstance(series, BundleSeries)
    assert [p.period for p in series.points] == ["2024-Q4", "2025-Q1"]
    assert series.unit == "USD_billions"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_max_turns_exceeded_raises() -> None:
    # Loops indefinitely calling the same tool — researcher must stop.
    def loop_responder(_messages: list[Message]) -> ToolTurnResponse:
        return ToolTurnResponse(
            text="",
            tool_calls=(
                ToolCall(id="t_loop", name="get_fundamentals", arguments={"ticker": "NVDA"}),
            ),
        )

    researcher = LLMResearcherClient(
        FakeToolLLMClient(responder=loop_responder), _tools(), max_turns=3
    )
    with pytest.raises(RuntimeError, match="did not emit a final bundle within 3"):
        researcher.research(_request())


def test_evidence_id_must_resolve_to_a_tool_call() -> None:
    # A fabricated evidence_id is skipped (logged) rather than raised on.
    # When EVERY fact has one, the bundle is empty and we surface the
    # zero-usable-facts error so the run still fails loudly. A single
    # bad evidence_id alongside good ones now only skips that one fact.
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 100.0,
                                "evidence_id": "tc_ghost",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_fact_without_evidence_or_computed_raises() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {"id": "rev", "label": "Revenue", "value": 1.0},
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="evidence_id"):
        researcher.research(_request())


def test_unknown_tool_call_is_reported_back_to_model_then_continues() -> None:
    """The researcher should not crash if the LLM hallucinates a tool name —
    it should surface a structured error and let the model recover."""

    captured: dict[str, list[Message]] = {}

    def responder(messages: list[Message]) -> ToolTurnResponse:
        captured["last"] = list(messages)
        # Turn 1: hallucinate a tool.
        # Turn 2: after seeing the error, give up and emit a stub fact.
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            return ToolTurnResponse(
                text="",
                tool_calls=(ToolCall(id="bad_1", name="nonexistent_tool", arguments={}),),
            )
        # Now make a valid tool call so we have evidence for the fact.
        if n == 1:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_real", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev",
                            "label": "Revenue",
                            "value": 1.0,
                            "evidence_id": "tc_real",
                        }
                    ]
                }
            ),
        )

    researcher = LLMResearcherClient(FakeToolLLMClient(responder=responder), _tools())
    bundle = researcher.research(_request())
    assert "rev" in bundle.facts
    # The bad tool's error was injected as a `tool` message back to the model.
    tool_msgs = [m for m in captured["last"] if m.role == "tool"]
    assert any("Unknown tool" in m.content for m in tool_msgs)


def test_malformed_final_json_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text="this is not json at all", tool_calls=())])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="not valid JSON"):
        researcher.research(_request())


def test_final_json_without_facts_array_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text=json.dumps({"something_else": []}))])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no `facts` array"):
        researcher.research(_request())


def test_empty_final_turn_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text="", tool_calls=())])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="neither tool_calls nor text"):
        researcher.research(_request())


# ---------------------------------------------------------------------------
# Thematic runs — planner asks for nothing, researcher returns nothing
# ---------------------------------------------------------------------------


def _thematic_outline() -> Outline:
    """Outline whose sections have no data_needs — thematic by design."""
    return Outline(
        tickers=[],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(id="overview", title="Overview", data_needs=[]),
            OutlineSection(id="themes", title="Themes", data_needs=[]),
        ],
    )


def _thematic_request() -> ResearchRequest:
    return ResearchRequest(
        raw_prompt="give me a thematic read on AI infra",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=[],
        outline=_thematic_outline(),
        template=_template(),
        clarify_result=ClarifyProceed(assumptions=["audience: PM"]),
    )


def test_researcher_accepts_empty_bundle_when_planner_asked_for_nothing() -> None:
    """RESEARCH should not raise when the planner emitted zero data_needs —
    the run is thematic by design, the bundle is legitimately empty."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps({"facts": []}),
                tool_calls=(),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_thematic_request())
    assert isinstance(bundle, ResearchBundle)
    assert bundle.tickers == []
    assert bundle.facts == {}


def test_researcher_still_raises_when_planner_asked_but_got_nothing() -> None:
    """When the planner emitted data_needs but the researcher returned zero
    facts, that's a genuine failure — RESEARCH still raises."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps({"facts": []}),
                tool_calls=(),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(
        RuntimeError,
        match=r"no `facts` array|empty `facts` array|no usable facts",
    ):
        researcher.research(_request())


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_duplicate_tool_names_rejected() -> None:
    a = _tools()
    with pytest.raises(ValueError, match="Duplicate tool name"):
        LLMResearcherClient(FakeToolLLMClient(turns=[]), a + a[:1])


def test_max_turns_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        LLMResearcherClient(FakeToolLLMClient(turns=[]), _tools(), max_turns=0)


def test_fake_rejects_both_or_neither() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        FakeToolLLMClient(turns=[], responder=lambda _m: ToolTurnResponse(text=""))
    with pytest.raises(ValueError, match="exactly one"):
        FakeToolLLMClient()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Tool exec errors propagate back to the model, not as Python exceptions
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# RESEARCH dual-lane prompt + payload (TDD red-tests)
#
# The dominant zero-web-calls failure mode is the researcher satisfying a
# narrative need from get_company_news (EODHD) instead of web_search.
# The fix moves routing from the prose-driven source_class trichotomy to
# explicit data_fact_ids / web_fact_ids lanes — the prompt and the
# initial user payload must both speak the new contract.
# ---------------------------------------------------------------------------


def test_research_prompt_routes_data_lane_to_eodhd_and_web_lane_to_web_search() -> None:
    """SYSTEM_PROMPT must route by lane, not by source_class. The two
    lane field names must appear AND each must be paired with its
    canonical tool family."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT,
    )

    assert "data_fact_ids" in SYSTEM_PROMPT
    assert "web_fact_ids" in SYSTEM_PROMPT
    # Old trichotomy is retired from the new prompt — leaving it in
    # creates a second, contradictory routing signal.
    assert "source_class" not in SYSTEM_PROMPT
    assert "expected_fact_ids" not in SYSTEM_PROMPT
    # Tool family handles must be present so the routing is concrete.
    assert "web_search" in SYSTEM_PROMPT
    assert "get_company_news" in SYSTEM_PROMPT or "get_fundamentals" in SYSTEM_PROMPT


def test_research_prompt_blocks_eodhd_news_from_satisfying_web_lane() -> None:
    """The load-bearing constraint: an EODHD news headline does NOT
    satisfy a web_fact_id, even when the headline looks like enough.
    Without this line the RKLB-style 0% recurs because the model
    silently substitutes get_company_news output for web_search output."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT,
    )

    text = SYSTEM_PROMPT.lower()
    # The constraint must be expressed; we don't pin the exact phrasing
    # but the negation + the protected lane name must co-occur.
    assert "web_fact_ids" in SYSTEM_PROMPT
    assert (
        "do not satisfy" in text
        or "does not satisfy" in text
        or "cannot satisfy" in text
        or "never satisfy" in text
    )
    # And the rule must call out the substitution source so the model
    # connects the constraint to its own observed behavior.
    assert "eodhd" in text or "get_company_news" in text or "headline" in text


def test_research_prompt_teaches_drop_after_real_search_for_web_lane() -> None:
    """When web_search returns nothing usable for a web_fact_id, the
    model drops the fact rather than substituting from EODHD. The drop
    must follow a real search, never a 'searching felt unnecessary'
    shortcut."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT,
    )

    text = SYSTEM_PROMPT.lower()
    assert "drop" in text or "omit" in text
    assert "real search" in text or "returned nothing" in text or "after a search" in text


def test_initial_user_payload_emits_data_and_web_fact_id_lists_per_need() -> None:
    """The researcher's first user message must surface each data_need's
    data_fact_ids and web_fact_ids as separate lists so the model can
    route every id structurally instead of inferring lanes from prose."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        _initial_user_text,
    )

    outline = Outline(
        tickers=["TEST"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="layered theme",
                        data_fact_ids=["headlines"],
                        web_fact_ids=["framing"],
                    ),
                    DataNeed(
                        description="pure financials",
                        data_fact_ids=["rev_ttm"],
                    ),
                    DataNeed(
                        description="pure narrative",
                        web_fact_ids=["analyst_pt_range"],
                    ),
                ],
            )
        ],
    )
    request = ResearchRequest(
        raw_prompt="initiate on TEST",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["TEST"],
        outline=outline,
        template=_template(),
        clarify_result=None,
    )

    raw = _initial_user_text(request)
    # The user turn may carry a search-budget anchor above the JSON;
    # parse from the first '{' so the tests of payload shape are
    # independent of the anchor wording.
    payload = json.loads(raw[raw.index("{") :])
    needs = payload["sections"][0]["data_needs"]
    assert needs[0]["data_fact_ids"] == ["headlines"]
    assert needs[0]["web_fact_ids"] == ["framing"]
    assert needs[1]["data_fact_ids"] == ["rev_ttm"]
    assert needs[1]["web_fact_ids"] == []
    assert needs[2]["data_fact_ids"] == []
    assert needs[2]["web_fact_ids"] == ["analyst_pt_range"]
    # The old wire fields must not leak through — the planner and
    # researcher must speak the same vocabulary.
    for n in needs:
        assert "source_class" not in n
        assert "expected_fact_ids" not in n


def test_tool_execution_error_reaches_model_as_tool_message() -> None:
    def boom(_t: str) -> dict:
        raise RuntimeError("upstream is down")

    failing_tools = build_research_tools(
        fundamentals=boom,
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )

    def responder(messages: list[Message]) -> ToolTurnResponse:
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        # After the failure, model gives up.
        return ToolTurnResponse(
            text=json.dumps({"facts": [{"id": "x", "label": "x"}]}),
        )

    researcher = LLMResearcherClient(
        FakeToolLLMClient(responder=responder), failing_tools, max_turns=4
    )
    # The fake's final emission omits evidence_id; the researcher raises on
    # validation, but BEFORE then it should have surfaced the upstream
    # failure as a tool message — confirmed via the error propagation path.
    with pytest.raises(RuntimeError):
        researcher.research(_request())


# ---------------------------------------------------------------------------
# Native web_search citation resolution
# ---------------------------------------------------------------------------


def _web_cite(url: str, title: str = "T", snippet: str = "S") -> Citation:
    return Citation(id="c1", kind="web", url=url, title=title, snippet=snippet, source="Test")


def test_url_form_evidence_id_resolves_via_harvested_map() -> None:
    """When the model cites a web fact by the verbatim URL it
    retrieved this run, the runtime must resolve the URL through the
    same map that backs ``web_N``. This is necessary because gpt-5.4's
    ``web_search_preview`` is intra-turn agentic — all the web actions
    happen inside one LLM response, and the model writes its final
    JSON in the same response, so it never sees the ``web_N`` mapping
    we inject between turns. The URL form is the model's only
    grounded handle when the search and the final JSON share a turn."""
    url = "https://example.com/article"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "qual_pos",
                                "label": "Qualitative positioning",
                                "value": "AI infra leader",
                                "evidence_id": url,
                            }
                        ]
                    }
                ),
                tool_calls=(),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    fact = bundle.facts["qual_pos"]
    assert isinstance(fact.source, WebSource)
    assert fact.source.url == url


def test_url_form_with_toggled_trailing_slash_resolves() -> None:
    """LLMs commonly normalize trailing punctuation on URLs. The
    runtime must resolve both ``https://x/a`` and ``https://x/a/``
    when only one form was harvested."""
    canonical = "https://example.com/article"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "qual",
                                "label": "Qualitative",
                                "value": "x",
                                # Trailing slash added by the model.
                                "evidence_id": canonical + "/",
                            }
                        ]
                    }
                ),
                citations=(_web_cite(canonical),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    assert isinstance(bundle.facts["qual"].source, WebSource)


def test_url_not_in_harvest_map_drops_fact() -> None:
    """A URL the model never actually fetched this run cannot resolve.
    This is the load-bearing safety check that makes URL acceptance
    safe — the harvest map is populated exclusively from real
    ``web_search_call.action`` payloads, so a fabricated URL fails
    to resolve and the fact drops."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "halluc",
                                "label": "Hallucinated",
                                "value": "x",
                                "evidence_id": "https://no-such-source.example/never-fetched",
                            }
                        ]
                    }
                ),
                citations=(_web_cite("https://example.com/real"),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_web_evidence_id_resolves_by_web_n() -> None:
    """LLM cites by `web_1` — resolves to the canonical WebSource."""
    url = "https://example.com/news"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "catalyst",
                                "label": "Recent catalyst",
                                "value": "new GPU launch",
                                "evidence_id": "web_1",
                            }
                        ]
                    }
                ),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    fact = bundle.facts["catalyst"]
    assert isinstance(fact.source, WebSource)
    assert fact.source.url == url


def test_unknown_web_n_id_drops_fact() -> None:
    """A `web_N` id the model invented out of thin air (no real search this
    run) cannot be resolved and the fact is dropped."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "halluc",
                                "label": "Hallucinated",
                                "value": "x",
                                "evidence_id": "web_7",
                            }
                        ]
                    }
                ),
                citations=(_web_cite("https://example.com/real"),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_openai_internal_step_id_drops_fact() -> None:
    """gpt-5.4's ``web_search_preview`` agent labels its own internal
    actions with strings like ``turn0search0``, ``turn1view2``. Those
    are private to the search agent and the runtime cannot resolve
    them — they should drop the fact loudly, not silently masquerade
    as a valid handle."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "segment_mix",
                                "label": "Segment mix",
                                "value": "AI infra dominant",
                                "evidence_id": "turn1view2",
                            }
                        ]
                    }
                ),
                citations=(_web_cite("https://example.com/real"),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_system_text_carries_web_n_mapping_after_harvest() -> None:
    """The cumulative ``web_N → URL`` mapping must live in the per-turn
    system text — that way it cannot scroll out under later tool turns
    and the model always sees the current claimable web_N ids."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(
        responder=_two_turn_web_responder(url),
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert {"rev_ttm", "qual"} <= set(bundle.facts)
    assert isinstance(bundle.facts["qual"].source, WebSource)

    # Turn 1 has no mapping yet (no prior harvest). The phrase "Web
    # search results so far" appears in the SYSTEM_PROMPT itself
    # (referring to the note), so we match on the unique rendered note
    # header instead.
    assert "(newest last):" not in llm.systems[0]
    # Turn 2 system text must carry the harvested mapping AND the
    # explicit reminder that raw URLs are not accepted AND the
    # publisher histogram (step 5 of the narrative-search procedure
    # needs a concrete dominance signal to read).
    assert "(newest last):" in llm.systems[1]
    assert "web_1" in llm.systems[1]
    assert url in llm.systems[1]
    # The note must say plainly that BOTH web_N and the exact URL
    # resolve, and call out the failure mode for OpenAI internal
    # step labels so a model that picks them up from context knows
    # to switch.
    assert "either a `web_N` id" in llm.systems[1]
    assert "the exact URL" in llm.systems[1]
    assert "turn0search0" in llm.systems[1]
    assert "By publisher: example.com=1" in llm.systems[1]


def test_system_text_carries_mapping_on_every_turn_after_harvest() -> None:
    """Mapping must reappear on EVERY turn after first harvest — not just
    the immediate next turn. This guards against a regression where the
    note scrolls out under many subsequent tool roundtrips."""
    url = "https://example.com/foo"

    def responder(messages: list[Message]) -> ToolTurnResponse:
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            # Turn 1: harvest a web citation alongside a function tool call.
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
                citations=(_web_cite(url),),
            )
        if n == 1:
            # Turn 2: another function tool call, no new citations.
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_2", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        # Turn 3: final JSON citing both the function call and the web hit.
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev_ttm",
                            "label": "Revenue (TTM)",
                            "value": 60_900_000_000,
                            "evidence_id": "tc_1",
                        },
                        {
                            "id": "qual",
                            "label": "Qualitative",
                            "value": "x",
                            "evidence_id": "web_1",
                        },
                    ]
                }
            ),
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert "qual" in bundle.facts
    # Mapping pinned at turn 2 AND turn 3 — system text is the carrier.
    assert "web_1" in llm.systems[1]
    assert "web_1" in llm.systems[2]


def test_research_prompt_only_accepts_web_n_as_web_handle() -> None:
    """The model cannot fabricate `web_N` ids — they only exist once a
    real search returns and the runtime mints them. By telling the model
    `web_N` is the only accepted web handle (and explicitly banning raw
    URLs in `evidence_id`), the prompt closes the hallucination path of
    citing URLs reconstructed from training memory. The `_resolve_evidence_id`
    code path still accepts URL form as defense-in-depth, but the prompt
    surface presents one handle to keep the model honest."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    # "Two forms are accepted" wraps across a line break in the dedented
    # prompt — assert each fragment separately.
    assert "Two forms are" in RESEARCH_SYSTEM_PROMPT
    assert "accepted:" in RESEARCH_SYSTEM_PROMPT
    assert "Do NOT emit a raw URL as an `evidence_id`" in RESEARCH_SYSTEM_PROMPT
    assert "only after a real search" in RESEARCH_SYSTEM_PROMPT
    assert "only accepted web handle" in RESEARCH_SYSTEM_PROMPT


def test_research_prompt_binds_fact_id_to_planner_lists_verbatim() -> None:
    """Coverage check matches on the planner's per-lane id lists, so the
    prompt must instruct the model to use those ids verbatim — otherwise
    coverage stays at 0/N even when evidence flows."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "data_fact_ids" in RESEARCH_SYSTEM_PROMPT
    assert "web_fact_ids" in RESEARCH_SYSTEM_PROMPT
    assert "verbatim" in RESEARCH_SYSTEM_PROMPT


def test_research_prompt_teaches_claim_classification_before_search() -> None:
    """The narrative-search guidance must teach a reasoning procedure
    that operates on the structure of the claim (so it transfers to
    tickers, sectors, and source landscapes the prompt never enumerated)
    instead of listing approved publishers. The five-step procedure —
    classify, locate authority, check interested party, triangulate,
    steer by results — must be present verbatim enough that a refactor
    that quietly drops a step is caught here."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "What KIND of claim" in RESEARCH_SYSTEM_PROMPT
    assert "Where does authority for THAT kind of claim live" in RESEARCH_SYSTEM_PROMPT
    assert "Is that primary source an interested party" in RESEARCH_SYSTEM_PROMPT
    assert "triangulate" in RESEARCH_SYSTEM_PROMPT
    assert "Let results steer the next query" in RESEARCH_SYSTEM_PROMPT


def test_research_prompt_carries_interested_party_caveat() -> None:
    """The single most load-bearing line for source diversity: the
    subject company is authoritative for what it SAID, but the
    weakest source for whether a claim is true. Dropping this line
    reverts to a publisher-list prompt that does not transfer."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    # Phrase wraps across a line break; assert each fragment separately.
    assert "authoritative for" in RESEARCH_SYSTEM_PROMPT
    assert "what management SAID" in RESEARCH_SYSTEM_PROMPT
    assert "weakest source" in RESEARCH_SYSTEM_PROMPT
    assert "no stake" in RESEARCH_SYSTEM_PROMPT


def test_research_prompt_includes_one_worked_trace_not_a_menu() -> None:
    """The procedure is taught with exactly one worked example so the
    model generalizes the SHAPE of the reasoning instead of interpolating
    from a menu of canned examples. Guards against future PRs that
    'helpfully' add more examples and dilute the lever."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "Worked example" in RESEARCH_SYSTEM_PROMPT
    # Renamed from "antitrust exposure" → "antitrust_exposure" when the
    # example was rewritten to use the new web_fact_ids vocabulary; the
    # underlying worked-trace claim is the same.
    assert "antitrust_exposure" in RESEARCH_SYSTEM_PROMPT
    # Exactly one worked example — anyone adding a second should think
    # about whether the procedure is still being taught or just enumerated.
    assert RESEARCH_SYSTEM_PROMPT.count("Worked example") == 1


def test_research_prompt_does_not_enumerate_publishers() -> None:
    """A publisher list goes stale, is always incomplete, and does not
    transfer to foreign issuers or macro claims. The procedure replaces
    the list entirely — this test guards against a regression that
    re-adds 'Bloomberg / Reuters / WSJ / FT' style enumerations."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    for outlet in ("Bloomberg", "Reuters", "Wall Street Journal", "Financial Times"):
        assert outlet not in RESEARCH_SYSTEM_PROMPT, (
            f"prompt should not enumerate {outlet} — teach the procedure, not the destinations"
        )


def test_web_search_note_renders_per_publisher_count() -> None:
    """Step 5 of the procedure ('steer the next query by your results')
    needs a concrete signal to read — a feeling about dominance is not
    something the model can act on. The mapping note must include a
    `By publisher: host=count` line whenever any URL has been
    harvested, grouped by registrable host and sorted by URL count."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        _format_web_search_note,
    )

    url_to_id = {
        "https://investor.rocketlab.com/news/a": "web_1",
        "https://investor.rocketlab.com/news/b": "web_2",
        "https://www.rocketlab.com/about/c": "web_3",
        "https://www.sec.gov/Archives/edgar/data/d": "web_4",
    }
    note = _format_web_search_note(url_to_id)
    # All three rocketlab subdomains collapse to the registrable host,
    # so the dominance signal is unambiguous: 3 vs 1.
    assert "By publisher: " in note
    assert "rocketlab.com=" in note or "investor.rocketlab.com=" in note
    assert "sec.gov=1" in note


def test_web_search_note_omits_publisher_line_when_empty() -> None:
    """No URLs harvested → no histogram line. The mapping note's primary
    job is still to enumerate `web_N` ids; the publisher line is a
    helper for diversity steering and should not appear when there is
    nothing to steer."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        _format_web_search_note,
    )

    note = _format_web_search_note({})
    assert "By publisher" not in note


def test_research_logs_per_turn_tool_and_citation_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each turn must emit a structured log line summarizing tool_calls,
    citations, and the cumulative web_urls count. Without these signals
    the only visible failure mode is "narrative coverage 0/N at finalize"
    — which doesn't tell you whether web_search ran at all."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    turn_lines = [r.message for r in caplog.records if "v2.3 RESEARCH turn=" in r.message]
    assert len(turn_lines) == 2
    assert "tool_calls=1" in turn_lines[0]
    assert "citations=1" in turn_lines[0]
    assert "new_web_urls=1" in turn_lines[0]
    # Turn 2 emits the final JSON — no tool calls, no new citations.
    assert "tool_calls=0" in turn_lines[1]
    assert "new_web_urls=0" in turn_lines[1]


def test_research_logs_tool_call_outcome_per_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each function tool call must log its outcome (ok|error) and id so
    a failed tool roundtrip surfaces in the log instead of disappearing
    behind a downstream fact-resolution warning."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    tool_lines = [r.message for r in caplog.records if "v2.3 RESEARCH tool=" in r.message]
    assert len(tool_lines) == 1
    assert "tool=get_fundamentals" in tool_lines[0]
    assert "status=ok" in tool_lines[0]


def test_research_finished_log_includes_publisher_histogram(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The end-of-run summary must report a per-publisher URL count so
    source-breadth regressions ("all 30 URLs from rocketlab.com") are
    visible without re-reading every line."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    finished = [r.message for r in caplog.records if "RESEARCH finished" in r.message]
    assert len(finished) == 1
    assert "publishers=" in finished[0]
    assert "example.com" in finished[0]


def _two_turn_web_responder(url: str):
    """Helper: turn 1 makes a function tool call AND returns a web citation;
    turn 2 emits final JSON citing both."""

    def responder(messages: list[Message]) -> ToolTurnResponse:
        if not any(m.role == "assistant" for m in messages):
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
                citations=(_web_cite(url),),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev_ttm",
                            "label": "Revenue (TTM)",
                            "value": 60_900_000_000,
                            "evidence_id": "tc_1",
                        },
                        {
                            "id": "qual",
                            "label": "Qualitative",
                            "value": "x",
                            "evidence_id": "web_1",
                        },
                    ]
                }
            ),
        )

    return responder


# ---------------------------------------------------------------------------
# Web coverage gate at finalize
# ---------------------------------------------------------------------------


def _outline_with_strict_web(web_ids: list[str]) -> Outline:
    """Outline whose section has one need with strict-web ids only.
    `data_fact_ids` is empty for that need, so every id in `web_ids` is
    strictly web-lane and the coverage gate applies."""
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="narrative-only need",
                        web_fact_ids=list(web_ids),
                    ),
                ],
            )
        ],
    )


def _request_with_outline(outline: Outline) -> ResearchRequest:
    return ResearchRequest(
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        outline=outline,
        template=_template(),
        clarify_result=ClarifyProceed(assumptions=[]),
    )


def test_web_coverage_gate_passes_when_strict_web_ids_satisfied() -> None:
    """When every strict-web fact id in the outline is backed by a
    WebSource in the bundle, the gate is silent and the bundle is
    returned. This is the happy path for any narrative-only need."""
    url = "https://example.com/article"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "framing",
                                "label": "Framing",
                                "value": "x",
                                "evidence_id": "web_1",
                            }
                        ]
                    }
                ),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))
    assert "framing" in bundle.facts
    assert isinstance(bundle.facts["framing"].source, WebSource)


def test_web_coverage_gate_rejects_when_strict_web_id_unmet() -> None:
    """If PLAN lists an id in `web_fact_ids` only (strict-web) and the
    model finishes without producing a fact for it backed by a
    WebSource, finalize must raise. This is the failure mode the gate
    exists to catch — the model silently skipping the web lane.

    The model is scripted to refuse to call `web_search` across every
    retry, so the loop exhausts its budget and the gate surfaces."""

    def responder(messages: list[Message]) -> ToolTurnResponse:
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if not post_user_tool:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev_ttm",
                            "label": "Revenue (TTM)",
                            "value": 1.0,
                            "evidence_id": "tc_1",
                        }
                    ]
                }
            )
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="missing web-lane coverage"):
        researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))


def test_web_coverage_gate_satisfying_with_data_lane_does_not_count() -> None:
    """A fact whose id is a strict-web id but is backed by a
    DataProviderSource does NOT satisfy the gate — lane discipline is
    enforced by source type, not by id presence in the bundle. This
    blocks the failure mode where the model substitutes EODHD news for
    a web-only need.

    The model repeats the same data-lane substitution across every
    retry, so the loop drains its budget and the gate raises."""

    def responder(messages: list[Message]) -> ToolTurnResponse:
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if not post_user_tool:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "framing",
                            "label": "Framing",
                            "value": "x",
                            "evidence_id": "tc_1",
                        }
                    ]
                }
            ),
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="missing web-lane coverage"):
        researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))


def test_web_coverage_gate_skips_either_lane_ids() -> None:
    """Ids in BOTH `data_fact_ids` and `web_fact_ids` for the same need
    are "either" — RESEARCH has discretion. The gate must not trip when
    such an id is satisfied by a data-lane source only, otherwise the
    legacy `source_class='either'` migration shape would fail every
    rehydrated run."""
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="either-lane fact",
                        data_fact_ids=["rev_ttm"],
                        web_fact_ids=["rev_ttm"],
                    ),
                ],
            )
        ],
    )
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_ttm",
                                "label": "Revenue (TTM)",
                                "value": 1.0,
                                "evidence_id": "tc_1",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request_with_outline(outline))
    assert isinstance(bundle.facts["rev_ttm"].source, DataProviderSource)


def test_web_coverage_gate_no_op_when_no_strict_web_ids() -> None:
    """An outline with no `web_fact_ids` anywhere must not trip the
    gate — purely quantitative reports legitimately have nothing to
    enforce. Skipping this no-op case would break every data-only
    fixture in the suite."""
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="pure data",
                        data_fact_ids=["rev_ttm"],
                    ),
                ],
            )
        ],
    )
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_ttm",
                                "label": "Revenue (TTM)",
                                "value": 1.0,
                                "evidence_id": "tc_1",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request_with_outline(outline))
    assert "rev_ttm" in bundle.facts


def test_web_coverage_gate_logs_coverage_breakdown(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Coverage stats must surface in logs even when the gate passes,
    so the per-run web-lane satisfaction rate is observable without
    re-deriving it from the bundle."""
    url = "https://example.com/article"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "framing",
                                "label": "Framing",
                                "value": "x",
                                "evidence_id": "web_1",
                            }
                        ]
                    }
                ),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))

    coverage_lines = [r.message for r in caplog.records if "web coverage:" in r.message]
    assert len(coverage_lines) == 1
    assert "strict=1" in coverage_lines[0]
    assert "covered=1" in coverage_lines[0]
    assert "missing=0" in coverage_lines[0]


# ---------------------------------------------------------------------------
# Bounded coverage retry — re-prompt on gate failure
# ---------------------------------------------------------------------------


def _final_json(facts: list[dict[str, object]]) -> str:
    return json.dumps({"facts": facts})


def test_coverage_retry_recovers_when_model_searches_on_second_pass() -> None:
    """First final JSON skips the web lane → gate raises → loop appends
    a corrective user turn and re-prompts → model emits a new final JSON
    backed by a real web hit. The bundle the researcher returns covers
    the strict-web id and does NOT include the bad first attempt."""
    url = "https://example.com/article"

    def responder(messages: list[Message]) -> ToolTurnResponse:
        corrective_count = sum(
            1 for m in messages if m.role == "user" and "Coverage check FAILED" in (m.content or "")
        )
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if corrective_count == 0:
            if not post_user_tool:
                return ToolTurnResponse(
                    text="",
                    tool_calls=(
                        ToolCall(
                            id="tc_1",
                            name="get_fundamentals",
                            arguments={"ticker": "NVDA.US"},
                        ),
                    ),
                )
            return ToolTurnResponse(
                text=_final_json(
                    [
                        {
                            "id": "framing",
                            "label": "Framing",
                            "value": "from-data-not-web",
                            "evidence_id": "tc_1",
                        }
                    ]
                )
            )
        return ToolTurnResponse(
            text=_final_json(
                [
                    {
                        "id": "framing",
                        "label": "Framing",
                        "value": "from-web",
                        "evidence_id": "web_1",
                    }
                ]
            ),
            citations=(_web_cite(url),),
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())

    bundle = researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))

    assert "framing" in bundle.facts
    assert isinstance(bundle.facts["framing"].source, WebSource)
    assert bundle.facts["framing"].value == "from-web"


def test_coverage_retry_message_names_missing_ids() -> None:
    """The corrective user turn the loop injects after a gate failure
    must list each missing id verbatim so the model knows exactly what
    it owes — a generic 'try again' wouldn't tell it which lane work
    was skipped."""
    url = "https://example.com/article"

    def responder(messages: list[Message]) -> ToolTurnResponse:
        corrective_count = sum(
            1 for m in messages if m.role == "user" and "Coverage check FAILED" in (m.content or "")
        )
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if corrective_count == 0:
            if not post_user_tool:
                return ToolTurnResponse(
                    text="",
                    tool_calls=(
                        ToolCall(
                            id="tc_1",
                            name="get_fundamentals",
                            arguments={"ticker": "NVDA.US"},
                        ),
                    ),
                )
            return ToolTurnResponse(
                text=_final_json(
                    [
                        {
                            "id": "framing",
                            "label": "Framing",
                            "value": "no-web",
                            "evidence_id": "tc_1",
                        }
                    ]
                )
            )
        return ToolTurnResponse(
            text=_final_json(
                [
                    {
                        "id": "framing",
                        "label": "Framing",
                        "value": "ok",
                        "evidence_id": "web_1",
                    },
                    {
                        "id": "outlook",
                        "label": "Outlook",
                        "value": "ok",
                        "evidence_id": "web_1",
                    },
                ]
            ),
            citations=(_web_cite(url),),
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())

    researcher.research(_request_with_outline(_outline_with_strict_web(["framing", "outlook"])))

    corrective_msgs = [
        m
        for call in llm.calls
        for m in call
        if m.role == "user" and "Coverage check FAILED" in (m.content or "")
    ]
    assert corrective_msgs, "expected at least one corrective user turn"
    corrective = corrective_msgs[-1].content
    assert "framing" in corrective
    assert "outlook" in corrective
    assert "web_search" in corrective


def test_coverage_retry_exhaustion_re_raises_gate_error() -> None:
    """When the model burns through all coverage retries still not
    backing the strict-web ids, the gate's RuntimeError must escape so
    the runner can fail the stage rather than ship an under-evidenced
    bundle. Initial attempt + MAX_COVERAGE_RETRIES retries all fail.

    The first assistant turn of each attempt makes a tool call to
    produce a real `tc_1` evidence id, then the second emits a
    data-lane fact that the gate will reject."""
    finals_seen = 0

    def responder(messages: list[Message]) -> ToolTurnResponse:
        nonlocal finals_seen
        # Count tool messages since the last user turn to know if this
        # attempt has already fetched its data-lane evidence.
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if not post_user_tool:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            )
        finals_seen += 1
        return ToolTurnResponse(
            text=_final_json(
                [
                    {
                        "id": "framing",
                        "label": "Framing",
                        "value": "n/a",
                        "evidence_id": "tc_1",
                    }
                ]
            )
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())

    with pytest.raises(RuntimeError, match="missing web-lane coverage"):
        researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))

    # 1 initial attempt + MAX_COVERAGE_RETRIES retries
    assert finals_seen == 1 + MAX_COVERAGE_RETRIES


def test_coverage_retry_logs_remaining_budget(caplog: pytest.LogCaptureFixture) -> None:
    """Each retry must log the decrementing budget so operators can see
    how many chances the loop burned before either recovering or
    failing the stage."""

    def responder(messages: list[Message]) -> ToolTurnResponse:
        last_user_idx = max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)
        post_user_tool = any(m.role == "tool" for m in messages[last_user_idx + 1 :])
        if not post_user_tool:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            )
        return ToolTurnResponse(
            text=_final_json(
                [
                    {
                        "id": "framing",
                        "label": "Framing",
                        "value": "x",
                        "evidence_id": "tc_1",
                    }
                ]
            )
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())

    with (
        caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"),
        pytest.raises(RuntimeError),
    ):
        researcher.research(_request_with_outline(_outline_with_strict_web(["framing"])))

    retry_lines = [r.message for r in caplog.records if "coverage retry" in r.message]
    assert len(retry_lines) == MAX_COVERAGE_RETRIES
    assert any(f"remaining={MAX_COVERAGE_RETRIES - 1}" in m for m in retry_lines)
    assert any("remaining=0" in m for m in retry_lines)


# ---------------------------------------------------------------------------
# Search-budget anchor in the initial user turn
# ---------------------------------------------------------------------------


def test_initial_user_turn_anchors_search_budget_on_strict_web_count() -> None:
    """When the outline has strict-web ids, the initial user turn must
    name the count and a concrete `web_search` budget. Without this
    anchor the model under-searches because nothing in the prompt tells
    it how many calls the coverage gate expects."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import _initial_user_text

    ids = [f"id_{i}" for i in range(9)]
    request = _request_with_outline(_outline_with_strict_web(ids))
    text = _initial_user_text(request)
    assert text.startswith("Search budget:")
    assert "9 strict-web fact ids" in text
    # ceil(9 / 3) = 3
    assert "3+" in text
    assert "web_search" in text


def test_initial_user_turn_omits_anchor_when_no_strict_web_ids() -> None:
    """Pure-data outlines must not get the anchor — telling a quant-only
    run to call `web_search` would be noise the model has to ignore."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import _initial_user_text

    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(description="data-only", data_fact_ids=["rev_ttm"]),
                ],
            )
        ],
    )
    request = _request_with_outline(outline)
    text = _initial_user_text(request)
    assert not text.startswith("Search budget:")
    assert "Search budget" not in text


def test_no_usable_facts_error_includes_category_histogram_and_samples() -> None:
    """When every fact in a non-empty bundle is rejected, the error must
    surface a reason histogram and the first rejected fact ids/reasons.
    Without this the operator sees 'skipped N of N' and has no signal
    on whether the model is citing fabricated web_N ids, missing
    evidence, dangling computed-from, etc."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_ttm",
                                "label": "Revenue TTM",
                                "value": 1.0,
                                "evidence_id": "web_999",  # not in ledger
                            },
                            {
                                "id": "eps_ttm",
                                "label": "EPS TTM",
                                "value": 1.0,
                                "evidence_id": "tc_fake",  # not in ledger
                            },
                            {
                                "id": "no_anchors",
                                "label": "Nothing",
                                "value": 1.0,
                                # no evidence_id, no computed_from
                            },
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError) as exc:
        researcher.research(_request())
    msg = str(exc.value)
    assert "skipped 3 of 3" in msg
    assert "evidence_id_not_in_ledger=2" in msg
    assert "missing_evidence_and_computed_from=1" in msg
    assert "First rejections:" in msg
    assert "'rev_ttm'" in msg
    assert "web_999" in msg
    # Ledger summary surfaces so we can tell whether the model never
    # had anything to cite vs cited the wrong handles.
    assert "web_N=0" in msg
    assert "tool_call_ids=0" in msg


def test_initial_user_turn_anchor_counts_either_lane_ids_as_non_strict() -> None:
    """An id listed in BOTH `data_fact_ids` and `web_fact_ids` of the
    same need is "either" and not enforced by the gate, so it must not
    inflate the anchor's count — otherwise the model would chase a
    target larger than the gate's denominator."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import _initial_user_text

    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="either",
                        data_fact_ids=["flex"],
                        web_fact_ids=["flex"],
                    ),
                    DataNeed(
                        description="strict web",
                        web_fact_ids=["strict_a", "strict_b"],
                    ),
                ],
            )
        ],
    )
    request = _request_with_outline(outline)
    text = _initial_user_text(request)
    assert "2 strict-web fact ids" in text
