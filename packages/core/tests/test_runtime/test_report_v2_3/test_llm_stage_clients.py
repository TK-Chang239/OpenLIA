"""Tests for the five JSON-stage LLM clients (PLAN / COMPUTE / SYNTHESIZE
/ WRITE / VERIFY). The clients are thin: validate Pydantic, wrap errors.
Tests prove the prompt/payload shape stays stable and the validators do
not silently drop bad JSON.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from openlia.llm.runtime.report_v2_3.clients.compute import ComputeRequest
from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
    LLMComputeClient,
    LLMPlannerClient,
    LLMSynthesizerClient,
    LLMVerifierClient,
    LLMWriterClient,
)
from openlia.llm.runtime.report_v2_3.clients.planner import PlannerRequest
from openlia.llm.runtime.report_v2_3.clients.synthesizer import SynthesizerRequest
from openlia.llm.runtime.report_v2_3.clients.verifier import VerifierRequest
from openlia.llm.runtime.report_v2_3.clients.writer import WriterRequest
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ClarifyProceed,
    CompsInputs,
    DataNeed,
    DataProviderSource,
    DCFInputs,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    SensitivityInputs,
    ValuationMethod,
    ValuationPlan,
    VerifyResult,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.templates import (
    SectionSpec,
    TemplateSpec,
    get_builtin,
)


def _template() -> TemplateSpec:
    return get_builtin(ReportType.INITIATION)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=60.9, source=_src()),
            "peer_avgo_ev_ebitda": BundleFact(
                id="peer_avgo_ev_ebitda",
                label="AVGO EV/EBITDA",
                value=22.0,
                source=_src(),
            ),
            "subject_ebitda_ttm": BundleFact(
                id="subject_ebitda_ttm",
                label="NVDA EBITDA TTM",
                value=42.0,
                source=_src(),
            ),
            "net_debt": BundleFact(id="net_debt", label="Net debt", value=10.0, source=_src()),
            "shares_outstanding": BundleFact(
                id="shares_outstanding", label="Shares out", value=2500.0, source=_src()
            ),
        },
    )


def _outline() -> Outline:
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="business",
                title="Business",
                data_needs=[DataNeed(description="rev mix", expected_fact_ids=["rev_ttm"])],
            )
        ],
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
    )


def _thesis() -> ReportThesis:
    return ReportThesis(
        language=Language.EN,
        central_argument="DC growth dominates the story.",
        key_takeaways=["AI capex tailwind", "Margin expansion"],
        valuation_stance="Long; DCF supports current price.",
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$60.9B")],
        mandates=[
            SectionMandate(
                section_id="business",
                covers="business mix",
                does_not_cover="competition",
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=[],
    )


def _capturing_call(canned: dict[str, Any]) -> tuple[Any, list[dict[str, Any]]]:
    """Return (call_fn, captured_invocations). The call_fn returns ``canned``
    and records each invocation as ``{"system":..., "user":...}``."""
    captured: list[dict[str, Any]] = []

    def _call(*, system: str, user: Any) -> dict[str, Any]:
        captured.append({"system": system, "user": user})
        return canned

    return _call, captured


# ---------------------------------------------------------------------------
# PLAN
# ---------------------------------------------------------------------------


def test_plan_validates_outline_and_passes_user_payload() -> None:
    canned = {
        "tickers": ["NVDA"],
        "report_type": "initiation",
        "sections": [
            {
                "id": "business",
                "title": "Business",
                "data_needs": [{"description": "rev mix", "expected_fact_ids": ["rev_mix"]}],
            }
        ],
        "valuation_plan": {"methods": ["dcf"]},
    }
    call, captured = _capturing_call(canned)
    client = LLMPlannerClient(call)

    outline = client.plan(
        PlannerRequest(
            raw_prompt="initiate NVDA",
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
            template=_template(),
            clarify_result=ClarifyProceed(assumptions=["audience: PM"]),
        )
    )
    assert isinstance(outline, Outline)
    assert outline.sections[0].id == "business"
    assert outline.valuation_plan.methods == [ValuationMethod.DCF]
    # Payload carries language + clarify dump.
    user = captured[0]["user"]
    assert user["language"] == "en"
    assert user["clarify_result"]["outcome"] == "proceed"


def test_plan_wraps_validation_errors_with_fragment() -> None:
    canned = {"sections": "not a list"}  # malformed
    call, _ = _capturing_call(canned)
    client = LLMPlannerClient(call)
    with pytest.raises(RuntimeError, match="PLAN LLM returned malformed JSON"):
        client.plan(
            PlannerRequest(
                raw_prompt="x",
                language=Language.EN,
                report_type=ReportType.INITIATION,
                tickers=["NVDA"],
                template=_template(),
            )
        )


def test_plan_repairs_after_one_validation_failure() -> None:
    """When the first LLM response fails validation, the client should
    re-prompt with the validation errors and accept the second response.
    This is the headline cost-saver: most schema slip-ups are recoverable
    in one round-trip instead of nuking the whole report."""
    bad = {"sections": "not a list"}
    good = {
        "tickers": ["NVDA"],
        "report_type": "initiation",
        "sections": [
            {
                "id": "business",
                "title": "Business",
                "data_needs": [{"description": "rev mix", "expected_fact_ids": ["rev_mix"]}],
            }
        ],
        "valuation_plan": {"methods": ["dcf"]},
    }
    sequence = [bad, good]
    captured: list[dict[str, Any]] = []

    def _call(*, system: str, user: Any) -> dict[str, Any]:
        captured.append({"system": system, "user": user})
        return sequence.pop(0)

    client = LLMPlannerClient(_call)
    outline = client.plan(
        PlannerRequest(
            raw_prompt="x",
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
            template=_template(),
        )
    )
    assert isinstance(outline, Outline)
    assert len(captured) == 2
    # The second call carries the repair envelope with the prior raw + errors.
    repair_user = captured[1]["user"]
    assert "your_previous_output" in repair_user
    assert "validation_errors" in repair_user
    assert repair_user["your_previous_output"] == bad


# ---------------------------------------------------------------------------
# COMPUTE — method-dispatched validation
# ---------------------------------------------------------------------------


def test_compute_dcf_returns_dcf_inputs() -> None:
    canned = {
        "revenue_base_fact_id": "rev_ttm",
        "revenue_growth_path": [0.15, 0.10, 0.07],
        "margin_path": [0.35, 0.36, 0.37],
        "wacc": 0.10,
        "terminal_growth": 0.025,
        "tax_rate": 0.21,
        "grounding_fact_ids": ["net_debt", "shares_outstanding"],
    }
    call, captured = _capturing_call(canned)
    client = LLMComputeClient(call)
    result = client.propose_inputs(
        ComputeRequest(
            method=ValuationMethod.DCF,
            raw_prompt="value NVDA",
            language=Language.EN,
            bundle=_bundle(),
            outline=_outline(),
        )
    )
    assert isinstance(result, DCFInputs)
    assert result.revenue_growth_path == [0.15, 0.10, 0.07]
    # Method is forwarded so the prompt can specialize.
    assert captured[0]["user"]["method"] == "dcf"


def test_compute_comps_returns_comps_inputs() -> None:
    canned = {
        "subject_ticker": "NVDA",
        "peers": [{"ticker": "AVGO", "metric_fact_ids": {"ev_ebitda": "peer_avgo_ev_ebitda"}}],
        "multiples": ["ev_ebitda"],
        "subject_metric_fact_ids": {"ev_ebitda": "subject_ebitda_ttm"},
    }
    call, _ = _capturing_call(canned)
    client = LLMComputeClient(call)
    result = client.propose_inputs(
        ComputeRequest(
            method=ValuationMethod.COMPS,
            raw_prompt="comps",
            language=Language.EN,
            bundle=_bundle(),
            outline=_outline(),
        )
    )
    assert isinstance(result, CompsInputs)
    assert result.subject_ticker == "NVDA"


def test_compute_sensitivity_returns_sensitivity_inputs() -> None:
    canned = {
        "base": {
            "revenue_base_fact_id": "rev_ttm",
            "revenue_growth_path": [0.1, 0.1],
            "margin_path": [0.35, 0.35],
            "wacc": 0.10,
            "terminal_growth": 0.025,
            "tax_rate": 0.21,
            "grounding_fact_ids": ["net_debt"],
        },
        "row_driver": "wacc",
        "col_driver": "terminal_growth",
        "row_values": [0.08, 0.09, 0.10],
        "col_values": [0.02, 0.025, 0.03],
    }
    call, _ = _capturing_call(canned)
    client = LLMComputeClient(call)
    result = client.propose_inputs(
        ComputeRequest(
            method=ValuationMethod.SENSITIVITY,
            raw_prompt="x",
            language=Language.EN,
            bundle=_bundle(),
            outline=_outline(),
        )
    )
    assert isinstance(result, SensitivityInputs)
    assert result.row_driver == "wacc"


def test_compute_dcf_rejects_misaligned_paths() -> None:
    canned = {
        "revenue_base_fact_id": "rev_ttm",
        "revenue_growth_path": [0.15, 0.10],
        "margin_path": [0.35, 0.36, 0.37],  # length mismatch
        "wacc": 0.10,
        "terminal_growth": 0.025,
        "tax_rate": 0.21,
        "grounding_fact_ids": [],
    }
    call, _ = _capturing_call(canned)
    client = LLMComputeClient(call)
    with pytest.raises(RuntimeError, match="COMPUTE/dcf"):
        client.propose_inputs(
            ComputeRequest(
                method=ValuationMethod.DCF,
                raw_prompt="x",
                language=Language.EN,
                bundle=_bundle(),
                outline=_outline(),
            )
        )


# ---------------------------------------------------------------------------
# SYNTHESIZE
# ---------------------------------------------------------------------------


def test_synthesize_returns_thesis() -> None:
    canned = {
        "language": "en",
        "central_argument": "DC dominates.",
        "key_takeaways": ["one", "two"],
        "valuation_stance": "Long.",
        "valuation_plan": {"methods": ["dcf"]},
        "canonical_figures": [{"fact_id": "rev_ttm", "display": "$60.9B"}],
        "mandates": [
            {
                "section_id": "business",
                "covers": "biz",
                "does_not_cover": "competition",
                "relevant_fact_ids": ["rev_ttm"],
            }
        ],
        "charts": [],
    }
    call, _ = _capturing_call(canned)
    client = LLMSynthesizerClient(call)
    thesis = client.synthesize(
        SynthesizerRequest(
            raw_prompt="x",
            language=Language.EN,
            bundle=_bundle(),
            outline=_outline(),
            template=_template(),
        )
    )
    assert isinstance(thesis, ReportThesis)
    assert thesis.canonical_figures[0].display == "$60.9B"


def test_synthesize_repairs_chart_with_mixed_units() -> None:
    """When SYNTHESIZE plots facts with mismatched units in one series
    (e.g. USD_millions next to bare USD), the post_validator flags it
    and the repair loop re-prompts. Without this, the chart's y-axis
    becomes meaningless — one bar represents billions, others read as
    flat zeros."""
    # Two facts whose values are close numerically but have different
    # units — the visual disaster scenario.
    bundle = ResearchBundle(
        tickers=["NBIS"],
        facts={
            "dcf_ev": BundleFact(
                id="dcf_ev",
                label="DCF EV",
                value=38000.0,
                unit="USD_millions",
                source=_src(),
            ),
            "comps_target": BundleFact(
                id="comps_target",
                label="Comps target",
                value=3886.0,
                unit="USD",
                source=_src(),
            ),
            "third_target": BundleFact(
                id="third_target",
                label="P/E target",
                value=6800.0,
                unit="USD",
                source=_src(),
            ),
        },
    )
    base = {
        "language": "en",
        "central_argument": "x",
        "key_takeaways": [],
        "valuation_stance": "x",
        "canonical_figures": [],
        "mandates": [
            {
                "section_id": "business",
                "covers": "x",
                "does_not_cover": "y",
                "chart_ids": ["bridge"],
                "relevant_fact_ids": ["dcf_ev", "comps_target", "third_target"],
            }
        ],
    }
    bad_chart = {
        "id": "bridge",
        "section_id": "business",
        "claim": "valuation dispersion is wide",
        "chart_type": "column",
        "title": "Valuation cross-check",
        "category_labels": ["DCF", "Comps", "P/E"],
        "series": [
            {
                "name": "Implied",
                "value_fact_ids": ["dcf_ev", "comps_target", "third_target"],
            }
        ],
    }
    # On retry the model drops the chart entirely (right answer when
    # units cannot be reconciled).
    sequence = [
        {**base, "charts": [bad_chart]},
        {**base, "charts": [], "mandates": [{**base["mandates"][0], "chart_ids": []}]},
    ]
    captured: list[dict[str, Any]] = []

    def _call(*, system: str, user: Any) -> dict[str, Any]:
        captured.append({"system": system, "user": user})
        return sequence.pop(0)

    client = LLMSynthesizerClient(_call)
    thesis = client.synthesize(
        SynthesizerRequest(
            raw_prompt="x",
            language=Language.EN,
            bundle=bundle,
            outline=_outline(),
            template=_template(),
        )
    )
    assert thesis.charts == []
    assert len(captured) == 2
    errs = captured[1]["user"]["validation_errors"]
    assert any("mixes unit types" in str(e) for e in errs)


def test_synthesize_repairs_chart_with_phantom_fact_id() -> None:
    """When SYNTHESIZE emits a chart whose series fact_ids don't exist
    in the bundle, the post_validator should flag them and the repair
    loop should re-prompt the LLM with a structured error so it can
    use real fact_ids on the retry.

    This is the failure mode that was shipping reports with zero charts:
    LLM invents ids like ``chart_rev_2022``, silent strip drops the
    whole chart, repair loop never fires because Pydantic accepted the
    JSON shape."""
    base = {
        "language": "en",
        "central_argument": "x",
        "key_takeaways": [],
        "valuation_stance": "x",
        "canonical_figures": [],
        "mandates": [
            {
                "section_id": "business",
                "covers": "x",
                "does_not_cover": "y",
                "chart_ids": ["rev_chart"],
                "relevant_fact_ids": ["rev_ttm"],
            }
        ],
    }
    bad_chart = {
        "id": "rev_chart",
        "section_id": "business",
        "claim": "x",
        "chart_type": "column",
        "title": "Revenue",
        "category_labels": ["a", "b", "c"],
        "series": [
            # All three references are invented; bundle only has rev_ttm.
            {"name": "s", "value_fact_ids": ["chart_rev_2022", "chart_rev_2023", "chart_rev_2024"]}
        ],
    }
    good_chart = {
        "id": "rev_chart",
        "section_id": "business",
        "claim": "x",
        "chart_type": "column",
        "title": "Revenue",
        "category_labels": ["a", "b", "c"],
        # Three real refs (broadcasting rev_ttm; the test bundle only
        # has one fact so the LLM realistically would have dropped the
        # chart, but here we just want to prove the repair fired).
        "series": [{"name": "s", "value_fact_ids": ["rev_ttm", "rev_ttm", "rev_ttm"]}],
    }
    sequence = [
        {**base, "charts": [bad_chart]},
        {**base, "charts": [good_chart]},
    ]
    captured: list[dict[str, Any]] = []

    def _call(*, system: str, user: Any) -> dict[str, Any]:
        captured.append({"system": system, "user": user})
        return sequence.pop(0)

    client = LLMSynthesizerClient(_call)
    thesis = client.synthesize(
        SynthesizerRequest(
            raw_prompt="x",
            language=Language.EN,
            bundle=_bundle(),
            outline=_outline(),
            template=_template(),
        )
    )
    assert len(thesis.charts) == 1
    assert thesis.charts[0].series[0].value_fact_ids == ["rev_ttm", "rev_ttm", "rev_ttm"]
    # Verify the repair envelope carried a complaint about the phantom ids.
    assert len(captured) == 2
    repair_user = captured[1]["user"]
    errs = repair_user["validation_errors"]
    assert any("chart_rev_2022" in str(e) for e in errs)


def test_synthesize_rejects_chart_for_unknown_section() -> None:
    canned = {
        "language": "en",
        "central_argument": "x",
        "key_takeaways": [],
        "valuation_stance": "x",
        "canonical_figures": [],
        "mandates": [
            {
                "section_id": "business",
                "covers": "x",
                "does_not_cover": "y",
                "relevant_fact_ids": [],
            }
        ],
        "charts": [
            {
                "id": "c1",
                "section_id": "ghost",  # not in mandates
                "claim": "x",
                "chart_type": "column",
                "title": "t",
                "category_labels": ["a"],
                "series": [{"name": "s", "value_fact_ids": ["rev_ttm"]}],
            }
        ],
    }
    call, _ = _capturing_call(canned)
    client = LLMSynthesizerClient(call)
    with pytest.raises(RuntimeError, match="SYNTHESIZE"):
        client.synthesize(
            SynthesizerRequest(
                raw_prompt="x",
                language=Language.EN,
                bundle=_bundle(),
                outline=_outline(),
                template=_template(),
            )
        )


def test_synthesize_payload_includes_template_section_intents():
    """The synthesizer payload must surface each template section's
    intent so the LLM can write mandate.covers text grounded in the
    user's intent."""
    import json

    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        _synthesize_payload,
    )
    from openlia.llm.runtime.report_v2_3.clients.synthesizer import (
        SynthesizerRequest,
    )
    from openlia.llm.runtime.report_v2_3.schemas import (
        Language,
        Outline,
        OutlineSection,
        ReportType,
        ResearchBundle,
        ValuationPlan,
    )
    from openlia.llm.runtime.report_v2_3.templates import (
        SectionSpec,
        TemplateSpec,
    )

    template = TemplateSpec(
        template_id="t",
        name="T",
        shape_description="...",
        sections=[
            SectionSpec(id="alpha", title="Alpha", intent="UNIQUE_ALPHA_INTENT"),
            SectionSpec(id="beta", title="Beta", intent="UNIQUE_BETA_INTENT"),
        ],
    )
    request = SynthesizerRequest(
        raw_prompt="initiate",
        language=Language.EN,
        bundle=ResearchBundle(tickers=["NVDA"], facts={}),
        outline=Outline(
            tickers=["NVDA"],
            report_type=ReportType.INITIATION,
            sections=[
                OutlineSection(id="alpha", title="Alpha"),
                OutlineSection(id="beta", title="Beta"),
            ],
            valuation_plan=ValuationPlan(),
        ),
        template=template,
    )
    payload = _synthesize_payload(request)

    serialized = json.dumps(payload)
    assert "UNIQUE_ALPHA_INTENT" in serialized
    assert "UNIQUE_BETA_INTENT" in serialized


def test_synthesize_system_prompt_references_template_intent():
    """The SYNTHESIZE_SYSTEM_PROMPT must instruct the LLM to use the
    template's section intent when authoring mandate.covers."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        SYNTHESIZE_SYSTEM_PROMPT,
    )

    assert "template" in SYNTHESIZE_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# WRITE
# ---------------------------------------------------------------------------


def test_write_returns_section() -> None:
    canned = {
        "section_id": "business",
        "title": "Business",
        "body": "Revenue is {{CITE:rev_ttm}}.",
    }
    call, captured = _capturing_call(canned)
    client = LLMWriterClient(call)

    section = client.write(
        WriterRequest(
            section_mandate=_thesis().mandates[0],
            thesis=_thesis(),
            template=_template(),
            language=Language.EN,
            relevant_facts={"rev_ttm": _bundle().facts["rev_ttm"]},
            assigned_charts=[],
        )
    )
    assert isinstance(section, WrittenSection)
    assert section.cited_fact_ids() == ["rev_ttm"]
    # No prior attempt is forwarded as None.
    assert captured[0]["user"]["prior_attempt"] is None


def test_write_forwards_prior_attempt_and_critique_on_retry() -> None:
    from openlia.llm.runtime.report_v2_3.schemas import (
        IssueKind,
        IssueSeverity,
        VerifyIssue,
    )

    prior = WrittenSection(
        section_id="business",
        title="Business",
        body="Old draft.",
    )
    critique = [
        VerifyIssue(
            section_id="business",
            kind=IssueKind.VALUE_MISMATCH,
            severity=IssueSeverity.HIGH,
            detail="Numbers wrong.",
        )
    ]
    canned = {
        "section_id": "business",
        "title": "Business",
        "body": "Better draft {{CITE:rev_ttm}}.",
    }
    call, captured = _capturing_call(canned)
    client = LLMWriterClient(call)
    client.write(
        WriterRequest(
            section_mandate=_thesis().mandates[0],
            thesis=_thesis(),
            template=_template(),
            language=Language.EN,
            relevant_facts={"rev_ttm": _bundle().facts["rev_ttm"]},
            assigned_charts=[],
            prior_attempt=prior,
            critique=critique,
        )
    )
    user = captured[0]["user"]
    assert user["prior_attempt"]["body"] == "Old draft."
    assert user["critique"][0]["kind"] == IssueKind.VALUE_MISMATCH


def test_write_payload_includes_template_section_intent():
    """The writer payload must surface the matching template section's
    intent so the LLM knows the user's intent for this section."""
    import json

    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        _write_payload,
    )

    template = TemplateSpec(
        template_id="t",
        name="T",
        shape_description="...",
        sections=[
            SectionSpec(id="business", title="Business", intent="UNIQUE_BUSINESS_INTENT"),
            SectionSpec(id="other", title="Other", intent="UNIQUE_OTHER_INTENT"),
        ],
    )
    request = WriterRequest(
        section_mandate=_thesis().mandates[0],  # section_id = "business"
        thesis=_thesis(),
        template=template,
        language=Language.EN,
        relevant_facts={"rev_ttm": _bundle().facts["rev_ttm"]},
        assigned_charts=[],
    )
    payload = _write_payload(request)

    assert payload["section_intent"] == "UNIQUE_BUSINESS_INTENT"
    serialized = json.dumps(payload)
    assert "UNIQUE_BUSINESS_INTENT" in serialized
    # The non-matching section's intent should not bleed in.
    assert "UNIQUE_OTHER_INTENT" not in serialized


def test_write_system_prompt_references_section_intent():
    """The WRITE_SYSTEM_PROMPT must instruct the writer to consume the
    template section's intent when shaping prose."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        WRITE_SYSTEM_PROMPT,
    )

    assert "intent" in WRITE_SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# VERIFY
# ---------------------------------------------------------------------------


def test_verify_returns_empty_when_clean() -> None:
    canned = {"issues": []}
    call, _ = _capturing_call(canned)
    client = LLMVerifierClient(call)
    result = client.verify(
        VerifierRequest(
            raw_prompt="x",
            language=Language.EN,
            thesis=_thesis(),
            bundle=_bundle(),
            sections=[],
        )
    )
    assert isinstance(result, VerifyResult)
    assert result.issues == []
    assert result.must_rewrite is False


def test_verify_must_rewrite_when_high_severity() -> None:
    canned = {
        "issues": [
            {
                "section_id": "valuation",
                "kind": "value_mismatch",
                "severity": "high",
                "detail": "x",
            }
        ]
    }
    call, _ = _capturing_call(canned)
    client = LLMVerifierClient(call)
    result = client.verify(
        VerifierRequest(
            raw_prompt="x",
            language=Language.EN,
            thesis=_thesis(),
            bundle=_bundle(),
            sections=[],
        )
    )
    assert result.must_rewrite is True


# ---------------------------------------------------------------------------
# Smoke — every client uses the same JsonCall keyword shape
# ---------------------------------------------------------------------------


def test_all_clients_call_json_with_system_and_user_keywords() -> None:
    canned_outline = {
        "tickers": ["NVDA"],
        "report_type": "initiation",
        "sections": [
            {
                "id": "b",
                "title": "B",
                "data_needs": [{"description": "x", "expected_fact_ids": []}],
            }
        ],
        "valuation_plan": {"methods": []},
    }
    call, captured = _capturing_call(canned_outline)
    LLMPlannerClient(call).plan(
        PlannerRequest(
            raw_prompt="x",
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
            template=_template(),
        )
    )
    # First-call shape check is enough to confirm the keyword contract.
    assert {"system", "user"} <= captured[0].keys()
    assert isinstance(captured[0]["system"], str)
    assert isinstance(captured[0]["user"], dict)


# ---------------------------------------------------------------------------
# PLAN — template-driven prompt (Task 6 of Phase 1)
# ---------------------------------------------------------------------------


def test_plan_system_prompt_no_longer_dictates_section_count():
    """The '4-8 sections is the usual band' guidance must be gone —
    section count is now the template's job, not a prompt opinion."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        PLAN_SYSTEM_PROMPT,
    )

    assert "4-8" not in PLAN_SYSTEM_PROMPT
    assert "usual band" not in PLAN_SYSTEM_PROMPT


def test_plan_prompt_shape_round_trips_through_llm_planner_client():
    """Guard against the silent-drop bug: the prompt's example JSON
    shape must survive Pydantic validation with fact_ids intact. If
    the prompt teaches one shape and the schema expects another, real
    LLM output loses fact_ids — Pydantic's default 'ignore extras'
    behavior drops them quietly."""
    # The literal JSON the prompt instructs the LLM to emit.
    llm_emitted_json = {
        "tickers": ["NVDA"],
        "report_type": "initiation",
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "data_needs": [
                    {
                        "description": "Recent revenue and segment mix",
                        "expected_fact_ids": ["rev_ttm", "segment_mix"],
                    }
                ],
            }
        ],
        "valuation_plan": {"methods": ["dcf"]},
    }
    call, _ = _capturing_call(llm_emitted_json)
    template = TemplateSpec(
        template_id="t",
        name="T",
        shape_description="...",
        sections=[
            SectionSpec(id="overview", title="Overview", intent="A."),
        ],
    )
    client = LLMPlannerClient(call)
    outline = client.plan(
        PlannerRequest(
            raw_prompt="initiate",
            language=Language.EN,
            report_type=ReportType.INITIATION,
            tickers=["NVDA"],
            template=template,
        )
    )

    assert len(outline.sections) == 1
    section = outline.sections[0]
    assert section.id == "overview"
    assert len(section.data_needs) == 1
    assert section.data_needs[0].expected_fact_ids == ["rev_ttm", "segment_mix"]
    assert section.data_needs[0].description == "Recent revenue and segment mix"


def test_plan_payload_includes_template_sections():
    """The PLAN request payload sent to the LLM must include the
    template's section list so the LLM knows what to fill in."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        _planner_payload,
    )
    from openlia.llm.runtime.report_v2_3.clients.planner import PlannerRequest

    template = TemplateSpec(
        template_id="t",
        name="T",
        shape_description="...",
        sections=[
            SectionSpec(id="alpha", title="Alpha", intent="A."),
            SectionSpec(id="beta", title="Beta", intent="B."),
        ],
    )
    req = PlannerRequest(
        raw_prompt="initiate",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=template,
    )
    payload = _planner_payload(req)
    assert "template" in payload
    assert [s["id"] for s in payload["template"]["sections"]] == ["alpha", "beta"]
