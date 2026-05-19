"""Peer fundamentals extractor tests.

Verifies that when the manifest contains multiple `get_fundamentals_data/*`
entries (subject + peers), the peer extractors emit per-ticker dicts with
source_ids pointing only to peer manifest entries — not the subject's.
"""

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


def _entry(id: int, identifier: str, payload: dict) -> ManifestEntry:
    return ManifestEntry(
        id=id,
        kind="fetch",
        provider="eodhd",
        identifier=identifier,
        raw_payload=payload,
        retrieved_at="2026-05-19T05:00:00Z",
    )


def _peer_payload(*, pe: float, rev_years: list[float], gp_years: list[float]) -> dict:
    """Minimal EODHD-shape payload with the fields peer extractors need."""
    assert len(rev_years) == len(gp_years) == 5
    yearly_rev = {f"{2020 + i}-12-31": {"totalRevenue": v} for i, v in enumerate(rev_years)}
    yearly_gp = {f"{2020 + i}-12-31": {"grossProfit": v} for i, v in enumerate(gp_years)}
    # Merge each year's metrics into one row keyed by date.
    yearly: dict[str, dict[str, float]] = {}
    for date, row in yearly_rev.items():
        yearly.setdefault(date, {}).update(row)
    for date, row in yearly_gp.items():
        yearly.setdefault(date, {}).update(row)
    return {
        "Highlights": {"PERatio": pe},
        "Financials": {"Income_Statement": {"yearly": yearly}},
    }


def _subject_manifest() -> list[ManifestEntry]:
    """Subject manifest using the NET fundamentals fixture."""
    payload = json.loads(FIXTURE.read_text())
    return [_entry(1, "get_fundamentals_data/NET.US", payload)]


def _multi_ticker_manifest() -> list[ManifestEntry]:
    """Subject (NET) plus three peer tickers with synthetic payloads."""
    return [
        *_subject_manifest(),
        _entry(
            11,
            "get_fundamentals_data/MSFT.US",
            _peer_payload(
                pe=38.2,
                rev_years=[143000, 168000, 198000, 211000, 245000],
                gp_years=[96000, 116000, 135000, 144000, 170000],
            ),
        ),
        _entry(
            12,
            "get_fundamentals_data/ORCL.US",
            _peer_payload(
                pe=25.1,
                rev_years=[39000, 40500, 42400, 50000, 53000],
                gp_years=[31000, 32000, 33000, 38000, 40000],
            ),
        ),
        _entry(
            13,
            "get_fundamentals_data/SAP.US",
            _peer_payload(
                pe=31.0,
                rev_years=[27500, 27800, 30900, 31200, 34300],
                gp_years=[20100, 20500, 22000, 22600, 24900],
            ),
        ),
    ]


def test_peer_pe_ratio_ttm_returns_dict_keyed_by_ticker() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_multi_ticker_manifest(),
        requested_facts=["peer_pe_ratio_ttm"],
        subject_ticker="NET",
    )
    fact = pack.get("peer_pe_ratio_ttm")
    assert fact.value == {"MSFT": 38.2, "ORCL": 25.1, "SAP": 31.0}
    assert fact.source_ids == [11, 12, 13]


def test_peer_revenue_cagr_3y_computes_per_peer() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_multi_ticker_manifest(),
        requested_facts=["peer_revenue_cagr_3y"],
        subject_ticker="NET",
    )
    fact = pack.get("peer_revenue_cagr_3y")
    assert set(fact.value.keys()) == {"MSFT", "ORCL", "SAP"}
    # MSFT: 245000/168000 over 3 years ≈ 13.4%
    assert pytest.approx(fact.value["MSFT"], rel=1e-3) == (245000 / 168000) ** (1 / 3) - 1
    assert fact.source_ids == [11, 12, 13]


def test_peer_gross_margin_ttm_computes_per_peer() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_multi_ticker_manifest(),
        requested_facts=["peer_gross_margin_ttm"],
        subject_ticker="NET",
    )
    fact = pack.get("peer_gross_margin_ttm")
    assert pytest.approx(fact.value["MSFT"], rel=1e-3) == 170000 / 245000
    assert pytest.approx(fact.value["ORCL"], rel=1e-3) == 40000 / 53000
    assert fact.source_ids == [11, 12, 13]


def test_peer_extractors_skip_subject_ticker() -> None:
    """When subject_ticker='MSFT', MSFT must NOT appear in peer dicts."""
    manifest = _multi_ticker_manifest()
    pack = compile_pack(
        registry=default_registry,
        manifest=manifest,
        requested_facts=["peer_pe_ratio_ttm"],
        subject_ticker="MSFT",
    )
    fact = pack.get("peer_pe_ratio_ttm")
    assert "MSFT" not in fact.value
    # NET fixture has its own PE; ORCL/SAP from synthetic peers.
    assert set(fact.value.keys()) >= {"ORCL", "SAP"}
    # source_ids must not include MSFT's manifest id (11).
    assert 11 not in fact.source_ids


def test_peer_extractors_return_empty_value_with_subject_fallback_when_no_peers() -> None:
    """No peers in manifest: value is {} but source_ids falls back to subject so the
    Fact contract (min 1 source) stays intact."""
    pack = compile_pack(
        registry=default_registry,
        manifest=_subject_manifest(),
        requested_facts=["peer_pe_ratio_ttm", "peer_revenue_cagr_3y", "peer_gross_margin_ttm"],
        subject_ticker="NET",
    )
    for name in ("peer_pe_ratio_ttm", "peer_revenue_cagr_3y", "peer_gross_margin_ttm"):
        fact = pack.get(name)
        assert fact.value == {}
        assert fact.source_ids == [1]


def test_subject_extractor_still_works_with_peers_present() -> None:
    """The existing pe_ratio_ttm extractor must still target the subject, not a peer."""
    pack = compile_pack(
        registry=default_registry,
        manifest=_multi_ticker_manifest(),
        requested_facts=["pe_ratio_ttm"],
        subject_ticker="NET",
    )
    # NET fixture P/E from test_extractors_deterministic.py is 142.1.
    assert pack.get("pe_ratio_ttm").value == 142.1
    assert pack.get("pe_ratio_ttm").source_ids == [1]


def test_subject_ticker_match_is_case_insensitive() -> None:
    pack = compile_pack(
        registry=default_registry,
        manifest=_multi_ticker_manifest(),
        requested_facts=["pe_ratio_ttm"],
        subject_ticker="net",
    )
    assert pack.get("pe_ratio_ttm").source_ids == [1]


def test_peer_pe_ratio_skips_peers_missing_pe_field() -> None:
    """If a peer payload is missing PERatio, the peer is dropped from the dict."""
    payload_no_pe = _peer_payload(
        pe=0.0, rev_years=[100, 110, 120, 130, 140], gp_years=[80, 88, 96, 104, 112]
    )
    payload_no_pe["Highlights"].pop("PERatio")
    manifest = [
        *_subject_manifest(),
        _entry(11, "get_fundamentals_data/MISSING.US", payload_no_pe),
        _entry(
            12,
            "get_fundamentals_data/GOOD.US",
            _peer_payload(
                pe=20.0, rev_years=[100, 110, 120, 130, 140], gp_years=[80, 88, 96, 104, 112]
            ),
        ),
    ]
    pack = compile_pack(
        registry=default_registry,
        manifest=manifest,
        requested_facts=["peer_pe_ratio_ttm"],
        subject_ticker="NET",
    )
    fact = pack.get("peer_pe_ratio_ttm")
    assert "MISSING" not in fact.value
    assert fact.value == {"GOOD": 20.0}
    assert fact.source_ids == [12]
