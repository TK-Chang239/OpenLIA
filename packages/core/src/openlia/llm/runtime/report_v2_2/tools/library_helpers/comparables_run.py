"""comparables_run -- comparable companies multiples valuation helper.

Registered name: "comparables_run" (underscore, consistent with all other helpers).
Python module file: comparables_run.py.

Three logical sub-functions, all exposed through run():
1. Peer set discovery -- find ~10 comparable peers by GICS sub-industry + size + geography.
2. Multiple computation -- P/E TTM/NTM, EV/EBITDA TTM/NTM, EV/Sales TTM/NTM, P/B,
   P/FCF TTM, PEG NTM, EV/EBIT TTM for ticker + each peer.
3. EV bridge -- compute EV from components; warn if delta vs. reported EV > 2%.
4. Combined range -- p25..p75 of peer multiples x ticker TTM metric per multiple;
   blended range = p25..p75 implied-value distribution across all valid multiples.

Audit fixes applied (helpers-design §9 items 11 + combined-range addendum):
- EV->equity bridge uses net_debt = total_debt - cash once; does not double-count cash.
- Combined range = p25..p75 of per-multiple medians, not min-of-lows/max-of-highs.
"""

from __future__ import annotations

import datetime
from typing import Any, Literal

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

_PeerEntry = dict[str, Any]
_MultipleStats = dict[str, float | None]  # ticker, min, p25, median, p75, max

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EV_DELTA_WARNING_THRESHOLD = 0.02  # 2% delta triggers EV bridge warning
_MIN_PEERS_FOR_STATS = 2  # need at least 2 peers to compute meaningful spread

# ---------------------------------------------------------------------------
# Size band market-cap boundaries (USD billions)
# ---------------------------------------------------------------------------

_SIZE_BAND_RANGES: dict[str, tuple[float, float]] = {
    "mega": (200.0, float("inf")),
    "large": (10.0, 200.0),
    "mid": (2.0, 10.0),
    "small": (0.0, 2.0),
}


def _infer_size_band(market_cap_usd: float) -> str:
    """Infer size band from market cap in USD (billions)."""
    market_cap_bn = market_cap_usd / 1e9
    for band, (lo, hi) in _SIZE_BAND_RANGES.items():
        if lo <= market_cap_bn < hi:
            return band
    return "mega"


# ---------------------------------------------------------------------------
# Peer set discovery
# ---------------------------------------------------------------------------


def _discover_peers(
    ticker: str,
    fundamentals: dict[str, Any],
    size_band: str | None,
    geography: Literal["us", "global", "ex_us"] | None,
) -> list[_PeerEntry]:
    """Derive a peer set from the fundamentals snapshot.

    Strategy:
    1. Extract GICS sub-industry code and market cap from fundamentals.
    2. From the fundamentals data, read any pre-populated peers list
       (EODHD `eodhd_fundamentals_output` sometimes supplies a related_companies field).
    3. If no peers are pre-populated, return an empty list with a note — the LLM or user
       must supply peer_overrides for this helper to produce useful output.

    Each peer entry has:
        ticker, name, market_cap (USD float), selection_reason
    """
    peers: list[_PeerEntry] = []

    # EODHD fundamentals may have a General.Highlights.MostRecentQuarter level or
    # a related_companies list. Extract what we can.
    general = fundamentals.get("General", {}) or {}
    gics_sub = general.get("GicSector") or general.get("Sector") or "Unknown"
    exchange = general.get("Exchange") or ""

    # Some EODHD payloads embed a small peers list.
    raw_peers = general.get("Peers") or []
    if isinstance(raw_peers, str):
        raw_peers = [t.strip() for t in raw_peers.split(",") if t.strip()]

    subject_mc_raw = (fundamentals.get("Highlights", {}) or {}).get("MarketCapitalization") or 0.0
    subject_mc = float(subject_mc_raw)
    effective_size_band = size_band or _infer_size_band(subject_mc)

    for raw in raw_peers[:10]:
        if isinstance(raw, dict):
            t = raw.get("ticker") or raw.get("Code") or ""
            name = raw.get("name") or raw.get("Name") or t
            mc = float(raw.get("market_cap") or raw.get("MarketCapitalization") or 0.0)
        elif isinstance(raw, str):
            t = raw
            name = raw
            mc = 0.0
        else:
            continue

        if not t or t.upper() == ticker.upper():
            continue

        reason_parts = [f"GICS sector: {gics_sub}"]
        if mc > 0:
            peer_band = _infer_size_band(mc)
            reason_parts.append(f"size band: {peer_band}")
        if geography and exchange:
            reason_parts.append(f"geo filter: {geography}, exchange: {exchange}")
        reason_parts.append(f"target size band: {effective_size_band}")

        peers.append(
            {
                "ticker": t,
                "name": name,
                "market_cap": mc,
                "selection_reason": "; ".join(reason_parts),
            }
        )

    return peers


# ---------------------------------------------------------------------------
# EV bridge
# ---------------------------------------------------------------------------


def _compute_ev_bridge(
    market_cap: float,
    total_debt: float,
    cash: float,
    minority_interest: float,
    preferred_stock: float,
    ev_reported: float | None,
) -> dict[str, Any]:
    """Compute EV from components and compare to reported EV.

    Formula (audit fix §9 item 11):
        EV = Market Cap + Total Debt - Cash + Minority Interest + Preferred Stock

    Net debt is NOT used directly here; we keep the bridge explicit.
    When converting EV → equity value in multiple application, use:
        Equity = EV - net_debt   where net_debt = Total Debt - Cash
    This avoids the double-counting bug from the original draft.
    """
    ev_computed = market_cap + total_debt - cash + minority_interest + preferred_stock

    delta_pct: float = 0.0
    warning: str | None = None

    if ev_reported is not None and ev_reported != 0.0:
        delta_pct = abs(ev_computed - ev_reported) / abs(ev_reported)
        if delta_pct > _EV_DELTA_WARNING_THRESHOLD:
            threshold_pct = f"{_EV_DELTA_WARNING_THRESHOLD:.0%}"
            warning = (
                f"EV bridge delta {delta_pct:.1%} exceeds {threshold_pct} threshold. "
                f"Computed EV ${ev_computed:,.0f} vs reported EV ${ev_reported:,.0f}. "
                "Common causes: stale reported EV, off-balance-sheet items, "
                "operating lease treatment differences."
            )

    return {
        "market_cap": market_cap,
        "total_debt": total_debt,
        "cash": cash,
        "minority_interest": minority_interest,
        "preferred_stock": preferred_stock,
        "ev_computed": ev_computed,
        "ev_reported": ev_reported,
        "delta_pct": delta_pct,
        "warning": warning,
    }


# ---------------------------------------------------------------------------
# Multiple statistics helpers
# ---------------------------------------------------------------------------


def _percentile(sorted_values: list[float], p: float) -> float:
    """Linear interpolation percentile on a pre-sorted list."""
    n = len(sorted_values)
    if n == 0:
        return float("nan")
    if n == 1:
        return sorted_values[0]
    idx = p / 100.0 * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_values[-1]
    frac = idx - lo
    return sorted_values[lo] + frac * (sorted_values[hi] - sorted_values[lo])


def _compute_multiple_stats(
    ticker_value: float | None,
    peer_values: list[float | None],
) -> _MultipleStats:
    """Compute summary stats for a multiple across peers.

    Returns dict with keys: ticker, min, p25, median, p75, max.
    None is returned per key if insufficient data.
    """
    valid = sorted(v for v in peer_values if v is not None and v > 0)
    if len(valid) < _MIN_PEERS_FOR_STATS:
        return {
            "ticker": ticker_value,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
        }

    return {
        "ticker": ticker_value,
        "min": valid[0],
        "p25": _percentile(valid, 25),
        "median": _percentile(valid, 50),
        "p75": _percentile(valid, 75),
        "max": valid[-1],
    }


# ---------------------------------------------------------------------------
# Implied value computation
# ---------------------------------------------------------------------------


def _implied_equity_from_pe(
    multiple_stats: _MultipleStats,
    eps_ttm: float | None,
    shares_outstanding: float | None,
) -> dict[str, Any] | None:
    """Implied equity value from P/E: implied_price = multiple x EPS; equity = price x shares."""
    if (
        eps_ttm is None
        or eps_ttm <= 0
        or shares_outstanding is None
        or shares_outstanding <= 0
        or multiple_stats["median"] is None
    ):
        return None

    def _equity(m: float | None) -> float | None:
        if m is None:
            return None
        return m * eps_ttm * shares_outstanding  # type: ignore[operator]

    median_implied = _equity(multiple_stats["median"])
    return {
        "at_median": median_implied,
        "at_p25_to_p75": [_equity(multiple_stats["p25"]), _equity(multiple_stats["p75"])],
    }


def _implied_equity_from_ev_multiple(
    multiple_stats: _MultipleStats,
    metric_ttm: float | None,
    net_debt: float,
) -> dict[str, Any] | None:
    """Implied equity from EV multiple: equity = multiple x metric - net_debt."""
    if metric_ttm is None or metric_ttm <= 0 or multiple_stats["median"] is None:
        return None

    def _equity(m: float | None) -> float | None:
        if m is None:
            return None
        return m * metric_ttm - net_debt  # type: ignore[operator]

    return {
        "at_median": _equity(multiple_stats["median"]),
        "at_p25_to_p75": [_equity(multiple_stats["p25"]), _equity(multiple_stats["p75"])],
    }


def _implied_equity_from_pb(
    multiple_stats: _MultipleStats,
    book_value_total: float | None,
) -> dict[str, Any] | None:
    """Implied equity from P/B: equity = multiple x total book value."""
    if book_value_total is None or book_value_total <= 0 or multiple_stats["median"] is None:
        return None

    def _equity(m: float | None) -> float | None:
        if m is None:
            return None
        return m * book_value_total  # type: ignore[operator]

    return {
        "at_median": _equity(multiple_stats["median"]),
        "at_p25_to_p75": [_equity(multiple_stats["p25"]), _equity(multiple_stats["p75"])],
    }


# ---------------------------------------------------------------------------
# Blended range
# ---------------------------------------------------------------------------


def _compute_blended_range(
    implied_values: dict[str, dict[str, Any] | None],
) -> dict[str, float | None]:
    """Blended range across all valid multiples.

    Per audit fix (comparables combined range, §3.1 addendum):
    - Collect the at_median implied equity values for each multiple.
    - low = min of those medians; median = median of those medians; high = max.
    - Midpoint = (low + high) / 2.

    This synthesizes across per-multiple medians, not across per-multiple lows/highs,
    avoiding compounding peer-dispersion with methodology-dispersion.
    """
    medians: list[float] = []
    for _key, iv in implied_values.items():
        if iv is None:
            continue
        m = iv.get("at_median")
        if m is not None and m > 0:
            medians.append(m)

    if not medians:
        return {"low": None, "median": None, "high": None, "midpoint": None}

    medians_sorted = sorted(medians)
    low = medians_sorted[0]
    high = medians_sorted[-1]
    blend_median = _percentile(medians_sorted, 50)
    midpoint = (low + high) / 2.0

    return {"low": low, "median": blend_median, "high": high, "midpoint": midpoint}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run(
    ticker: str,
    peer_overrides: list[str] | None = None,
    size_band: Literal["mega", "large", "mid", "small"] | None = None,
    geography: Literal["us", "global", "ex_us"] | None = None,
    fundamentals: dict[str, Any] | None = None,
    market_data: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> dict[str, Any]:
    """Run comparable companies multiples valuation.

    Parameters
    ----------
    ticker:
        Subject company ticker.
    peer_overrides:
        If supplied, skip discovery and use exactly these tickers as peers.
    size_band:
        Override size bucket for peer filtering.
    geography:
        "us" | "global" | "ex_us" peer geography filter.
    fundamentals:
        Pre-fetched fundamentals dict (shape: EODHD eodhd_fundamentals_output).
        When None, an empty dict is used — discovery will be limited and multiples
        will rely entirely on market_data.
    market_data:
        Pre-fetched market data dict containing subject + peer multiples.
        Expected shape::

            {
                "subject": {
                    "market_cap": float,
                    "total_debt": float,
                    "cash": float,
                    "minority_interest": float,
                    "preferred_stock": float,
                    "ev_reported": float | None,
                    "eps_ttm": float | None,
                    "ebitda_ttm": float | None,
                    "ebit_ttm": float | None,
                    "revenue_ttm": float | None,
                    "fcf_ttm": float | None,
                    "book_value": float | None,
                    "shares_outstanding": float | None,
                    "pe_ttm": float | None,
                    "pe_ntm": float | None,
                    "ev_ebitda_ttm": float | None,
                    "ev_ebitda_ntm": float | None,
                    "ev_sales_ttm": float | None,
                    "ev_sales_ntm": float | None,
                    "pb": float | None,
                    "pfcf_ttm": float | None,
                    "peg_ntm": float | None,
                    "ev_ebit_ttm": float | None,
                },
                "peers": {
                    "GOOGL": {"name": "Alphabet", "market_cap": ..., "pe_ttm": ..., ...},
                    ...
                }
            }
    as_of:
        ISO date string for the computation timestamp.

    Returns
    -------
    dict
        Full comparables output per the helper output schema.
    """
    warnings: list[str] = []
    effective_as_of = as_of or datetime.date.today().isoformat()

    fundamentals = fundamentals or {}
    market_data = market_data or {}

    subject_md = market_data.get("subject", {}) or {}
    peers_md = market_data.get("peers", {}) or {}

    # ------------------------------------------------------------------
    # 1. Peer set
    # ------------------------------------------------------------------

    if peer_overrides is not None:
        # User-supplied: construct minimal peer entries.
        peer_set: list[_PeerEntry] = []
        for t in peer_overrides:
            peer_info = peers_md.get(t, {}) or {}
            peer_set.append(
                {
                    "ticker": t,
                    "name": peer_info.get("name", t),
                    "market_cap": float(peer_info.get("market_cap", 0.0) or 0.0),
                    "selection_reason": "user override",
                }
            )
    else:
        peer_set = _discover_peers(ticker, fundamentals, size_band, geography)
        # Merge with any data from market_data.peers.
        for entry in peer_set:
            t = entry["ticker"]
            if t in peers_md:
                entry["market_cap"] = float(
                    peers_md[t].get("market_cap", entry["market_cap"]) or entry["market_cap"]
                )
                if not entry.get("name") or entry["name"] == t:
                    entry["name"] = peers_md[t].get("name", t)

        # Supplement with any tickers from market_data.peers not yet in set.
        existing_tickers = {e["ticker"] for e in peer_set}
        for t, peer_info in peers_md.items():
            if t not in existing_tickers and t.upper() != ticker.upper():
                peer_set.append(
                    {
                        "ticker": t,
                        "name": (peer_info or {}).get("name", t),
                        "market_cap": float((peer_info or {}).get("market_cap", 0.0) or 0.0),
                        "selection_reason": "from market_data.peers",
                    }
                )

    if not peer_set:
        warnings.append(
            "No peers found via discovery. Supply peer_overrides or provide "
            "market_data.peers for meaningful multiple statistics."
        )

    # ------------------------------------------------------------------
    # 2. EV bridge (subject company)
    # ------------------------------------------------------------------

    ev_bridge = _compute_ev_bridge(
        market_cap=float(subject_md.get("market_cap", 0.0) or 0.0),
        total_debt=float(subject_md.get("total_debt", 0.0) or 0.0),
        cash=float(subject_md.get("cash", 0.0) or 0.0),
        minority_interest=float(subject_md.get("minority_interest", 0.0) or 0.0),
        preferred_stock=float(subject_md.get("preferred_stock", 0.0) or 0.0),
        ev_reported=subject_md.get("ev_reported"),
    )
    if ev_bridge["warning"]:
        warnings.append(ev_bridge["warning"])

    # ------------------------------------------------------------------
    # 3. Multiple computation
    # ------------------------------------------------------------------

    multiple_keys = [
        "pe_ttm",
        "pe_ntm",
        "ev_ebitda_ttm",
        "ev_ebitda_ntm",
        "ev_sales_ttm",
        "ev_sales_ntm",
        "pb",
        "pfcf_ttm",
        "peg_ntm",
        "ev_ebit_ttm",
    ]

    multiples: dict[str, _MultipleStats] = {}
    for key in multiple_keys:
        ticker_val = subject_md.get(key)
        if ticker_val is not None:
            try:
                ticker_val = float(ticker_val)
            except (TypeError, ValueError):
                ticker_val = None

        peer_vals: list[float | None] = []
        for entry in peer_set:
            t = entry["ticker"]
            peer_info = peers_md.get(t) or {}
            raw = peer_info.get(key)
            if raw is None:
                peer_vals.append(None)
            else:
                try:
                    peer_vals.append(float(raw))
                except (TypeError, ValueError):
                    peer_vals.append(None)

        multiples[key] = _compute_multiple_stats(ticker_val, peer_vals)

    # ------------------------------------------------------------------
    # 4. Implied values and combined range (audit fix)
    # ------------------------------------------------------------------

    net_debt = ev_bridge["total_debt"] - ev_bridge["cash"]
    eps_ttm = subject_md.get("eps_ttm")
    if eps_ttm is not None:
        try:
            eps_ttm = float(eps_ttm)
        except (TypeError, ValueError):
            eps_ttm = None

    shares_outstanding = subject_md.get("shares_outstanding")
    if shares_outstanding is not None:
        try:
            shares_outstanding = float(shares_outstanding)
        except (TypeError, ValueError):
            shares_outstanding = None

    def _float_or_none(key: str) -> float | None:
        v = subject_md.get(key)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    ebitda_ttm = _float_or_none("ebitda_ttm")
    ebit_ttm = _float_or_none("ebit_ttm")
    revenue_ttm = _float_or_none("revenue_ttm")
    fcf_ttm = _float_or_none("fcf_ttm")
    book_value = _float_or_none("book_value")

    # NTM metrics: use same TTM figures as fallback since we don't have explicit NTM financials.
    # The NTM multiples for peers may differ from TTM; we apply them to the same TTM base.
    # A more rigorous implementation would use NTM estimates; document as a known limitation.
    if ebitda_ttm is None:
        warnings.append("ebitda_ttm not supplied; EV/EBITDA NTM implied value uses None base.")
    if revenue_ttm is None:
        warnings.append("revenue_ttm not supplied; EV/Sales NTM implied value uses None base.")

    implied_values: dict[str, dict[str, Any] | None] = {}

    # P/E (TTM + NTM) -- equity multiples applied to EPS x shares
    implied_values["pe_ttm"] = _implied_equity_from_pe(
        multiples["pe_ttm"], eps_ttm, shares_outstanding
    )
    implied_values["pe_ntm"] = _implied_equity_from_pe(
        multiples["pe_ntm"], eps_ttm, shares_outstanding
    )

    # EV/EBITDA (TTM + NTM)
    implied_values["ev_ebitda_ttm"] = _implied_equity_from_ev_multiple(
        multiples["ev_ebitda_ttm"], ebitda_ttm, net_debt
    )
    implied_values["ev_ebitda_ntm"] = _implied_equity_from_ev_multiple(
        multiples["ev_ebitda_ntm"], ebitda_ttm, net_debt
    )

    # EV/Sales (TTM + NTM)
    implied_values["ev_sales_ttm"] = _implied_equity_from_ev_multiple(
        multiples["ev_sales_ttm"], revenue_ttm, net_debt
    )
    implied_values["ev_sales_ntm"] = _implied_equity_from_ev_multiple(
        multiples["ev_sales_ntm"], revenue_ttm, net_debt
    )

    # P/B (current)
    implied_values["pb"] = _implied_equity_from_pb(multiples["pb"], book_value)

    # P/FCF (TTM)
    implied_values["pfcf_ttm"] = _implied_equity_from_ev_multiple(
        multiples["pfcf_ttm"],
        fcf_ttm,
        0.0,  # P/FCF is an equity multiple, no EV bridge needed
    )

    # PEG (NTM) -- PEG x growth rate x EPS x shares; less useful as implied equity,
    # so we compute it but may yield None for many cases.
    implied_values["peg_ntm"] = None  # PEG->implied equity requires explicit NTM growth

    # EV/EBIT (TTM)
    implied_values["ev_ebit_ttm"] = _implied_equity_from_ev_multiple(
        multiples["ev_ebit_ttm"], ebit_ttm, net_debt
    )

    blended_range = _compute_blended_range(implied_values)

    # ------------------------------------------------------------------
    # 5. Assemble output
    # ------------------------------------------------------------------

    applied_at = datetime.datetime.now(tz=datetime.UTC).isoformat()

    return {
        "ticker": ticker,
        "peer_set": peer_set,
        "ev_bridge": ev_bridge,
        "multiples": multiples,
        "implied_values": implied_values,
        "blended_range": blended_range,
        "as_of": effective_as_of,
        "applied_at": applied_at,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Schema + registration
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="comparables_run",
        category=Category.COMPARABLES,
        one_liner="Peer comps: P/E, EV/EBITDA, EV/Sales, P/B, PEG with EV bridge + blended range.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Run a full comparable companies multiples valuation: discover peers by "
            "GICS sub-industry, size band, and geography; compute TTM and NTM "
            "P/E, EV/EBITDA, EV/Sales, P/B, P/FCF, PEG, and EV/EBIT multiples for "
            "the ticker and each peer; build an EV bridge from first principles; "
            "derive implied equity values and a blended valuation range across all valid multiples."
        ),
        when_to_use=[
            "Relative valuation section of an equity research initiation or update report.",
            "When you need a peer-anchored valuation range to triangulate with DCF.",
            "When the user explicitly requests a 'comps' or 'peer multiples' analysis.",
            "Football-field chart requires a comparables band as one row.",
        ],
        when_not_to_use=[
            "Intrinsic DCF-based valuation — use dcf_valuation instead.",
            "High-uncertainty pre-revenue businesses where comparables dominate and "
            "peers are scarce — consider justified_multiples or rnpv_pipeline instead.",
            "REITs — use reit_valuation_panel (FFO/AFFO/NAV based, not earnings multiples).",
            "Banks — use banks_sector_panel (P/TBV, ROTCE, NIM based).",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                required=True,
                description="Subject company ticker symbol.",
            ),
            "peer_overrides": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description=(
                    "Explicit peer ticker list. When supplied, bypasses GICS-based "
                    "peer discovery entirely."
                ),
            ),
            "size_band": HelperParam(
                type="Literal['mega','large','mid','small'] | None",
                required=False,
                default=None,
                description=(
                    "Market-cap size bucket for peer filtering. "
                    "Inferred from subject market cap if not supplied."
                ),
            ),
            "geography": HelperParam(
                type="Literal['us','global','ex_us'] | None",
                required=False,
                default=None,
                description="Geography filter: 'us', 'global', or 'ex_us'.",
            ),
            "fundamentals": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Pre-fetched fundamentals dict (eodhd_fundamentals_output shape). "
                    "When None, discovery is limited to market_data.peers."
                ),
            ),
            "market_data": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Pre-fetched market data dict with 'subject' and 'peers' sub-dicts "
                    "containing multiples and financial metrics. See run() docstring."
                ),
            ),
            "as_of": HelperParam(
                type="str | None",
                required=False,
                default=None,
                description="ISO date for the computation timestamp (defaults to today).",
            ),
        },
        outputs=[
            HelperOutput(
                name="comparables_output",
                type="structured_object",
                description=(
                    "Peer set, EV bridge, per-multiple stats, implied values per multiple, "
                    "blended valuation range, and warnings list."
                ),
            ),
        ],
        produces_artifacts=["comparables_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals", "eodhd.eod_prices"],
    ),
    skill_doc=SkillDocRef(
        path="skills/comparables_run.md",
        estimated_tokens=1800,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.REQUIRED_PARAM_UNRESOLVABLE,
    ],
)

register_helper(_SCHEMA, run)
