"""Per-fact freshness budgets (WS10-B).

Each fact has a maximum age in days. If a Fact's `data_as_of` exceeds its
budget, the runner refuses to render the report (severity="hard_block").
Missing `data_as_of` is surfaced as severity="missing" — a warning, not a
block — because the upstream payload may legitimately lack any filing date.

Budgets are matched by name *prefix* (longest-match wins). Add new buckets
to `FRESHNESS_BUDGETS` rather than embedding them in the checker.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from openlia.llm.runtime.report_v2.types import Fact

# Name-prefix → max age in days. Longest matching prefix wins, so more
# specific budgets (e.g. "consensus_revenue_") override shorter ones
# (e.g. "consensus_"). Order does not matter; the checker sorts by length.
FRESHNESS_BUDGETS: dict[str, int] = {
    # Price- and live-quote-driven facts must be near-current.
    "current_price": 7,
    "pe_ratio_ttm": 7,
    "market_cap": 7,
    # Analyst-driven facts refresh weekly to monthly.
    "consensus_": 14,
    "analyst_": 30,
    # Quarterly facts: one quarter + buffer.
    "revenue_q": 100,
    "eps_q": 100,
    # Annual facts: one year + grace for late filers.
    "revenue_annual": 380,
    "eps_annual": 380,
    "gross_profit_annual": 380,
    "operating_income_annual": 380,
    "net_income_annual": 380,
    "cogs_annual": 380,
    "total_assets_annual": 380,
    "total_liabilities_annual": 380,
    "equity_annual": 380,
    "cash_annual": 380,
    "total_debt_annual": 380,
    "gross_margin_annual": 380,
    "operating_margin_annual": 380,
    "net_margin_annual": 380,
    "revenue_cagr_3y": 380,
}


Severity = Literal["hard_block", "missing", "warn"]


@dataclass(frozen=True)
class FreshnessViolation:
    fact_name: str
    data_as_of: datetime | str | None
    age_days: int | None
    budget_days: int
    severity: Severity


class StaleDataError(Exception):
    """Raised by the runner when one or more facts violate hard-block budgets.

    `violations` carries the full structured list so the caller can render an
    actionable diagnostic (offending fact, its `data_as_of`, and the budget)."""

    def __init__(self, violations: list[FreshnessViolation]) -> None:
        self.violations = violations
        super().__init__(self._format(violations))

    @staticmethod
    def _format(violations: list[FreshnessViolation]) -> str:
        hard = [v for v in violations if v.severity == "hard_block"]
        parts = [
            f"{v.fact_name} (as_of={v.data_as_of}, age={v.age_days}d > budget={v.budget_days}d)"
            for v in hard
        ]
        return "stale data: " + "; ".join(parts) if parts else "stale data"


def _budget_for(name: str, budgets: dict[str, int] | None = None) -> int | None:
    """Return the freshness budget in days for `name`, or None when unbudgeted.

    Uses longest-prefix matching so a specific bucket beats a generic one.
    `budgets` defaults to the module-level `FRESHNESS_BUDGETS` for backward
    compatibility; callers should pass the active template's budget map.
    """
    table = budgets if budgets is not None else FRESHNESS_BUDGETS
    best: tuple[int, int] | None = None  # (prefix_len, budget_days)
    for prefix, days in table.items():
        if name == prefix or name.startswith(prefix):
            n = len(prefix)
            if best is None or n > best[0]:
                best = (n, days)
    return best[1] if best is not None else None


def _to_datetime(value: datetime | str | None) -> datetime | None:
    """Parse a date-like value to a UTC-aware datetime. Returns None for None
    or unparseable input — callers treat unparseable like missing."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        # Accept "YYYY-MM-DD", ISO 8601, and ISO with trailing Z.
        s = value.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(s)
        except ValueError:
            try:
                parsed = datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                return None
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return None


def check_freshness(
    facts: dict[str, Fact],
    as_of: datetime,
    budgets: dict[str, int] | None = None,
) -> list[FreshnessViolation]:
    """Return the list of freshness violations for `facts` measured against `as_of`.

    `budgets` is the per-template name-prefix → max-age map. When None, falls
    back to the module-level `FRESHNESS_BUDGETS` for backward compatibility;
    callers driving uploaded templates should pass `template.freshness_budgets`.
    Facts without a registered budget are skipped silently. Facts whose
    `data_as_of` is None are reported as severity="missing" so the runner
    can warn without blocking.
    """
    as_of_aware = as_of if as_of.tzinfo is not None else as_of.replace(tzinfo=UTC)
    out: list[FreshnessViolation] = []
    for name, fact in facts.items():
        budget = _budget_for(name, budgets)
        if budget is None:
            continue
        dt = _to_datetime(fact.data_as_of)
        if dt is None:
            out.append(
                FreshnessViolation(
                    fact_name=name,
                    data_as_of=fact.data_as_of,
                    age_days=None,
                    budget_days=budget,
                    severity="missing",
                )
            )
            continue
        age = (as_of_aware - dt).days
        if age > budget:
            out.append(
                FreshnessViolation(
                    fact_name=name,
                    data_as_of=fact.data_as_of,
                    age_days=age,
                    budget_days=budget,
                    severity="hard_block",
                )
            )
    return out


def oldest_data_as_of(facts: dict[str, Fact]) -> datetime | str | None:
    """Return the oldest `data_as_of` across `facts` (the conservative banner date).

    Skips facts with `data_as_of=None` and facts whose date is unparseable.
    Returns the original `data_as_of` value (str or datetime) for display."""
    oldest: tuple[datetime, datetime | str] | None = None
    for fact in facts.values():
        dt = _to_datetime(fact.data_as_of)
        if dt is None:
            continue
        if oldest is None or dt < oldest[0]:
            oldest = (dt, fact.data_as_of)
    return oldest[1] if oldest is not None else None
