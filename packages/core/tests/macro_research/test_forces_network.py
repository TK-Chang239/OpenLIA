"""Baked Five Forces influence matrix + accessors. Pure; no I/O, no LLM, no RNG."""

from openlia.macro_research.quant.forces_network import (
    FORCE_LABELS,
    FORCE_ORDER,
    PERSISTENCE,
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
