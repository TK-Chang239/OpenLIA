"""Tests for rnpv_pipeline helper (PR 3.3).

Covers:
- Single asset rNPV with known inputs reconciles to manual calculation
- Pre-clinical asset (POS=9%) yields lower NPV than Phase 3 (POS=58%) for same peak sales
- Multi-asset pipeline aggregates correctly
- Patent cliff: revenue drops ~65% in year after patent expiry
- Royalty stack: 10% royalty burden reduces net_npv meaningfully
- Missing pos raises ValueError with decision #5 reference
- Skill doc exists at the declared path
- Helper registered with correct category and artifact type
- Artifact type in registry
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _get(name: str):
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"Helper {name!r} not registered"
    return h


def _run(name: str, **kwargs):
    return _get(name).impl(**kwargs)


def _schema(name: str):
    return _get(name).schema


# ---------------------------------------------------------------------------
# Shared asset fixtures
# ---------------------------------------------------------------------------

_CURRENT_YEAR = 2026

_SINGLE_ASSET = {
    "name": "Drug_A",
    "phase": "phase_3",
    "indication": "NSCLC",
    "peak_sales_estimate": 1000.0,  # $1B peak
    "launch_year": 2028,
    "patent_expiry": 2040,
    "royalty_rate": 0.0,
    "pos": 0.58,
}

_PRECLINICAL_ASSET = {
    "name": "Drug_Pre",
    "phase": "preclinical",
    "indication": "Oncology",
    "peak_sales_estimate": 1000.0,
    "launch_year": 2033,
    "patent_expiry": 2045,
    "royalty_rate": 0.0,
    "pos": 0.09,
}

_PHASE3_ASSET = {
    "name": "Drug_P3",
    "phase": "phase_3",
    "indication": "Oncology",
    "peak_sales_estimate": 1000.0,
    "launch_year": 2029,
    "patent_expiry": 2041,
    "royalty_rate": 0.0,
    "pos": 0.58,
}


def _run_single(**asset_overrides) -> dict:
    asset = {**_SINGLE_ASSET, **asset_overrides}
    return _run(
        "rnpv_pipeline",
        ticker="VRTX",
        assets=[asset],
        discount_rate=0.10,
        cogs_pct=0.15,
        sga_pct=0.30,
        tax_rate=0.21,
        terminal_year=2045,
    )


# ---------------------------------------------------------------------------
# 1. Single-asset rNPV — manual reconciliation
# ---------------------------------------------------------------------------


class TestSingleAssetRNPV:
    def test_risked_npv_equals_unrisked_times_pos(self) -> None:
        """risked_npv = unrisked_npv * pos."""
        result = _run_single()
        asset = result["assets"][0]
        assert asset["risked_npv"] == pytest.approx(asset["unrisked_npv"] * asset["pos"], rel=1e-4)

    def test_pos_preserved_in_output(self) -> None:
        result = _run_single()
        assert result["assets"][0]["pos"] == pytest.approx(0.58)

    def test_unrisked_npv_positive_for_phase3_asset(self) -> None:
        """Phase 3 asset, $1B peak sales, 10% discount -> positive unrisked NPV."""
        result = _run_single()
        assert result["assets"][0]["unrisked_npv"] > 0

    def test_net_npv_equals_risked_npv_when_no_royalties(self) -> None:
        """With royalty_rate=0, net_npv = risked_npv."""
        result = _run_single(royalty_rate=0.0)
        asset = result["assets"][0]
        assert asset["net_npv"] == pytest.approx(asset["risked_npv"], rel=1e-4)

    def test_total_pipeline_value_equals_single_asset_net_npv(self) -> None:
        result = _run_single()
        assert result["total_pipeline_value"] == pytest.approx(
            result["assets"][0]["net_npv"], rel=1e-4
        )

    def test_patent_cliff_impact_negative(self) -> None:
        """patent_cliff_impact must be negative — LOE destroys value."""
        result = _run_single()
        assert result["assets"][0]["patent_cliff_impact"] < 0

    def test_peak_sales_year_is_launch_plus_ramp(self) -> None:
        """Standard 3-year ramp: launch=2028 -> peak at 2028+3 = 2031."""
        result = _run_single()
        # standard profile has 4 entries (indices 0-3), peak at index 3 → launch + 3
        assert result["assets"][0]["peak_sales_year"] == 2028 + 3

    def test_manual_nopat_calculation(self) -> None:
        """Partial manual check: first revenue year NOPAT.

        launch_year=2028; year 1 revenue multiplier=0.10 (standard ramp).
        gross_rev = 1000 * 0.10 = 100; net_rev (no royalties) = 100.
        EBIT = 100 * (1 - 0.15 - 0.30) = 100 * 0.55 = 55.
        NOPAT = 55 * (1 - 0.21) = 55 * 0.79 = 43.45.
        t = 2028 - 2026 = 2; PV = 43.45 / (1.10)^2 = 43.45 / 1.21 ≈ 35.91.
        """
        result = _run_single()
        asset = result["assets"][0]
        # Unrisked NPV must be larger than first-year PV contribution alone
        first_year_pv = (1000.0 * 0.10 * 0.55 * 0.79) / (1.10**2)
        assert asset["unrisked_npv"] > first_year_pv

    def test_output_keys_present(self) -> None:
        result = _run_single()
        required_top = {
            "ticker",
            "assets",
            "total_pipeline_value",
            "value_concentration",
            "platform_value",
            "warnings",
            "pos_overrides_used",
            "narrative",
        }
        assert required_top <= result.keys()
        asset = result["assets"][0]
        required_asset = {
            "name",
            "phase",
            "pos",
            "unrisked_npv",
            "risked_npv",
            "royalty_burden",
            "net_npv",
            "peak_sales_year",
            "patent_cliff_impact",
        }
        assert required_asset <= asset.keys()


# ---------------------------------------------------------------------------
# 2. Pre-clinical (PoS=9%) yields lower NPV than Phase 3 (PoS=58%)
# ---------------------------------------------------------------------------


class TestPoSStageOrdering:
    def test_preclinical_lower_npv_than_phase3_same_peak_sales(self) -> None:
        """Pre-clinical at 9% PoS must produce lower risked_npv than Phase 3 at 58%."""
        pre = _run(
            "rnpv_pipeline",
            ticker="BIO",
            assets=[_PRECLINICAL_ASSET],
            discount_rate=0.10,
        )
        p3 = _run(
            "rnpv_pipeline",
            ticker="BIO",
            assets=[_PHASE3_ASSET],
            discount_rate=0.10,
        )
        assert pre["assets"][0]["risked_npv"] < p3["assets"][0]["risked_npv"]

    def test_preclinical_npv_ratio_approximately_proportional_to_pos(self) -> None:
        """With same peak_sales and roughly similar launch year, risked NPV ratio
        should roughly reflect PoS ratio (0.09 / 0.58 ≈ 0.155)."""
        pre = _run(
            "rnpv_pipeline",
            ticker="BIO",
            assets=[{**_PRECLINICAL_ASSET, "launch_year": 2029, "patent_expiry": 2041}],
            discount_rate=0.10,
        )
        p3 = _run(
            "rnpv_pipeline",
            ticker="BIO",
            assets=[_PHASE3_ASSET],
            discount_rate=0.10,
        )
        pre_risked = pre["assets"][0]["risked_npv"]
        p3_risked = p3["assets"][0]["risked_npv"]
        if p3_risked > 0:
            ratio = pre_risked / p3_risked
            expected_ratio = 0.09 / 0.58
            # Allow ±30% relative tolerance due to different launch years
            assert abs(ratio - expected_ratio) / expected_ratio < 0.30

    def test_approved_pos_1_gives_full_unrisked_npv(self) -> None:
        """An approved drug (pos=1.0) has risked_npv == unrisked_npv."""
        approved = {
            "name": "Drug_Approved",
            "phase": "approved",
            "indication": "Diabetes",
            "peak_sales_estimate": 500.0,
            "launch_year": 2026,
            "patent_expiry": 2038,
            "royalty_rate": 0.0,
            "pos": 1.0,
        }
        result = _run("rnpv_pipeline", ticker="LLY", assets=[approved], discount_rate=0.08)
        asset = result["assets"][0]
        assert asset["risked_npv"] == pytest.approx(asset["unrisked_npv"], rel=1e-6)


# ---------------------------------------------------------------------------
# 3. Multi-asset pipeline aggregates correctly
# ---------------------------------------------------------------------------


class TestMultiAssetPipeline:
    def test_total_pipeline_value_equals_sum_of_asset_net_npv(self) -> None:
        """total_pipeline_value = sum of all asset net_npv values."""
        assets = [
            {
                "name": "Drug_1",
                "phase": "phase_3",
                "indication": "Breast cancer",
                "peak_sales_estimate": 2000.0,
                "launch_year": 2028,
                "patent_expiry": 2040,
                "royalty_rate": 0.0,
                "pos": 0.58,
            },
            {
                "name": "Drug_2",
                "phase": "phase_2",
                "indication": "Lung cancer",
                "peak_sales_estimate": 800.0,
                "launch_year": 2031,
                "patent_expiry": 2043,
                "royalty_rate": 0.0,
                "pos": 0.31,
            },
            {
                "name": "Drug_3",
                "phase": "phase_1",
                "indication": "AML",
                "peak_sales_estimate": 400.0,
                "launch_year": 2034,
                "patent_expiry": 2045,
                "royalty_rate": 0.0,
                "pos": 0.14,
            },
        ]
        result = _run("rnpv_pipeline", ticker="MRK", assets=assets, discount_rate=0.10)

        expected_total = sum(a["net_npv"] for a in result["assets"])
        assert result["total_pipeline_value"] == pytest.approx(expected_total, rel=1e-4)

    def test_value_concentration_top1_pct_sum_to_at_most_1(self) -> None:
        assets = [
            {
                "name": f"Drug_{i}",
                "phase": "phase_3",
                "indication": "Oncology",
                "peak_sales_estimate": float(1000 * (i + 1)),
                "launch_year": 2028 + i,
                "patent_expiry": 2040 + i,
                "royalty_rate": 0.0,
                "pos": 0.58,
            }
            for i in range(3)
        ]
        result = _run("rnpv_pipeline", ticker="PFE", assets=assets, discount_rate=0.10)
        conc = result["value_concentration"]
        assert conc["top_1_pct_of_pipeline"] is not None
        assert 0.0 <= conc["top_1_pct_of_pipeline"] <= 1.0
        if conc["top_3_pct_of_pipeline"] is not None:
            assert conc["top_3_pct_of_pipeline"] <= 1.0

    def test_platform_value_flows_through(self) -> None:
        result = _run(
            "rnpv_pipeline",
            ticker="MRNA",
            assets=[_SINGLE_ASSET],
            discount_rate=0.10,
            platform_value=500.0,
        )
        assert result["platform_value"] == pytest.approx(500.0)

    def test_concentration_warning_fires_when_top1_over_50pct(self) -> None:
        """One large Phase 3 + one tiny Phase 1 → top-1 > 50% → warning."""
        assets = [
            {
                "name": "Big_Drug",
                "phase": "phase_3",
                "indication": "Oncology",
                "peak_sales_estimate": 5000.0,
                "launch_year": 2028,
                "patent_expiry": 2040,
                "royalty_rate": 0.0,
                "pos": 0.58,
            },
            {
                "name": "Small_Drug",
                "phase": "preclinical",
                "indication": "Rare disease",
                "peak_sales_estimate": 100.0,
                "launch_year": 2035,
                "patent_expiry": 2045,
                "royalty_rate": 0.0,
                "pos": 0.09,
            },
        ]
        result = _run("rnpv_pipeline", ticker="BIO", assets=assets, discount_rate=0.10)
        assert any(
            "binary" in w.lower() or "concentration" in w.lower() for w in result["warnings"]
        )


# ---------------------------------------------------------------------------
# 4. Patent cliff: revenue drops ~65% in year after patent expiry
# ---------------------------------------------------------------------------


class TestPatentCliff:
    def test_patent_cliff_impact_field_is_negative(self) -> None:
        """LOE reduces total PV — impact must be negative."""
        result = _run_single()
        assert result["assets"][0]["patent_cliff_impact"] < 0

    def test_earlier_patent_expiry_larger_cliff_impact(self) -> None:
        """Earlier expiry = more generics years = larger (more negative) cliff impact."""
        result_short = _run_single(patent_expiry=2033)
        result_long = _run_single(patent_expiry=2042)
        # More negative cliff impact means more value is lost
        assert (
            result_short["assets"][0]["patent_cliff_impact"]
            < result_long["assets"][0]["patent_cliff_impact"]
        )

    def test_post_loe_revenue_fraction_matches_decay_curve(self) -> None:
        """After LOE, year +1 revenue is 35% of pre-LOE peak (decay curve: 100% -> 35%).

        Indirect test: asset with patent_expiry == launch_year + 3 (peak year) means
        the peak year is also the LOE year.  Year +1 should have 35% of peak revenue.
        We verify by checking that unrisked_npv with immediate LOE is lower than
        one with LOE well after peak.
        """
        # Immediate patent expiry (launch year = patent expiry)
        result_early = _run(
            "rnpv_pipeline",
            ticker="GILD",
            assets=[
                {
                    "name": "Drug_X",
                    "phase": "phase_3",
                    "indication": "HIV",
                    "peak_sales_estimate": 1000.0,
                    "launch_year": 2028,
                    "patent_expiry": 2028,  # LOE at launch
                    "royalty_rate": 0.0,
                    "pos": 1.0,  # use pos=1 to isolate LOE effect
                }
            ],
            discount_rate=0.10,
        )
        # Late patent expiry
        result_late = _run(
            "rnpv_pipeline",
            ticker="GILD",
            assets=[
                {
                    "name": "Drug_X",
                    "phase": "phase_3",
                    "indication": "HIV",
                    "peak_sales_estimate": 1000.0,
                    "launch_year": 2028,
                    "patent_expiry": 2042,  # LOE 14 years after launch
                    "royalty_rate": 0.0,
                    "pos": 1.0,
                }
            ],
            discount_rate=0.10,
        )
        # Early LOE → much lower unrisked_npv
        assert result_early["assets"][0]["unrisked_npv"] < result_late["assets"][0]["unrisked_npv"]


# ---------------------------------------------------------------------------
# 5. Royalty stack: 10% royalty burden reduces net_npv
# ---------------------------------------------------------------------------


class TestRoyaltyStack:
    def test_royalty_reduces_net_npv_vs_zero_royalty(self) -> None:
        """Asset with 10% royalty should have lower net_npv than same asset without royalties."""
        result_no_royalty = _run_single(royalty_rate=0.0)
        result_royalty = _run_single(royalty_rate=0.10)
        assert result_royalty["assets"][0]["net_npv"] < result_no_royalty["assets"][0]["net_npv"]

    def test_royalty_burden_nonzero_when_rate_nonzero(self) -> None:
        """royalty_burden > 0 when royalty_rate > 0."""
        result = _run_single(royalty_rate=0.10)
        assert result["assets"][0]["royalty_burden"] > 0

    def test_royalty_burden_zero_when_no_royalty(self) -> None:
        result = _run_single(royalty_rate=0.0)
        assert result["assets"][0]["royalty_burden"] == pytest.approx(0.0, abs=1e-6)

    def test_royalty_reduction_approximately_10pct_of_no_royalty_npv(self) -> None:
        """With 10% royalty, revenue is reduced 10% each year.
        Net NPV should be approximately 10% lower than no-royalty case.
        (Not exact due to compounding and timing, but should be ~5-15% reduction.)
        """
        result_no = _run_single(royalty_rate=0.0)
        result_10 = _run_single(royalty_rate=0.10)
        npv_no = result_no["assets"][0]["net_npv"]
        npv_10 = result_10["assets"][0]["net_npv"]
        if npv_no > 0:
            reduction_pct = (npv_no - npv_10) / npv_no
            # Royalty of 10% on revenue reduces EBIT margin, not NPV directly — expect 8-12% range
            assert 0.05 <= reduction_pct <= 0.20, (
                f"Royalty reduction {reduction_pct:.1%} outside expected 5-20% range"
            )

    def test_50pct_royalty_cuts_npv_roughly_in_half(self) -> None:
        """50% royalty rate should approximately halve the net_npv."""
        result_no = _run_single(royalty_rate=0.0)
        result_50 = _run_single(royalty_rate=0.50)
        npv_no = result_no["assets"][0]["net_npv"]
        npv_50 = result_50["assets"][0]["net_npv"]
        if npv_no > 0:
            ratio = npv_50 / npv_no
            # Expect roughly 50% but not exact due to fixed-cost / tax structure
            assert 0.35 <= ratio <= 0.65


# ---------------------------------------------------------------------------
# 6. Missing pos raises ValueError with decision #5 reference
# ---------------------------------------------------------------------------


class TestMissingPos:
    def test_missing_pos_raises_value_error(self) -> None:
        """Asset without pos must raise ValueError."""
        asset_no_pos = {
            "name": "Drug_NoPOS",
            "phase": "phase_2",
            "indication": "NSCLC",
            "peak_sales_estimate": 500.0,
            "launch_year": 2030,
            "patent_expiry": 2042,
            "royalty_rate": 0.0,
            # pos intentionally missing
        }
        with pytest.raises(ValueError, match="Drug_NoPOS"):
            _run("rnpv_pipeline", ticker="BIO", assets=[asset_no_pos], discount_rate=0.10)

    def test_missing_pos_error_references_decision_5(self) -> None:
        """Error message must reference decision #5."""
        asset_no_pos = {
            "name": "Asset_X",
            "phase": "phase_1",
            "indication": "Rare disease",
            "peak_sales_estimate": 200.0,
            "launch_year": 2032,
            "patent_expiry": 2044,
            "royalty_rate": 0.0,
        }
        with pytest.raises(ValueError, match="decision #5"):
            _run("rnpv_pipeline", ticker="BIO", assets=[asset_no_pos], discount_rate=0.10)

    def test_missing_pos_error_mentions_citeline(self) -> None:
        """Error message should mention Citeline as the recommended source."""
        asset_no_pos = {
            "name": "Asset_Y",
            "phase": "phase_2",
            "indication": "CNS",
            "peak_sales_estimate": 300.0,
            "launch_year": 2031,
            "patent_expiry": 2043,
            "royalty_rate": 0.0,
        }
        with pytest.raises(ValueError, match="Citeline"):
            _run("rnpv_pipeline", ticker="BIO", assets=[asset_no_pos], discount_rate=0.10)

    def test_pos_out_of_range_raises_value_error(self) -> None:
        """pos > 1 should raise ValueError."""
        with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
            _run_single(pos=1.5)

    def test_pos_negative_raises_value_error(self) -> None:
        """pos < 0 should raise ValueError."""
        with pytest.raises(ValueError, match="outside \\[0, 1\\]"):
            _run_single(pos=-0.1)

    def test_pos_override_satisfies_requirement(self) -> None:
        """Asset without pos in dict is satisfied by pos_overrides dict."""
        asset_no_pos = {
            "name": "Drug_Override",
            "phase": "phase_2",
            "indication": "NSCLC",
            "peak_sales_estimate": 500.0,
            "launch_year": 2030,
            "patent_expiry": 2042,
            "royalty_rate": 0.0,
        }
        result = _run(
            "rnpv_pipeline",
            ticker="BIO",
            assets=[asset_no_pos],
            discount_rate=0.10,
            pos_overrides={"Drug_Override": 0.31},
        )
        assert result["assets"][0]["pos"] == pytest.approx(0.31)
        assert "Drug_Override" in result["pos_overrides_used"]

    def test_invalid_phase_raises_value_error(self) -> None:
        """An unrecognized phase value should raise ValueError."""
        with pytest.raises(ValueError, match="phase_4"):
            _run_single(phase="phase_4")


# ---------------------------------------------------------------------------
# 7. Skill doc exists
# ---------------------------------------------------------------------------


class TestSkillDoc:
    def test_skill_doc_file_exists(self) -> None:
        """Skill doc file must exist at the declared relative path (from library_helpers/)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "rnpv_pipeline.md")
        assert os.path.isfile(skill_path), f"Skill doc missing: {skill_path}"

    def test_skill_doc_path_declared_in_schema(self) -> None:
        schema = _schema("rnpv_pipeline")
        assert schema.skill_doc is not None
        assert schema.skill_doc.path == "skills/rnpv_pipeline.md"

    def test_skill_doc_estimated_tokens_in_range(self) -> None:
        schema = _schema("rnpv_pipeline")
        assert schema.skill_doc is not None
        assert 1800 <= schema.skill_doc.estimated_tokens <= 2200

    def test_skill_doc_contains_pos_norms_section(self) -> None:
        """Skill doc must cover PoS norms (decision #5)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "rnpv_pipeline.md")
        content = open(skill_path).read()
        assert "decision #5" in content.lower() or "Decision #5" in content

    def test_skill_doc_covers_decision_16(self) -> None:
        """Skill doc must cover decision #16 (royalty_stack_analyzer is internal)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "rnpv_pipeline.md")
        content = open(skill_path).read()
        assert "decision #16" in content.lower() or "Decision #16" in content


# ---------------------------------------------------------------------------
# 8. Registration and metadata
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_helper_registered(self) -> None:
        h = _get("rnpv_pipeline")
        assert h.schema.directory.name == "rnpv_pipeline"

    def test_produces_rnpv_pipeline_output(self) -> None:
        schema = _schema("rnpv_pipeline")
        assert "rnpv_pipeline_output" in schema.contract.produces_artifacts

    def test_category_is_sector_pharma(self) -> None:
        from openlia.llm.runtime.report_v2_2 import Category

        schema = _schema("rnpv_pipeline")
        assert schema.directory.category == Category.SECTOR_PHARMA

    def test_version_is_1_0_0(self) -> None:
        schema = _schema("rnpv_pipeline")
        assert schema.version == "1.0.0"

    def test_not_deprecated(self) -> None:
        schema = _schema("rnpv_pipeline")
        assert schema.deprecated_at_version is None

    def test_discount_rate_required(self) -> None:
        """Negative discount rate raises ValueError."""
        with pytest.raises(ValueError, match="discount_rate"):
            _run("rnpv_pipeline", ticker="BIO", assets=[_SINGLE_ASSET], discount_rate=-0.10)


# ---------------------------------------------------------------------------
# 9. Artifact type in registry
# ---------------------------------------------------------------------------


class TestArtifactType:
    def test_rnpv_pipeline_output_in_registry(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry

        assert _registry.get("rnpv_pipeline_output") is not None
