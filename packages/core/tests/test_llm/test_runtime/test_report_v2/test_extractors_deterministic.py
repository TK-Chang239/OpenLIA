from __future__ import annotations

import json
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import FactRegistry
from openlia.llm.runtime.report_v2.types import ManifestEntry

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


def _load_fundamentals_manifest() -> list[ManifestEntry]:
    payload = json.loads(FIXTURE.read_text())
    return [
        ManifestEntry(
            id=1,
            kind="fetch",
            provider="eodhd",
            identifier="get_fundamentals_data/NET.US",
            raw_payload=payload,
            retrieved_at="2026-05-17T20:00:00Z",
        )
    ]


def _registry_with_stock_initiation_facts() -> FactRegistry:
    from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    return default_registry


@pytest.mark.parametrize(
    "fact_name,expected",
    [
        ("market_cap", 30_200_000_000),
        ("pe_ratio_ttm", 142.1),
        ("sector", "Technology"),
        ("company_name", "Cloudflare, Inc."),
    ],
)
def test_deterministic_extractors_pull_from_fixture(fact_name: str, expected) -> None:
    reg = _registry_with_stock_initiation_facts()
    pack = compile_pack(
        registry=reg,
        manifest=_load_fundamentals_manifest(),
        requested_facts=[fact_name],
    )
    assert pack.get(fact_name).value == expected
    assert pack.get(fact_name).source_ids == [1]


def test_revenue_annual_returns_five_year_series() -> None:
    reg = _registry_with_stock_initiation_facts()
    pack = compile_pack(
        registry=reg,
        manifest=_load_fundamentals_manifest(),
        requested_facts=["revenue_annual"],
    )
    series = pack.get("revenue_annual").value
    assert len(series) == 5
    assert series[-1] == 1_670_000_000
    assert series[0] == 431_100_000
