"""insider_signal_panel — Form 4 insider trading signal, code-filtered and role-weighted.

Registered name: "insider_signal_panel"

Converts SEC Form 4 insider transactions into a structured buying/selling signal.
Only discretionary open-market trades (codes P/S) enter the signal; compensation-
related codes (A, M, F, G, C, D, X) are excluded and counted separately.

This helper is listed as complex (18-list per schema-and-skills §6).
Skill doc: skills/insider_signal_panel.md
"""

from __future__ import annotations

from typing import Any

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
# Constants
# ---------------------------------------------------------------------------

_EXCLUDED_CODES = frozenset({"A", "M", "F", "G", "C", "D", "X"})
_BUY_CODES = frozenset({"P"})
_SELL_CODES = frozenset({"S"})

_EXCLUDED_CODE_LABELS: dict[str, str] = {
    "A": "grants_A",
    "M": "option_exercises_M",
    "F": "tax_withholding_F",
    "G": "gifts_G",
    "C": "conversion_C",
    "D": "disposition_to_issuer_D",
    "X": "derivative_exercise_X",
}

_DEFAULT_ROLE_WEIGHTS: dict[str, float] = {
    "CEO": 1.0,
    "CFO": 1.0,
    "President": 0.8,
    "Officer": 0.6,
    "Director": 0.5,
    "10%_owner": 0.3,
    "Other": 0.4,
}

_EPSILON = 1e-9


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _role_weight(role: str, weights: dict[str, float]) -> float:
    """Return role weight; fall back to 'Other' then 0.4."""
    if role in weights:
        return weights[role]
    # Partial match: if role contains a known key (e.g. "Chief Executive Officer" -> CEO)
    upper_role = role.upper()
    if "CEO" in upper_role or "CHIEF EXECUTIVE" in upper_role:
        return weights.get("CEO", 1.0)
    if "CFO" in upper_role or "CHIEF FINANCIAL" in upper_role:
        return weights.get("CFO", 1.0)
    if "PRESIDENT" in upper_role:
        return weights.get("President", 0.8)
    if "DIRECTOR" in upper_role:
        return weights.get("Director", 0.5)
    if "OFFICER" in upper_role:
        return weights.get("Officer", 0.6)
    return weights.get("Other", 0.4)


def _is_10b5_scheduled(txn: dict[str, Any]) -> bool:
    """Return True if transaction is flagged as a scheduled 10b5-1 plan sale."""
    footnote = str(txn.get("footnote", "") or txn.get("plan_type", "") or "")
    return "10b5-1" in footnote or "10b51" in footnote.replace("-", "")


def _parse_date(date_str: str) -> tuple[int, int, int]:
    """Return (year, month, day) from ISO date string YYYY-MM-DD."""
    parts = date_str.split("-")
    if len(parts) != 3:
        raise ValueError(f"Expected YYYY-MM-DD date, got {date_str!r}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def _days_between(a: str, b: str) -> int:
    """Return abs days between two YYYY-MM-DD strings (approximate, no leap correction)."""
    ay, am, ad = _parse_date(a)
    by_, bm, bd = _parse_date(b)
    # Simple day count via day-of-year approximation
    a_total = ay * 365 + am * 30 + ad
    b_total = by_ * 365 + bm * 30 + bd
    return abs(a_total - b_total)


def _txn_within_window(txn_date: str, as_of: str, days: int) -> bool:
    return _days_between(txn_date, as_of) <= days


def _detect_cluster(buy_txns: list[dict[str, Any]], window_days: int = 30) -> bool:
    """True if >= 3 distinct insiders made open-market buys within any 30-day sub-window."""
    if len(buy_txns) < 3:
        return False
    dates = [t["date"] for t in buy_txns]
    insiders = [t["insider_name"] for t in buy_txns]

    for _i, anchor_date in enumerate(dates):
        buyers_in_window: set[str] = set()
        for j, d in enumerate(dates):
            if _days_between(anchor_date, d) <= window_days:
                buyers_in_window.add(insiders[j])
        if len(buyers_in_window) >= 3:
            return True
    return False


def _aggregate_window(
    transactions: list[dict[str, Any]],
    as_of: str,
    window_days: int,
    role_weights: dict[str, float],
) -> dict[str, Any]:
    """Compute buy/sell stats for a single lookback window."""
    buy_txns: list[dict[str, Any]] = []
    sell_txns: list[dict[str, Any]] = []
    sell_standalone: list[dict[str, Any]] = []

    for txn in transactions:
        code = str(txn.get("transaction_code", txn.get("type", ""))).strip().upper()
        date = str(txn.get("date", ""))
        if not date or not _txn_within_window(date, as_of, window_days):
            continue
        if code in _EXCLUDED_CODES:
            continue
        if code in _BUY_CODES:
            buy_txns.append(txn)
        elif code in _SELL_CODES:
            # Determine if standalone or scheduled
            if _is_10b5_scheduled(txn):
                pass  # scheduled; do not count as bearish signal
            else:
                sell_standalone.append(txn)
            sell_txns.append(txn)

    # Aggregates for buys
    buy_count = len(buy_txns)
    buy_distinct = len({t["insider_name"] for t in buy_txns})
    buy_shares = sum(float(t.get("shares", 0) or 0) for t in buy_txns)
    buy_value = sum(float(t.get("value", 0) or 0) for t in buy_txns)

    # Aggregates for sells (all S codes, including scheduled)
    sell_count = len(sell_txns)
    sell_distinct = len({t["insider_name"] for t in sell_txns})
    sell_shares = sum(float(t.get("shares", 0) or 0) for t in sell_txns)
    sell_value = sum(float(t.get("value", 0) or 0) for t in sell_txns)

    # Net
    net_shares = buy_shares - sell_shares
    net_value = buy_value - sell_value
    buy_sell_ratio = buy_value / max(sell_value, _EPSILON)

    # Active insiders = distinct buyers + distinct standalone sellers
    distinct_standalone_sellers = len({t["insider_name"] for t in sell_standalone})
    active_distinct = buy_distinct + distinct_standalone_sellers
    pct_buying = buy_distinct / max(active_distinct, 1)

    # Cluster detection (buy only)
    cluster_detected = _detect_cluster(buy_txns, window_days=30)

    # Role-weighted net value
    rw_buy = sum(
        float(t.get("value", 0) or 0) * _role_weight(str(t.get("role", "Other")), role_weights)
        for t in buy_txns
    )
    rw_sell = sum(
        float(t.get("value", 0) or 0) * _role_weight(str(t.get("role", "Other")), role_weights)
        for t in sell_standalone
    )
    role_weighted_net_value = rw_buy - rw_sell

    # Largest single buy
    largest_buy: dict[str, Any] | None = None
    if buy_txns:
        top = max(buy_txns, key=lambda t: float(t.get("value", 0) or 0))
        shares_before = float(top.get("shares_owned_after", 0) or 0) - float(
            top.get("shares", 0) or 0
        )
        pct_inc = (
            float(top.get("shares", 0) or 0) / max(abs(shares_before), _EPSILON)
            if shares_before >= 0
            else None
        )
        largest_buy = {
            "insider": str(top.get("insider_name", "")),
            "role": str(top.get("role", "")),
            "value": float(top.get("value", 0) or 0),
            "pct_increase_in_holdings": round(pct_inc, 4) if pct_inc is not None else None,
        }

    return {
        "open_market_buys": {
            "count": buy_count,
            "distinct_insiders": buy_distinct,
            "shares": buy_shares,
            "value": buy_value,
        },
        "open_market_sells": {
            "count": sell_count,
            "distinct_insiders": sell_distinct,
            "shares": sell_shares,
            "value": sell_value,
        },
        "standalone_sells": len(sell_standalone),
        "net_shares": net_shares,
        "net_value": net_value,
        "buy_sell_value_ratio": round(buy_sell_ratio, 4),
        "pct_insiders_buying": round(pct_buying, 4),
        "cluster_buy_detected": cluster_detected,
        "role_weighted_net_value": round(role_weighted_net_value, 2),
        "largest_single_buy": largest_buy,
    }


def _classify_signal(
    windows: dict[str, dict[str, Any]],
) -> tuple[str, str]:
    """Return (signal_classification, signal_confidence)."""
    # Use primary window (90d if present, else first available)
    primary_key = next(iter(windows))
    for k in windows:
        if k.startswith("90"):
            primary_key = k
            break

    w = windows[primary_key]
    net_value = w["net_value"]
    cluster = w["cluster_buy_detected"]
    pct_buying = w["pct_insiders_buying"]
    rw_net = w["role_weighted_net_value"]
    buy_count = w["open_market_buys"]["count"]
    buy_distinct = w["open_market_buys"]["distinct_insiders"]
    standalone_sells = w["standalone_sells"]

    if cluster and rw_net > 0 and pct_buying >= 0.5:
        classification = "bullish"
    elif net_value > 0 and buy_count >= 1:
        # Check if CEO or CFO among buyers
        classification = "mildly_bullish"
    elif abs(net_value) < 1.0:
        classification = "neutral"
    elif standalone_sells > 2 and net_value < 0:
        classification = "bearish"
    elif net_value < 0:
        classification = "mildly_bearish"
    else:
        classification = "neutral"

    # Confidence: scale with distinct insiders and whether cluster detected
    if buy_distinct >= 3 or cluster:
        confidence = "high"
    elif buy_distinct >= 1 and buy_count >= 1:
        confidence = "moderate"
    else:
        confidence = "low"

    return classification, confidence


def execute(
    transactions: list[dict[str, Any]],
    lookback_windows: list[int] | None = None,
    as_of: str | None = None,
    role_weights: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Compute insider signal panel from Form 4 transactions.

    Args:
        transactions: List of Form 4 transaction records. Each should contain:
            date (YYYY-MM-DD), insider_name, role, transaction_code (P/S/A/M/F/etc.),
            shares, value (total USD), shares_owned_after.
        lookback_windows: Trailing day windows to summarize. Default [90, 180, 365].
        as_of: Reference date (YYYY-MM-DD). Default "9999-12-31" (includes all).
        role_weights: Custom role weights dict. Defaults to CEO/CFO/President/Officer/Director.

    Returns:
        Dict with windows summary, signal_classification, signal_confidence,
        excluded_transactions counts.
    """
    if not transactions:
        raise ValueError("transactions must not be empty")

    if lookback_windows is None:
        lookback_windows = [90, 180, 365]
    if as_of is None:
        # Use a far-future date so all transactions are included
        as_of = "9999-12-31"
    if role_weights is None:
        role_weights = _DEFAULT_ROLE_WEIGHTS

    # Count excluded codes across all transactions
    excluded_counts: dict[str, int] = {}
    for txn in transactions:
        code = str(txn.get("transaction_code", txn.get("type", ""))).strip().upper()
        if code in _EXCLUDED_CODES:
            label = _EXCLUDED_CODE_LABELS.get(code, f"other_{code}")
            excluded_counts[label] = excluded_counts.get(label, 0) + 1

    # Compute per-window stats
    windows: dict[str, dict[str, Any]] = {}
    for days in lookback_windows:
        key = f"{days}d"
        windows[key] = _aggregate_window(transactions, as_of, days, role_weights)

    signal_class, signal_conf = _classify_signal(windows)

    return {
        "windows": windows,
        "signal_classification": signal_class,
        "signal_confidence": signal_conf,
        "excluded_transactions": excluded_counts,
        "data_as_of": as_of,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="insider_signal_panel",
        category=Category.SIGNALS,
        one_liner="Form 4 insider trading signal: code-filtered, role-weighted, cluster-detected.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Convert SEC Form 4 insider transactions into a structured buying/selling signal. "
            "Filters out compensation-related codes (A/M/F/G), weights by insider role, "
            "detects cluster buying (>=3 distinct insiders in 30 days), and classifies "
            "signal direction (bullish/mildly_bullish/neutral/mildly_bearish/bearish)."
        ),
        when_to_use=[
            "Initiation reports: add insider conviction context to the thesis.",
            "Update reports post-quarter: check if insiders bought the dip or sold into strength.",
            "Sector comparisons: cross-company cohort insider activity.",
        ],
        when_not_to_use=[
            "Real-time trading decisions — Form 4 filings have a 2-business-day lag.",
            "When raw transactions only have a coarse buy/sell flag (no transaction code) — "
            "the code-filtering step is a build-blocker; fall back to a simple net-buy count.",
            "Options / derivative analysis — use ft_capital_structure or dedicated options helper.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "transactions": HelperParam(
                type="list[dict]",
                required=True,
                description=(
                    "Form 4 transaction records from eodhd_insider_transactions. "
                    "Required keys per record: date (YYYY-MM-DD), insider_name, role, "
                    "transaction_code (P/S/A/M/F/G/C/D/X), shares, value (USD)."
                ),
            ),
            "lookback_windows": HelperParam(
                type="list[int]",
                required=False,
                default=[90, 180, 365],
                description="Trailing-day windows for aggregation. Default [90, 180, 365].",
            ),
            "as_of": HelperParam(
                type="str | None",
                required=False,
                default=None,
                description=(
                    "Reference date YYYY-MM-DD. Transactions after this date excluded. "
                    "Default: include all."
                ),
            ),
            "role_weights": HelperParam(
                type="dict | None",
                required=False,
                default=None,
                description=(
                    "Custom role weights. Default: CEO/CFO=1.0, President=0.8, "
                    "Officer=0.6, Director=0.5, 10%_owner=0.3."
                ),
            ),
        },
        outputs=[
            HelperOutput(
                name="insider_signal_panel",
                type="dict",
                description=(
                    "windows (90d/180d/365d): buy/sell counts, net value, cluster_detected, "
                    "role_weighted_net_value, largest_single_buy. "
                    "signal_classification, signal_confidence, excluded_transactions."
                ),
            ),
        ],
        produces_artifacts=["insider_signal_output"],
        consumes_artifacts=["eodhd_insider_transactions_output"],
    ),
    skill_doc=SkillDocRef(path="skills/insider_signal_panel.md", estimated_tokens=1600),
    verifier_hooks=[
        VerifierIssueType.NUMERIC_INCONSISTENCY,
        VerifierIssueType.CITATION_MISSING,
        VerifierIssueType.FACTUAL_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
