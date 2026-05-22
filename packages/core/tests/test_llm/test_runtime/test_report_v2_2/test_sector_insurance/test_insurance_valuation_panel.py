"""Tests for insurance_valuation_panel helper (PR 3.5).

Covers:
- Combined ratio = loss_ratio + expense_ratio
- P&C combined_ratio = 95% -> underwriting profit, no warning
- P&C combined_ratio = 105% -> underwriting loss + warning
- Life: VNB margin = NBV / APE
- Life: solvency < 150% triggers warning
- Composite returns both pc and life blocks
- Adverse prior-year reserve development triggers warning
- Float metrics present for P&C
- Balance sheet BVPS and P/TBV computed correctly
- ROE computed correctly
- Composite insurance health score in [0, 100]
- Skill doc exists
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
# Base fixtures
# ---------------------------------------------------------------------------

_BASE_FINANCIALS: dict = {
    "invested_assets": 145_000,
    "investment_income": 3_800,
    "book_value_equity_gaap": 28_500,
    "intangibles_and_goodwill": 4_300,
    "shares_outstanding_diluted": 412,
    "current_price": 107.0,
    "net_income": 3_200,
    "avg_equity": 27_500,
}

_BASE_PC_SPECIFIC: dict = {
    "premiums_earned": 12_300,
    "premiums_written": 12_800,
    "losses_and_lae": 7_443,  # loss_ratio = 7443/12300 = 0.605
    "underwriting_expenses": 3_382,  # expense_ratio = 3382/12300 = 0.275
    "catastrophe_losses_disclosed": 468,  # cat_load = 468/12300 ≈ 0.038
    "prior_year_reserve_development": -120,  # favorable
}

_BASE_LIFE_SPECIFIC: dict = {
    "gross_premiums": 8_000,
    "net_premiums": 7_500,
    "benefits_and_claims_paid": 4_200,
    "change_in_reserves": 1_500,
    "embedded_value_disclosed": 25_000,
    "new_business_value_disclosed": 750,
    "annual_premium_equivalent": 3_000,
    "solvency_ratio": 1.80,  # 180% > 150%
    "persistency_rate": 0.88,
}


def _run_pc(**overrides) -> dict:
    ispec = {**_BASE_PC_SPECIFIC, **overrides}
    return _run(
        "insurance_valuation_panel",
        ticker="CB",
        insurance_type="pc",
        financials=_BASE_FINANCIALS,
        insurance_specific=ispec,
        as_of="2026-Q1",
    )


def _run_life(fin_overrides: dict | None = None, spec_overrides: dict | None = None) -> dict:
    fin = {**_BASE_FINANCIALS, **(fin_overrides or {})}
    ispec = {**_BASE_LIFE_SPECIFIC, **(spec_overrides or {})}
    return _run(
        "insurance_valuation_panel",
        ticker="PRU",
        insurance_type="life",
        financials=fin,
        insurance_specific=ispec,
        as_of="2026-Q1",
    )


def _run_composite(fin_overrides: dict | None = None, spec_overrides: dict | None = None) -> dict:
    fin = {**_BASE_FINANCIALS, **(fin_overrides or {})}
    ispec = {**_BASE_PC_SPECIFIC, **_BASE_LIFE_SPECIFIC, **(spec_overrides or {})}
    return _run(
        "insurance_valuation_panel",
        ticker="ALL",
        insurance_type="composite",
        financials=fin,
        insurance_specific=ispec,
        as_of="2026-Q1",
    )


# ---------------------------------------------------------------------------
# 1. Combined ratio formula correctness
# ---------------------------------------------------------------------------


class TestCombinedRatioFormula:
    def test_combined_ratio_equals_loss_plus_expense(self) -> None:
        """combined_ratio = loss_ratio + expense_ratio (no policyholder dividend)."""
        result = _run_pc()
        pc = result["pc"]
        cr = pc["combined_ratio_pct"]
        lr = pc["loss_ratio_pct"]
        er = pc["expense_ratio_pct"]
        assert cr is not None
        assert lr is not None
        assert er is not None
        assert cr == pytest.approx(lr + er, rel=1e-5)

    def test_combined_ratio_includes_pd_ratio_when_nonzero(self) -> None:
        """combined_ratio = loss + expense + pd_ratio."""
        result = _run_pc(policyholder_dividends=246)  # 246/12300 = 0.02
        pc = result["pc"]
        cr = pc["combined_ratio_pct"]
        lr = pc["loss_ratio_pct"]
        er = pc["expense_ratio_pct"]
        pd_r = pc["policyholder_dividend_ratio_pct"]
        assert pd_r is not None
        assert cr == pytest.approx(lr + er + pd_r, rel=1e-5)

    def test_loss_ratio_excludes_favorable_py_development(self) -> None:
        """Loss ratio removes favorable PY development from numerator.

        losses_and_lae = 7443, prior_year_dev = -120 (favorable).
        adjusted_losses = 7443 - (-120) = 7563; LR = 7563/12300.
        """
        result = _run_pc(prior_year_reserve_development=-120)
        expected_lr = (7_443 - (-120)) / 12_300
        assert result["pc"]["loss_ratio_pct"] == pytest.approx(expected_lr, rel=1e-5)

    def test_loss_ratio_adjusts_for_adverse_development(self) -> None:
        """Adverse PY dev (positive) reduces effective losses in numerator.

        prior_year_dev = 200 (adverse); adjusted_losses = 7443 - 200 = 7243.
        """
        result = _run_pc(prior_year_reserve_development=200)
        expected_lr = (7_443 - 200) / 12_300
        assert result["pc"]["loss_ratio_pct"] == pytest.approx(expected_lr, rel=1e-5)

    def test_combined_ratio_none_when_premiums_missing(self) -> None:
        result = _run(
            "insurance_valuation_panel",
            ticker="X",
            insurance_type="pc",
            financials={},
            insurance_specific={"losses_and_lae": 100, "underwriting_expenses": 20},
            as_of="2026-Q1",
        )
        assert result["pc"]["combined_ratio_pct"] is None


# ---------------------------------------------------------------------------
# 2. P&C combined ratio 95% — underwriting profit
# ---------------------------------------------------------------------------


class TestPCProfitableUnderwriting:
    def _setup_cr_95(self) -> dict:
        """Build inputs for combined ratio = 95%: LR 60% + ER 35% = 95%."""
        return _run_pc(
            premiums_earned=10_000,
            losses_and_lae=6_000,  # LR = 6000/10000 = 60%
            underwriting_expenses=3_500,  # ER = 3500/10000 = 35%
            prior_year_reserve_development=0,
            catastrophe_losses_disclosed=None,
        )

    def test_combined_ratio_is_95pct(self) -> None:
        result = self._setup_cr_95()
        assert result["pc"]["combined_ratio_pct"] == pytest.approx(0.95, rel=1e-5)

    def test_underwriting_profit_positive(self) -> None:
        """CR < 100% -> underwriting profit = premiums_earned * (1 - CR) > 0."""
        result = self._setup_cr_95()
        assert result["pc"]["underwriting_profit"] is not None
        assert result["pc"]["underwriting_profit"] > 0

    def test_no_combined_ratio_warning_at_95pct(self) -> None:
        """CR = 95% -> no underwriting loss warning."""
        result = self._setup_cr_95()
        assert not any(
            "combined ratio" in w.lower() or "underwriting loss" in w.lower()
            for w in result["warnings"]
        )

    def test_cycle_phase_not_distressed(self) -> None:
        """CR = 95% -> cycle phase not distressed or structural_loss."""
        result = self._setup_cr_95()
        assert result["underwriting_cycle_phase"] not in ("distressed", "structural_loss")


# ---------------------------------------------------------------------------
# 3. P&C combined ratio 105% — underwriting loss + warning
# ---------------------------------------------------------------------------


class TestPCUnderwritingLoss:
    def _setup_cr_105(self) -> dict:
        """Build inputs for combined ratio = 105%: LR 70% + ER 35% = 105%."""
        return _run_pc(
            premiums_earned=10_000,
            losses_and_lae=7_000,  # LR = 70%
            underwriting_expenses=3_500,  # ER = 35%
            prior_year_reserve_development=0,
            catastrophe_losses_disclosed=None,
        )

    def test_combined_ratio_is_105pct(self) -> None:
        result = self._setup_cr_105()
        assert result["pc"]["combined_ratio_pct"] == pytest.approx(1.05, rel=1e-5)

    def test_underwriting_profit_negative(self) -> None:
        """CR > 100% -> underwriting profit (loss) < 0."""
        result = self._setup_cr_105()
        assert result["pc"]["underwriting_profit"] < 0

    def test_warning_fires_for_cr_above_100(self) -> None:
        """CR = 105% triggers 'underwriting loss' or 'combined ratio' warning."""
        result = self._setup_cr_105()
        assert any(
            "underwriting loss" in w.lower() or "combined ratio" in w.lower() or "100%" in w
            for w in result["warnings"]
        )

    def test_float_cost_positive_when_cr_above_100(self) -> None:
        """When CR > 100%, float has a positive cost."""
        result = self._setup_cr_105()
        assert result["float_metrics"] is not None
        fc = result["float_metrics"]["float_generation_cost_pct"]
        assert fc is not None
        assert fc > 0


# ---------------------------------------------------------------------------
# 4. Life: VNB margin = NBV / APE
# ---------------------------------------------------------------------------


class TestLifeVNBMargin:
    def test_vnb_margin_formula(self) -> None:
        """VNB margin = new_business_value_disclosed / annual_premium_equivalent."""
        result = _run_life(
            spec_overrides={"new_business_value_disclosed": 750, "annual_premium_equivalent": 3_000}
        )
        expected = 750 / 3_000
        assert result["life"]["vnb_margin_pct"] == pytest.approx(expected, rel=1e-5)

    def test_vnb_margin_none_when_ape_missing(self) -> None:
        result = _run_life(
            spec_overrides={"new_business_value_disclosed": 500, "annual_premium_equivalent": None}
        )
        assert result["life"]["vnb_margin_pct"] is None

    def test_vnb_margin_none_when_nbv_missing(self) -> None:
        result = _run_life(
            spec_overrides={
                "new_business_value_disclosed": None,
                "annual_premium_equivalent": 3_000,
            }
        )
        assert result["life"]["vnb_margin_pct"] is None

    def test_vnb_margin_high_value(self) -> None:
        """VNB margin 30% correctly computed."""
        result = _run_life(
            spec_overrides={"new_business_value_disclosed": 900, "annual_premium_equivalent": 3_000}
        )
        assert result["life"]["vnb_margin_pct"] == pytest.approx(0.30, rel=1e-5)


# ---------------------------------------------------------------------------
# 5. Life: solvency < 150% triggers warning
# ---------------------------------------------------------------------------


class TestLifeSolvencyWarning:
    def test_solvency_below_150pct_triggers_warning(self) -> None:
        """Solvency ratio = 130% < 150% threshold -> warning fires."""
        result = _run_life(spec_overrides={"solvency_ratio": 1.30})
        assert any("solvency" in w.lower() or "150" in w for w in result["warnings"])

    def test_solvency_below_100pct_triggers_breach_warning(self) -> None:
        """Solvency ratio = 90% < 100% Solvency II breach -> stronger warning."""
        result = _run_life(spec_overrides={"solvency_ratio": 0.90})
        assert any(
            "below 100%" in w.lower() or "solvency ii" in w.lower() or "regulatory" in w.lower()
            for w in result["warnings"]
        )

    def test_solvency_at_180pct_no_warning(self) -> None:
        """Solvency ratio = 180% >= 150% -> no solvency warning."""
        result = _run_life(spec_overrides={"solvency_ratio": 1.80})
        assert not any("solvency" in w.lower() for w in result["warnings"])

    def test_solvency_ratio_stored_in_life_block(self) -> None:
        result = _run_life(spec_overrides={"solvency_ratio": 1.75})
        assert result["life"]["solvency_ratio"] == pytest.approx(1.75)


# ---------------------------------------------------------------------------
# 6. Composite returns both pc and life blocks
# ---------------------------------------------------------------------------


class TestComposite:
    def test_composite_has_pc_block(self) -> None:
        result = _run_composite()
        assert result["pc"] is not None
        assert result["pc"]["combined_ratio_pct"] is not None

    def test_composite_has_life_block(self) -> None:
        result = _run_composite()
        assert result["life"] is not None

    def test_composite_pc_has_combined_ratio(self) -> None:
        result = _run_composite()
        assert result["pc"]["combined_ratio_pct"] is not None

    def test_composite_life_has_vnb_margin(self) -> None:
        result = _run_composite()
        assert result["life"]["vnb_margin_pct"] is not None

    def test_composite_insurance_type_in_output(self) -> None:
        result = _run_composite()
        assert result["insurance_type"] == "composite"

    def test_pc_only_has_null_life_block(self) -> None:
        result = _run_pc()
        assert result["life"] is None

    def test_life_only_has_null_pc_block(self) -> None:
        result = _run_life()
        assert result["pc"] is None


# ---------------------------------------------------------------------------
# 7. Adverse prior-year reserve development warning
# ---------------------------------------------------------------------------


class TestReserveDevelopment:
    def test_adverse_development_triggers_warning(self) -> None:
        """Positive PY development (adverse) triggers warning."""
        result = _run_pc(prior_year_reserve_development=250)
        assert any(
            "adverse" in w.lower() or "reserve development" in w.lower() for w in result["warnings"]
        )

    def test_favorable_development_no_warning(self) -> None:
        """Negative PY development (favorable) does NOT trigger reserve warning."""
        result = _run_pc(prior_year_reserve_development=-120)
        assert not any("adverse" in w.lower() for w in result["warnings"])

    def test_zero_development_no_warning(self) -> None:
        result = _run_pc(prior_year_reserve_development=0)
        assert not any("adverse" in w.lower() for w in result["warnings"])

    def test_favorable_development_stored_correctly(self) -> None:
        result = _run_pc(prior_year_reserve_development=-200)
        assert result["pc"]["prior_year_reserve_development"] == -200


# ---------------------------------------------------------------------------
# 8. Float metrics (P&C only)
# ---------------------------------------------------------------------------


class TestFloatMetrics:
    def test_float_metrics_present_for_pc(self) -> None:
        result = _run_pc()
        assert result["float_metrics"] is not None

    def test_float_metrics_none_for_life(self) -> None:
        result = _run_life()
        assert result["float_metrics"] is None

    def test_float_equity_ratio_computed(self) -> None:
        """float_equity_ratio = invested_assets / book_value_equity_gaap = 145000/28500."""
        result = _run_pc()
        expected = 145_000 / 28_500
        assert result["float_metrics"]["float_equity_ratio"] == pytest.approx(expected, rel=1e-4)

    def test_float_cost_zero_when_cr_below_100(self) -> None:
        """When CR < 100%, float generation cost = 0 (free float)."""
        result = _run_pc(
            premiums_earned=10_000,
            losses_and_lae=6_000,  # LR 60%
            underwriting_expenses=3_000,  # ER 30%, CR = 90%
            prior_year_reserve_development=0,
        )
        assert result["float_metrics"]["float_generation_cost_pct"] == 0.0


# ---------------------------------------------------------------------------
# 9. Balance sheet and book value metrics
# ---------------------------------------------------------------------------


class TestBalanceSheet:
    def test_bvps_gaap(self) -> None:
        """BVPS = book_equity_gaap / shares_outstanding = 28500 / 412."""
        result = _run_pc()
        expected = 28_500 / 412
        assert result["balance_sheet"]["book_value_per_share_gaap"] == pytest.approx(
            expected, rel=1e-4
        )

    def test_tangible_bvps(self) -> None:
        """Tangible BVPS = (book_equity - intangibles) / shares = (28500-4300)/412."""
        result = _run_pc()
        expected = (28_500 - 4_300) / 412
        assert result["balance_sheet"]["tangible_book_value_per_share"] == pytest.approx(
            expected, rel=1e-4
        )

    def test_price_to_tangible_book(self) -> None:
        """P/TBV = current_price / tangible_bvps = 107 / ((28500-4300)/412)."""
        result = _run_pc()
        tbvps = (28_500 - 4_300) / 412
        expected = 107.0 / tbvps
        assert result["balance_sheet"]["price_to_tangible_book"] == pytest.approx(
            expected, rel=1e-4
        )

    def test_negative_equity_triggers_warning(self) -> None:
        """Negative GAAP equity -> warning fires and per-share metrics are None."""
        result = _run(
            "insurance_valuation_panel",
            ticker="WEAK",
            insurance_type="pc",
            financials={
                **_BASE_FINANCIALS,
                "book_value_equity_gaap": -1_000,
            },
            insurance_specific=_BASE_PC_SPECIFIC,
            as_of="2026-Q1",
        )
        assert any("negative" in w.lower() or "impairment" in w.lower() for w in result["warnings"])
        assert result["balance_sheet"]["book_value_per_share_gaap"] is None

    def test_tbvps_growth_computed(self) -> None:
        """TBVPS growth = (tbvps_current - tbvps_prior) / tbvps_prior."""
        fin = {
            **_BASE_FINANCIALS,
            "tangible_book_value_prior_year": 22_000,  # prior tangible BV (total, not per share)
        }
        result = _run(
            "insurance_valuation_panel",
            ticker="CB",
            insurance_type="pc",
            financials=fin,
            insurance_specific=_BASE_PC_SPECIFIC,
            as_of="2026-Q1",
        )
        current_tbv = 28_500 - 4_300  # = 24_200
        tbvps_current = current_tbv / 412
        tbvps_prior = 22_000 / 412
        expected_growth = (tbvps_current - tbvps_prior) / tbvps_prior
        assert result["balance_sheet"]["tangible_book_value_per_share_growth_pct"] == pytest.approx(
            expected_growth, rel=1e-4
        )


# ---------------------------------------------------------------------------
# 10. ROE
# ---------------------------------------------------------------------------


class TestROE:
    def test_roe_computed(self) -> None:
        """ROE = net_income / avg_equity = 3200 / 27500."""
        result = _run_pc()
        expected = 3_200 / 27_500
        assert result["roe_pct"] == pytest.approx(expected, rel=1e-5)

    def test_roe_none_when_equity_missing(self) -> None:
        fin = {k: v for k, v in _BASE_FINANCIALS.items() if k != "avg_equity"}
        result = _run(
            "insurance_valuation_panel",
            ticker="X",
            insurance_type="pc",
            financials=fin,
            insurance_specific=_BASE_PC_SPECIFIC,
            as_of="2026-Q1",
        )
        assert result["roe_pct"] is None


# ---------------------------------------------------------------------------
# 11. Composite insurance health score
# ---------------------------------------------------------------------------


class TestCompositeHealthScore:
    def test_health_score_in_range(self) -> None:
        result = _run_pc()
        score = result["composite_health_score"]
        if score is not None:
            assert 0.0 <= score <= 100.0

    def test_excellent_insurer_high_score(self) -> None:
        """CR 88%, ROE 15%, good solvency, positive yield -> high score."""
        fin = {
            **_BASE_FINANCIALS,
            "net_income": 4_125,  # ROE = 4125/27500 = 15%
            "rbc_ratio_disclosed": 2.5,  # 250% -> normalized to 1.25 -> solvency ok
        }
        ispec = {
            **_BASE_PC_SPECIFIC,
            "premiums_earned": 10_000,
            "losses_and_lae": 5_300,  # LR = 53%
            "underwriting_expenses": 3_500,  # ER = 35%, CR = 88%
            "prior_year_reserve_development": -100,
        }
        result = _run(
            "insurance_valuation_panel",
            ticker="GREAT",
            insurance_type="pc",
            financials=fin,
            insurance_specific=ispec,
            as_of="2026-Q1",
        )
        score = result["composite_health_score"]
        if score is not None:
            assert score >= 50.0

    def test_health_score_none_when_no_inputs(self) -> None:
        result = _run(
            "insurance_valuation_panel",
            ticker="EMPTY",
            insurance_type="pc",
            financials={},
            insurance_specific={},
            as_of="2026-Q1",
        )
        assert result["composite_health_score"] is None


# ---------------------------------------------------------------------------
# 12. Output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:
    def test_required_top_level_keys_present(self) -> None:
        result = _run_pc()
        for key in (
            "ticker",
            "insurance_type",
            "as_of",
            "investment_portfolio",
            "balance_sheet",
            "capital_adequacy",
            "composite_health_score",
            "underwriting_cycle_phase",
            "warnings",
            "narrative",
        ):
            assert key in result, f"Missing top-level key: {key}"

    def test_ticker_in_output(self) -> None:
        result = _run_pc()
        assert result["ticker"] == "CB"

    def test_warnings_is_list(self) -> None:
        result = _run_pc()
        assert isinstance(result["warnings"], list)

    def test_source_provenance_default_empty(self) -> None:
        result = _run_pc()
        assert result["source_provenance"] == []

    def test_narrative_contains_ticker(self) -> None:
        result = _run_pc()
        assert "CB" in result["narrative"]

    def test_investment_yield_computed(self) -> None:
        """Investment yield = investment_income / invested_assets = 3800/145000."""
        result = _run_pc()
        expected = 3_800 / 145_000
        assert result["investment_portfolio"]["investment_yield_pct"] == pytest.approx(
            expected, rel=1e-5
        )

    def test_ev_per_share_for_life(self) -> None:
        """EV per share = embedded_value_disclosed / shares = 25000 / 412."""
        result = _run_life()
        expected = 25_000 / 412
        assert result["life"]["ev_per_share"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# 13. Registration and metadata
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_helper_registered(self) -> None:
        h = _get("insurance_valuation_panel")
        assert h.schema.directory.name == "insurance_valuation_panel"

    def test_produces_correct_artifact(self) -> None:
        schema = _schema("insurance_valuation_panel")
        assert "insurance_valuation_panel_output" in schema.contract.produces_artifacts

    def test_category_is_sector_insurance(self) -> None:
        from openlia.llm.runtime.report_v2_2 import Category

        schema = _schema("insurance_valuation_panel")
        assert schema.directory.category == Category.SECTOR_INSURANCE

    def test_version_is_1_0_0(self) -> None:
        schema = _schema("insurance_valuation_panel")
        assert schema.version == "1.0.0"

    def test_not_deprecated(self) -> None:
        schema = _schema("insurance_valuation_panel")
        assert schema.deprecated_at_version is None

    def test_skill_doc_path_declared(self) -> None:
        schema = _schema("insurance_valuation_panel")
        assert schema.skill_doc is not None
        assert schema.skill_doc.path == "skills/insurance_valuation_panel.md"

    def test_skill_doc_file_exists(self) -> None:
        """Skill doc must exist at the declared relative path (from library_helpers/)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "insurance_valuation_panel.md")
        assert os.path.isfile(skill_path), f"Skill doc missing: {skill_path}"

    def test_skill_doc_estimated_tokens_in_range(self) -> None:
        schema = _schema("insurance_valuation_panel")
        assert schema.skill_doc is not None
        assert 1800 <= schema.skill_doc.estimated_tokens <= 2200


# ---------------------------------------------------------------------------
# 14. Artifact type registration
# ---------------------------------------------------------------------------


class TestArtifactType:
    def test_insurance_valuation_panel_output_in_registry(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry

        assert _registry.get("insurance_valuation_panel_output") is not None
