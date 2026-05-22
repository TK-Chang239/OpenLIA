"""Tests for PR 4.2: pdfplumber + 7 LLM-orchestrated NLP helpers.

Covers:
  - Registration of all 8 helpers
  - pdf_ingest: known fixture PDF yields expected text on page 1
  - transcript_tone_analysis: mocked LLM returns canned classification
  - mda_extraction: mocked LLM with sample MD&A returns expected structure
  - guidance_tracker: pure-Python beat/miss logic (no LLM needed)
  - All 7 LLM-backed helpers handle llm_provider=None by attempting to load default
    (asserts the import path exists, not actual provider load — avoids env coupling)
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_FIXTURES = Path(__file__).parent / "fixtures"
_SAMPLE_PDF = _FIXTURES / "sample.pdf"

# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------

NLP_HELPERS = [
    "pdf_ingest",
    "transcript_tone_analysis",
    "tone_shift_qoq",
    "mda_extraction",
    "risk_factors_extraction",
    "forward_looking_statements",
    "guidance_tracker",
    "customer_concentration_extraction",
]


@pytest.mark.parametrize("name", NLP_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


@pytest.mark.parametrize("name", NLP_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) >= 1


@pytest.mark.parametrize("name", NLP_HELPERS)
def test_helper_no_skill_doc(name: str) -> None:
    """None of the 8 NLP helpers are on the complex-skill list; no skill doc expected."""
    helper = get_helper(name)
    assert helper is not None
    assert helper.schema.skill_doc is None


# ---------------------------------------------------------------------------
# pdf_ingest — fixture-based (no LLM)
# ---------------------------------------------------------------------------


def test_pdf_ingest_from_path() -> None:
    result = get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF)
    assert result["metadata"]["page_count"] == 1
    assert len(result["pages"]) == 1
    page = result["pages"][0]
    assert page["page_number"] == 1
    assert "Hello from page one." in page["text"]


def test_pdf_ingest_from_bytes() -> None:
    raw = _SAMPLE_PDF.read_bytes()
    result = get_helper("pdf_ingest").impl(pdf_bytes=raw)
    assert result["metadata"]["page_count"] == 1
    assert "Hello from page one." in result["pages"][0]["text"]


def test_pdf_ingest_page_filter() -> None:
    result = get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF, pages=[1])
    assert len(result["pages"]) == 1


def test_pdf_ingest_invalid_page() -> None:
    with pytest.raises(ValueError, match="out of range"):
        get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF, pages=[99])


def test_pdf_ingest_requires_one_source() -> None:
    with pytest.raises(ValueError):
        get_helper("pdf_ingest").impl()
    with pytest.raises(ValueError):
        get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF, pdf_bytes=_SAMPLE_PDF.read_bytes())


def test_pdf_ingest_metadata_fields() -> None:
    result = get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF)
    meta = result["metadata"]
    assert "sha256" in meta
    assert "file_size_bytes" in meta
    assert "extraction_quality" in meta
    assert meta["file_size_bytes"] > 0
    assert len(meta["sha256"]) == 64


def test_pdf_ingest_no_tables_flag() -> None:
    result = get_helper("pdf_ingest").impl(pdf_path=_SAMPLE_PDF, extract_tables=False)
    assert "tables" not in result


# ---------------------------------------------------------------------------
# transcript_tone_analysis — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_TONE = {
    "speakers": [
        {
            "name": "CEO Jane Doe",
            "role": "management",
            "tone": "confident",
            "evidence_quotes": ["We delivered record revenue."],
            "hedging_language_count": 1,
            "forward_looking_count": 3,
        }
    ],
    "prepared_remarks_tone": "confident",
    "qa_tone": "slightly cautious",
    "prepared_vs_qa_tone_differential": "QA more cautious than prepared remarks",
    "hedging_language_themes": ["macroeconomic conditions"],
    "extraction_quality": "high",
}


def _make_mock_provider(json_payload: dict) -> MagicMock:
    response = MagicMock()
    response.text = json.dumps(json_payload)
    provider = MagicMock()
    provider.generate = AsyncMock(return_value=response)
    return provider


def test_transcript_tone_analysis_mocked() -> None:
    provider = _make_mock_provider(_CANNED_TONE)
    result = get_helper("transcript_tone_analysis").impl(
        transcript_text="CEO: We delivered record revenue. Analyst: What is Q2 outlook?",
        llm_provider=provider,
    )
    assert result["prepared_remarks_tone"] == "confident"
    assert len(result["speakers"]) == 1
    assert result["speakers"][0]["tone"] == "confident"
    assert result["extraction_quality"] == "high"


def test_transcript_tone_analysis_empty_raises() -> None:
    provider = _make_mock_provider(_CANNED_TONE)
    with pytest.raises(ValueError, match="empty"):
        get_helper("transcript_tone_analysis").impl(transcript_text="   ", llm_provider=provider)


def test_transcript_tone_analysis_default_provider_import_path() -> None:
    """Assert the default provider import path exists in the module source."""
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import (
        transcript_tone_analysis as mod,
    )

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src


# ---------------------------------------------------------------------------
# tone_shift_qoq — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_SHIFT = {
    "current_quarter": "Q1 FY26",
    "prior_quarter": "Q4 FY25",
    "overall_tone_shift": "more cautious",
    "key_shifts": [],
    "hedging_language_change_pct": 0.20,
    "narrative": "CEO struck a more cautious tone.",
}


def test_tone_shift_qoq_mocked() -> None:
    provider = _make_mock_provider(_CANNED_SHIFT)
    result = get_helper("tone_shift_qoq").impl(
        current_text="Q1 call text here.",
        prior_text="Q4 call text here.",
        current_quarter="Q1 FY26",
        prior_quarter="Q4 FY25",
        llm_provider=provider,
    )
    assert result["overall_tone_shift"] == "more cautious"
    assert result["hedging_language_change_pct"] == 0.20


def test_tone_shift_qoq_empty_raises() -> None:
    provider = _make_mock_provider(_CANNED_SHIFT)
    with pytest.raises(ValueError, match="empty"):
        get_helper("tone_shift_qoq").impl(
            current_text="text", prior_text="  ", llm_provider=provider
        )


def test_tone_shift_qoq_default_provider_import_path() -> None:
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import tone_shift_qoq as mod

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src


# ---------------------------------------------------------------------------
# mda_extraction — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_MDA = {
    "company": "Acme Corp",
    "period": "Q3 FY25",
    "key_drivers_mentioned": [
        {
            "driver": "Cloud services growth",
            "direction": "positive",
            "evidence_quote": "Cloud grew 32% YoY.",
        }
    ],
    "key_headwinds_mentioned": [
        {"headwind": "FX impact", "magnitude_quote": "$50M headwind", "estimated_impact": "$50M"}
    ],
    "management_outlook_statements": ["We expect Q4 revenue of $1.2B."],
    "non_gaap_reconciliation_mentions": ["See non-GAAP table on page 12."],
    "segment_commentary": [
        {"segment": "Cloud", "growth_rate_disclosed": 0.32, "narrative": "Strong adoption."}
    ],
}


def test_mda_extraction_mocked() -> None:
    provider = _make_mock_provider(_CANNED_MDA)
    result = get_helper("mda_extraction").impl(
        mda_text="Cloud grew 32% YoY. FX impact $50M. We expect Q4 revenue of $1.2B.",
        company="Acme Corp",
        period="Q3 FY25",
        llm_provider=provider,
    )
    assert result["company"] == "Acme Corp"
    assert len(result["key_drivers_mentioned"]) == 1
    assert result["key_drivers_mentioned"][0]["direction"] == "positive"
    assert len(result["management_outlook_statements"]) == 1
    assert result["segment_commentary"][0]["growth_rate_disclosed"] == 0.32


def test_mda_extraction_empty_raises() -> None:
    provider = _make_mock_provider(_CANNED_MDA)
    with pytest.raises(ValueError, match="empty"):
        get_helper("mda_extraction").impl(mda_text="", llm_provider=provider)


def test_mda_extraction_default_provider_import_path() -> None:
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import mda_extraction as mod

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src


# ---------------------------------------------------------------------------
# risk_factors_extraction — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_RISKS = {
    "total_risk_count": 2,
    "risks": [
        {
            "title": "Advertising revenue dependence",
            "category": "operational",
            "text_excerpt": "We depend on advertising for 85% of revenue.",
            "first_appeared_year": None,
            "language_changed_from_prior_year": False,
            "language_change_summary": None,
        },
        {
            "title": "Regulatory risk",
            "category": "regulatory",
            "text_excerpt": "GDPR compliance costs may increase.",
            "first_appeared_year": None,
            "language_changed_from_prior_year": True,
            "language_change_summary": "Added GDPR specificity.",
        },
    ],
    "categories_breakdown": {
        "operational": 1,
        "financial": 0,
        "governance": 0,
        "macro": 0,
        "regulatory": 1,
        "competitive": 0,
    },
    "new_risks_this_year": [],
    "removed_risks_from_prior_year": [],
}


def test_risk_factors_extraction_mocked() -> None:
    provider = _make_mock_provider(_CANNED_RISKS)
    result = get_helper("risk_factors_extraction").impl(
        risk_text=(
            "We depend on advertising for 85% of revenue. GDPR compliance costs may increase."
        ),
        llm_provider=provider,
    )
    assert result["total_risk_count"] == 2
    assert result["categories_breakdown"]["operational"] == 1
    assert result["categories_breakdown"]["regulatory"] == 1


def test_risk_factors_extraction_default_provider_import_path() -> None:
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import (
        risk_factors_extraction as mod,
    )

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src


# ---------------------------------------------------------------------------
# forward_looking_statements — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_FLS = {
    "source": "earnings_call",
    "statements": [
        {
            "text": "We expect Q2 revenue to be in the range of $1.2B to $1.25B.",
            "category": "guidance",
            "confidence_indicator": "high",
            "qualifiers": ["expect"],
            "time_horizon": "Q2 FY26",
            "metric": "revenue",
            "value_range": [1200000000, 1250000000],
        }
    ],
}


def test_forward_looking_statements_mocked() -> None:
    provider = _make_mock_provider(_CANNED_FLS)
    result = get_helper("forward_looking_statements").impl(
        text="We expect Q2 revenue to be in the range of $1.2B to $1.25B.",
        source="earnings_call",
        llm_provider=provider,
    )
    assert result["source"] == "earnings_call"
    assert len(result["statements"]) == 1
    assert result["statements"][0]["category"] == "guidance"
    assert result["statements"][0]["confidence_indicator"] == "high"


def test_forward_looking_statements_invalid_source() -> None:
    provider = _make_mock_provider(_CANNED_FLS)
    with pytest.raises(ValueError, match="source must be one of"):
        get_helper("forward_looking_statements").impl(
            text="some text", source="invalid_source", llm_provider=provider
        )


def test_forward_looking_statements_default_provider_import_path() -> None:
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import (
        forward_looking_statements as mod,
    )

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src


# ---------------------------------------------------------------------------
# guidance_tracker — pure Python (no LLM)
# ---------------------------------------------------------------------------

_SAMPLE_RECORDS = [
    {
        "guidance_quarter": "Q4 FY24",
        "guidance_for_period": "Q1 FY25",
        "guidance_issued": {"revenue_low": 1100, "revenue_high": 1150},
        "actual_results": {"revenue": 1130},
    },
    {
        "guidance_quarter": "Q1 FY25",
        "guidance_for_period": "Q2 FY25",
        "guidance_issued": {"revenue_low": 1150, "revenue_high": 1200},
        "actual_results": {"revenue": 1080},
    },
    {
        "guidance_quarter": "Q2 FY25",
        "guidance_for_period": "Q3 FY25",
        "guidance_issued": {"revenue_low": 1200, "revenue_high": 1250},
        "actual_results": {"revenue": 1400},  # beat_large: > 1250 by > 5%
    },
    {
        "guidance_quarter": "Q3 FY25",
        "guidance_for_period": "Q4 FY25",
        "guidance_issued": {"revenue_low": 1300, "revenue_high": 1350},
        "actual_results": {"revenue": 1360},  # beat_modest: > 1350 by < 5%
    },
]


def test_guidance_tracker_verdicts() -> None:
    result = get_helper("guidance_tracker").impl(guidance_records=_SAMPLE_RECORDS)
    assert result["quarters_analyzed"] == 4
    track = result["guidance_track_record"]
    assert track[0]["verdict"] == "within_range"  # 1130 in [1100, 1150]
    assert track[1]["verdict"] == "miss"  # 1080 < 1150
    assert track[2]["verdict"] == "beat_large"  # 1400 > 1250 by > 5%
    assert track[3]["verdict"] == "beat_modest"  # 1360 > 1350 by < 5%


def test_guidance_tracker_summary_rates() -> None:
    result = get_helper("guidance_tracker").impl(guidance_records=_SAMPLE_RECORDS)
    summary = result["summary"]
    # beat_count = 3 (within_range=1, beat_modest=1, beat_large=1), miss=1
    assert summary["miss_rate"] == 0.25
    assert summary["within_range_rate"] == 0.25
    assert summary["beat_rate"] == 0.5


def test_guidance_tracker_accuracy_heuristic() -> None:
    result = get_helper("guidance_tracker").impl(guidance_records=_SAMPLE_RECORDS)
    # within_range(1.0) + miss(0.0) + beat_large(0.7) + beat_modest(1.0) = 2.7 / 4 = 0.675
    assert abs(result["summary"]["guidance_accuracy_heuristic"] - 0.675) < 0.001


def test_guidance_tracker_custom_weights() -> None:
    result = get_helper("guidance_tracker").impl(
        guidance_records=_SAMPLE_RECORDS,
        accuracy_weights={"within_range": 1.0, "beat_modest": 1.0, "beat_large": 1.0, "miss": 0.0},
    )
    # With equal beat weights: (1+0+1+1)/4 = 0.75
    assert abs(result["summary"]["guidance_accuracy_heuristic"] - 0.75) < 0.001


def test_guidance_tracker_empty_records_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        get_helper("guidance_tracker").impl(guidance_records=[])


def test_guidance_tracker_missing_key_raises() -> None:
    with pytest.raises(ValueError, match="missing required key"):
        get_helper("guidance_tracker").impl(guidance_records=[{"guidance_quarter": "Q1"}])


def test_guidance_tracker_with_eps() -> None:
    records = [
        {
            "guidance_quarter": "Q4 FY24",
            "guidance_for_period": "Q1 FY25",
            "guidance_issued": {
                "revenue_low": 1100,
                "revenue_high": 1150,
                "eps_low": 1.40,
                "eps_high": 1.45,
            },
            "actual_results": {"revenue": 1130, "eps": 1.48},
        }
    ]
    result = get_helper("guidance_tracker").impl(guidance_records=records)
    entry = result["guidance_track_record"][0]
    assert entry["verdict"] == "within_range"
    assert entry["eps_verdict"] == "beat_modest"  # 1.48 > 1.45 by ~2%


# ---------------------------------------------------------------------------
# customer_concentration_extraction — mocked LLM
# ---------------------------------------------------------------------------

_CANNED_CONC = {
    "disclosed": True,
    "top_customer_pct_of_revenue": 0.18,
    "top_3_customers_pct": 0.35,
    "top_10_customers_pct": 0.60,
    "named_customers": ["Customer A"],
    "geographic_concentration_pct_by_region": {"Americas": 0.55},
    "industry_concentration_pct_by_industry": {"financial_services": 0.30},
    "source_quote": "Customer A represented 18% of revenue.",
    "risk_framing": "moderate",
}


def test_customer_concentration_extraction_mocked() -> None:
    provider = _make_mock_provider(_CANNED_CONC)
    result = get_helper("customer_concentration_extraction").impl(
        text="Customer A represented 18% of revenue.",
        llm_provider=provider,
    )
    # top_customer_pct = 0.18 > 0.10 OR top_3 = 0.35 > 0.30 => risk_framing overridden to "high"
    assert result["risk_framing"] == "high"
    assert result["top_customer_pct_of_revenue"] == 0.18


def test_customer_concentration_risk_framing_low() -> None:
    canned = {
        **_CANNED_CONC,
        "top_customer_pct_of_revenue": 0.03,
        "top_3_customers_pct": 0.08,
        "risk_framing": "high",  # LLM got it wrong; should be overridden to "low"
    }
    provider = _make_mock_provider(canned)
    result = get_helper("customer_concentration_extraction").impl(
        text="No significant customer concentration.",
        llm_provider=provider,
    )
    assert result["risk_framing"] == "low"


def test_customer_concentration_default_provider_import_path() -> None:
    import inspect

    from openlia.llm.runtime.report_v2_2.tools.library_helpers.nlp import (
        customer_concentration_extraction as mod,
    )

    src = inspect.getsource(mod.execute)
    assert "from openlia.llm.providers import get_default_provider" in src
