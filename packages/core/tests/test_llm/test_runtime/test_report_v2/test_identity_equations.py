"""Tests for the PR 4 identity-equation spec + evaluator.

Identity equations of the shape `lhs_op_a OP lhs_op_b ≈ rhs` are now declared
per-template. The default equity-research loader populates the three standard
equations (market_cap, op income, upside reconciliation). Custom templates may
add their own; templates without any declared equations get no algebraic
cross-section checks but still benefit from the other universal validators.

Prose-vs-fact regex checks and categorical rating-coherence rules stay in
`_check_identity_equations` itself for v1 — they don't fit the declarative
A-op-B-vs-C shape.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.types import Fact


def _fact(name: str, value: float) -> Fact:
    return Fact(
        name=name,
        value=value,
        source_ids=[0],
        extractor="deterministic",
        data_as_of=datetime.now(UTC),
    )


def test_identity_equation_spec_constructs_with_required_fields() -> None:
    from openlia.llm.runtime.report_v2.validators.identity_equations import IdentityEquationSpec

    eq = IdentityEquationSpec(
        name="market_cap_check",
        lhs_a="current_price",
        op="mul",
        lhs_b="shares_outstanding",
        rhs="market_cap",
        tolerance_pct=2.0,
    )

    assert eq.name == "market_cap_check"
    assert eq.op == "mul"
    assert eq.tolerance_pct == 2.0


def test_evaluate_equations_returns_no_failures_when_within_tolerance() -> None:
    from openlia.llm.runtime.report_v2.validators.identity_equations import (
        IdentityEquationSpec,
        evaluate_equations,
    )

    facts = {
        "current_price": _fact("current_price", 100.0),
        "shares_outstanding": _fact("shares_outstanding", 1_000_000.0),
        "market_cap": _fact("market_cap", 100_000_000.0),
    }
    eq = IdentityEquationSpec(
        name="market_cap_check",
        lhs_a="current_price",
        op="mul",
        lhs_b="shares_outstanding",
        rhs="market_cap",
        tolerance_pct=2.0,
    )

    failures = evaluate_equations([eq], facts)

    assert failures == []


def test_evaluate_equations_returns_failure_when_outside_tolerance() -> None:
    from openlia.llm.runtime.report_v2.validators.identity_equations import (
        IdentityEquationSpec,
        evaluate_equations,
    )

    facts = {
        "current_price": _fact("current_price", 100.0),
        "shares_outstanding": _fact("shares_outstanding", 1_000_000.0),
        "market_cap": _fact("market_cap", 50_000_000.0),  # 50% off
    }
    eq = IdentityEquationSpec(
        name="market_cap_check",
        lhs_a="current_price",
        op="mul",
        lhs_b="shares_outstanding",
        rhs="market_cap",
        tolerance_pct=2.0,
    )

    failures = evaluate_equations([eq], facts)

    assert len(failures) == 1
    assert failures[0].fact_name == "market_cap"
    assert failures[0].failure_type == "identity_equation_violation"


def test_evaluate_equations_skips_when_any_operand_missing() -> None:
    from openlia.llm.runtime.report_v2.validators.identity_equations import (
        IdentityEquationSpec,
        evaluate_equations,
    )

    facts = {
        "current_price": _fact("current_price", 100.0),
        # shares_outstanding missing
        "market_cap": _fact("market_cap", 100_000_000.0),
    }
    eq = IdentityEquationSpec(
        name="market_cap_check",
        lhs_a="current_price",
        op="mul",
        lhs_b="shares_outstanding",
        rhs="market_cap",
        tolerance_pct=2.0,
    )

    failures = evaluate_equations([eq], facts)

    assert failures == []  # operand missing → silently skip


def test_default_template_declares_canonical_identity_equations() -> None:
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()

    equation_names = {eq.name for eq in spec.identity_equations}
    assert "market_cap_check" in equation_names
    assert "operating_income_check" in equation_names
