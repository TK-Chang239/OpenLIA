"""Tests for comparables.run helper (PR 2.1).

Covers:
- EV bridge with known inputs produces expected EV.
- EV bridge fires warning when delta_pct > 2%.
- EV bridge no warning when delta_pct <= 2%.
- Multiples computed correctly for known inputs.
- Combined range = blended over per-multiple medians.
- peer_overrides bypasses discovery.
- Helper is registered with skill_doc.
- Skill doc file exists at expected path.
- Output shape: required keys present.
- All-None peer multiples yields all-None stats.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MSFT_SUBJECT = {
    "market_cap": 3_000_000_000_000.0,
    "total_debt": 50_000_000_000.0,
    "cash": 80_000_000_000.0,
    "minority_interest": 0.0,
    "preferred_stock": 0.0,
    "ev_reported": 2_970_000_000_000.0,
    "eps_ttm": 11.45,
    "ebitda_ttm": 120_000_000_000.0,
    "ebit_ttm": 105_000_000_000.0,
    "revenue_ttm": 245_000_000_000.0,
    "fcf_ttm": 70_000_000_000.0,
    "book_value": 240_000_000_000.0,
    "shares_outstanding": 7_400_000_000.0,
    "pe_ttm": 36.0,
    "pe_ntm": 30.0,
    "ev_ebitda_ttm": 24.8,
    "ev_ebitda_ntm": 21.0,
    "ev_sales_ttm": 12.1,
    "ev_sales_ntm": 10.5,
    "pb": 14.0,
    "pfcf_ttm": 42.0,
    "peg_ntm": 1.5,
    "ev_ebit_ttm": 28.3,
}

_PEER_DATA = {
    "GOOGL": {
        "name": "Alphabet",
        "market_cap": 2_000_000_000_000.0,
        "pe_ttm": 22.0,
        "pe_ntm": 19.0,
        "ev_ebitda_ttm": 15.5,
        "ev_ebitda_ntm": 13.0,
        "ev_sales_ttm": 5.5,
        "ev_sales_ntm": 4.8,
        "pb": 6.5,
        "pfcf_ttm": 25.0,
        "peg_ntm": 1.1,
        "ev_ebit_ttm": 18.0,
    },
    "AAPL": {
        "name": "Apple",
        "market_cap": 3_200_000_000_000.0,
        "pe_ttm": 31.0,
        "pe_ntm": 28.0,
        "ev_ebitda_ttm": 22.0,
        "ev_ebitda_ntm": 19.5,
        "ev_sales_ttm": 8.0,
        "ev_sales_ntm": 7.0,
        "pb": 45.0,
        "pfcf_ttm": 30.0,
        "peg_ntm": 1.8,
        "ev_ebit_ttm": 26.0,
    },
    "META": {
        "name": "Meta",
        "market_cap": 1_400_000_000_000.0,
        "pe_ttm": 25.0,
        "pe_ntm": 21.0,
        "ev_ebitda_ttm": 17.0,
        "ev_ebitda_ntm": 14.0,
        "ev_sales_ttm": 6.5,
        "ev_sales_ntm": 5.5,
        "pb": 7.0,
        "pfcf_ttm": 28.0,
        "peg_ntm": 1.2,
        "ev_ebit_ttm": 20.0,
    },
    "AMZN": {
        "name": "Amazon",
        "market_cap": 2_200_000_000_000.0,
        "pe_ttm": 45.0,
        "pe_ntm": 35.0,
        "ev_ebitda_ttm": 30.0,
        "ev_ebitda_ntm": 25.0,
        "ev_sales_ttm": 3.5,
        "ev_sales_ntm": 3.0,
        "pb": 9.0,
        "pfcf_ttm": 55.0,
        "peg_ntm": 1.5,
        "ev_ebit_ttm": 35.0,
    },
    "ORCL": {
        "name": "Oracle",
        "market_cap": 500_000_000_000.0,
        "pe_ttm": 28.0,
        "pe_ntm": 24.0,
        "ev_ebitda_ttm": 18.0,
        "ev_ebitda_ntm": 15.5,
        "ev_sales_ttm": 7.0,
        "ev_sales_ntm": 6.0,
        "pb": 18.0,
        "pfcf_ttm": 35.0,
        "peg_ntm": 1.4,
        "ev_ebit_ttm": 22.0,
    },
}

_MARKET_DATA = {
    "subject": _MSFT_SUBJECT,
    "peers": _PEER_DATA,
}


def _run(**kwargs):  # type: ignore[return]
    """Convenience wrapper around the registered helper impl."""
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None, "comparables_run not registered"
    return h.impl(**kwargs)


# ---------------------------------------------------------------------------
# EV bridge tests
# ---------------------------------------------------------------------------


def test_ev_bridge_known_inputs() -> None:
    """EV = market_cap + total_debt - cash + minority_interest + preferred_stock."""
    result = _run(
        ticker="MSFT",
        peer_overrides=["GOOGL", "AAPL"],
        market_data={
            "subject": {
                "market_cap": 1_000.0,
                "total_debt": 200.0,
                "cash": 50.0,
                "minority_interest": 10.0,
                "preferred_stock": 5.0,
            },
            "peers": {
                "GOOGL": {"pe_ttm": 22.0},
                "AAPL": {"pe_ttm": 31.0},
            },
        },
    )
    bridge = result["ev_bridge"]
    assert bridge["ev_computed"] == pytest.approx(1_165.0)
    assert bridge["ev_reported"] is None
    assert bridge["delta_pct"] == pytest.approx(0.0)
    assert bridge["warning"] is None


def test_ev_bridge_warning_fires_above_threshold() -> None:
    """Warning fires when |computed - reported| / reported > 2%."""
    # Computed EV = 1000 + 200 - 50 = 1150; reported = 1260 → delta ~8.7%
    result = _run(
        ticker="XYZ",
        peer_overrides=["A", "B"],
        market_data={
            "subject": {
                "market_cap": 1_000.0,
                "total_debt": 200.0,
                "cash": 50.0,
                "minority_interest": 0.0,
                "preferred_stock": 0.0,
                "ev_reported": 1_260.0,
            },
            "peers": {
                "A": {"pe_ttm": 15.0},
                "B": {"pe_ttm": 18.0},
            },
        },
    )
    bridge = result["ev_bridge"]
    assert bridge["delta_pct"] > 0.02
    assert bridge["warning"] is not None
    assert "threshold" in bridge["warning"]
    # top-level warnings should also contain the message
    assert any("threshold" in w for w in result["warnings"])


def test_ev_bridge_no_warning_within_threshold() -> None:
    """No warning when delta <= 2%."""
    # Computed EV = 1000 + 200 - 50 = 1150; reported = 1160 → delta ~0.87%
    result = _run(
        ticker="ABC",
        peer_overrides=["A", "B"],
        market_data={
            "subject": {
                "market_cap": 1_000.0,
                "total_debt": 200.0,
                "cash": 50.0,
                "minority_interest": 0.0,
                "preferred_stock": 0.0,
                "ev_reported": 1_160.0,
            },
            "peers": {
                "A": {"pe_ttm": 15.0},
                "B": {"pe_ttm": 18.0},
            },
        },
    )
    bridge = result["ev_bridge"]
    assert bridge["delta_pct"] < 0.02
    assert bridge["warning"] is None


# ---------------------------------------------------------------------------
# Multiple computation tests
# ---------------------------------------------------------------------------


def test_multiples_computed_for_known_inputs() -> None:
    """With 5 known peers, verify median P/E TTM is the true median."""
    result = _run(
        ticker="MSFT",
        peer_overrides=list(_PEER_DATA.keys()),
        market_data=_MARKET_DATA,
    )
    pe_ttm = result["multiples"]["pe_ttm"]

    # Peer P/E TTM values: [22, 25, 28, 31, 45] -> sorted [22, 25, 28, 31, 45]
    # median = 28.0
    assert pe_ttm["median"] == pytest.approx(28.0)
    assert pe_ttm["min"] == pytest.approx(22.0)
    assert pe_ttm["max"] == pytest.approx(45.0)
    assert pe_ttm["ticker"] == pytest.approx(36.0)


def test_multiples_p25_p75_within_bounds() -> None:
    """p25 <= median <= p75 for every multiple with valid data."""
    result = _run(
        ticker="MSFT",
        peer_overrides=list(_PEER_DATA.keys()),
        market_data=_MARKET_DATA,
    )
    for key, stats in result["multiples"].items():
        if stats["median"] is None:
            continue
        assert stats["p25"] <= stats["median"] <= stats["p75"], (
            f"{key}: p25={stats['p25']} median={stats['median']} p75={stats['p75']}"
        )


def test_multiples_none_when_insufficient_peers() -> None:
    """With only 1 valid peer, all stats are None."""
    result = _run(
        ticker="MSFT",
        peer_overrides=["GOOGL"],
        market_data={
            "subject": _MSFT_SUBJECT,
            "peers": {"GOOGL": _PEER_DATA["GOOGL"]},
        },
    )
    # Only 1 peer — less than _MIN_PEERS_FOR_STATS=2
    pe_ttm = result["multiples"]["pe_ttm"]
    assert pe_ttm["median"] is None
    assert pe_ttm["p25"] is None
    assert pe_ttm["p75"] is None


# ---------------------------------------------------------------------------
# Combined range (blended valuation) tests
# ---------------------------------------------------------------------------


def test_combined_range_uses_medians_of_medians() -> None:
    """Blended range low <= median <= high; all from per-multiple median-implied values."""
    result = _run(
        ticker="MSFT",
        peer_overrides=list(_PEER_DATA.keys()),
        market_data=_MARKET_DATA,
    )
    br = result["blended_range"]
    assert br["low"] is not None
    assert br["median"] is not None
    assert br["high"] is not None
    assert br["midpoint"] is not None
    assert br["low"] <= br["median"] <= br["high"]
    assert br["midpoint"] == pytest.approx((br["low"] + br["high"]) / 2.0)


def test_combined_range_none_when_no_implied_values() -> None:
    """Blended range is all None when no multiples produce valid implied values."""
    # Subject has no eps_ttm/ebitda/etc — no implied values can be computed.
    result = _run(
        ticker="MSFT",
        peer_overrides=["GOOGL", "AAPL"],
        market_data={
            "subject": {
                "market_cap": 3_000_000_000_000.0,
                "total_debt": 50_000_000_000.0,
                "cash": 80_000_000_000.0,
            },
            "peers": {
                "GOOGL": {"pe_ttm": 22.0},
                "AAPL": {"pe_ttm": 31.0},
            },
        },
    )
    br = result["blended_range"]
    assert br["median"] is None
    assert br["low"] is None
    assert br["high"] is None


def test_combined_range_excludes_ev_ebitda_when_none_metric() -> None:
    """If ebitda_ttm is None, EV/EBITDA implied value is None and excluded from blend."""
    # Supply eps_ttm but not ebitda_ttm; EV/EBITDA should not contribute to blend.
    result = _run(
        ticker="T",
        peer_overrides=["A", "B", "C"],
        market_data={
            "subject": {
                "market_cap": 100.0,
                "total_debt": 10.0,
                "cash": 5.0,
                "eps_ttm": 5.0,
                "shares_outstanding": 10.0,
                # no ebitda_ttm
            },
            "peers": {
                "A": {"pe_ttm": 15.0, "ev_ebitda_ttm": 12.0},
                "B": {"pe_ttm": 18.0, "ev_ebitda_ttm": 14.0},
                "C": {"pe_ttm": 20.0, "ev_ebitda_ttm": 16.0},
            },
        },
    )
    assert result["implied_values"]["ev_ebitda_ttm"] is None
    # Blended range should still work based on P/E.
    assert result["blended_range"]["median"] is not None


# ---------------------------------------------------------------------------
# peer_overrides test
# ---------------------------------------------------------------------------


def test_peer_overrides_bypass_discovery() -> None:
    """With peer_overrides, peer_set matches exactly the provided tickers."""
    peers = ["GOOGL", "AAPL", "META"]
    result = _run(
        ticker="MSFT",
        peer_overrides=peers,
        market_data={
            "subject": {"market_cap": 1_000.0},
            "peers": {
                "GOOGL": {"name": "Alphabet", "pe_ttm": 22.0},
                "AAPL": {"name": "Apple", "pe_ttm": 31.0},
                "META": {"name": "Meta", "pe_ttm": 25.0},
            },
        },
    )
    returned_tickers = [p["ticker"] for p in result["peer_set"]]
    assert set(returned_tickers) == set(peers)
    # All have selection_reason = "user override"
    for p in result["peer_set"]:
        assert p["selection_reason"] == "user override"


def test_peer_overrides_sets_name_from_market_data() -> None:
    """Peer names pulled from market_data.peers when peer_overrides is used."""
    result = _run(
        ticker="MSFT",
        peer_overrides=["GOOGL"],
        market_data={
            "subject": {"market_cap": 1_000.0},
            "peers": {"GOOGL": {"name": "Alphabet Inc.", "pe_ttm": 22.0}},
        },
    )
    peer = result["peer_set"][0]
    assert peer["ticker"] == "GOOGL"
    assert peer["name"] == "Alphabet Inc."


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------


def test_output_has_required_keys() -> None:
    """Output dict contains all required top-level keys."""
    result = _run(
        ticker="MSFT",
        peer_overrides=list(_PEER_DATA.keys()),
        market_data=_MARKET_DATA,
    )
    required_keys = {
        "ticker",
        "peer_set",
        "ev_bridge",
        "multiples",
        "implied_values",
        "blended_range",
        "as_of",
        "applied_at",
        "warnings",
    }
    assert required_keys.issubset(result.keys())


def test_ev_bridge_has_required_keys() -> None:
    result = _run(
        ticker="MSFT",
        peer_overrides=["GOOGL"],
        market_data={"subject": {"market_cap": 100.0}, "peers": {"GOOGL": {"pe_ttm": 22.0}}},
    )
    bridge_keys = {
        "market_cap",
        "total_debt",
        "cash",
        "minority_interest",
        "preferred_stock",
        "ev_computed",
        "ev_reported",
        "delta_pct",
        "warning",
    }
    assert bridge_keys.issubset(result["ev_bridge"].keys())


def test_multiple_stats_have_required_keys() -> None:
    result = _run(
        ticker="MSFT",
        peer_overrides=list(_PEER_DATA.keys()),
        market_data=_MARKET_DATA,
    )
    for key, stats in result["multiples"].items():
        assert {"ticker", "min", "p25", "median", "p75", "max"}.issubset(stats.keys()), (
            f"{key} missing expected keys"
        )


def test_ticker_echoed_in_output() -> None:
    result = _run(
        ticker="MSFT",
        peer_overrides=[],
        market_data={"subject": {}, "peers": {}},
    )
    assert result["ticker"] == "MSFT"


# ---------------------------------------------------------------------------
# Registration and skill doc
# ---------------------------------------------------------------------------


def test_helper_is_registered() -> None:
    """comparables_run must appear in the helper registry."""
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None
    assert h.schema.directory.name == "comparables_run"


def test_helper_has_skill_doc_reference() -> None:
    """HelperSchema must declare a SkillDocRef (non-None skill_doc)."""
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None
    assert h.schema.skill_doc is not None, "comparables_run must have a skill_doc"
    assert h.schema.skill_doc.path == "skills/comparables_run.md"


def test_skill_doc_file_exists() -> None:
    """The skill doc .md file must exist at the declared path."""
    # parents[5] = packages/core; src is a sibling of tests within packages/core
    skills_dir = (
        Path(__file__).resolve().parents[5]
        / "src/openlia/llm/runtime/report_v2_2"
        / "tools/library_helpers/skills"
    )
    expected = skills_dir / "comparables_run.md"
    assert expected.exists(), f"Skill doc missing at {expected}"


def test_helper_category_is_comparables() -> None:
    from openlia.llm.runtime.report_v2_2.enums import Category
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None
    assert h.schema.directory.category == Category.COMPARABLES


def test_helper_produces_comparables_output_artifact() -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry as art_reg
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper("comparables_run")
    assert h is not None
    assert "comparables_output" in h.schema.contract.produces_artifacts
    assert art_reg.get("comparables_output") is not None
