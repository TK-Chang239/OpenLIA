"""End-to-end smoke tests for Plan 17 against shapes Plans 18 and 19 will use."""

from __future__ import annotations

import pytest
from openlia.formula import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    RequirementRef,
    extract_requirements,
    parse,
)


def test_public_api_exports():
    # Names that Plans 18 and 19 depend on — locked.
    from openlia.formula import (  # noqa: F401
        EvaluationContext,
        Expression,
        FormulaEngine,
        FormulaError,
        RequirementRef,
        extract_requirements,
        parse,
    )


def test_panic_thermometer_like_threshold_rule():
    """Mirrors a PT red-status rule: oil streak above MA200 times a buffer."""
    engine = FormulaEngine()
    # A simplified form (the real spec injects `streak_days`; here we test
    # the building blocks).
    source = "price > rolling_mean(price, 20) * 1.15 and pct_change(price, 5) > 3.0"

    # Canned 25-bar series ending with an upward break-out.
    history = {
        "price": [
            70.0,
            70.5,
            70.3,
            70.8,
            71.0,
            71.5,
            72.0,
            72.5,
            73.0,
            73.2,
            73.4,
            73.8,
            74.0,
            74.5,
            75.0,
            75.2,
            75.5,
            76.0,
            76.4,
            76.8,
            77.0,
            82.0,
            86.0,
            88.0,
            91.0,
        ]
    }
    ctx = EvaluationContext(
        values={"price": history["price"][-1]},
        history=history,
    )

    assert engine.evaluate(source, ctx) is True

    # Requirement extraction yields a single series with the larger lookback.
    refs = extract_requirements(source)
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_macro_research_like_metric_formula():
    """Mirrors an MR T2 metric: weighted combination of sub-indicators."""
    engine = FormulaEngine()
    # Weighted mean with a guard for missing data.
    source = (
        "(debt_to_gdp * 0.5 + credit_growth * 0.3 + short_rate * 0.2) if debt_to_gdp > 0 else 0"
    )
    ctx = EvaluationContext(
        values={
            "debt_to_gdp": 120.0,
            "credit_growth": 4.5,
            "short_rate": 1.75,
        }
    )
    value = engine.evaluate(source, ctx)
    assert value == pytest.approx(61.7, rel=1e-3)

    refs = extract_requirements(source)
    assert refs == [
        RequirementRef(name="credit_growth", max_lag=0),
        RequirementRef(name="debt_to_gdp", max_lag=0),
        RequirementRef(name="short_rate", max_lag=0),
    ]


def test_accepts_prebuilt_ast_for_hot_path():
    engine = FormulaEngine()
    tree = parse("price > 100 and not recession")
    ctx = EvaluationContext(values={"price": 125.0, "recession": False})
    assert engine.evaluate(tree, ctx) is True


def test_error_propagation_across_parse_and_eval():
    engine = FormulaEngine()
    # Unknown identifier surfaces as FormulaError at eval time, with position.
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("price > threshold", EvaluationContext(values={"price": 1.0}))
    assert "threshold" in str(exc.value)
    assert exc.value.line == 1
