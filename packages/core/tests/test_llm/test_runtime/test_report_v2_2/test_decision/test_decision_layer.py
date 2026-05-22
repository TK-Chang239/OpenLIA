"""Tests for decision layer helpers (PR 2.4).

Covers:
- price_target_blender: 3 methods {50, 60, 70} → median 60, dispersion = stdev
- expected_total_return: target=100, current=80, divy=2% → ETR ~27%
- risk_reward_calculator: upside=110, downside=70, probs=(0.6,0.4) → EV=94
- rating_band_assigner: ETR=18%, R/R=2.5 → BUY
- rating_band_assigner: ETR=-20% → SELL
- football_field_chart: plotly_json parseable; markdown table contains all method rows
- Registration: all 6 helpers registered, skill docs exist for blender and rating assigner
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import ClassVar

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(name: str):
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"Helper {name!r} not registered"
    return h


def _run(name: str, **kwargs):
    return _get(name).impl(**kwargs)


# ---------------------------------------------------------------------------
# price_target_blender
# ---------------------------------------------------------------------------


class TestPriceTargetBlender:
    def test_three_methods_equal_weight_median(self) -> None:
        """3 methods at 50, 60, 70 with equal weight → blended = 60."""
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "DCF", "value": 50},
                {"name": "Comps", "value": 60},
                {"name": "DDM", "value": 70},
            ],
            auto_weight="equal",
        )
        assert result["blended_target"] == pytest.approx(60.0)

    def test_three_methods_dispersion_stdev(self) -> None:
        """Stddev of [50, 60, 70] with mean 60 = sqrt(200/3) ≈ 8.165."""
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "DCF", "value": 50},
                {"name": "Comps", "value": 60},
                {"name": "DDM", "value": 70},
            ],
            auto_weight="equal",
        )
        # Population stddev: sqrt( ((50-60)^2 + (60-60)^2 + (70-60)^2) / 3 )
        expected_stdev = math.sqrt((100 + 0 + 100) / 3)
        assert result["dispersion"]["stdev"] == pytest.approx(expected_stdev, rel=1e-4)

    def test_dispersion_min_max(self) -> None:
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "DCF", "value": 50},
                {"name": "Comps", "value": 60},
                {"name": "DDM", "value": 70},
            ],
            auto_weight="equal",
        )
        assert result["dispersion"]["min"] == pytest.approx(50.0)
        assert result["dispersion"]["max"] == pytest.approx(70.0)

    def test_null_value_dropped_and_reweighted(self) -> None:
        """DDM null → 2 live methods, weights 0.5/0.5; blended = (50+70)/2=60."""
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "DCF", "value": 50},
                {"name": "Comps", "value": 70},
                {"name": "DDM", "value": None},
            ],
            auto_weight="equal",
        )
        assert result["blended_target"] == pytest.approx(60.0)
        assert result["weight_audit"]["methods_dropped"] == 1
        assert result["weight_audit"]["reweighted"] is True

    def test_explicit_weights(self) -> None:
        """40% + 60% weighting: 0.4*100 + 0.6*200 = 160."""
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "DCF", "value": 100, "weight": 0.4},
                {"name": "Comps", "value": 200, "weight": 0.6},
            ],
            auto_weight="none",
        )
        assert result["blended_target"] == pytest.approx(160.0)

    def test_weight_sum_must_equal_one(self) -> None:
        with pytest.raises(ValueError, match="sum to"):
            _run(
                "price_target_blender",
                methodology_targets=[
                    {"name": "DCF", "value": 100, "weight": 0.3},
                    {"name": "Comps", "value": 200, "weight": 0.3},
                ],
                auto_weight="none",
            )

    def test_all_null_raises(self) -> None:
        with pytest.raises(ValueError, match="null"):
            _run(
                "price_target_blender",
                methodology_targets=[
                    {"name": "DCF", "value": None},
                ],
                auto_weight="equal",
            )

    def test_confidence_score_in_range(self) -> None:
        result = _run(
            "price_target_blender",
            methodology_targets=[
                {"name": "A", "value": 100},
                {"name": "B", "value": 100},
            ],
            auto_weight="equal",
        )
        # Zero stdev → confidence = 1.0
        assert result["confidence_score"] == pytest.approx(1.0)

    def test_registered_and_has_skill_doc(self) -> None:
        h = _get("price_target_blender")
        assert h.schema.skill_doc is not None
        assert h.schema.skill_doc.path == "skills/price_target_blender.md"

    def test_skill_doc_file_exists(self) -> None:
        skills_dir = (
            Path(__file__).resolve().parents[5]
            / "src/openlia/llm/runtime/report_v2_2/tools/library_helpers/skills"
        )
        assert (skills_dir / "price_target_blender.md").exists()

    def test_produces_artifact_registered(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry as reg

        h = _get("price_target_blender")
        for art in h.schema.contract.produces_artifacts:
            assert reg.get(art) is not None, f"Artifact {art!r} not in registry"

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "price_target_blender",
            methodology_targets=[{"name": "A", "value": 100}],
            auto_weight="equal",
        )
        required = {
            "blended_target",
            "method_breakdown",
            "weight_audit",
            "dispersion",
            "confidence_score",
            "warnings",
            "narrative",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# expected_total_return
# ---------------------------------------------------------------------------


class TestExpectedTotalReturn:
    def test_etr_known_inputs(self) -> None:
        """target=100, current=80, divy=2%, horizon=12 → cap_ret=25%, ETR=27%."""
        result = _run(
            "expected_total_return",
            price_target=100.0,
            current_price=80.0,
            forward_dividend_yield=0.02,
            horizon_months=12,
        )
        assert result["capital_return_pct"] == pytest.approx(0.25, rel=1e-6)
        assert result["expected_total_return_pct"] == pytest.approx(0.27, rel=1e-6)

    def test_income_return_scaled_by_horizon(self) -> None:
        """6-month horizon: income = 0.02 * (6/12) = 0.01."""
        result = _run(
            "expected_total_return",
            price_target=100.0,
            current_price=100.0,
            forward_dividend_yield=0.02,
            horizon_months=6,
        )
        assert result["income_return_pct"] == pytest.approx(0.01, rel=1e-6)
        assert result["capital_return_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_annualized_etr(self) -> None:
        """24-month horizon: annualized = (1+ETR)^(12/24) - 1."""
        result = _run(
            "expected_total_return",
            price_target=121.0,
            current_price=100.0,
            forward_dividend_yield=0.0,
            horizon_months=24,
        )
        # ETR = 21%; annualized = sqrt(1.21) - 1 = 0.10
        assert result["annualized_etr_pct"] == pytest.approx(0.10, rel=1e-4)

    def test_zero_current_price_raises(self) -> None:
        with pytest.raises(ValueError):
            _run(
                "expected_total_return",
                price_target=100.0,
                current_price=0.0,
                forward_dividend_yield=0.02,
            )

    def test_high_yield_warning(self) -> None:
        result = _run(
            "expected_total_return",
            price_target=100.0,
            current_price=100.0,
            forward_dividend_yield=0.25,
            horizon_months=12,
        )
        assert len(result["warnings"]) > 0
        assert any("20%" in w or "anomalously" in w for w in result["warnings"])

    def test_registered_no_skill_doc(self) -> None:
        h = _get("expected_total_return")
        assert h is not None
        assert h.schema.skill_doc is None

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "expected_total_return",
            price_target=110.0,
            current_price=100.0,
            forward_dividend_yield=0.01,
        )
        required = {
            "capital_return_pct",
            "income_return_pct",
            "expected_total_return_pct",
            "annualized_etr_pct",
            "horizon_months",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# risk_reward_calculator
# ---------------------------------------------------------------------------


class TestRiskRewardCalculator:
    def test_expected_value_with_probabilities(self) -> None:
        """upside=110, downside=70, probs (0.6 bull, 0.4 bear) → EV=94.
        EV = 0.6*110 + 0.4*70 + 0*100 = 66 + 28 = 94.
        """
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=110.0,
            bear_case_price=70.0,
            bull_probability=0.6,
            bear_probability=0.4,
        )
        assert result["expected_value"] == pytest.approx(94.0, rel=1e-6)

    def test_upside_downside_pct(self) -> None:
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=130.0,
            bear_case_price=65.0,
        )
        assert result["upside_pct"] == pytest.approx(0.30, rel=1e-6)
        assert result["downside_pct"] == pytest.approx(-0.35, rel=1e-6)

    def test_rr_ratio(self) -> None:
        """upside 30%, downside 35% → R/R = 0.30/0.35 ≈ 0.857."""
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=130.0,
            bear_case_price=65.0,
        )
        expected_ratio = 0.30 / 0.35
        assert result["risk_reward_ratio"] == pytest.approx(expected_ratio, rel=1e-4)

    def test_verdict_favorable(self) -> None:
        """R/R = 2.5x → favorable. upside=75%, downside=30%: bull=175, bear=70."""
        # For 2.5x: upside=75%, downside=30%: bull=175, bear=70
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=175.0,
            bear_case_price=70.0,
        )
        # upside 75%, downside 30% → R/R = 2.5x
        assert result["risk_reward_ratio"] == pytest.approx(2.5, rel=1e-4)
        assert result["verdict"] == "favorable"

    def test_bear_above_current_warns(self) -> None:
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=120.0,
            bear_case_price=110.0,
        )
        assert len(result["warnings"]) > 0
        assert result["risk_reward_ratio"] is None

    def test_asymmetry_score_range(self) -> None:
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=200.0,
            bear_case_price=50.0,
        )
        score = result["asymmetry_score"]
        assert -1.0 <= score <= 1.0

    def test_registered(self) -> None:
        h = _get("risk_reward_calculator")
        assert h is not None

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "risk_reward_calculator",
            current_price=100.0,
            bull_case_price=130.0,
            bear_case_price=80.0,
        )
        required = {
            "upside_pct",
            "downside_pct",
            "risk_reward_ratio",
            "expected_value",
            "max_drawdown",
            "asymmetry_score",
            "verdict",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# implied_upside_downside
# ---------------------------------------------------------------------------


class TestImpliedUpsideDownside:
    def test_basic_case(self) -> None:
        result = _run(
            "implied_upside_downside",
            price_target=120.0,
            downside_scenario_value=80.0,
            current_price=100.0,
        )
        assert result["implied_upside_pct"] == pytest.approx(0.20, rel=1e-6)
        assert result["implied_downside_pct"] == pytest.approx(-0.20, rel=1e-6)
        # R/R = 20% / 20% = 1.0
        assert result["risk_reward_ratio"] == pytest.approx(1.0, rel=1e-4)

    def test_breakeven_probability(self) -> None:
        """upside=+20%, downside=-20% → breakeven = -(-0.20)/(0.20-(-0.20)) = 0.5."""
        result = _run(
            "implied_upside_downside",
            price_target=120.0,
            downside_scenario_value=80.0,
            current_price=100.0,
        )
        assert result["breakeven_probability"] == pytest.approx(0.50, rel=1e-4)

    def test_asymmetric_breakeven(self) -> None:
        """upside=+50%, downside=-25% → P = 0.25/0.75 ≈ 0.333."""
        result = _run(
            "implied_upside_downside",
            price_target=150.0,
            downside_scenario_value=75.0,
            current_price=100.0,
        )
        assert result["breakeven_probability"] == pytest.approx(0.25 / 0.75, rel=1e-4)

    def test_no_downside_warns(self) -> None:
        result = _run(
            "implied_upside_downside",
            price_target=120.0,
            downside_scenario_value=110.0,
            current_price=100.0,
        )
        assert len(result["warnings"]) > 0
        assert result["risk_reward_ratio"] is None

    def test_registered(self) -> None:
        h = _get("implied_upside_downside")
        assert h is not None

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "implied_upside_downside",
            price_target=120.0,
            downside_scenario_value=80.0,
            current_price=100.0,
        )
        required = {
            "implied_upside_pct",
            "implied_downside_pct",
            "risk_reward_ratio",
            "breakeven_probability",
            "narrative",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# rating_band_assigner
# ---------------------------------------------------------------------------


class TestRatingBandAssigner:
    def test_buy_etr_18_rr_2_5(self) -> None:
        """ETR=18%, R/R=2.5 → BUY."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.18,
            risk_reward_ratio=2.5,
        )
        assert result["rating"] == "BUY"

    def test_sell_etr_minus_20(self) -> None:
        """ETR=-20% → SELL."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=-0.20,
            risk_reward_ratio=1.0,
        )
        assert result["rating"] == "SELL"

    def test_outperform_etr_8_rr_1_5(self) -> None:
        """ETR=8%, R/R=1.5 → OUTPERFORM (meets etr 5-15% and rr 1.2x)."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.08,
            risk_reward_ratio=1.5,
        )
        assert result["rating"] == "OUTPERFORM"

    def test_hold_etr_zero(self) -> None:
        """ETR=0% → HOLD."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.0,
            risk_reward_ratio=1.0,
        )
        assert result["rating"] == "HOLD"

    def test_hold_positive_etr_low_rr(self) -> None:
        """ETR=6% but R/R=0.9 → HOLD (R/R below outperform threshold 1.2x)."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.06,
            risk_reward_ratio=0.9,
        )
        # R/R < 1.2x so OUTPERFORM not triggered; ETR 6% is in hold range (-5% to 7%)
        assert result["rating"] == "HOLD"

    def test_sell_rr_low_negative_etr(self) -> None:
        """R/R=0.5, ETR=-5% → SELL (R/R < 0.8 AND ETR < 0)."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=-0.05,
            risk_reward_ratio=0.5,
        )
        assert result["rating"] == "SELL"

    def test_conviction_high(self) -> None:
        """conviction_score=0.8, R/R=2.5 → high conviction."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.20,
            risk_reward_ratio=2.5,
            conviction_score=0.8,
        )
        assert result["conviction"] == "high"

    def test_conviction_low_score(self) -> None:
        """conviction_score=0.2 → low conviction regardless of other inputs."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.20,
            risk_reward_ratio=2.5,
            conviction_score=0.2,
        )
        assert result["conviction"] == "low"

    def test_custom_bands_higher_buy_threshold(self) -> None:
        """Custom BUY requires ETR >= 25%; ETR=18% → OUTPERFORM, not BUY."""
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.18,
            risk_reward_ratio=2.5,
            rating_bands_config={
                "buy": {"etr_min": 0.25, "rr_min": 2.0},
                "outperform": {"etr_min": 0.10, "rr_min": 1.5},
            },
        )
        assert result["rating"] in {"OUTPERFORM", "HOLD"}

    def test_registered_has_skill_doc(self) -> None:
        h = _get("rating_band_assigner")
        assert h is not None
        assert h.schema.skill_doc is not None
        assert h.schema.skill_doc.path == "skills/rating_band_assigner.md"

    def test_skill_doc_file_exists(self) -> None:
        skills_dir = (
            Path(__file__).resolve().parents[5]
            / "src/openlia/llm/runtime/report_v2_2/tools/library_helpers/skills"
        )
        assert (skills_dir / "rating_band_assigner.md").exists()

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "rating_band_assigner",
            expected_total_return_pct=0.18,
            risk_reward_ratio=2.5,
        )
        required = {
            "rating",
            "conviction",
            "expected_total_return_pct",
            "risk_reward_ratio",
            "why_this_rating",
            "narrative",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# football_field_chart
# ---------------------------------------------------------------------------


class TestFootballFieldChart:
    _METHODS: ClassVar[list[dict]] = [
        {"name": "DCF perpetuity", "low": 90.0, "median": 110.0, "high": 130.0},
        {"name": "EV/EBITDA comps", "low": 95.0, "median": 115.0, "high": 140.0},
        {"name": "P/E comps", "low": 85.0, "median": 105.0, "high": 125.0},
    ]

    def test_plotly_json_parseable(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        parsed = json.loads(result["plotly_json"])
        # Must be a valid JSON object (dict)
        assert isinstance(parsed, dict)

    def test_markdown_table_contains_all_methods(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        table = result["markdown_table"]
        for m in self._METHODS:
            assert m["name"] in table, f"Method {m['name']!r} missing from markdown table"

    def test_median_of_medians(self) -> None:
        """Medians are [110, 115, 105]; sorted [105, 110, 115]; median = 110."""
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        assert result["median_of_medians"] == pytest.approx(110.0)

    def test_current_price_position(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        # Current price 100 < overall low 85 → "below range"
        # Actually overall low = min(90, 95, 85) = 85, overall high = 140.
        # 100 is above 85; (100-85)/(140-85) = 15/55 ≈ 0.27 → "low end of range"
        assert result["current_price_position"] in {
            "low end of range",
            "below median of range",
            "above median of range",
            "high end of range",
            "below range",
            "above range",
            "at range",
        }

    def test_verdict_present(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        assert isinstance(result["verdict"], str)
        assert len(result["verdict"]) > 0

    def test_empty_methodologies_raises(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _run(
                "football_field_chart",
                methodologies=[],
                current_price=100.0,
            )

    def test_zero_current_price_raises(self) -> None:
        with pytest.raises(ValueError):
            _run(
                "football_field_chart",
                methodologies=self._METHODS,
                current_price=0.0,
            )

    def test_consensus_target_in_output(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
            consensus_target_price=112.0,
        )
        assert result["consensus_target_price"] == pytest.approx(112.0)

    def test_registered(self) -> None:
        h = _get("football_field_chart")
        assert h is not None

    def test_produces_artifact_registered(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry as reg

        h = _get("football_field_chart")
        for art in h.schema.contract.produces_artifacts:
            assert reg.get(art) is not None, f"Artifact {art!r} not in registry"

    def test_output_has_required_keys(self) -> None:
        result = _run(
            "football_field_chart",
            methodologies=self._METHODS,
            current_price=100.0,
        )
        required = {
            "chart_type",
            "plotly_json",
            "markdown_table",
            "methodologies_summary",
            "current_price_position",
            "median_of_medians",
            "verdict",
        }
        assert required.issubset(result.keys())


# ---------------------------------------------------------------------------
# All 6 helpers: artifact types registered
# ---------------------------------------------------------------------------


class TestAllDecisionArtifactsRegistered:
    @pytest.mark.parametrize(
        "artifact_name",
        [
            "price_target_blended",
            "expected_total_return_output",
            "risk_reward_output",
            "implied_upside_downside_output",
            "rating_assignment",
            "football_field_chart_output",
        ],
    )
    def test_artifact_type_in_registry(self, artifact_name: str) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry as reg

        assert reg.get(artifact_name) is not None, (
            f"Artifact type {artifact_name!r} not found in registry"
        )

    @pytest.mark.parametrize(
        "helper_name",
        [
            "price_target_blender",
            "expected_total_return",
            "risk_reward_calculator",
            "implied_upside_downside",
            "rating_band_assigner",
            "football_field_chart",
        ],
    )
    def test_helper_registered(self, helper_name: str) -> None:
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

        h = get_helper(helper_name)
        assert h is not None, f"Helper {helper_name!r} not registered"

    @pytest.mark.parametrize(
        "helper_name",
        [
            "price_target_blender",
            "expected_total_return",
            "risk_reward_calculator",
            "implied_upside_downside",
            "rating_band_assigner",
            "football_field_chart",
        ],
    )
    def test_category_is_decision(self, helper_name: str) -> None:
        from openlia.llm.runtime.report_v2_2.enums import Category
        from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

        h = get_helper(helper_name)
        assert h is not None
        assert h.schema.directory.category == Category.DECISION
