"""Industry-mode selector (WS9).

Picks one of four `stock_initiation` overlays based on subject industry/sector
facts and the material-events scan output. The runner consults this module
between facts compilation and section dispatch, then applies the matching
overlay JSON via `framework_overlay.deep_merge`.

Selection rules (deterministic, auditable, override-able):

  1. If any material event in the last 24 months indicates Chapter 11,
     bankruptcy emergence, or delisting OR the audit opinion is going-concern
     qualified OR TTM revenue growth is below -30% with negative FCF -> distressed.
  2. Else if sector == "Technology" AND industry matches the SaaS regex -> saas.
  3. Else if sector == "Technology" AND industry matches the semis regex -> semis.
  4. Else -> generic.

Distressed is sticky for 24 months post-emergence by design — the event window
captures both the filing and the emergence; either triggers distressed mode.

Manual override: the runner accepts `report_mode_override: ReportMode | None`.
When supplied it bypasses auto-selection entirely.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from openlia.llm.runtime.report_v2.scanners.material_events import MaterialEvent
from openlia.llm.runtime.report_v2.types import Fact

ReportMode = Literal["generic", "saas", "semis", "distressed"]

# Event classes the selector treats as evidence of distress when they fall
# within the last 24 months of the as-of date.
_DISTRESS_EVENT_CLASSES: frozenset[str] = frozenset(
    {"chapter_11", "bankruptcy_emergence", "delisting"}
)

# Industry regex patterns. Compiled at module load — module-level constants are
# safe under the deterministic-selector contract.
_SAAS_INDUSTRY_PATTERN = re.compile(
    r"(Software|Cloud|SaaS|Information Technology Services|Internet Software & Services)",
    re.IGNORECASE,
)
_SEMIS_INDUSTRY_PATTERN = re.compile(
    r"(Semiconductors|Semiconductor Equipment|Electronic Components|Hardware)",
    re.IGNORECASE,
)

# Distressed audit-opinion sentinel substring (case-insensitive).
_GOING_CONCERN_SUBSTR = "going concern"

# Distress thresholds for the financial-trigger branch (TTM growth < -30% with
# negative FCF). Expressed as ratios (not percent points).
_DISTRESS_GROWTH_THRESHOLD = -0.30


def _fact_value(facts: dict[str, Fact], name: str) -> object | None:
    f = facts.get(name)
    return None if f is None else f.value


def _as_str(value: object | None) -> str:
    return "" if value is None else str(value)


def _as_float(value: object | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):  # bool subclasses int — must precede int check
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().rstrip("%")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _event_within_window(event: MaterialEvent, as_of: date, window_months: int) -> bool:
    """True iff `event.event_date` is within the last `window_months` months of `as_of`.

    A null event_date falls through to True — the scanner has high confidence
    in the event class but couldn't parse a date, and the conservative call is
    to treat it as recent."""
    if event.event_date is None:
        return True
    window = timedelta(days=window_months * 31)  # generous month approximation
    return as_of - event.event_date <= window


def _has_recent_distress_event(
    events: list[MaterialEvent],
    as_of: date,
    window_months: int = 24,
) -> bool:
    for e in events:
        if e.event_class in _DISTRESS_EVENT_CLASSES and _event_within_window(
            e, as_of, window_months
        ):
            return True
    return False


def _is_going_concern_qualified(facts: dict[str, Fact]) -> bool:
    """Check the `audit_opinion` fact for a going-concern qualification."""
    val = _fact_value(facts, "audit_opinion")
    return _GOING_CONCERN_SUBSTR in _as_str(val).lower()


def _is_distressed_financials(facts: dict[str, Fact]) -> bool:
    """TTM revenue growth < -30% AND negative free cash flow."""
    growth = _as_float(_fact_value(facts, "revenue_growth_ttm"))
    fcf = _as_float(_fact_value(facts, "free_cash_flow_ttm"))
    if growth is None or fcf is None:
        return False
    return growth < _DISTRESS_GROWTH_THRESHOLD and fcf < 0


def select_report_mode(
    facts: dict[str, Fact],
    material_events: list[MaterialEvent],
    *,
    as_of: date | None = None,
) -> ReportMode:
    """Pick one of four overlays based on subject industry, sector, and events.

    `as_of` defaults to today (UTC) when None — only used for the distress
    event-recency window. Selection is deterministic given the inputs."""
    as_of_date = as_of if as_of is not None else datetime.now(UTC).date()

    # 1) Distressed gate — first because it overrides industry classification.
    if (
        _has_recent_distress_event(material_events, as_of_date)
        or _is_going_concern_qualified(facts)
        or _is_distressed_financials(facts)
    ):
        return "distressed"

    sector = _as_str(_fact_value(facts, "sector"))
    industry = _as_str(_fact_value(facts, "industry"))

    if sector == "Technology" and _SAAS_INDUSTRY_PATTERN.search(industry):
        return "saas"

    if sector == "Technology" and _SEMIS_INDUSTRY_PATTERN.search(industry):
        return "semis"

    return "generic"
