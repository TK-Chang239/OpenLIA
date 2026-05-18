from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.pack import PayloadView, compile_pack
from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


def _entry(id: int, identifier: str, payload: dict) -> ManifestEntry:
    return ManifestEntry(
        id=id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=payload,
        retrieved_at="2026-05-17T20:00:00Z",
    )


def test_compile_single_deterministic_fact() -> None:
    reg = FactRegistry()

    @reg.register("market_cap", tier="deterministic", depends_on=[])
    def _mc(payloads: PayloadView, facts) -> Fact:
        ident = "get_fundamentals_data/NET.US"
        mc = payloads.by_identifier(ident)["Highlights"]["MarketCapitalization"]
        return Fact(
            name="market_cap",
            value=mc,
            source_ids=[payloads.manifest_id_for(ident)],
            extractor="deterministic",
        )

    manifest = [
        _entry(
            1,
            "get_fundamentals_data/NET.US",
            {"Highlights": {"MarketCapitalization": 30_200_000_000}},
        ),
    ]
    pack = compile_pack(registry=reg, manifest=manifest, requested_facts=["market_cap"])
    assert pack.get("market_cap").value == 30_200_000_000
    assert pack.get("market_cap").source_ids == [1]


def test_compile_compute_inherits_union_of_sources() -> None:
    reg = FactRegistry()

    @reg.register("revenue_y1", tier="deterministic", depends_on=[])
    def _r1(payloads, facts):
        return Fact(name="revenue_y1", value=100, source_ids=[1], extractor="deterministic")

    @reg.register("revenue_y3", tier="deterministic", depends_on=[])
    def _r3(payloads, facts):
        return Fact(name="revenue_y3", value=180, source_ids=[2], extractor="deterministic")

    @reg.register("revenue_cagr_2y", tier="compute", depends_on=["revenue_y1", "revenue_y3"])
    def _c(payloads, facts):
        v1 = facts["revenue_y1"].value
        v3 = facts["revenue_y3"].value
        return Fact(
            name="revenue_cagr_2y",
            value=(v3 / v1) ** 0.5 - 1,
            source_ids=sorted({*facts["revenue_y1"].source_ids, *facts["revenue_y3"].source_ids}),
            extractor="compute",
        )

    manifest = [_entry(1, "rev_y1", {}), _entry(2, "rev_y3", {})]
    pack = compile_pack(registry=reg, manifest=manifest, requested_facts=["revenue_cagr_2y"])
    assert pack.get("revenue_cagr_2y").source_ids == [1, 2]


def test_slice_for_section_returns_only_requested_names() -> None:
    reg = FactRegistry()
    for n in ["a", "b", "c"]:

        @reg.register(n, tier="deterministic", depends_on=[])
        def _f(payloads, facts, _name=n):
            return Fact(name=_name, value=1, source_ids=[1], extractor="deterministic")

    pack = compile_pack(
        registry=reg,
        manifest=[_entry(1, "x", {})],
        requested_facts=["a", "b", "c"],
    )
    sliced = pack.slice_for(["a", "c"])
    assert set(sliced.keys()) == {"a", "c"}


def test_slice_for_unknown_fact_raises() -> None:
    reg = FactRegistry()

    @reg.register("known", tier="deterministic", depends_on=[])
    def _f(payloads, facts):
        return Fact(name="known", value=1, source_ids=[1], extractor="deterministic")

    pack = compile_pack(registry=reg, manifest=[_entry(1, "x", {})], requested_facts=["known"])
    try:
        pack.slice_for(["unknown"])
    except KeyError as e:
        assert "unknown" in str(e)
    else:
        raise AssertionError("expected KeyError")
