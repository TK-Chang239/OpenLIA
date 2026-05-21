"""Tests for param_resolver — explicit → derived → default → unresolved priority chain."""

from __future__ import annotations

from unittest.mock import MagicMock

from openlia.llm.runtime.report_v2.pipeline.param_resolver import resolve_params
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperRegistration,
    HelperSchema,
    register_helper,
    reset_helpers_for_tests,
)


def _make_dcf_helper() -> None:
    """Register DCF helper: base_revenue (required, derivable) and discount_rate (has default)."""
    schema = HelperSchema(
        name="dcf",
        description="DCF model",
        params={
            "base_revenue": HelperParam(
                type="float",
                required=True,
                derivation="extract base_revenue from research_pool financials",
                description="Base revenue figure",
            ),
            "discount_rate": HelperParam(
                type="float",
                default=0.1,
                required=False,
                description="Discount rate",
            ),
        },
    )
    register_helper(
        HelperRegistration(
            schema=schema,
            execute=lambda **kw: {"npv": 100},
            available=True,
        )
    )


class TestExplicitWins:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_explicit_wins(self):
        llm = MagicMock()
        result = resolve_params(
            "dcf",
            explicit={"base_revenue": 500.0, "discount_rate": 0.08},
            research_pool={},
            llm=llm,
        )
        assert not result.failed
        assert result.resolved["base_revenue"] == 500.0
        assert result.resolved["discount_rate"] == 0.08
        assert result.provenance["base_revenue"] == "explicit"
        assert result.provenance["discount_rate"] == "explicit"
        llm.call.assert_not_called()


class TestDefaultFallback:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_default_when_no_explicit_no_derivation(self):
        llm = MagicMock()
        # LLM returns None for derivation of base_revenue
        llm.call.return_value = {"value": None}
        result = resolve_params(
            "dcf",
            explicit={},
            research_pool={},
            llm=llm,
        )
        # discount_rate should use default
        assert result.resolved.get("discount_rate") == 0.1
        assert result.provenance.get("discount_rate") == "default"


class TestDerivation:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_derivation_runs_when_missing_required(self):
        llm = MagicMock()
        llm.call.return_value = {"value": 750.0}
        result = resolve_params(
            "dcf",
            explicit={},
            research_pool={"financials": {"revenue": 750}},
            llm=llm,
        )
        assert not result.failed
        assert result.resolved["base_revenue"] == 750.0
        assert result.provenance["base_revenue"] == "derived"
        llm.call.assert_called_once()


class TestUnresolvableRequired:
    def setup_method(self):
        reset_helpers_for_tests()
        _make_dcf_helper()

    def test_unresolvable_required_marks_failed(self):
        llm = MagicMock()
        llm.call.return_value = {"value": None}
        result = resolve_params(
            "dcf",
            explicit={},
            research_pool={},
            llm=llm,
        )
        assert result.failed
        assert "base_revenue" in result.unresolved
        assert result.reason is not None
