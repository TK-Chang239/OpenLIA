# packages/core/tests/test_llm/test_runtime/test_report_v2/test_extractors_compute.py
from __future__ import annotations

import json
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
from openlia.llm.runtime.report_v2.facts.pack import compile_pack
from openlia.llm.runtime.report_v2.facts.registry import default_registry
from openlia.llm.runtime.report_v2.types import ManifestEntry

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


def _manifest() -> list[ManifestEntry]:
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


def test_revenue_cagr_3y_computed_correctly() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_manifest(),
        requested_facts=["revenue_cagr_3y"],
    )
    # 2021 → 2024 revenue: 656.4M → 1670M, CAGR = (1670/656.4)^(1/3) - 1 = 0.365 approx
    assert pack.get("revenue_cagr_3y").value == pytest.approx(0.365, abs=0.005)


def test_revenue_cagr_3y_inherits_source_from_revenue_annual() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_manifest(),
        requested_facts=["revenue_cagr_3y"],
    )
    assert pack.get("revenue_cagr_3y").source_ids == [1]
    assert pack.get("revenue_cagr_3y").extractor == "compute"


def test_gross_margin_ttm_uses_latest_year() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_manifest(),
        requested_facts=["gross_margin_ttm"],
    )
    # 2024: 1290/1670 = 0.7725
    assert pack.get("gross_margin_ttm").value == pytest.approx(0.7725, abs=0.001)
