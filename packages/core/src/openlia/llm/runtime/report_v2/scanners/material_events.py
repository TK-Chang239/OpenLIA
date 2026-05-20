"""Material-events gate (WS3 Part B).

Scans manifest news/filing entries for seven event classes that, if present
after the subject's `data_as_of`, must either hard-block the run (Chapter 11,
bankruptcy emergence, going-private completed, delisting, restatement) or
inject a warning banner (stock splits, recent M&A close).

Detection is regex-only: high-precision keyword patterns over headlines and
news bodies. No LLM judgment is used in this pass. False negatives are
mitigated by a wide set of synonym patterns per class; false positives are
mitigated by company-name presence and (where applicable) negation guards.

Event classes (from the plan, WS3-B):
  1. chapter_11           — Chapter 11 / Chapter 7 voluntary petition
  2. bankruptcy_emergence — Plan-of-reorganization effective / fresh-start
  3. going_private        — Take-private agreement / completed
  4. ma_target            — Definitive M&A; subject is the acquired party
  5. delisting            — Delisting / trading halt
  6. stock_split          — Forward or reverse split (effective date)
  7. restatement          — Restatement of recent financials
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Literal

from openlia.llm.runtime.report_v2.types import ManifestEntry

EventClass = Literal[
    "chapter_11",
    "bankruptcy_emergence",
    "going_private",
    "ma_target",
    "delisting",
    "stock_split",
    "restatement",
]

Confidence = Literal["high", "medium", "low"]

Severity = Literal["hard_block", "warning_banner", "informational"]


@dataclass(frozen=True)
class MaterialEvent:
    event_class: EventClass
    event_date: date | None
    confidence: Confidence
    severity: Severity
    evidence: list[int]
    description: str


class MaterialEventError(Exception):
    """Raised when one or more hard-block material events are detected after
    the subject's `data_as_of`. Carries the offending events for diagnostics."""

    def __init__(self, events: list[MaterialEvent]) -> None:
        self.events = events
        super().__init__(self._format(events))

    @staticmethod
    def _format(events: list[MaterialEvent]) -> str:
        parts = [f"{e.event_class} ({e.event_date}): {e.description}" for e in events]
        return "material event detected: " + "; ".join(parts) if parts else "material event"


# Hard-block severities — the runner refuses to render unless overridden.
_HARD_BLOCK_CLASSES: frozenset[EventClass] = frozenset(
    {"chapter_11", "bankruptcy_emergence", "going_private", "delisting", "restatement"}
)
# Warning-banner severities — runner proceeds but injects a banner.
_WARNING_CLASSES: frozenset[EventClass] = frozenset({"stock_split", "ma_target"})


# Per-class regex sets. Each pattern is compiled case-insensitively. A class
# fires "high" confidence when the company name (ticker or, when supplied,
# the company name token) is present in the same article and at least one
# pattern matches. Without name presence, confidence downgrades to "medium"
# (still surfaced) or "low" when only weak patterns fire.
_PATTERNS: dict[EventClass, dict[str, list[re.Pattern[str]]]] = {
    "chapter_11": {
        "strong": [
            re.compile(r"\bchapter\s*11\b", re.IGNORECASE),
            re.compile(r"\bchapter\s*7\b", re.IGNORECASE),
            re.compile(r"\bvoluntary\s+petition\b", re.IGNORECASE),
            re.compile(r"\bprepackaged\s+bankruptcy\b", re.IGNORECASE),
            re.compile(r"\bfiles?\s+for\s+bankruptcy\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bbankruptcy\s+protection\b", re.IGNORECASE),
            re.compile(r"\bfile[ds]?\s+bankruptcy\b", re.IGNORECASE),
        ],
    },
    "bankruptcy_emergence": {
        "strong": [
            re.compile(r"\bemerged?\s+from\s+(chapter\s*11|bankruptcy)\b", re.IGNORECASE),
            re.compile(r"\bemergence\s+from\s+(chapter\s*11|bankruptcy)\b", re.IGNORECASE),
            re.compile(r"\bfresh[-\s]start\s+accounting\b", re.IGNORECASE),
            re.compile(
                r"\bplan\s+of\s+reorganization\s+(became\s+effective|consummated)\b",
                re.IGNORECASE,
            ),
        ],
        "weak": [
            re.compile(r"\bpost[-\s]emergence\b", re.IGNORECASE),
        ],
    },
    "going_private": {
        "strong": [
            re.compile(r"\bgo(?:ing)?[-\s]private\b", re.IGNORECASE),
            re.compile(r"\btake[-\s]private\b", re.IGNORECASE),
            re.compile(
                r"\bagreement\b.{0,40}\bacquire\b.{0,40}\ball\b.{0,20}\boutstanding\s+shares\b",
                re.IGNORECASE | re.DOTALL,
            ),
        ],
        "weak": [
            re.compile(r"\bprivatization\b", re.IGNORECASE),
        ],
    },
    "ma_target": {
        "strong": [
            re.compile(r"\bdefinitive\s+(merger|acquisition)\s+agreement\b", re.IGNORECASE),
            re.compile(r"\b(?:agreed|enters)\s+to\s+(?:be\s+)?acquired\b", re.IGNORECASE),
            re.compile(r"\bmerger\s+completed?\b", re.IGNORECASE),
            re.compile(r"\bacquisition\s+closed?\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\b(merger|acquisition)\s+agreement\b", re.IGNORECASE),
        ],
    },
    "delisting": {
        "strong": [
            re.compile(r"\bdelisting\b", re.IGNORECASE),
            re.compile(r"\bdelisted\b", re.IGNORECASE),
            re.compile(r"\btrading\s+halt(ed)?\b", re.IGNORECASE),
            re.compile(r"\bremoved\s+from\s+(the\s+)?listing\b", re.IGNORECASE),
            re.compile(r"\bsuspended\s+from\s+trading\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bnon[-\s]compliance\s+notice\b", re.IGNORECASE),
        ],
    },
    "stock_split": {
        "strong": [
            re.compile(
                r"\b(\d+)[-\s]for[-\s](\d+)\s+(forward\s+|reverse\s+)?(?:stock\s+)?split\b",
                re.IGNORECASE,
            ),
            re.compile(r"\b(forward|reverse)\s+stock\s+split\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bstock\s+split\b", re.IGNORECASE),
        ],
    },
    "restatement": {
        "strong": [
            re.compile(
                r"\brestat(?:e|ing|ement|ed)\s+of\s+(?:the\s+)?(?:previously\s+issued\s+)?financial",
                re.IGNORECASE,
            ),
            re.compile(r"\bnon[-\s]reliance\s+on\s+previously(?:\s+issued)?\b", re.IGNORECASE),
            re.compile(r"\bitem\s+4\.02\b", re.IGNORECASE),  # 8-K restatement item code
        ],
        "weak": [
            re.compile(r"\brestatement\b", re.IGNORECASE),
        ],
    },
}


# Negation guard regex per class — when present, treat as "not this company"
# or "industry-wide" mention. Conservative on purpose; only a few clear cases.
_NEGATIONS: dict[EventClass, list[re.Pattern[str]]] = {
    "chapter_11": [
        re.compile(r"\bavoided?\s+bankruptcy\b", re.IGNORECASE),
        re.compile(r"\bno\s+chapter\s*11\b", re.IGNORECASE),
    ],
    "ma_target": [
        re.compile(r"\bterminated\s+(merger|acquisition)\b", re.IGNORECASE),
        re.compile(r"\bcalled\s+off\b", re.IGNORECASE),
    ],
}


def _parse_date(value: Any) -> date | None:
    """Parse a date-like value from a news payload field to a `date`.

    Accepts date, datetime, ISO 8601 strings, and 'YYYY-MM-DD'. Returns
    None for unparseable inputs."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(s).date()
        except ValueError:
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                return None
    return None


def _iter_news_articles(entry: ManifestEntry) -> list[dict[str, Any]]:
    """Extract news article dicts from a manifest entry.

    Recognised shapes:
      - EODHD `financial_news` / `get_company_news`: list[dict] with `date`,
        `title`, `content` (or `body`), `link`, `symbols`.
      - Wrapped {"items": [...]} or {"data": [...]} envelopes.
    """
    payload = entry.raw_payload
    if isinstance(payload, list):
        return [a for a in payload if isinstance(a, dict)]
    if isinstance(payload, dict):
        for key in ("items", "data", "articles", "news"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return [a for a in inner if isinstance(a, dict)]
    return []


def _is_news_entry(entry: ManifestEntry) -> bool:
    """Heuristic — entry identifier or provider implies news content."""
    ident = (entry.identifier or "").lower()
    return (
        "news" in ident or "financial_news" in ident or entry.provider.lower() in {"news", "edgar"}
    )


def _article_text(article: dict[str, Any]) -> str:
    """Concatenate the text fields the regexes scan over (title + body)."""
    parts: list[str] = []
    for key in ("title", "headline"):
        v = article.get(key)
        if isinstance(v, str):
            parts.append(v)
    for key in ("content", "body", "summary", "description"):
        v = article.get(key)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def _name_present(text: str, names: list[str]) -> bool:
    """Case-insensitive substring match on any of the supplied identifiers."""
    if not names:
        return False
    low = text.lower()
    return any(name.lower() in low for name in names if name)


def _classify(text: str, event_class: EventClass) -> tuple[bool, Literal["strong", "weak"] | None]:
    """Return (matched, strength) for `text` against `event_class` patterns.

    Strong wins over weak. Negations veto the match entirely."""
    for neg in _NEGATIONS.get(event_class, []):
        if neg.search(text):
            return (False, None)
    for pat in _PATTERNS[event_class]["strong"]:
        if pat.search(text):
            return (True, "strong")
    for pat in _PATTERNS[event_class]["weak"]:
        if pat.search(text):
            return (True, "weak")
    return (False, None)


def _severity_for(event_class: EventClass) -> Severity:
    if event_class in _HARD_BLOCK_CLASSES:
        return "hard_block"
    if event_class in _WARNING_CLASSES:
        return "warning_banner"
    return "informational"


def _confidence(strength: Literal["strong", "weak"], name_match: bool) -> Confidence:
    if strength == "strong" and name_match:
        return "high"
    if strength == "strong":
        return "medium"
    # weak pattern only
    return "low" if not name_match else "medium"


@dataclass
class MaterialEventScanner:
    """Scans manifest entries for the seven WS3-B event classes.

    Parameters:
      subject_ticker: ticker symbol used to validate company-name presence
      company_names: additional name aliases (full legal name, common name)
      as_of_date: cutoff for severity escalation. Events with `event_date`
        strictly after this date keep their natural severity; events on or
        before this date are demoted to "informational" so the runner does
        not hard-block on already-known facts.
    """

    subject_ticker: str
    company_names: list[str] = field(default_factory=list)
    as_of_date: date | None = None

    def _name_aliases(self) -> list[str]:
        # Strip exchange suffix (e.g. ".US") and add lowercase variants.
        bare = self.subject_ticker.split(".")[0]
        names = [self.subject_ticker, bare, *self.company_names]
        return [n for n in names if n]

    def scan(self, manifest: list[ManifestEntry]) -> list[MaterialEvent]:
        names = self._name_aliases()
        out: list[MaterialEvent] = []
        for entry in manifest:
            if not _is_news_entry(entry):
                continue
            for article in _iter_news_articles(entry):
                text = _article_text(article)
                if not text:
                    continue
                name_match = _name_present(text, names)
                article_date = _parse_date(article.get("date") or article.get("published_at"))
                for event_class in _PATTERNS:
                    matched, strength = _classify(text, event_class)
                    if not matched or strength is None:
                        continue
                    conf = _confidence(strength, name_match)
                    severity = self._effective_severity(event_class, article_date)
                    out.append(
                        MaterialEvent(
                            event_class=event_class,
                            event_date=article_date,
                            confidence=conf,
                            severity=severity,
                            evidence=[entry.id],
                            description=self._describe(event_class, article, text),
                        )
                    )
        return out

    def _effective_severity(self, event_class: EventClass, event_date: date | None) -> Severity:
        """Demote events on/before the `as_of_date` to informational so the
        runner only blocks on genuinely-new corporate events."""
        natural = _severity_for(event_class)
        if self.as_of_date is None or event_date is None:
            return natural
        if event_date <= self.as_of_date:
            return "informational"
        return natural

    @staticmethod
    def _describe(event_class: EventClass, article: dict[str, Any], text: str) -> str:
        # Prefer the article's own title; fall back to the first text line.
        title = article.get("title") or article.get("headline")
        if isinstance(title, str) and title.strip():
            return f"{event_class}: {title.strip()[:200]}"
        first_line = text.strip().splitlines()[0] if text.strip() else event_class
        return f"{event_class}: {first_line[:200]}"


def scan_manifest(
    manifest: list[ManifestEntry],
    *,
    subject_ticker: str,
    company_names: list[str] | None = None,
    as_of_date: date | datetime | str | None = None,
) -> list[MaterialEvent]:
    """One-call entry point used by the runner.

    `as_of_date` here is the oldest `data_as_of` of the manifest's facts (from
    the P1 freshness gate). Events after this date carry their natural
    severity; events on or before it are demoted to informational."""
    as_of: date | None
    if isinstance(as_of_date, datetime):
        as_of = as_of_date.date()
    elif isinstance(as_of_date, date):
        as_of = as_of_date
    elif isinstance(as_of_date, str):
        as_of = _parse_date(as_of_date)
    else:
        as_of = None
    scanner = MaterialEventScanner(
        subject_ticker=subject_ticker,
        company_names=company_names or [],
        as_of_date=as_of,
    )
    return scanner.scan(manifest)


def now_utc() -> datetime:
    return datetime.now(UTC)
