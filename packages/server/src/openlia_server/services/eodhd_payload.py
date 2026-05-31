"""EODHD fundamentals payload trimming.

Shared by the v3 and Earnings-Update transport wiring: the raw EODHD
fundamentals payload is enormous and expensive to feed to the model on every
research turn, so this module strips it down to the load-bearing slice.
"""

from __future__ import annotations

from typing import Any

# How many periods to keep when trimming the multi-year statements.
# Five years annual + six quarters quarterly gives the model enough
# trend to compute YoY/QoQ and CAGR without dumping the decade-long
# EODHD history that bloats input cost by 5-10x.
_EODHD_KEEP_ANNUAL = 5
_EODHD_KEEP_QUARTERLY = 6

# Top-level sections to drop wholesale — high-volume, low-signal for an
# equity-research narrative. Holders/insider lists and the full splits/
# dividend history alone routinely add 5-15k tokens per ticker.
_EODHD_DROP_SECTIONS = frozenset(
    {
        "Holders",
        "InsiderTransactions",
        "outstandingShares",
        "ETF_Data",
        "ESGScores",
        "Components",
        "Listings",
    }
)

# Fields inside the `General` section to drop. These are either prose
# (stale company narrative, exec bios) or contact metadata that has no
# business shaping research output. Dropping them serves two ends:
#
#  - Token cost: `Description` + `Officers` together routinely add
#    2-5k tokens per fundamentals call, with zero load-bearing value
#    for an equity-research report.
#  - Behavioral: the prose is point-in-time and reads to the model as
#    "narrative coverage already supplied", which causes the researcher
#    to skip web_search for genuinely-current qualitative needs
#    (regulatory status, catalysts, management commentary). Removing
#    the false-sufficiency signal is the load-bearing reason to drop
#    them, even with the dual-lane data_fact_ids / web_fact_ids
#    routing in place.
_EODHD_GENERAL_DROP_FIELDS = frozenset(
    {
        "Description",
        "Officers",
        "Address",
        "AddressData",
        "Phone",
        "WebURL",
        "LogoURL",
        "InternationalDomestic",
    }
)


def trim_eodhd_fundamentals(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip EODHD fundamentals down to what an equity-research report
    actually needs.

    The raw EODHD payload is enormous: every quarter back to inception,
    every dividend, every insider trade, every share-count change. The
    model only reads a small slice of this to build a fact bundle, but
    we pay for the full payload as input tokens on every RESEARCH turn
    where the result is in scope. Trimming here cuts ~60-80% of the
    bytes the model has to read without losing anything load-bearing.
    """
    if not isinstance(payload, dict):
        return payload

    trimmed: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _EODHD_DROP_SECTIONS:
            continue
        if key == "General" and isinstance(value, dict):
            trimmed[key] = _trim_general(value)
            continue
        if key == "SplitsDividends" and isinstance(value, dict):
            trimmed[key] = _trim_splits_dividends(value)
            continue
        if key == "Earnings" and isinstance(value, dict):
            trimmed[key] = _trim_earnings(value)
            continue
        if key == "Financials" and isinstance(value, dict):
            trimmed[key] = _trim_financials(value)
            continue
        trimmed[key] = value
    return trimmed


def _trim_general(section: dict[str, Any]) -> dict[str, Any]:
    """Drop prose + contact fields from `General`; keep structured
    metadata (sector/industry/country/employees/IPO date)."""
    return {k: v for k, v in section.items() if k not in _EODHD_GENERAL_DROP_FIELDS}


def _trim_splits_dividends(section: dict[str, Any]) -> dict[str, Any]:
    """Keep current yield / payout fields; drop historical lists."""
    keep_keys = {
        "ForwardAnnualDividendRate",
        "ForwardAnnualDividendYield",
        "PayoutRatio",
        "DividendDate",
        "ExDividendDate",
        "LastSplitFactor",
        "LastSplitDate",
    }
    return {k: section.get(k) for k in keep_keys if k in section}


def _trim_earnings(section: dict[str, Any]) -> dict[str, Any]:
    """Earnings has History (per-quarter EPS) + Trend + Annual. Cap each
    to the most recent N periods — older entries rarely earn their
    tokens."""
    out: dict[str, Any] = {}
    for sub_key in ("History", "Trend", "Annual"):
        block = section.get(sub_key)
        out[sub_key] = _cap_period_dict(block, _EODHD_KEEP_QUARTERLY)
    return out


def _trim_financials(section: dict[str, Any]) -> dict[str, Any]:
    """Income/Balance/CashFlow each carry yearly + quarterly maps keyed
    by ISO date. Keep the N most recent of each."""
    out: dict[str, Any] = {}
    for stmt_key in ("Income_Statement", "Balance_Sheet", "Cash_Flow"):
        stmt = section.get(stmt_key)
        if not isinstance(stmt, dict):
            continue
        out[stmt_key] = {
            "yearly": _cap_period_dict(stmt.get("yearly"), _EODHD_KEEP_ANNUAL),
            "quarterly": _cap_period_dict(stmt.get("quarterly"), _EODHD_KEEP_QUARTERLY),
            "currency_symbol": stmt.get("currency_symbol"),
        }
    return out


def _cap_period_dict(block: Any, keep: int) -> dict[str, Any] | None:
    """EODHD encodes period series as ``{"2025-12-31": {...}, ...}``.
    Keep the ``keep`` most recent keys (lexicographic sort works because
    keys are ISO dates)."""
    if not isinstance(block, dict) or not block:
        return block if isinstance(block, dict) else None
    most_recent_first = sorted(block.keys(), reverse=True)[:keep]
    return {k: block[k] for k in most_recent_first}
