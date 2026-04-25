"""evaluate_ruleset semantics."""

from __future__ import annotations

import pytest
from openlia.formula import FormulaError, Rule, RuleSet, evaluate_ruleset


def test_first_match_wins():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="value > 10", label="hot"),
            Rule(status="amber", formula="value > 5", label="warm"),
            Rule(status="green", formula="true", label="cool"),
        ),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 20})
    assert r.status == "red"
    assert r.label == "hot"


def test_second_rule_matches_when_first_false():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="value > 100", label="x"),
            Rule(status="amber", formula="value > 5", label="warm"),
            Rule(status="green", formula="true", label="cool"),
        ),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 7})
    assert r.status == "amber"


def test_default_green_when_no_rule_matches():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="value > 100", label="x"),
            Rule(status="amber", formula="value > 50", label="y"),
        ),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 10})
    assert r.status == "green"
    assert r.matched_rule_index is None


def test_dict_input_supported():
    r = evaluate_ruleset(
        {
            "rules": [
                {"status": "red", "formula": "value > 5", "label": "hit"},
                {"status": "green", "formula": "true", "label": "ok"},
            ],
        },
        raw_series={},
        scalars={"value": 10},
    )
    assert r.status == "red"


def test_label_interpolation():
    rs = RuleSet(
        rules=(Rule(status="red", formula="value > 5", label="value is {value}"),),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 7})
    assert "7" in r.label


def test_label_missing_placeholder_fallback_keeps_raw():
    rs = RuleSet(
        rules=(Rule(status="red", formula="value > 0", label="ghost: {missing}"),),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 1})
    # Missing placeholder kept intact (fallback dict).
    assert "{missing}" in r.label


def test_params_override_reserved_raises():
    rs = RuleSet(
        rules=(Rule(status="green", formula="true", label="ok"),),
    )
    with pytest.raises(FormulaError):
        evaluate_ruleset(rs, raw_series={"price": [1.0]}, scalars={}, params={"ma200": 1.0})


def test_scalars_override_reserved_raises():
    rs = RuleSet(
        rules=(Rule(status="green", formula="true", label="ok"),),
    )
    with pytest.raises(FormulaError):
        evaluate_ruleset(rs, raw_series={"price": [1.0]}, scalars={"price": 99.0})


def test_streak_days_works_when_streak_condition_supplied():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="streak_days >= 3", label="streak {streak_days}"),
            Rule(status="green", formula="true", label="ok"),
        ),
        streak_condition="price > 80",
    )
    r = evaluate_ruleset(rs, raw_series={"price": [85.0, 90.0, 95.0]}, scalars={})
    assert r.status == "red"
    assert "3" in r.label


def test_missing_streak_condition_raises_when_rule_uses_streak_days():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="streak_days >= 1", label="x"),
            Rule(status="green", formula="true", label="ok"),
        ),
        streak_condition=None,
    )
    with pytest.raises(FormulaError):
        evaluate_ruleset(rs, raw_series={"price": [85.0]}, scalars={})


def test_resolved_values_includes_referenced_identifiers():
    rs = RuleSet(
        rules=(Rule(status="red", formula="value > 5", label="x"),),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={"value": 10, "other": 99})
    assert r.resolved_values.get("value") == 10
    # `other` not referenced -> not in resolved_values
    assert "other" not in r.resolved_values


def test_derived_scalars_returned_when_price_series_long_enough():
    closes = [100.0 + i for i in range(250)]
    rs = RuleSet(rules=(Rule(status="green", formula="true", label="ok"),))
    r = evaluate_ruleset(rs, raw_series={"price": closes}, scalars={})
    assert r.derived_scalars["ma200"] is not None


def test_bad_rule_formula_does_not_abort_ruleset():
    rs = RuleSet(
        rules=(
            Rule(status="red", formula="ghost > 1", label="x"),  # unknown var
            Rule(status="green", formula="true", label="ok"),
        ),
    )
    r = evaluate_ruleset(rs, raw_series={}, scalars={})
    assert r.status == "green"
    assert any("rule 0" in w for w in r.warnings)
