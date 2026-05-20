"""Valuation helpers (WS7): peer multiples, P/E band, PEG, DCF, SOTP, reverse DCF."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from statistics import mean, median, pstdev
from typing import Any

from openlia.llm.runtime.report_v2.facts.extractors.compute import union_source_ids
from openlia.llm.runtime.report_v2.facts.helpers._util import oldest_data_as_of_of_deps
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile (p in [0, 1])."""
    if not values:
        raise ValueError("empty values")
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    rank = p * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return s[lo] + (s[hi] - s[lo]) * frac


def _implied_from_multiples(
    subject_input: float | None, multiples: dict[str, float]
) -> dict[str, float] | None:
    if subject_input is None or not multiples:
        return None
    vals = [v for v in multiples.values() if v is not None]
    if not vals:
        return None
    return {
        "low": min(vals) * subject_input,
        "p25": _percentile(vals, 0.25) * subject_input,
        "median": median(vals) * subject_input,
        "p75": _percentile(vals, 0.75) * subject_input,
        "high": max(vals) * subject_input,
    }


def peer_multiple_implied_range(
    subject_eps: float | None,
    subject_ebitda: float | None,
    subject_revenue: float | None,
    peer_pe_dict: dict[str, float],
    peer_ev_ebitda_dict: dict[str, float],
    peer_ev_sales_dict: dict[str, float] | None = None,
) -> dict:
    out: dict[str, dict | None] = {
        "pe_implied": _implied_from_multiples(subject_eps, peer_pe_dict or {}),
        "ev_ebitda_implied": _implied_from_multiples(subject_ebitda, peer_ev_ebitda_dict or {}),
        "ev_sales_implied": _implied_from_multiples(subject_revenue, peer_ev_sales_dict or {}),
    }
    return out


def historical_pe_band(
    daily_pe_series: list[tuple[date, float]],
    current_pe: float,
    window_years: int = 5,
) -> dict:
    """Mean, +/-1 stdev, current percentile, and z-score over `window_years`."""
    if not daily_pe_series:
        raise ValueError("daily_pe_series is empty")
    cutoff_year = daily_pe_series[-1][0].year - window_years
    windowed = [v for d, v in daily_pe_series if d.year >= cutoff_year and v is not None]
    if len(windowed) < 2:
        raise ValueError("not enough points within window")
    m = mean(windowed)
    sd = pstdev(windowed)
    below = sum(1 for v in windowed if v <= current_pe)
    percentile = below / len(windowed)
    z = (current_pe - m) / sd if sd > 0 else 0.0
    return {
        "mean": m,
        "std": sd,
        "plus_1_sigma": m + sd,
        "minus_1_sigma": m - sd,
        "current_pe": current_pe,
        "current_percentile": percentile,
        "current_z_score": z,
    }


def peg_ratio_correct(forward_pe: float, forward_eps_growth_pct: float | None) -> float | None:
    """PEG using forward EPS growth.

    Convention: `forward_eps_growth_pct` is in *percent units* (e.g. 25 means
    25%), matching how sell-side notes quote it. Returns `pe / growth_pct`.

    Refuses inputs that look like a revenue CAGR or other large number — any
    `forward_eps_growth_pct` above 200 raises ValueError. Returns None when
    growth is None or zero."""
    if forward_eps_growth_pct is None:
        return None
    if forward_eps_growth_pct > 200:
        raise ValueError(
            f"forward_eps_growth_pct={forward_eps_growth_pct} exceeds 200; "
            "passed value looks like a revenue CAGR or wrong unit"
        )
    if forward_eps_growth_pct == 0:
        return None
    return forward_pe / forward_eps_growth_pct


def dcf_intrinsic_value(
    forward_revenue_path: list[float],
    ebit_margin_path: list[float],
    tax_rate: float,
    capex_pct_of_revenue: float,
    change_in_nwc_pct_of_revenue_change: float,
    terminal_growth: float,
    wacc: float,
    shares_outstanding: float,
) -> dict:
    """Two-stage FCF DCF with mid-year-equivalent end-of-year discounting.

    FCFF_t = EBIT_t * (1 - tax) - capex_t - ΔNWC_t,
    where capex_t = capex_pct * revenue_t and
    ΔNWC_t = change_in_nwc_pct * (revenue_t - revenue_{t-1}).
    Terminal value uses the Gordon formula on FCFF_{N+1}."""
    if not (0.05 <= wacc <= 0.20):
        raise ValueError(f"wacc={wacc} must be in [0.05, 0.20]")
    if not (0.0 <= terminal_growth <= 0.04):
        raise ValueError(f"terminal_growth={terminal_growth} must be in [0.0, 0.04]")
    if not (0.0 <= tax_rate <= 0.40):
        raise ValueError(f"tax_rate={tax_rate} must be in [0.0, 0.40]")
    if not (0.0 <= capex_pct_of_revenue <= 0.30):
        raise ValueError(f"capex_pct_of_revenue={capex_pct_of_revenue} must be in [0.0, 0.30]")
    if not (5 <= len(forward_revenue_path) <= 10):
        raise ValueError(
            f"len(forward_revenue_path)={len(forward_revenue_path)} must be in [5, 10]"
        )
    if len(ebit_margin_path) != len(forward_revenue_path):
        raise ValueError("ebit_margin_path length must equal forward_revenue_path length")
    if wacc <= terminal_growth:
        raise ValueError("wacc must exceed terminal_growth for a finite terminal value")
    if shares_outstanding <= 0:
        raise ValueError("shares_outstanding must be positive")

    fcffs: list[float] = []
    prior_rev = forward_revenue_path[0]
    for t, (rev, margin) in enumerate(zip(forward_revenue_path, ebit_margin_path, strict=True)):
        ebit = rev * margin
        capex = capex_pct_of_revenue * rev
        delta_nwc = change_in_nwc_pct_of_revenue_change * (rev - prior_rev) if t > 0 else 0.0
        fcff = ebit * (1.0 - tax_rate) - capex - delta_nwc
        fcffs.append(fcff)
        prior_rev = rev

    pv_explicit = sum(fcff / ((1.0 + wacc) ** (t + 1)) for t, fcff in enumerate(fcffs))
    terminal_fcff = fcffs[-1] * (1.0 + terminal_growth)
    terminal_value = terminal_fcff / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + wacc) ** len(fcffs))
    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value
    intrinsic_per_share = equity_value / shares_outstanding

    sensitivity: dict[tuple[float, float], float] = {}
    tg_grid = [max(0.0, terminal_growth - 0.01), terminal_growth, min(0.04, terminal_growth + 0.01)]
    wacc_grid = [
        max(0.05, wacc - 0.01),
        wacc,
        min(0.20, wacc + 0.01),
    ]
    for tg in tg_grid:
        for w in wacc_grid:
            if w <= tg:
                continue
            tv = fcffs[-1] * (1.0 + tg) / (w - tg)
            pv_tv = tv / ((1.0 + w) ** len(fcffs))
            pv_exp = sum(fcff / ((1.0 + w) ** (i + 1)) for i, fcff in enumerate(fcffs))
            sensitivity[(round(tg, 4), round(w, 4))] = (pv_exp + pv_tv) / shares_outstanding
    return {
        "intrinsic_value_per_share": intrinsic_per_share,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "terminal_value": terminal_value,
        "pv_explicit": pv_explicit,
        "pv_terminal": pv_terminal,
        "fcff_path": fcffs,
        "sensitivity_grid": sensitivity,
    }


def sum_of_parts(
    segment_revenue_dict: dict[str, float], segment_multiple_dict: dict[str, float]
) -> dict:
    ev_by_segment: dict[str, float] = {}
    breakdown: list[dict] = []
    for seg, rev in segment_revenue_dict.items():
        m = segment_multiple_dict.get(seg)
        if m is None:
            continue
        ev = rev * m
        ev_by_segment[seg] = ev
        breakdown.append({"segment": seg, "revenue": rev, "multiple": m, "ev": ev})
    total_ev = sum(ev_by_segment.values())
    return {
        "ev_by_segment": ev_by_segment,
        "total_ev": total_ev,
        "breakdown": breakdown,
    }


def reverse_dcf(
    current_price: float,
    shares_outstanding: float,
    current_fcf: float,
    wacc: float,
    terminal_growth: float,
    years: int = 10,
) -> dict:
    """Solve for the FCF growth rate the current market cap implies.

    Two-stage: `years` of growth at constant rate g, then Gordon terminal.
    Binary search on g in [-0.10, 0.50]."""
    if current_fcf <= 0:
        raise ValueError("current_fcf must be positive for reverse DCF")
    if wacc <= terminal_growth:
        raise ValueError("wacc must exceed terminal_growth")
    target_ev = current_price * shares_outstanding

    def ev_for(g: float) -> float:
        pv = 0.0
        fcf = current_fcf
        for t in range(1, years + 1):
            fcf = fcf * (1.0 + g)
            pv += fcf / ((1.0 + wacc) ** t)
        tv = fcf * (1.0 + terminal_growth) / (wacc - terminal_growth)
        pv += tv / ((1.0 + wacc) ** years)
        return pv

    lo, hi = -0.10, 0.50
    for _ in range(100):
        mid = (lo + hi) / 2
        if ev_for(mid) < target_ev:
            lo = mid
        else:
            hi = mid
    return {
        "implied_growth_rate": (lo + hi) / 2,
        "inputs_echo": {
            "current_price": current_price,
            "shares_outstanding": shares_outstanding,
            "current_fcf": current_fcf,
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "years": years,
        },
    }


def football_field(method_outputs: dict[str, dict]) -> dict:
    """Shape `{method: {low, mid, high}}` into a horizontal-bar exhibit."""
    rows: list[dict] = []
    lows: list[float] = []
    highs: list[float] = []
    for name, vals in method_outputs.items():
        low = vals.get("low")
        mid = vals.get("mid")
        high = vals.get("high")
        if low is None or high is None:
            continue
        rows.append({"method": name, "low": low, "mid": mid, "high": high})
        lows.append(low)
        highs.append(high)
    return {
        "rows": rows,
        "x_min": min(lows) if lows else None,
        "x_max": max(highs) if highs else None,
        "method_count": len(rows),
    }


# -- Registered Facts -------------------------------------------------------


_PEER_IMPLIED_DEPS = [
    "eps_ttm",
    "ebitda_ttm",
    "revenue_ttm",
    "peer_pe_ratio_ttm",
    "peer_ev_to_ebitda",
]


@register_fact("peer_multiple_implied_range", tier="compute", depends_on=_PEER_IMPLIED_DEPS)
def peer_multiple_implied_range_fact(payloads, facts) -> Fact:
    eps_f = facts["eps_ttm"]
    ebitda_f = facts["ebitda_ttm"]
    rev_f = facts["revenue_ttm"]
    pe_f = facts["peer_pe_ratio_ttm"]
    ev_eb_f = facts["peer_ev_to_ebitda"]
    pe_dict = pe_f.value if isinstance(pe_f.value, dict) else {}
    ev_eb_dict = ev_eb_f.value if isinstance(ev_eb_f.value, dict) else {}
    try:
        value = peer_multiple_implied_range(
            subject_eps=eps_f.value if isinstance(eps_f.value, (int, float)) else None,
            subject_ebitda=ebitda_f.value if isinstance(ebitda_f.value, (int, float)) else None,
            subject_revenue=rev_f.value if isinstance(rev_f.value, (int, float)) else None,
            peer_pe_dict={k: v for k, v in pe_dict.items() if v is not None},
            peer_ev_ebitda_dict={k: v for k, v in ev_eb_dict.items() if v is not None},
        )
    except ValueError:
        value = None
    return Fact(
        name="peer_multiple_implied_range",
        value=value,
        source_ids=union_source_ids(eps_f, ebitda_f, rev_f, pe_f, ev_eb_f),
        extractor="compute",
        depends_on=_PEER_IMPLIED_DEPS,
        data_as_of=oldest_data_as_of_of_deps([eps_f, ebitda_f, rev_f, pe_f, ev_eb_f]),
        source_tier="derived",
    )


_PEG_DEPS = ["pe_ratio_forward", "consensus_eps_growth_fy_next"]


@register_fact("peg_ratio_correct", tier="compute", depends_on=_PEG_DEPS)
def peg_ratio_correct_fact(payloads, facts) -> Fact:
    pe_f = facts["pe_ratio_forward"]
    g_f = facts["consensus_eps_growth_fy_next"]
    pe = pe_f.value if isinstance(pe_f.value, (int, float)) else None
    g_raw = g_f.value if isinstance(g_f.value, (int, float)) else None
    # `consensus_eps_growth_fy_next` is stored as a fractional growth rate
    # (e.g. 0.25 for 25%); the helper convention is percent units, so scale.
    g_pct = g_raw * 100.0 if g_raw is not None else None
    value: float | None
    if pe is None:
        value = None
    else:
        try:
            value = peg_ratio_correct(forward_pe=pe, forward_eps_growth_pct=g_pct)
        except ValueError:
            value = None
    return Fact(
        name="peg_ratio_correct",
        value=value,
        source_ids=union_source_ids(pe_f, g_f),
        extractor="compute",
        depends_on=_PEG_DEPS,
        data_as_of=oldest_data_as_of_of_deps([pe_f, g_f]),
        source_tier="derived",
    )


_SOTP_DEPS = ["segment_revenue_latest"]


@register_fact("sum_of_parts", tier="compute", depends_on=_SOTP_DEPS)
def sum_of_parts_fact(payloads, facts) -> Fact:
    """SOTP requires segment revenue and per-segment multiples. Without an
    LLM-supplied multiple dict the helper returns None — the section dispatcher
    is expected to supply named segment multiples when invoking SOTP."""
    seg_f = facts["segment_revenue_latest"]
    value: dict | None = None
    if isinstance(seg_f.value, dict):
        value = sum_of_parts(seg_f.value, {})
        if not value["breakdown"]:
            value = None
    return Fact(
        name="sum_of_parts",
        value=value,
        source_ids=union_source_ids(seg_f),
        extractor="compute",
        depends_on=_SOTP_DEPS,
        data_as_of=oldest_data_as_of_of_deps([seg_f]),
        source_tier="derived",
    )


_FF_DEPS = ["peer_multiple_implied_range", "analyst_target_mean"]


@register_fact("football_field", tier="compute", depends_on=_FF_DEPS)
def football_field_fact(payloads, facts) -> Fact:
    """Assemble a football-field exhibit from helper-derived ranges and
    sourced sell-side targets. DCF / historical-PE-band methods are merged
    in by the section when their inputs are available."""
    pmir = facts["peer_multiple_implied_range"]
    target_f = facts["analyst_target_mean"]
    methods: dict[str, dict] = {}
    if isinstance(pmir.value, dict):
        pe_imp = pmir.value.get("pe_implied")
        if pe_imp:
            methods["peer_pe"] = {
                "low": pe_imp["low"],
                "mid": pe_imp["median"],
                "high": pe_imp["high"],
            }
        ev_imp = pmir.value.get("ev_ebitda_implied")
        if ev_imp:
            methods["peer_ev_ebitda"] = {
                "low": ev_imp["low"],
                "mid": ev_imp["median"],
                "high": ev_imp["high"],
            }
    if isinstance(target_f.value, (int, float)):
        methods["sell_side_mean"] = {
            "low": target_f.value,
            "mid": target_f.value,
            "high": target_f.value,
        }
    value: dict | None = football_field(methods) if methods else None
    return Fact(
        name="football_field",
        value=value,
        source_ids=union_source_ids(pmir, target_f),
        extractor="compute",
        depends_on=_FF_DEPS,
        data_as_of=oldest_data_as_of_of_deps([pmir, target_f]),
        source_tier="derived",
    )


# `sensitivity_grid`, `historical_pe_band`, `dcf_intrinsic_value`, and
# `reverse_dcf` are exposed as helper functions only. The section dispatcher
# invokes them with section-specific inputs (revenue path, daily P/E series,
# WACC, etc.), so they are not auto-registered as standalone facts. The pure
# helpers above are tested directly.


def sensitivity_grid(
    base_inputs: dict,
    sweep_dim_a: tuple[str, list[float]],
    sweep_dim_b: tuple[str, list[float]],
    output_fn: Callable[[dict], Any],
) -> dict:
    """Generic 2D sweep. Returns {'rows': [{a, b, output}], 'a_name', 'b_name'}."""
    a_name, a_vals = sweep_dim_a
    b_name, b_vals = sweep_dim_b
    rows: list[dict] = []
    for a in a_vals:
        for b in b_vals:
            inputs = dict(base_inputs)
            inputs[a_name] = a
            inputs[b_name] = b
            rows.append({a_name: a, b_name: b, "output": output_fn(inputs)})
    return {"rows": rows, "a_name": a_name, "b_name": b_name}
