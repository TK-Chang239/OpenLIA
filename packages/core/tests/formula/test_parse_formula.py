"""parse_formula primitive: AST + identifier listing."""

from __future__ import annotations

import pytest
from openlia.formula import FormulaError, parse_formula


def test_extracts_simple_identifiers():
    p = parse_formula("a + b * c")
    assert set(p.identifiers) == {"a", "b", "c"}


def test_extracts_history_identifiers():
    p = parse_formula("price[t-1] - price[t-5]")
    assert set(p.identifiers) == {"price"}


def test_extracts_through_function_call():
    p = parse_formula("rolling_mean(price, n) + slope(value, k)")
    assert set(p.identifiers) == {"price", "value", "n", "k"}


def test_unknown_identifiers_against_known_set():
    p = parse_formula(
        "a + ghost * c",
        known_names={"a", "c"},
    )
    assert "ghost" in p.unknown_identifiers
    assert "a" not in p.unknown_identifiers
    assert "c" not in p.unknown_identifiers


def test_unknown_identifiers_empty_when_all_known():
    p = parse_formula(
        "x + y",
        known_names={"x", "y"},
    )
    assert p.unknown_identifiers == []


def test_no_known_set_means_no_unknowns_reported():
    p = parse_formula("a + b")
    assert p.unknown_identifiers == []


def test_mixed_valid_and_invalid():
    p = parse_formula(
        "price > threshold and missing_metric > 0",
        known_names={"price", "threshold"},
    )
    assert "missing_metric" in p.unknown_identifiers
    assert "price" not in p.unknown_identifiers


def test_invalid_syntax_raises():
    with pytest.raises(FormulaError):
        parse_formula("1 +")


def test_ast_is_returned():
    p = parse_formula("1 + 2")
    assert p.ast is not None


def test_warnings_field_exists_and_is_list():
    p = parse_formula("a + b")
    assert isinstance(p.warnings, list)


def test_identifiers_sorted():
    p = parse_formula("z + a + m")
    assert p.identifiers == sorted(p.identifiers)


def test_unknown_identifiers_sorted():
    p = parse_formula(
        "z + a + m",
        known_names=set(),
    )
    assert p.unknown_identifiers == sorted(p.unknown_identifiers)


def test_function_call_callee_not_in_identifiers():
    """Function names like `min`, `max`, `pct_change` are not identifiers."""
    p = parse_formula("min(a, b)")
    assert "min" not in p.identifiers
    assert {"a", "b"} <= set(p.identifiers)


def test_string_literal_not_identifier():
    p = parse_formula('days_since("FOMC")', known_names=set())
    # "FOMC" is a string literal, not an identifier.
    assert "FOMC" not in p.identifiers
