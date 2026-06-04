"""Baked Five Forces influence matrix + accessors. Pure; no I/O, no LLM, no RNG."""

from openlia.macro_research.quant.forces import ForceScores
from openlia.macro_research.quant.forces_network import (
    FORCE_LABELS,
    FORCE_ORDER,
    INFLUENCE,
    PERSISTENCE,
    analyze_force_network,
    coupling,
)


def test_force_order_is_the_five_forces() -> None:
    assert FORCE_ORDER == (
        "debt_money",
        "political",
        "geopolitical",
        "technology",
        "natural",
    )


def test_every_force_has_a_label() -> None:
    assert set(FORCE_LABELS) == set(FORCE_ORDER)


def test_influence_entries_in_range_and_zero_diagonal() -> None:
    assert set(INFLUENCE) == set(FORCE_ORDER)
    assert "debt_money" in INFLUENCE
    for driver in FORCE_ORDER:
        for driven in FORCE_ORDER:
            c = coupling(driver, driven)
            assert 0.0 <= c <= 1.0
            if driver == driven:
                assert c == 0.0


def test_coupling_reads_the_matrix_and_defaults_zero() -> None:
    assert coupling("debt_money", "political") == 0.6
    # An unspecified pair defaults to 0.0.
    assert coupling("technology", "natural") == 0.0


def test_persistence_is_a_fraction() -> None:
    assert 0.0 < PERSISTENCE < 1.0


_LOW = ForceScores(debt_money=3, political=3, geopolitical=3, technology=3, natural=3)


def test_all_low_has_no_active_edges_and_is_contained() -> None:
    out = analyze_force_network(_LOW)
    assert out.edges == ()
    assert out.contagion == 0.0
    assert out.contagion_label == "Contained"
    # Projections are always present, one per force.
    assert len(out.projections) == 5


def test_intense_driver_activates_its_outgoing_edges_ranked() -> None:
    # Only debt_money is intense (>=7); its two outgoing edges activate.
    scores = ForceScores(debt_money=8, political=3, geopolitical=3, technology=3, natural=3)
    out = analyze_force_network(scores)
    pairs = [(e.from_label, e.to_label, round(e.strength, 3)) for e in out.edges]
    assert pairs == [
        ("Debt / money", "Internal politics", 0.48),  # 0.6 * 0.8
        ("Debt / money", "Geopolitical", 0.32),  # 0.4 * 0.8
    ]
    # Ranked descending by strength.
    assert out.edges[0].strength >= out.edges[1].strength


def test_projection_is_clamped_and_pulled_up_by_intense_driver() -> None:
    scores = ForceScores(debt_money=8, political=3, geopolitical=3, technology=3, natural=3)
    out = analyze_force_network(scores)
    by_force = {p.force: p for p in out.projections}
    pol = by_force["Internal politics"]
    assert 0.0 <= pol.projected <= 10.0
    # Intense debt_money drives politics up next period.
    assert pol.delta > 0.0
    assert pol.projected > pol.current


def test_amplifier_and_absorber_labels() -> None:
    # debt_money is the strongest driver (out-couplings 0.6+0.4); when it is the
    # only intense force it is the amplifier. Internal politics has the largest
    # incoming coupling, so it is the absorber.
    scores = ForceScores(debt_money=9, political=2, geopolitical=2, technology=2, natural=2)
    out = analyze_force_network(scores)
    assert out.amplifier == "Debt / money"
    assert out.absorber == "Internal politics"


def test_contagion_buckets() -> None:
    # Only debt_money maxed: two edges (0.6, 0.4), mean 0.5 -> Self-reinforcing.
    hot = ForceScores(debt_money=10, political=0, geopolitical=0, technology=0, natural=0)
    out_hot = analyze_force_network(hot)
    assert out_hot.contagion == 0.5
    assert out_hot.contagion_label == "Self-reinforcing"
    # Everything maxed: many edges dilute the mean into the Spreading band.
    allmax = ForceScores(debt_money=10, political=10, geopolitical=10, technology=10, natural=10)
    out_all = analyze_force_network(allmax)
    assert 0.25 <= out_all.contagion < 0.5
    assert out_all.contagion_label == "Spreading"
