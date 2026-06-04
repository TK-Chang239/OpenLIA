"""Baked Four Seasons transition matrix + quadrant resolver. Pure; no I/O, no LLM."""

from openlia.macro_research.quant.markov import (
    SEASON_ORDER,
    TRANSITION_MATRIX,
    markov_outlook,
    resolve_quadrant,
)
from openlia.macro_research.quant.seasons import SeasonsInputs, classify_four_seasons


def test_season_order_is_the_four_quadrants() -> None:
    assert SEASON_ORDER == ("Spring", "Summer", "Autumn", "Winter")


def test_matrix_rows_are_stochastic() -> None:
    for season in SEASON_ORDER:
        row = TRANSITION_MATRIX[season]
        assert set(row) == set(SEASON_ORDER)
        assert all(p >= 0.0 for p in row.values())
        assert abs(sum(row.values()) - 1.0) < 1e-9


def test_resolve_quadrant_passes_through_canonical_seasons() -> None:
    spring = classify_four_seasons(
        SeasonsInputs(pmi=54.0, gdp_yoy=2.5, cpi_yoy=1.8, credit_spread=0.03)
    )
    assert spring.season == "Spring"
    assert resolve_quadrant(spring) == "Spring"

    autumn = classify_four_seasons(
        SeasonsInputs(pmi=47.0, gdp_yoy=0.2, cpi_yoy=4.0, credit_spread=0.06)
    )
    assert autumn.season == "Autumn"
    assert resolve_quadrant(autumn) == "Autumn"


def test_resolve_quadrant_maps_transitioning_via_marker() -> None:
    # Mixed signals -> classifier returns "Transitioning"; resolver picks the
    # nearest quadrant from the marker coordinates (growth x>=50, inflation y>=50).
    c = classify_four_seasons(SeasonsInputs(pmi=48.0, gdp_yoy=1.5, cpi_yoy=2.5, credit_spread=0.04))
    assert c.season == "Transitioning"
    # pmi 48 -> x = (48-45)*10 = 30 (<50, growth falling)
    # cpi 2.5 -> y = (2.5-1)*25 = 37.5 (<50, inflation falling) -> Winter
    assert resolve_quadrant(c) == "Winter"


def test_resolve_quadrant_each_marker_corner() -> None:
    from openlia.macro_research.quant.seasons import SeasonsClassification

    def _stub(x: int, y: int) -> SeasonsClassification:
        return SeasonsClassification(
            season="Transitioning",
            severity="amber",
            confidence="transitioning",
            growth_axis="flat",
            inflation_axis="steady",
            marker_x_pct=x,
            marker_y_pct=y,
        )

    assert resolve_quadrant(_stub(80, 20)) == "Spring"  # growth rising, inflation falling
    assert resolve_quadrant(_stub(80, 80)) == "Summer"  # growth rising, inflation rising
    assert resolve_quadrant(_stub(20, 80)) == "Autumn"  # growth falling, inflation rising
    assert resolve_quadrant(_stub(20, 20)) == "Winter"  # growth falling, inflation falling


def test_outlook_distribution_is_the_matrix_row() -> None:
    out = markov_outlook("Summer")
    assert out.current_season == "Summer"
    assert out.distribution == {
        "Spring": 0.07,
        "Summer": 0.65,
        "Autumn": 0.25,
        "Winter": 0.03,
    }
    assert abs(sum(out.distribution.values()) - 1.0) < 1e-9


def test_outlook_persistence_is_diagonal() -> None:
    out = markov_outlook("Autumn")
    assert out.persistence == 0.60


def test_outlook_most_likely_next_and_adverse() -> None:
    out = markov_outlook("Summer")
    assert out.most_likely_next == "Summer"  # persistence dominates
    assert out.adverse_season == "Autumn"
    assert out.adverse_prob == 0.25


def test_outlook_expected_dwell() -> None:
    out = markov_outlook("Spring")  # persistence 0.65
    assert abs(out.expected_dwell_quarters - (1.0 / (1.0 - 0.65))) < 1e-9


def test_outlook_horizon_is_matrix_power_and_stochastic() -> None:
    out = markov_outlook("Spring", steps=4)
    assert out.horizon_quarters == 4
    assert abs(sum(out.horizon_distribution.values()) - 1.0) < 1e-9
    # 1-step distribution is more concentrated on the current season than the
    # 4-step distribution (the chain mixes toward its stationary spread).
    assert out.horizon_distribution["Spring"] < out.distribution["Spring"]


def test_outlook_unknown_season_raises() -> None:
    import pytest

    with pytest.raises(ValueError, match="unknown season"):
        markov_outlook("Monsoon")
