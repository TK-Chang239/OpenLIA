"""Tests for justified_multiples helper."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers.justified_multiples import execute

# ---------------------------------------------------------------------------
# Forward P/E
# ---------------------------------------------------------------------------


def test_forward_pe_known_value() -> None:
    """payout=0.5, Re=0.10, g=0.04 → forward_PE = 0.5 / 0.06 = 8.333..."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.04,
        roe=0.15,
        payout_ratio=0.50,
        multiples_to_compute=["forward_pe"],
    )
    fpe = result["justified_multiples"]["forward_pe"]["value"]
    assert abs(fpe - 8.333) < 0.001


def test_forward_pe_derived_payout() -> None:
    """When payout_ratio not supplied, derived as 1 - g/ROE.

    g=0.04, ROE=0.15 → payout = 1 - 0.04/0.15 = 0.7333
    forward_PE = 0.7333 / (0.10 - 0.04) = 12.22
    """
    result = execute(
        cost_of_equity=0.10,
        growth=0.04,
        roe=0.15,
        multiples_to_compute=["forward_pe"],
    )
    # payout = 1 - 4/15 = 11/15
    expected_payout = 1.0 - 0.04 / 0.15
    expected_fpe = expected_payout / (0.10 - 0.04)
    fpe = result["justified_multiples"]["forward_pe"]["value"]
    assert abs(fpe - expected_fpe) < 0.001


# ---------------------------------------------------------------------------
# P/B
# ---------------------------------------------------------------------------


def test_pb_known_value() -> None:
    """ROE=0.15, Re=0.10, g=0.04 → P/B = (0.15 - 0.04) / (0.10 - 0.04) = 0.11 / 0.06 = 1.833..."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.04,
        roe=0.15,
        multiples_to_compute=["pb"],
    )
    pb = result["justified_multiples"]["pb"]["value"]
    assert abs(pb - 1.8333) < 0.001


def test_pb_roe_equals_re_gives_one() -> None:
    """P/B = 1 when ROE = Re regardless of growth."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.03,
        roe=0.10,
        multiples_to_compute=["pb"],
    )
    pb = result["justified_multiples"]["pb"]["value"]
    assert abs(pb - 1.0) < 1e-9


def test_pb_roe_below_re_is_below_one() -> None:
    """P/B < 1 when ROE < Re (value destruction)."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.02,
        roe=0.07,
        multiples_to_compute=["pb"],
    )
    pb = result["justified_multiples"]["pb"]["value"]
    assert 0 < pb < 1.0


# ---------------------------------------------------------------------------
# EV/EBITDA — capex_volatility_signal warning
# ---------------------------------------------------------------------------


def test_ev_ebitda_capex_volatility_warning_fires() -> None:
    """capex_volatility_signal=True must trigger EV/EBITDA warning."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.03,
        roe=0.15,
        wacc=0.08,
        tax_rate=0.21,
        reinvest_rate=0.30,
        capex_volatility_signal=True,
        multiples_to_compute=["ev_ebitda"],
    )
    ev_result = result["justified_multiples"]["ev_ebitda"]
    assert ev_result.get("value") is not None
    assert len(ev_result.get("warnings", [])) > 0
    combined_warnings = " ".join(ev_result["warnings"]).lower()
    assert "capital intensity" in combined_warnings or "capex" in combined_warnings


def test_ev_ebitda_no_warning_without_signal() -> None:
    """capex_volatility_signal=False must not fire the warning."""
    result = execute(
        cost_of_equity=0.10,
        growth=0.03,
        roe=0.15,
        wacc=0.08,
        tax_rate=0.21,
        reinvest_rate=0.30,
        capex_volatility_signal=False,
        multiples_to_compute=["ev_ebitda"],
    )
    ev_result = result["justified_multiples"]["ev_ebitda"]
    assert ev_result.get("value") is not None
    assert len(ev_result.get("warnings", [])) == 0


def test_ev_ebitda_missing_inputs_returns_null() -> None:
    result = execute(
        cost_of_equity=0.10,
        growth=0.03,
        roe=0.15,
        multiples_to_compute=["ev_ebitda"],
    )
    ev_result = result["justified_multiples"]["ev_ebitda"]
    assert ev_result["value"] is None
    assert "reason" in ev_result


# ---------------------------------------------------------------------------
# Spread computation
# ---------------------------------------------------------------------------


def test_spreads_computed_when_actuals_provided() -> None:
    result = execute(
        cost_of_equity=0.10,
        growth=0.04,
        roe=0.15,
        payout_ratio=0.50,
        current_multiples={"forward_pe": 10.0},
        multiples_to_compute=["forward_pe"],
    )
    spreads = result["spreads"]
    assert spreads is not None
    fpe_spread = spreads["forward_pe"]
    # justified ≈ 8.33, actual = 10.0 → spread ≈ +20%
    assert fpe_spread["spread_pct"] is not None
    assert fpe_spread["spread_pct"] > 0


def test_spreads_none_without_actuals() -> None:
    result = execute(
        cost_of_equity=0.10,
        growth=0.04,
        roe=0.15,
        payout_ratio=0.50,
        multiples_to_compute=["forward_pe"],
    )
    assert result["spreads"] is None


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------


def test_growth_ge_re_raises() -> None:
    with pytest.raises(ValueError, match="must be >"):
        execute(
            cost_of_equity=0.05,
            growth=0.06,
            roe=0.15,
        )


def test_growth_gt_roe_raises() -> None:
    with pytest.raises(ValueError, match="must be <= ROE"):
        execute(
            cost_of_equity=0.15,
            growth=0.12,
            roe=0.10,
        )
