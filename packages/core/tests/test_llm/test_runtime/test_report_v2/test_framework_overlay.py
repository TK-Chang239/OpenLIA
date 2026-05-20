"""Tests for the industry-mode overlay deep-merge and loader (WS9)."""

from __future__ import annotations

import json
from importlib import resources

from openlia.llm.runtime.report_v2.framework_overlay import (
    apply_facts_overlay,
    deep_merge,
    load_overlay,
    overlay_section_emphasis,
    report_mode_label,
)

# ---------------------------------------------------------------------------
# deep_merge — scalar / list / dict semantics
# ---------------------------------------------------------------------------


def test_deep_merge_scalar_right_wins() -> None:
    assert deep_merge(1, 2) == 2
    assert deep_merge("a", "b") == "b"
    assert deep_merge(None, "x") == "x"


def test_deep_merge_none_overlay_returns_base() -> None:
    assert deep_merge({"a": 1}, None) == {"a": 1}


def test_deep_merge_dict_scalar_overrides() -> None:
    base = {"a": 1, "b": 2}
    overlay = {"a": 10}
    assert deep_merge(base, overlay) == {"a": 10, "b": 2}


def test_deep_merge_dict_adds_new_key() -> None:
    base = {"a": 1}
    overlay = {"b": 2}
    assert deep_merge(base, overlay) == {"a": 1, "b": 2}


def test_deep_merge_list_extension() -> None:
    base = ["x", "y"]
    overlay = ["z", "w"]
    assert deep_merge(base, overlay) == ["x", "y", "z", "w"]


def test_deep_merge_list_dedup_preserves_order() -> None:
    base = ["x", "y", "z"]
    overlay = ["y", "w", "z"]
    assert deep_merge(base, overlay) == ["x", "y", "z", "w"]


def test_deep_merge_nested_dict_recurse() -> None:
    base = {"facts": {"cover": ["a", "b"], "business_model": ["c"]}}
    overlay = {"facts": {"cover": ["x"], "risk_analysis": ["r1"]}}
    result = deep_merge(base, overlay)
    assert result == {
        "facts": {
            "cover": ["a", "b", "x"],
            "business_model": ["c"],
            "risk_analysis": ["r1"],
        }
    }


def test_deep_merge_type_mismatch_overlay_wins() -> None:
    base = {"a": [1, 2]}
    overlay = {"a": "scalar"}
    assert deep_merge(base, overlay) == {"a": "scalar"}


# ---------------------------------------------------------------------------
# apply_facts_overlay — base facts framework + overlay facts block
# ---------------------------------------------------------------------------


def test_apply_facts_overlay_extends_section_fact_lists() -> None:
    base = {
        "cover": ["company_name", "sector"],
        "business_model": ["company_name", "revenue_cagr_3y"],
    }
    overlay = {
        "facts": {
            "cover": ["nrr_dollar_based"],
            "business_model": ["nrr_dollar_based", "rule_of_40_score"],
        }
    }
    merged = apply_facts_overlay(base, overlay)
    assert merged["cover"] == ["company_name", "sector", "nrr_dollar_based"]
    assert merged["business_model"] == [
        "company_name",
        "revenue_cagr_3y",
        "nrr_dollar_based",
        "rule_of_40_score",
    ]


def test_apply_facts_overlay_adds_new_section_fact_list() -> None:
    base = {"cover": ["company_name"]}
    overlay = {"facts": {"valuation_analysis": ["ev_to_sales_forward"]}}
    merged = apply_facts_overlay(base, overlay)
    assert merged["valuation_analysis"] == ["ev_to_sales_forward"]
    assert merged["cover"] == ["company_name"]


def test_apply_facts_overlay_empty_overlay_returns_base_copy() -> None:
    base = {"cover": ["a"]}
    merged = apply_facts_overlay(base, {})
    assert merged == base


def test_apply_facts_overlay_dedup_preserves_first_position() -> None:
    base = {"cover": ["company_name", "sector", "market_cap"]}
    overlay = {"facts": {"cover": ["sector", "rule_of_40_score"]}}
    merged = apply_facts_overlay(base, overlay)
    assert merged["cover"] == ["company_name", "sector", "market_cap", "rule_of_40_score"]


# ---------------------------------------------------------------------------
# Per-mode overlay JSON files load and merge cleanly onto the real base
# ---------------------------------------------------------------------------


def _load_base_facts() -> dict[str, list[str]]:
    path = (
        resources.files("openlia.llm.runtime.report_v2.frameworks") / "stock_initiation.facts.json"
    )
    return json.loads(path.read_text())["sections"]


def test_saas_overlay_loads_and_extends_business_model_facts() -> None:
    base = _load_base_facts()
    overlay = load_overlay("saas")
    merged = apply_facts_overlay(base, overlay)
    bm = merged["business_model"]
    assert "nrr_dollar_based" in bm
    assert "rule_of_40_score" in bm
    assert "cRPO" in bm
    assert "billings_ttm" in bm
    assert "sbc_dilution_bridge" in bm
    # Base entries are preserved.
    assert "company_name" in bm
    assert "segment_revenue_latest" in bm


def test_semis_overlay_loads_and_extends_risk_facts() -> None:
    base = _load_base_facts()
    overlay = load_overlay("semis")
    merged = apply_facts_overlay(base, overlay)
    risk = merged["risk_analysis"]
    assert "customer_concentration_top1_pct" in risk
    assert "customer_concentration_top5_pct" in risk
    assert "geographic_revenue_split" in risk
    assert "china_export_control_exposure_dollars" in risk
    assert "purchase_commitments_dollars" in risk


def test_distressed_overlay_loads_and_extends_valuation_facts() -> None:
    base = _load_base_facts()
    overlay = load_overlay("distressed")
    merged = apply_facts_overlay(base, overlay)
    val = merged["valuation_analysis"]
    assert "ev_to_sales_forward" in val
    assert "ev_to_ebitda_forward" in val
    assert "recovery_per_claim_class" in val
    assert "post_emergence_share_count" in val
    fin = merged["financial_analysis"]
    assert "cash_burn_ttm" in fin
    assert "debt_maturity_schedule" in fin
    assert "covenant_status" in fin
    assert "dip_facility_details" in fin


def test_generic_overlay_is_essentially_empty() -> None:
    base = _load_base_facts()
    overlay = load_overlay("generic")
    merged = apply_facts_overlay(base, overlay)
    # Generic overlay only carries the report_mode_label; facts stay base.
    assert merged == base
    assert report_mode_label(overlay) == "Initiation report — generic"


def test_all_overlays_have_report_mode_label() -> None:
    for mode in ("generic", "saas", "semis", "distressed"):
        overlay = load_overlay(mode)  # type: ignore[arg-type]
        label = report_mode_label(overlay)
        assert isinstance(label, str)
        assert label.strip(), f"empty label for mode {mode!r}"


# ---------------------------------------------------------------------------
# section_emphasis extraction
# ---------------------------------------------------------------------------


def test_overlay_section_emphasis_returns_dict() -> None:
    overlay = load_overlay("saas")
    emphasis = overlay_section_emphasis(overlay)
    assert "business_model" in emphasis
    assert "risk_analysis" in emphasis
    assert "recent_developments" in emphasis
    # Must be strings, non-empty.
    for sid, text in emphasis.items():
        assert isinstance(text, str)
        assert text.strip(), f"empty emphasis for {sid!r}"


def test_overlay_section_emphasis_missing_returns_empty_dict() -> None:
    # generic overlay has no section_emphasis.
    overlay = load_overlay("generic")
    assert overlay_section_emphasis(overlay) == {}


def test_distressed_emphasis_forbids_growth_framing() -> None:
    overlay = load_overlay("distressed")
    emphasis = overlay_section_emphasis(overlay)
    # Distressed sections must explicitly forbid growth-mode framing.
    val_text = emphasis.get("valuation_analysis", "")
    assert "Do NOT describe revenue growth" in val_text
    assert "call option" in val_text


def test_distressed_competitive_analysis_uses_ev_multiples() -> None:
    overlay = load_overlay("distressed")
    emphasis = overlay_section_emphasis(overlay)
    comp_text = emphasis.get("competitive_analysis", "")
    assert "EV/Sales" in comp_text
    assert "NOT P/E" in comp_text


def test_distressed_overlay_overrides_cover_instructions() -> None:
    overlay = load_overlay("distressed")
    # Cover instructions override is a top-level string (not a nested key on
    # the base framework's cover block). It is plumbed onto the cover at
    # render time by the runner.
    assert isinstance(overlay.get("cover_instructions_override"), str)
    text = overlay["cover_instructions_override"]
    assert "solvency-first" in text
    assert "Do NOT lead with revenue growth" in text
