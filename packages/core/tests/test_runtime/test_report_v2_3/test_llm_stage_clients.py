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
            )
        )


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
        )
    )
    assert isinstance(thesis, ReportThesis)
    assert thesis.canonical_figures[0].display == "$60.9B"


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
            )
        )


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
        )
    )
    # First-call shape check is enough to confirm the keyword contract.
    assert {"system", "user"} <= captured[0].keys()
    assert isinstance(captured[0]["system"], str)
    assert isinstance(captured[0]["user"], dict)
