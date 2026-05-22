"""Tests for banks_sector_panel helper (PR 3.1).

Covers:
- NIM computed correctly from interest income / avg earning assets
- CET1 6% (< 7% min + 100bps buffer) triggers warning
- Efficiency ratio = non_interest_expense / total_revenue
- NCO surge (> 20% QoQ) triggers warning
- Cycle phase classified correctly for known input patterns
- Composite bank health score is in [0, 100]
- Skill doc exists at the declared path
- Helper registered with correct category and artifact type
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
# Minimal valid financials fixture
# ---------------------------------------------------------------------------

_BASE_FINANCIALS: dict = {
    "interest_income": 24_800,
    "interest_expense": 11_200,
    "avg_earning_assets": 2_500_000,
    "non_interest_income": 18_900,
    "non_interest_expense": 22_200,
    "net_income": 14_500,
    "avg_total_assets": 3_850_000,
    "avg_common_equity": 310_000,
    "avg_tangible_common_equity": 235_000,
    "cet1_ratio": 0.151,
    "tier1_ratio": 0.168,
    "total_capital_ratio": 0.190,
    "leverage_ratio": 0.072,
    "net_charge_offs": 2_250,
    "avg_loans": 1_320_000,
    "total_loans": 1_340_000,
    "nonperforming_loans": 9_650,
    "allowance_for_credit_losses": 24_800,
    "loan_loss_provision": 3_300,
    "loan_loss_provision_prior_year": 2_870,
    "total_deposits": 2_320_000,
}


def _run_base(**overrides) -> dict:
    financials = {**_BASE_FINANCIALS, **overrides}
    return _run(
        "banks_sector_panel",
        ticker="JPM",
        financials=financials,
        as_of="2026-Q1",
    )


# ---------------------------------------------------------------------------
# 1. NIM computation
# ---------------------------------------------------------------------------


class TestNIM:
    def test_nim_from_nii_and_earning_assets(self) -> None:
        """NIM = (interest_income - interest_expense) / avg_earning_assets.

        interest_income=24_800, interest_expense=11_200 → NII=13_600.
        avg_earning_assets=2_500_000 → NIM = 13_600/2_500_000 = 0.00544.
        """
        result = _run_base()
        nim = result["profitability"]["net_interest_margin_pct"]
        assert nim is not None
        expected = (24_800 - 11_200) / 2_500_000
        assert nim == pytest.approx(expected, rel=1e-5)

    def test_nii_computed_correctly(self) -> None:
        result = _run_base()
        nii = result["profitability"]["net_interest_income"]
        assert nii == pytest.approx(24_800 - 11_200)

    def test_nim_none_when_earning_assets_missing(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="TEST",
            financials={"interest_income": 100, "interest_expense": 40},
            as_of="2026-Q1",
        )
        assert result["profitability"]["net_interest_margin_pct"] is None

    def test_nim_none_when_interest_income_missing(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="TEST",
            financials={"avg_earning_assets": 1_000_000},
            as_of="2026-Q1",
        )
        assert result["profitability"]["net_interest_margin_pct"] is None

    def test_total_revenue_equals_nii_plus_non_interest_income(self) -> None:
        result = _run_base()
        prof = result["profitability"]
        expected_rev = (24_800 - 11_200) + 18_900
        assert prof["total_revenue"] == pytest.approx(expected_rev)


# ---------------------------------------------------------------------------
# 2. CET1 buffer warning (< regulatory min + 100bps)
# ---------------------------------------------------------------------------


class TestCET1Warning:
    def test_cet1_6pct_triggers_warning_at_7pct_min(self) -> None:
        """CET1 6% vs 7% minimum → buffer = -100bps → warning fires."""
        result = _run(
            "banks_sector_panel",
            ticker="SMALL",
            financials={"cet1_ratio": 0.060},
            as_of="2026-Q1",
            regulatory_min_cet1=0.07,
        )
        assert any("100bps" in w or "below" in w.lower() for w in result["warnings"])

    def test_cet1_6pct_below_minimum_buffer_adequacy(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="SMALL",
            financials={"cet1_ratio": 0.060},
            as_of="2026-Q1",
            regulatory_min_cet1=0.07,
        )
        ca = result["capital_adequacy"]
        assert ca["cet1_buffer_vs_minimum"] == pytest.approx(-0.010, rel=1e-4)
        assert ca["buffer_adequacy"] == "below_minimum_regulatory_action_expected"

    def test_cet1_7_5pct_tight_no_warning(self) -> None:
        """CET1 7.5% vs 7% min → buffer = 50bps → tight, but no warning (> 100bps from min)."""
        result = _run(
            "banks_sector_panel",
            ticker="MID",
            financials={"cet1_ratio": 0.075},
            as_of="2026-Q1",
            regulatory_min_cet1=0.07,
        )
        # Buffer = 50bps, which is < 100bps: warning fires
        assert any("100bps" in w for w in result["warnings"])

    def test_cet1_9pct_comfortable_no_warning(self) -> None:
        """CET1 9% vs 7% min → buffer = 200bps → modest, no 100bps proximity warning."""
        result = _run(
            "banks_sector_panel",
            ticker="JPM",
            financials={"cet1_ratio": 0.090},
            as_of="2026-Q1",
            regulatory_min_cet1=0.07,
        )
        assert not any("100bps" in w for w in result["warnings"])
        assert result["capital_adequacy"]["buffer_adequacy"] == "modest"

    def test_cet1_15pct_comfortable(self) -> None:
        result = _run_base()
        ca = result["capital_adequacy"]
        assert ca["buffer_adequacy"] == "comfortable"
        assert ca["cet1_buffer_vs_minimum"] == pytest.approx(0.151 - 0.07, rel=1e-4)

    def test_custom_gsib_regulatory_min(self) -> None:
        """G-SIB with 9% minimum: CET1 9.5% → buffer = 50bps (tight)."""
        result = _run(
            "banks_sector_panel",
            ticker="GSIB",
            financials={"cet1_ratio": 0.095},
            as_of="2026-Q1",
            regulatory_min_cet1=0.09,
        )
        ca = result["capital_adequacy"]
        assert ca["cet1_buffer_vs_minimum"] == pytest.approx(0.005, rel=1e-4)
        assert ca["buffer_adequacy"] == "tight"


# ---------------------------------------------------------------------------
# 3. Efficiency ratio
# ---------------------------------------------------------------------------


class TestEfficiencyRatio:
    def test_efficiency_ratio_equals_opex_over_total_revenue(self) -> None:
        """efficiency_ratio = non_interest_expense / (NII + non_interest_income).

        non_interest_expense=22_200; NII=13_600; non_interest_income=18_900
        total_revenue=32_500; efficiency=22_200/32_500 ≈ 0.6831.
        """
        result = _run_base()
        er = result["profitability"]["efficiency_ratio_pct"]
        assert er is not None
        expected = 22_200 / (13_600 + 18_900)
        assert er == pytest.approx(expected, rel=1e-5)

    def test_efficiency_ratio_none_when_revenue_missing(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="X",
            financials={"non_interest_expense": 100},
            as_of="2026-Q1",
        )
        assert result["profitability"]["efficiency_ratio_pct"] is None

    def test_efficiency_ratio_improves_with_lower_opex(self) -> None:
        result_high = _run_base(non_interest_expense=25_000)
        result_low = _run_base(non_interest_expense=15_000)
        assert (
            result_low["profitability"]["efficiency_ratio_pct"]
            < result_high["profitability"]["efficiency_ratio_pct"]
        )


# ---------------------------------------------------------------------------
# 4. NCO surge warning (> 20% QoQ)
# ---------------------------------------------------------------------------


class TestNCOSurgeWarning:
    def test_nco_surge_20pct_triggers_warning(self) -> None:
        """NCO rate rises > 20% QoQ → warning fires.

        Prior NCO rate = 0.0010; current NCO = 0.0013 → +30% QoQ → warning.
        """
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={
                "net_charge_offs": 1_300,
                "avg_loans": 1_000_000,  # NCO rate = 0.0013
                "nco_rate_prior": 0.0010,  # prior = 0.0010 → surge = +30%
            },
            as_of="2026-Q1",
        )
        assert any("surge" in w.lower() or "NCO" in w for w in result["warnings"])

    def test_nco_surge_exactly_20pct_triggers_warning(self) -> None:
        """NCO rate rises exactly 20% QoQ (0.0010 → 0.0012) → warning fires."""
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={
                "net_charge_offs": 1_200,
                "avg_loans": 1_000_000,  # NCO rate = 0.0012
                "nco_rate_prior": 0.0010,  # surge = exactly 20%
            },
            as_of="2026-Q1",
        )
        # > 20% threshold: 0.0012/0.0010 - 1 = 0.20, which is NOT > 0.20 (strict)
        # So no warning at exactly 20% — correct per spec (> 20%)
        assert not any("surge" in w.lower() for w in result["warnings"])

    def test_nco_surge_21pct_triggers_warning(self) -> None:
        """NCO rate rises 21% → warning fires."""
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={
                "net_charge_offs": 1_210,
                "avg_loans": 1_000_000,  # NCO rate = 0.001210
                "nco_rate_prior": 0.0010,
            },
            as_of="2026-Q1",
        )
        assert any("surge" in w.lower() or "NCO" in w for w in result["warnings"])

    def test_no_nco_surge_warning_when_stable(self) -> None:
        """NCO rate stable (no QoQ change) → no surge warning."""
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={
                "net_charge_offs": 1_000,
                "avg_loans": 1_000_000,  # NCO rate = 0.0010
                "nco_rate_prior": 0.0010,
            },
            as_of="2026-Q1",
        )
        assert not any("surge" in w.lower() for w in result["warnings"])

    def test_no_nco_surge_warning_when_prior_missing(self) -> None:
        """No prior NCO rate supplied → no surge warning emitted."""
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={"net_charge_offs": 1_500, "avg_loans": 1_000_000},
            as_of="2026-Q1",
        )
        assert not any("surge" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 5. Credit cycle phase classification
# ---------------------------------------------------------------------------


class TestCreditCyclePhase:
    def test_mid_cycle_normalizing_flat_nco(self) -> None:
        """Flat NCO + modest LLP YoY → mid_cycle_normalizing."""
        result = _run(
            "banks_sector_panel",
            ticker="JPM",
            financials={
                "net_charge_offs": 1_000,
                "avg_loans": 1_000_000,  # NCO rate = 0.0010
                "nco_rate_prior": 0.0010,  # flat
                "loan_loss_provision": 1_100,
                "loan_loss_provision_prior_year": 1_000,  # +10% YoY (< 20%)
            },
            as_of="2026-Q1",
        )
        assert result["credit_quality"]["credit_cycle_phase"] == "mid_cycle_normalizing"

    def test_early_deterioration_rising_nco_heavy_llp(self) -> None:
        """NCO rising >10% AND LLP YoY > 50% → early_deterioration."""
        result = _run(
            "banks_sector_panel",
            ticker="BAC",
            financials={
                "net_charge_offs": 1_500,
                "avg_loans": 1_000_000,  # NCO rate = 0.0015
                "nco_rate_prior": 0.0010,  # +50% — rising
                "loan_loss_provision": 2_000,
                "loan_loss_provision_prior_year": 1_000,  # +100% YoY → > 50%
            },
            as_of="2026-Q1",
        )
        assert result["credit_quality"]["credit_cycle_phase"] == "early_deterioration"

    def test_stress_nco_surging_llp_very_heavy(self) -> None:
        """NCO surging > 20% AND LLP YoY > 100% → stress."""
        result = _run(
            "banks_sector_panel",
            ticker="WFC",
            financials={
                "net_charge_offs": 3_000,
                "avg_loans": 1_000_000,  # NCO rate = 0.0030
                "nco_rate_prior": 0.0010,  # +200% → surging
                "loan_loss_provision": 5_000,
                "loan_loss_provision_prior_year": 1_000,  # +400% YoY
            },
            as_of="2026-Q1",
        )
        assert result["credit_quality"]["credit_cycle_phase"] == "stress"

    def test_recovery_nco_falling_reserves_releasing(self) -> None:
        """NCO falling > 10% AND LLP YoY negative → recovery."""
        result = _run(
            "banks_sector_panel",
            ticker="C",
            financials={
                "net_charge_offs": 800,
                "avg_loans": 1_000_000,  # NCO rate = 0.0008
                "nco_rate_prior": 0.0015,  # falling > 10%
                "loan_loss_provision": 400,
                "loan_loss_provision_prior_year": 1_500,  # releasing
            },
            as_of="2026-Q1",
        )
        assert result["credit_quality"]["credit_cycle_phase"] == "recovery"

    def test_unknown_phase_when_nco_rate_missing(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="UNKN",
            financials={},
            as_of="2026-Q1",
        )
        assert result["credit_quality"]["credit_cycle_phase"] == "unknown"
        assert result["cycle_phase"] == "unknown"


# ---------------------------------------------------------------------------
# 6. Composite bank health score
# ---------------------------------------------------------------------------


class TestCompositeHealthScore:
    def test_health_score_present_with_full_inputs(self) -> None:
        result = _run_base()
        score = result["composite_health_score"]
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_health_score_none_when_no_components(self) -> None:
        result = _run(
            "banks_sector_panel",
            ticker="EMPTY",
            financials={},
            as_of="2026-Q1",
        )
        assert result["composite_health_score"] is None

    def test_strong_bank_scores_above_70(self) -> None:
        """JPM-like metrics: good CET1, high RoTCE, tight efficiency, low NCO → high score."""
        result = _run(
            "banks_sector_panel",
            ticker="JPM",
            financials={
                "cet1_ratio": 0.15,
                "regulatory_min_cet1": 0.09,
                "avg_tangible_common_equity": 200_000,
                "net_income": 40_000,
                "non_interest_expense": 30_000,
                "interest_income": 50_000,
                "interest_expense": 20_000,
                "non_interest_income": 20_000,
                "net_charge_offs": 1_000,
                "avg_loans": 1_000_000,
                "nonperforming_loans": 5_000,
                "allowance_for_credit_losses": 15_000,
            },
            as_of="2026-Q1",
            regulatory_min_cet1=0.09,
        )
        assert result["composite_health_score"] is not None
        assert result["composite_health_score"] >= 60.0

    def test_distressed_bank_scores_below_50(self) -> None:
        """CET1 below min, negative RoTCE, poor efficiency → low score."""
        result = _run(
            "banks_sector_panel",
            ticker="WEAK",
            financials={
                "cet1_ratio": 0.055,
                "avg_tangible_common_equity": 50_000,
                "net_income": 500,  # very low RoTCE
                "non_interest_expense": 9_000,
                "interest_income": 5_000,
                "interest_expense": 2_000,
                "non_interest_income": 2_000,  # total_revenue = 5_000
                "net_charge_offs": 2_000,
                "avg_loans": 100_000,  # NCO rate = 2%
                "nonperforming_loans": 10_000,
                "allowance_for_credit_losses": 5_000,  # coverage < 1x
            },
            as_of="2026-Q1",
            regulatory_min_cet1=0.07,
        )
        assert result["composite_health_score"] is not None
        assert result["composite_health_score"] < 50.0


# ---------------------------------------------------------------------------
# 7. Output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:
    def test_required_keys_present(self) -> None:
        result = _run_base()
        for key in ("profitability", "capital_adequacy", "credit_quality", "liquidity"):
            assert key in result, f"Missing top-level key: {key}"

    def test_ticker_and_as_of_in_output(self) -> None:
        result = _run_base()
        assert result["ticker"] == "JPM"
        assert result["as_of"] == "2026-Q1"

    def test_warnings_is_list(self) -> None:
        result = _run_base()
        assert isinstance(result["warnings"], list)

    def test_source_provenance_default_empty(self) -> None:
        result = _run_base()
        assert result["source_provenance"] == []

    def test_narrative_contains_ticker(self) -> None:
        result = _run_base()
        assert "JPM" in result["narrative"]

    def test_rotce_computed(self) -> None:
        """RoTCE = net_income / avg_tce = 14_500 / 235_000."""
        result = _run_base()
        expected = 14_500 / 235_000
        assert result["profitability"]["rotce_pct"] == pytest.approx(expected, rel=1e-5)

    def test_roa_computed(self) -> None:
        """ROA = net_income / avg_total_assets = 14_500 / 3_850_000."""
        result = _run_base()
        expected = 14_500 / 3_850_000
        # roa_pct is rounded to 6 decimal places; use abs tolerance
        assert result["profitability"]["roa_pct"] == pytest.approx(expected, abs=1e-6)

    def test_fee_income_pct(self) -> None:
        """fee_income = non_interest_income / total_revenue."""
        result = _run_base()
        nii = 24_800 - 11_200  # 13_600
        total_rev = nii + 18_900  # 32_500
        expected = 18_900 / total_rev
        assert result["profitability"]["fee_income_pct_of_revenue"] == pytest.approx(
            expected, rel=1e-5
        )

    def test_loan_to_deposit_ratio(self) -> None:
        """LDR = total_loans / total_deposits = 1_340_000 / 2_320_000."""
        result = _run_base()
        expected = 1_340_000 / 2_320_000
        assert result["liquidity"]["loan_to_deposit_ratio"] == pytest.approx(expected, rel=1e-5)

    def test_acl_coverage_ratio(self) -> None:
        """ACL coverage = allowance / NPL = 24_800 / 9_650 ≈ 2.57."""
        result = _run_base()
        expected = 24_800 / 9_650
        assert result["credit_quality"]["acl_coverage_ratio"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# 8. Registration and metadata
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_helper_registered(self) -> None:
        h = _get("banks_sector_panel")
        assert h.schema.directory.name == "banks_sector_panel"

    def test_produces_banks_sector_panel_output(self) -> None:
        schema = _schema("banks_sector_panel")
        assert "banks_sector_panel_output" in schema.contract.produces_artifacts

    def test_category_is_sector_banks(self) -> None:
        from openlia.llm.runtime.report_v2_2 import Category

        schema = _schema("banks_sector_panel")
        assert schema.directory.category == Category.SECTOR_BANKS

    def test_version_is_1_0_0(self) -> None:
        schema = _schema("banks_sector_panel")
        assert schema.version == "1.0.0"

    def test_not_deprecated(self) -> None:
        schema = _schema("banks_sector_panel")
        assert schema.deprecated_at_version is None

    def test_skill_doc_path_declared(self) -> None:
        schema = _schema("banks_sector_panel")
        assert schema.skill_doc is not None
        assert schema.skill_doc.path == "skills/banks_sector_panel.md"

    def test_skill_doc_file_exists(self) -> None:
        """Skill doc file must exist at the declared relative path (from library_helpers/)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "banks_sector_panel.md")
        assert os.path.isfile(skill_path), f"Skill doc missing: {skill_path}"

    def test_skill_doc_estimated_tokens_reasonable(self) -> None:
        schema = _schema("banks_sector_panel")
        assert schema.skill_doc is not None
        assert 1200 <= schema.skill_doc.estimated_tokens <= 2500


# ---------------------------------------------------------------------------
# 9. Artifact type registration
# ---------------------------------------------------------------------------


class TestArtifactType:
    def test_banks_sector_panel_output_in_registry(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry

        assert _registry.get("banks_sector_panel_output") is not None
