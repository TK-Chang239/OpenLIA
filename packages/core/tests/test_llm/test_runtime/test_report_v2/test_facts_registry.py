from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.registry import (
    FactRegistry,
    register_fact,
)
from openlia.llm.runtime.report_v2.types import Fact


def test_register_and_retrieve_deterministic() -> None:
    reg = FactRegistry()

    @reg.register("dummy_price", tier="deterministic", depends_on=[])
    def _extract(payloads, facts):
        return Fact(
            name="dummy_price",
            value=42.0,
            source_ids=[1],
            extractor="deterministic",
            depends_on=[],
        )

    entry = reg.get("dummy_price")
    assert entry.name == "dummy_price"
    assert entry.tier == "deterministic"
    assert entry.depends_on == []


def test_duplicate_registration_rejected() -> None:
    reg = FactRegistry()

    @reg.register("x", tier="deterministic", depends_on=[])
    def _a(payloads, facts):
        return Fact(name="x", value=1, source_ids=[1], extractor="deterministic")

    with pytest.raises(ValueError, match="already registered"):
        @reg.register("x", tier="compute", depends_on=[])
        def _b(payloads, facts):
            return Fact(name="x", value=2, source_ids=[1], extractor="compute")


def test_unknown_dependency_rejected_at_get_resolution_order() -> None:
    reg = FactRegistry()

    @reg.register("downstream", tier="compute", depends_on=["does_not_exist"])
    def _f(payloads, facts):
        return Fact(name="downstream", value=0, source_ids=[1], extractor="compute")

    with pytest.raises(ValueError, match="unknown dependency"):
        reg.resolution_order(["downstream"])


def test_resolution_order_respects_dag() -> None:
    reg = FactRegistry()

    @reg.register("a", tier="deterministic", depends_on=[])
    def _a(payloads, facts):
        return Fact(name="a", value=1, source_ids=[1], extractor="deterministic")

    @reg.register("b", tier="compute", depends_on=["a"])
    def _b(payloads, facts):
        return Fact(name="b", value=2, source_ids=[1], extractor="compute")

    @reg.register("c", tier="compute", depends_on=["a", "b"])
    def _c(payloads, facts):
        return Fact(name="c", value=3, source_ids=[1], extractor="compute")

    order = reg.resolution_order(["c"])
    assert order == ["a", "b", "c"]


def test_resolution_order_dedupes_shared_deps() -> None:
    reg = FactRegistry()

    @reg.register("shared", tier="deterministic", depends_on=[])
    def _s(payloads, facts):
        return Fact(name="shared", value=1, source_ids=[1], extractor="deterministic")

    @reg.register("x", tier="compute", depends_on=["shared"])
    def _x(payloads, facts):
        return Fact(name="x", value=1, source_ids=[1], extractor="compute")

    @reg.register("y", tier="compute", depends_on=["shared"])
    def _y(payloads, facts):
        return Fact(name="y", value=1, source_ids=[1], extractor="compute")

    order = reg.resolution_order(["x", "y"])
    assert order.count("shared") == 1
    assert order.index("shared") < order.index("x")
    assert order.index("shared") < order.index("y")


def test_cycle_detection() -> None:
    reg = FactRegistry()

    @reg.register("p", tier="compute", depends_on=["q"])
    def _p(payloads, facts):
        return Fact(name="p", value=0, source_ids=[1], extractor="compute")

    @reg.register("q", tier="compute", depends_on=["p"])
    def _q(payloads, facts):
        return Fact(name="q", value=0, source_ids=[1], extractor="compute")

    with pytest.raises(ValueError, match="cycle"):
        reg.resolution_order(["p"])


def test_global_default_registry_singleton() -> None:
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    @register_fact("globally_registered", tier="deterministic", depends_on=[])
    def _f(payloads, facts):
        return Fact(name="globally_registered", value=0, source_ids=[1], extractor="deterministic")

    assert "globally_registered" in default_registry.names()
