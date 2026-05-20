"""Numeric reconciliation validator (WS4 / P7).

Runs after all section files are written but before the report is finalised.
Catches the class of LLM error that the per-section validator cannot see:
year-label slips, fabricated numbers, arithmetic mistakes, cross-section
identity-equation violations, missing date stamps, first-person voice in the
analyst_view section, and tombstone phrases anywhere.

The validator is pure Python over already-generated markdown text. It does
NOT call the LLM. When a section carries a soft `numeric_not_in_facts`
failure, the runner MAY choose to re-render that one section with the
failure details inlined into the retry prompt — see the
`build_section_retry_prompt` helper at the bottom of this module. The runner
caps retries at 1 to avoid infinite loops.

Tolerances are tuned for institutional-quality reports:

* Numeric equality:           tolerance_pct (default 1.0%)
* Arithmetic spot-checks:     arithmetic_tolerance_pct (default 0.5%)
* Identity equations:         identity_tolerance_pct (default 2.0%)
* Operating margin agreement: 0.5 percentage points (absolute)
* Upside equation:            0.5 percentage points (absolute)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from openlia.llm.runtime.report_v2.sections.prompts import TOMBSTONE_PHRASES
from openlia.llm.runtime.report_v2.types import Fact

FailureType = Literal[
    "year_label_mismatch",
    "numeric_not_in_facts",
    "arithmetic_disagreement",
    "identity_equation_violation",
    "missing_data_as_of",
    "first_person_voice",
    "tombstone_phrase",
]

# Failure types that are hard-blocking by default. The runner can flip
# `numeric_validation_override=True` to bypass everything, but on a normal
# run the presence of any hard failure raises NumericValidationError.
_HARD_FAILURE_TYPES: frozenset[FailureType] = frozenset(
    {
        "identity_equation_violation",
        "arithmetic_disagreement",
        "first_person_voice",
        "tombstone_phrase",
        "year_label_mismatch",
    }
)


@dataclass
class ValidatorFailure:
    section_id: str
    failure_type: FailureType
    detail: str
    offending_text: str | None = None
    expected_value: Any | None = None
    actual_value: Any | None = None
    fact_name: str | None = None
    tolerance: float | None = None


@dataclass
class ValidatorReport:
    failures: list[ValidatorFailure] = field(default_factory=list)
    sections_inspected: int = 0
    numbers_inspected: int = 0
    identity_equations_checked: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.failures) == 0

    @property
    def hard_failures(self) -> list[ValidatorFailure]:
        return [f for f in self.failures if f.failure_type in _HARD_FAILURE_TYPES]

    @property
    def soft_failures(self) -> list[ValidatorFailure]:
        return [f for f in self.failures if f.failure_type not in _HARD_FAILURE_TYPES]


class NumericValidationError(Exception):
    """Raised when hard numeric-consistency failures are present.

    The runner can bypass this with `numeric_validation_override=True`. The
    structured failure list is preserved on `.failures` so the caller can
    surface an actionable diagnostic.
    """

    def __init__(self, failures: list[ValidatorFailure]) -> None:
        self.failures = failures
        super().__init__(self._format(failures))

    @staticmethod
    def _format(failures: list[ValidatorFailure]) -> str:
        if not failures:
            return "numeric validation failed"
        parts = [f"[{f.section_id}] {f.failure_type}: {f.detail}" for f in failures[:10]]
        suffix = "" if len(failures) <= 10 else f" (+{len(failures) - 10} more)"
        return "numeric validation failed: " + " | ".join(parts) + suffix


# ---------------------------------------------------------------------------
# Numeric extraction
# ---------------------------------------------------------------------------

# Match common quantitative figures in prose. Patterns are tried in order;
# the first match wins for each text span. False positives are acceptable
# because each match is then checked against the facts within tolerance; a
# false-positive number that happens to match a fact still passes.
#
# Each pattern carries a `kind`: currency, percent, basis_points, ratio,
# dollar_amount, count.

_NUM = r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # $1.2B, $215.9 B, $5.3 trillion, $100M, etc.
    (
        "currency_scaled",
        re.compile(
            rf"\$\s?({_NUM})\s*(trillion|billion|million|thousand|[TtBbMmKk])\b",
            re.IGNORECASE,
        ),
    ),
    # 23.5%, -1.0%, +5.4%
    ("percent", re.compile(rf"([+-]?{_NUM})\s*%")),
    # 250bps, 250 bps, 250bp
    ("basis_points", re.compile(rf"({_NUM})\s*bps?\b", re.IGNORECASE)),
    # 38.2x, 0.68x (multiples). Must not be preceded by a letter (avoid
    # IDs like "block-3x" or words ending in x).
    ("ratio", re.compile(rf"(?<![A-Za-z\d]){_NUM}x\b")),
    # $173, $5,200, $1.23 (un-scaled currency)
    ("currency_plain", re.compile(rf"\$\s?({_NUM})(?![A-Za-z\d])")),
]


@dataclass
class ExtractedNumber:
    raw: str
    kind: Literal["currency_scaled", "currency_plain", "percent", "basis_points", "ratio"]
    value: float
    start: int
    end: int


_SCALE_MAP: dict[str, float] = {
    "t": 1e12,
    "trillion": 1e12,
    "b": 1e9,
    "billion": 1e9,
    "m": 1e6,
    "million": 1e6,
    "k": 1e3,
    "thousand": 1e3,
}


def _normalize(raw: str) -> float:
    return float(raw.replace(",", "").replace("+", "").strip())


def extract_numbers(text: str) -> list[ExtractedNumber]:
    """Pull every quantitative figure out of `text` with its normalized value.

    Percent values are returned as decimals (60.4% -> 0.604). Basis points
    are returned as decimals (250bps -> 0.025). Currency-scaled amounts are
    expanded to their full numeric form ($215.9B -> 215_900_000_000).
    Ratios ("38.2x") are returned as plain floats.

    Overlapping matches are de-duplicated by start position (first pattern
    in `_PATTERNS` wins).
    """
    seen: set[tuple[int, int]] = set()
    out: list[ExtractedNumber] = []
    for kind, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if any(s <= span[0] < e or s < span[1] <= e for s, e in seen):
                continue
            try:
                if kind == "currency_scaled":
                    base = _normalize(m.group(1))
                    suffix = m.group(2).lower()
                    value = base * _SCALE_MAP[suffix]
                elif kind == "percent":
                    value = _normalize(m.group(1)) / 100.0
                elif kind == "basis_points":
                    value = _normalize(m.group(1)) / 10_000.0
                elif kind == "ratio":
                    value = _normalize(m.group(0)[:-1])
                elif kind == "currency_plain":
                    value = _normalize(m.group(1))
                else:  # pragma: no cover — exhaustive above
                    continue
            except (KeyError, ValueError):
                continue
            seen.add(span)
            out.append(
                ExtractedNumber(
                    raw=m.group(0).strip(),
                    kind=kind,  # type: ignore[arg-type]
                    value=value,
                    start=span[0],
                    end=span[1],
                )
            )
    return sorted(out, key=lambda n: n.start)


# ---------------------------------------------------------------------------
# Year-label consistency
# ---------------------------------------------------------------------------

_FY_RE = re.compile(r"FY\s?(20\d{2})")


def _allowed_years(facts: dict[str, Fact]) -> set[int]:
    allowed: set[int] = set()
    rev_years = facts.get("revenue_years")
    if rev_years is not None and isinstance(rev_years.value, list | tuple):
        for y in rev_years.value:
            try:
                allowed.add(int(y))
            except (TypeError, ValueError):
                continue
    fy_end = facts.get("fiscal_year_end_latest")
    if fy_end is not None and isinstance(fy_end.value, str):
        m = re.search(r"(20\d{2})", fy_end.value)
        if m:
            allowed.add(int(m.group(1)))
    return allowed


def _check_year_labels(
    section_id: str, prose: str, facts: dict[str, Fact]
) -> list[ValidatorFailure]:
    allowed = _allowed_years(facts)
    if not allowed:
        return []
    failures: list[ValidatorFailure] = []
    for m in _FY_RE.finditer(prose):
        year = int(m.group(1))
        if year not in allowed:
            failures.append(
                ValidatorFailure(
                    section_id=section_id,
                    failure_type="year_label_mismatch",
                    detail=(f"prose cites FY{year} but allowed years are {sorted(allowed)}"),
                    offending_text=m.group(0),
                    expected_value=sorted(allowed),
                    actual_value=year,
                )
            )
    return failures


# ---------------------------------------------------------------------------
# Numeric ↔ fact equality
# ---------------------------------------------------------------------------


def _is_numeric(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _within_pct(actual: float, expected: float, tolerance_pct: float) -> bool:
    if expected == 0:
        return abs(actual) <= tolerance_pct / 100.0
    return abs(actual - expected) / abs(expected) <= tolerance_pct / 100.0


def _closest_fact(
    value: float, facts: dict[str, Fact], tolerance_pct: float
) -> tuple[str | None, float | None]:
    """Find the closest numeric fact to `value` within `tolerance_pct`.

    Returns (fact_name, fact_value) or (None, None) if no fact is within
    tolerance. When a fact matches, the closest by relative distance wins.
    """
    best_name: str | None = None
    best_value: float | None = None
    best_dist: float = float("inf")
    for name, fact in facts.items():
        v = fact.value
        if not _is_numeric(v):
            continue
        f = float(v)
        if not _within_pct(value, f, tolerance_pct):
            continue
        denom = abs(f) if f != 0 else 1.0
        dist = abs(value - f) / denom
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_value = f
    return best_name, best_value


def _is_derivable(value: float, facts: dict[str, Fact], tolerance_pct: float) -> bool:
    """Quick check whether `value` is derivable from facts via small operations.

    Tries: pairwise ratios, sums, simple differences, growth %. False
    positives are OK because they shrink the noise rate of
    `numeric_not_in_facts`; false negatives are not OK because they trigger
    needless retries.
    """
    numeric: list[float] = [float(f.value) for f in facts.values() if _is_numeric(f.value)]
    if not numeric:
        return False
    # Pairwise ratios and differences (cap to first 25 numeric facts to keep
    # the loop bounded).
    sample = numeric[:25]
    for a in sample:
        for b in sample:
            if a is b:
                continue
            if b != 0:
                if _within_pct(value, a / b, tolerance_pct):
                    return True
                # Growth %
                if _within_pct(value, (a - b) / b, tolerance_pct):
                    return True
            if _within_pct(value, a + b, tolerance_pct):
                return True
            if _within_pct(value, a - b, tolerance_pct):
                return True
    return False


def _closest_for_diagnostic(
    value: float, facts: dict[str, Fact]
) -> tuple[str | None, float | None]:
    """Closest numeric fact to `value` ignoring tolerance (for diagnostic only)."""
    best_name: str | None = None
    best_value: float | None = None
    best_dist: float = float("inf")
    for name, fact in facts.items():
        v = fact.value
        if not _is_numeric(v):
            continue
        f = float(v)
        denom = abs(f) if f != 0 else 1.0
        dist = abs(value - f) / denom
        if dist < best_dist:
            best_dist = dist
            best_name = name
            best_value = f
    return best_name, best_value


def _check_numeric_equality(
    section_id: str,
    prose: str,
    facts: dict[str, Fact],
    tolerance_pct: float,
    numbers_inspected_counter: list[int],
) -> list[ValidatorFailure]:
    failures: list[ValidatorFailure] = []
    for n in extract_numbers(prose):
        numbers_inspected_counter[0] += 1
        # Years like "2024" are filtered already by our regex (no $/%/x).
        match_name, _ = _closest_fact(n.value, facts, tolerance_pct)
        if match_name is not None:
            continue
        if _is_derivable(n.value, facts, tolerance_pct):
            continue
        # Diagnostic: closest fact even if out-of-tolerance.
        closest_name, closest_value = _closest_for_diagnostic(n.value, facts)
        failures.append(
            ValidatorFailure(
                section_id=section_id,
                failure_type="numeric_not_in_facts",
                detail=(
                    f"prose cites {n.raw!r} (normalized {n.value:g}) which "
                    f"matches no fact within {tolerance_pct}% tolerance"
                ),
                offending_text=n.raw,
                expected_value=closest_value,
                actual_value=n.value,
                fact_name=closest_name,
                tolerance=tolerance_pct,
            )
        )
    return failures


# ---------------------------------------------------------------------------
# Arithmetic spot-checks
# ---------------------------------------------------------------------------

# "PEG of 0.68", "PEG 1.2x"
_PEG_RE = re.compile(r"PEG\s+(?:of\s+|ratio\s+(?:of\s+)?)?(-?\d+(?:\.\d+)?)x?", re.IGNORECASE)
# "EV/EBITDA of 18.2x"
_EV_EBITDA_RE = re.compile(
    r"EV\s*/\s*EBITDA\s+(?:of\s+|ratio\s+(?:of\s+)?)?(-?\d+(?:\.\d+)?)x?", re.IGNORECASE
)
# "margin spread of 1240 bps" or "spread of 12.4 percentage points"
_SPREAD_RE = re.compile(
    r"(?:gross\s*-\s*to\s*-\s*operating|gross\s+to\s+operating)\s+"
    r"(?:margin\s+)?spread\s+of\s+(-?\d+(?:\.\d+)?)\s*(bps?|pp|percentage\s+points|%)",
    re.IGNORECASE,
)


def _facts_get_numeric(facts: dict[str, Fact], name: str) -> float | None:
    f = facts.get(name)
    if f is None or not _is_numeric(f.value):
        return None
    return float(f.value)


def _check_arithmetic(
    section_id: str,
    prose: str,
    facts: dict[str, Fact],
    arithmetic_tolerance_pct: float,
) -> list[ValidatorFailure]:
    failures: list[ValidatorFailure] = []

    # PEG: pe_ratio_forward / consensus_eps_growth_fy_next (in percent units,
    # per P4 convention — i.e. 1.00 = 100%).
    for m in _PEG_RE.finditer(prose):
        cited = float(m.group(1))
        pe = _facts_get_numeric(facts, "pe_ratio_forward")
        growth = _facts_get_numeric(facts, "consensus_eps_growth_fy_next")
        if pe is None or growth is None or growth == 0:
            continue
        # Convention: growth is stored as decimal (1.00 = 100%); PEG divides
        # P/E by percent growth (NOT by decimal), so multiply by 100.
        expected = pe / (growth * 100.0)
        if not _within_pct(cited, expected, arithmetic_tolerance_pct):
            failures.append(
                ValidatorFailure(
                    section_id=section_id,
                    failure_type="arithmetic_disagreement",
                    detail=(
                        f"cited PEG {cited} disagrees with computed "
                        f"pe_ratio_forward / (consensus_eps_growth_fy_next "
                        f"* 100) = {expected:.4f}"
                    ),
                    offending_text=m.group(0),
                    expected_value=expected,
                    actual_value=cited,
                    fact_name="pe_ratio_forward / consensus_eps_growth_fy_next",
                    tolerance=arithmetic_tolerance_pct,
                )
            )

    # EV/EBITDA: prefer ev_to_ebitda_forward fact; fall back to derived.
    for m in _EV_EBITDA_RE.finditer(prose):
        cited = float(m.group(1))
        direct = _facts_get_numeric(facts, "ev_to_ebitda_forward")
        derived: float | None = None
        market_cap = _facts_get_numeric(facts, "market_cap")
        total_debt = _facts_get_numeric(facts, "total_debt")
        cash = _facts_get_numeric(facts, "cash_and_short_term_investments")
        ebitda = _facts_get_numeric(facts, "ebitda_ttm")
        if all(v is not None for v in (market_cap, total_debt, cash, ebitda)) and ebitda:  # type: ignore[truthy-bool]
            derived = (market_cap + total_debt - cash) / ebitda  # type: ignore[operator]
        expected = direct if direct is not None else derived
        if expected is None:
            continue
        if not _within_pct(cited, expected, arithmetic_tolerance_pct):
            failures.append(
                ValidatorFailure(
                    section_id=section_id,
                    failure_type="arithmetic_disagreement",
                    detail=(f"cited EV/EBITDA {cited} disagrees with expected {expected:.4f}"),
                    offending_text=m.group(0),
                    expected_value=expected,
                    actual_value=cited,
                    fact_name="ev_to_ebitda_forward",
                    tolerance=arithmetic_tolerance_pct,
                )
            )

    # Margin spread: recompute from gross_margin_ttm - operating_margin_ttm.
    for m in _SPREAD_RE.finditer(prose):
        cited_raw = float(m.group(1))
        unit = m.group(2).lower()
        if "bp" in unit:
            cited = cited_raw / 10_000.0
        elif "%" in unit:
            cited = cited_raw / 100.0
        else:  # percentage points
            cited = cited_raw / 100.0
        gm = _facts_get_numeric(facts, "gross_margin_ttm")
        om = _facts_get_numeric(facts, "operating_margin_ttm")
        if gm is None or om is None:
            continue
        expected = gm - om
        if not _within_pct(cited, expected, arithmetic_tolerance_pct):
            failures.append(
                ValidatorFailure(
                    section_id=section_id,
                    failure_type="arithmetic_disagreement",
                    detail=(
                        f"cited margin spread {cited:.4f} disagrees with "
                        f"gross_margin_ttm - operating_margin_ttm = "
                        f"{expected:.4f}"
                    ),
                    offending_text=m.group(0),
                    expected_value=expected,
                    actual_value=cited,
                    fact_name="gross_margin_ttm - operating_margin_ttm",
                    tolerance=arithmetic_tolerance_pct,
                )
            )

    return failures


# ---------------------------------------------------------------------------
# Cross-section identity equations
# ---------------------------------------------------------------------------

_BUY_RATINGS: frozenset[str] = frozenset({"buy", "strong buy", "strongbuy"})
_SELL_RATINGS: frozenset[str] = frozenset({"sell", "strong sell", "strongsell"})


def _check_identity_equations(
    section_files: dict[str, str],
    facts: dict[str, Fact],
    consensus_facts: dict[str, Any] | None,
    identity_tolerance_pct: float,
    arithmetic_tolerance_pct: float,
    tolerance_pct: float,
) -> tuple[list[ValidatorFailure], list[str]]:
    failures: list[ValidatorFailure] = []
    checked: list[str] = []

    current_price = _facts_get_numeric(facts, "current_price")
    shares_outstanding = _facts_get_numeric(facts, "shares_outstanding")
    market_cap = _facts_get_numeric(facts, "market_cap")
    revenue_ttm = _facts_get_numeric(facts, "revenue_ttm")
    operating_margin_ttm = _facts_get_numeric(facts, "operating_margin_ttm")
    operating_income_ttm = _facts_get_numeric(facts, "operating_income_ttm")

    # consensus_target_mean / consensus_upside_pct / consensus_rating may
    # live under analyst_* facts or in the supplied consensus_facts dict.
    def _get_consensus(name: str, alt: str | None = None) -> Any:
        if consensus_facts is not None and name in consensus_facts:
            return consensus_facts[name]
        f = facts.get(name)
        if f is not None:
            return f.value
        if alt is not None:
            f = facts.get(alt)
            if f is not None:
                return f.value
        return None

    consensus_target_mean = _get_consensus("consensus_target_mean", "analyst_target_mean")
    consensus_upside_pct = _get_consensus("consensus_upside_pct")
    consensus_rating = _get_consensus("consensus_rating", "analyst_consensus_rating")

    # 1. current_price x shares_outstanding ≈ market_cap (within 2%)
    if all(v is not None for v in (current_price, shares_outstanding, market_cap)):
        checked.append("current_price * shares_outstanding ≈ market_cap")
        expected_mc = current_price * shares_outstanding  # type: ignore[operator]
        if not _within_pct(expected_mc, market_cap, identity_tolerance_pct):  # type: ignore[arg-type]
            failures.append(
                ValidatorFailure(
                    section_id="<cross-section>",
                    failure_type="identity_equation_violation",
                    detail=(
                        f"current_price x shares_outstanding = "
                        f"{expected_mc:.2f} disagrees with market_cap "
                        f"{market_cap}"
                    ),
                    expected_value=expected_mc,
                    actual_value=market_cap,
                    fact_name="market_cap",
                    tolerance=identity_tolerance_pct,
                )
            )

    # 2. Upside = (target - price) / price (within 0.5pp on the percent).
    if all(v is not None for v in (current_price, consensus_target_mean, consensus_upside_pct)):
        checked.append("(target - price) / price ≈ consensus_upside_pct")
        expected_upside = (consensus_target_mean - current_price) / current_price  # type: ignore[operator]
        # consensus_upside_pct: decimal in this codebase (e.g. 0.22 = 22%).
        # Tolerance: 0.5pp absolute (0.005 decimal).
        if abs(expected_upside - float(consensus_upside_pct)) > 0.005:
            failures.append(
                ValidatorFailure(
                    section_id="<cross-section>",
                    failure_type="identity_equation_violation",
                    detail=(
                        f"computed upside {expected_upside:.4f} disagrees "
                        f"with consensus_upside_pct {consensus_upside_pct} "
                        f"(target={consensus_target_mean}, "
                        f"price={current_price})"
                    ),
                    expected_value=expected_upside,
                    actual_value=consensus_upside_pct,
                    fact_name="consensus_upside_pct",
                    tolerance=0.5,
                )
            )

    # 3. revenue_ttm x operating_margin_ttm ≈ operating_income_ttm (within 0.5%).
    if all(v is not None for v in (revenue_ttm, operating_margin_ttm, operating_income_ttm)):
        checked.append("revenue_ttm * operating_margin_ttm ≈ operating_income_ttm")
        expected_oi = revenue_ttm * operating_margin_ttm  # type: ignore[operator]
        if not _within_pct(expected_oi, operating_income_ttm, arithmetic_tolerance_pct):  # type: ignore[arg-type]
            failures.append(
                ValidatorFailure(
                    section_id="<cross-section>",
                    failure_type="identity_equation_violation",
                    detail=(
                        f"revenue_ttm x operating_margin_ttm = "
                        f"{expected_oi:.2f} disagrees with "
                        f"operating_income_ttm {operating_income_ttm}"
                    ),
                    expected_value=expected_oi,
                    actual_value=operating_income_ttm,
                    fact_name="operating_income_ttm",
                    tolerance=arithmetic_tolerance_pct,
                )
            )

    # 4. Every prose mention of operating margin agrees with
    #    operating_margin_ttm within 0.5pp.
    if operating_margin_ttm is not None:
        checked.append("prose operating margin ≈ operating_margin_ttm (within 0.5pp)")
        op_margin_re = re.compile(
            r"(?:operating\s+margin|op\s+margin|operating-?margin)[^.\n]{0,40}?"
            r"([+-]?\d+(?:\.\d+)?)\s*%",
            re.IGNORECASE,
        )
        for sid, prose in section_files.items():
            for m in op_margin_re.finditer(prose):
                cited = float(m.group(1)) / 100.0
                if abs(cited - operating_margin_ttm) > 0.005:
                    failures.append(
                        ValidatorFailure(
                            section_id=sid,
                            failure_type="identity_equation_violation",
                            detail=(
                                f"prose cites operating margin "
                                f"{cited * 100:.2f}% but operating_margin_ttm "
                                f"is {operating_margin_ttm * 100:.2f}%"
                            ),
                            offending_text=m.group(0),
                            expected_value=operating_margin_ttm,
                            actual_value=cited,
                            fact_name="operating_margin_ttm",
                            tolerance=0.5,
                        )
                    )

    # 5. Every prose mention of current price uses the same value (within 1%).
    if current_price is not None:
        checked.append("prose current price ≈ current_price (within 1%)")
        # Match "$X" plain currency in proximity to "share" / "current" /
        # "trading at"/"closed at"/"price of" — a tighter context filter
        # keeps random $-figures from being treated as price mentions.
        price_re = re.compile(
            r"(?:share[s]?\s+at|trading\s+at|closed\s+at|price\s+of|current\s+price\s+of)"
            r"\s+\$\s?(\d+(?:,\d{3})*(?:\.\d+)?)\b",
            re.IGNORECASE,
        )
        for sid, prose in section_files.items():
            for m in price_re.finditer(prose):
                cited = float(m.group(1).replace(",", ""))
                if not _within_pct(cited, current_price, tolerance_pct):
                    failures.append(
                        ValidatorFailure(
                            section_id=sid,
                            failure_type="identity_equation_violation",
                            detail=(
                                f"prose cites current price ${cited:.2f} but "
                                f"current_price fact is ${current_price:.2f}"
                            ),
                            offending_text=m.group(0),
                            expected_value=current_price,
                            actual_value=cited,
                            fact_name="current_price",
                            tolerance=tolerance_pct,
                        )
                    )

    # 6. Rating ↔ upside coherence.
    if consensus_rating is not None and consensus_upside_pct is not None:
        checked.append("rating ↔ upside coherence")
        rating_str = str(consensus_rating).strip().lower()
        try:
            upside_val = float(consensus_upside_pct)
        except (TypeError, ValueError):
            upside_val = 0.0
        if rating_str in _BUY_RATINGS and upside_val < 0:
            failures.append(
                ValidatorFailure(
                    section_id="<cross-section>",
                    failure_type="identity_equation_violation",
                    detail=(
                        f"consensus_rating={consensus_rating!r} but "
                        f"consensus_upside_pct={upside_val} is negative — "
                        f"buy-rated names should imply positive upside"
                    ),
                    expected_value=">= 0",
                    actual_value=upside_val,
                    fact_name="consensus_upside_pct",
                )
            )
        if rating_str in _SELL_RATINGS and upside_val > 0:
            failures.append(
                ValidatorFailure(
                    section_id="<cross-section>",
                    failure_type="identity_equation_violation",
                    detail=(
                        f"consensus_rating={consensus_rating!r} but "
                        f"consensus_upside_pct={upside_val} is positive — "
                        f"sell-rated names should imply non-positive upside"
                    ),
                    expected_value="<= 0",
                    actual_value=upside_val,
                    fact_name="consensus_upside_pct",
                )
            )

    return failures, checked


# ---------------------------------------------------------------------------
# First-person voice + tombstone phrases
# ---------------------------------------------------------------------------

_FIRST_PERSON_RE = re.compile(
    r"\b(we believe|we think|our view|our base case|our analysis|in our view|"
    r"we estimate|we project|our target|we initiate|we rate|we recommend|"
    r"our rating|our price target|we view this as)\b",
    re.IGNORECASE,
)


def _check_first_person(section_id: str, prose: str) -> list[ValidatorFailure]:
    if section_id not in {"analyst_view", "investment_recommendation"}:
        return []
    failures: list[ValidatorFailure] = []
    for m in _FIRST_PERSON_RE.finditer(prose):
        failures.append(
            ValidatorFailure(
                section_id=section_id,
                failure_type="first_person_voice",
                detail=(
                    f"first-person advocacy phrase {m.group(0)!r} found in "
                    f"{section_id}; required to be sourced third-person voice"
                ),
                offending_text=m.group(0),
            )
        )
    return failures


def _check_tombstones(section_id: str, prose: str) -> list[ValidatorFailure]:
    failures: list[ValidatorFailure] = []
    lower = prose.lower()
    for phrase in TOMBSTONE_PHRASES:
        if phrase.lower() in lower:
            idx = lower.find(phrase.lower())
            failures.append(
                ValidatorFailure(
                    section_id=section_id,
                    failure_type="tombstone_phrase",
                    detail=f"tombstone phrase {phrase!r} found in prose",
                    offending_text=prose[idx : idx + len(phrase)],
                )
            )
    return failures


# ---------------------------------------------------------------------------
# Date-stamp coverage
# ---------------------------------------------------------------------------

_HEADLINE_FACT_PREFIXES: tuple[str, ...] = (
    "revenue",
    "operating_margin",
    "gross_margin",
    "net_margin",
    "cash",
    "total_debt",
    "market_cap",
    "shares_outstanding",
    "current_price",
)

_AS_OF_RE = re.compile(r"\bas\s+of\s+\d", re.IGNORECASE)


def _section_cites_headline(facts_used: list[Fact]) -> bool:
    return any(any(f.name.startswith(p) for p in _HEADLINE_FACT_PREFIXES) for f in facts_used)


def _check_data_as_of(
    section_id: str,
    prose: str,
    facts: dict[str, Fact],
) -> list[ValidatorFailure]:
    """Heuristic: if the section references a headline figure AND no
    'as of <date>' string is present, surface a soft warning. This is a
    soft failure (does not block the run)."""
    if _AS_OF_RE.search(prose):
        return []
    # Only fire when at least one headline fact appears to be referenced by
    # name-match in the prose. Otherwise the section may legitimately not
    # need a date stamp.
    referenced: list[Fact] = []
    for fact in facts.values():
        if any(fact.name.startswith(p) for p in _HEADLINE_FACT_PREFIXES):
            # Cheap proxy: fact value as a normalized number appears in prose
            # numerics. We don't re-extract here — instead, surface one
            # generic warning per section.
            referenced.append(fact)
    if not referenced:
        return []
    return [
        ValidatorFailure(
            section_id=section_id,
            failure_type="missing_data_as_of",
            detail=(
                "section appears to cite headline figures but contains no 'as of <date>' annotation"
            ),
            fact_name=referenced[0].name,
        )
    ]


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------


def validate_sections(
    section_files: dict[str, str],
    facts: dict[str, Fact],
    consensus_facts: dict[str, Any] | None = None,
    tolerance_pct: float = 1.0,
    arithmetic_tolerance_pct: float = 0.5,
    identity_tolerance_pct: float = 2.0,
) -> ValidatorReport:
    """Run every WS4 check against `section_files` (section_id -> markdown).

    Returns a structured report; the caller decides what to do with hard vs
    soft failures.
    """
    report = ValidatorReport()
    numbers_inspected_counter = [0]

    for section_id, markdown in section_files.items():
        if markdown is None:
            continue
        report.sections_inspected += 1
        # 1. Year-label consistency
        report.failures.extend(_check_year_labels(section_id, markdown, facts))
        # 2. Numeric ↔ fact equality
        report.failures.extend(
            _check_numeric_equality(
                section_id,
                markdown,
                facts,
                tolerance_pct,
                numbers_inspected_counter,
            )
        )
        # 3. Arithmetic spot-checks
        report.failures.extend(
            _check_arithmetic(section_id, markdown, facts, arithmetic_tolerance_pct)
        )
        # 6. First-person voice (analyst_view only)
        report.failures.extend(_check_first_person(section_id, markdown))
        # 7. Tombstone phrases
        report.failures.extend(_check_tombstones(section_id, markdown))
        # 5. Date-stamp coverage (soft)
        report.failures.extend(_check_data_as_of(section_id, markdown, facts))

    # 4. Cross-section identity equations
    id_failures, checked = _check_identity_equations(
        section_files,
        facts,
        consensus_facts,
        identity_tolerance_pct,
        arithmetic_tolerance_pct,
        tolerance_pct,
    )
    report.failures.extend(id_failures)
    report.identity_equations_checked = checked

    report.numbers_inspected = numbers_inspected_counter[0]
    return report


# ---------------------------------------------------------------------------
# Per-section retry hook
# ---------------------------------------------------------------------------


def build_section_retry_prompt(base_prompt: str, failures: list[ValidatorFailure]) -> str:
    """Append validator feedback to `base_prompt` for a single-section retry.

    Caller (the runner / dispatcher) is responsible for capping retries at 1
    and re-invoking the writer for the offending section only.
    """
    if not failures:
        return base_prompt
    lines = ["", "YOUR PREVIOUS ATTEMPT FAILED NUMERIC RECONCILIATION:"]
    for f in failures:
        if f.failure_type == "numeric_not_in_facts":
            expected = (
                f" (closest fact: {f.fact_name}={f.expected_value:g})"
                if f.fact_name is not None and isinstance(f.expected_value, int | float)
                else ""
            )
            lines.append(
                f"- {f.failure_type}: {f.offending_text!r} not in facts within "
                f"{f.tolerance}% tolerance{expected}"
            )
        else:
            lines.append(f"- {f.failure_type}: {f.detail}")
    lines.append("")
    lines.append(
        "Re-emit the section. Replace every offending number with a fact-backed "
        "value. If a number cannot be sourced to a fact in the slice, drop the "
        "sentence rather than fabricate."
    )
    return base_prompt + "\n".join(lines)
