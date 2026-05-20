"""Fresh-catalyst pack (WS3 Part A).

Pre-section pass that scans manifest news entries for *catalyst-class events*
— things like product announcements (GTC / WWDC keynotes, new model GA),
customer-concentration disclosures (10-K "10% customer" language), hyperscaler
capex prints (Microsoft/Meta/Alphabet/Amazon FY capex updates), sovereign-AI
deals, export-control changes (BIS rules, H20 licensing), material partnerships,
and guidance updates. The detector packs each hit as a `CatalystEvent` with a
manifest-id evidence list so body sections can cite catalysts like any other
source.

Detection is keyword + simple structural pattern matching. Each catalyst class
fires "high" when at least one strong pattern matches AND the subject company
name (ticker or alias) is present in the article; "medium" when a strong
pattern matches without name presence; "low" when only a weak pattern fires.
For broad-industry catalyst classes (hyperscaler capex, sovereign AI, export
control), the scanner does not require the subject name in the article — the
relevance is captured in the `relevance_score` instead.

The precision/recall trade-off here favours recall (better to surface a
borderline catalyst to the section and let the LLM judge than to miss it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from openlia.llm.runtime.report_v2.scanners._news_utils import (
    article_body,
    article_date,
    article_text,
    article_title,
    article_url,
    is_news_entry,
    iter_news_articles,
    name_present,
    parse_date,
)
from openlia.llm.runtime.report_v2.types import ManifestEntry

CatalystClass = Literal[
    "product_announcement",
    "customer_concentration_disclosure",
    "hyperscaler_capex_print",
    "sovereign_ai_deal",
    "export_control_change",
    "material_partnership",
    "guidance_update",
]

Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class CatalystEvent:
    """A single catalyst-class event extracted from a manifest news entry.

    `evidence` lists the manifest IDs that support the event. `relevance_score`
    (0-1) is a downstream signal for section consumers — higher scores indicate
    the catalyst is more central to the subject (e.g. strong pattern + name
    match + body content present).
    """

    catalyst_class: CatalystClass
    event_date: date | None
    confidence: Confidence
    title: str
    summary: str  # 1-2 sentence summary extracted from news body
    evidence: list[int]  # manifest IDs
    source_url: str | None
    relevance_score: float  # 0-1 scoring for downstream section consumers


# Catalyst classes whose relevance is industry-wide rather than subject-scoped.
# For these, name presence in the article is *not* required for the event to
# fire — the LLM uses the catalyst as context for the subject's outlook.
_INDUSTRY_SCOPE_CLASSES: frozenset[CatalystClass] = frozenset(
    {
        "hyperscaler_capex_print",
        "sovereign_ai_deal",
        "export_control_change",
    }
)


# Per-class regex sets. Patterns split into "strong" (high-precision phrases)
# and "weak" (broader matches). Strong wins over weak.
_PATTERNS: dict[CatalystClass, dict[str, list[re.Pattern[str]]]] = {
    "product_announcement": {
        "strong": [
            re.compile(r"\bunveils?\b", re.IGNORECASE),
            re.compile(r"\bannounces?\s+general\s+availability\b", re.IGNORECASE),
            re.compile(r"\bgeneral\s+availability\b", re.IGNORECASE),
            re.compile(r"\bnext[-\s]generation\b", re.IGNORECASE),
            re.compile(r"\blaunches?\s+(?:new|next)\b", re.IGNORECASE),
            re.compile(
                r"\bnew\s+(?:model|platform|chip|gpu|processor|architecture)\b",
                re.IGNORECASE,
            ),
        ],
        "weak": [
            re.compile(r"\blaunches?\b", re.IGNORECASE),
            re.compile(r"\bannounces?\b", re.IGNORECASE),
            re.compile(r"\bunveiling\b", re.IGNORECASE),
            re.compile(r"\bGA\b"),  # General Availability acronym, case-sensitive
        ],
    },
    "customer_concentration_disclosure": {
        "strong": [
            re.compile(r"\b10\s*%\s*customer\b", re.IGNORECASE),
            re.compile(
                r"\b(?:single\s+)?(?:largest|top)\s+customer\s+(?:represents?|accounted\s+for)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\btop\s+(?:five|5)\s+customers\b", re.IGNORECASE),
            re.compile(r"\bcustomer\s+concentration\b", re.IGNORECASE),
            re.compile(
                r"\b(?:represents?|accounted\s+for|accounts\s+for)\s+\d{1,2}\s*%\s+of\s+(?:total\s+)?revenue\b",
                re.IGNORECASE,
            ),
            re.compile(r"\bconcentration\s+risk\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\btop\s+customer\b", re.IGNORECASE),
            re.compile(r"\bmajor\s+customer\b", re.IGNORECASE),
        ],
    },
    "hyperscaler_capex_print": {
        "strong": [
            re.compile(
                r"\b(?:Microsoft|Meta|Alphabet|Google|Amazon|AWS|Oracle)\b.{0,80}\b"
                r"(?:capital\s+expenditures?|capex|cap[-\s]ex)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\b(?:capital\s+expenditures?|capex|cap[-\s]ex)\b.{0,80}\b"
                r"(?:Microsoft|Meta|Alphabet|Google|Amazon|AWS|Oracle)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\b(?:AI\s+)?capital\s+expenditure\b.{0,40}\$\s*\d+\s*(?:billion|B)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\$\s*\d+(?:\.\d+)?\s*(?:billion|B)\b.{0,40}\bcapex\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\b(?:raise[ds]?|raising|cut|cuts|lower(?:ed|s)?)\s+(?:FY\d{2,4}\s+)?capex\b",
                re.IGNORECASE,
            ),
        ],
        "weak": [
            re.compile(
                r"\bdata\s+center\s+(?:spending|investment|build[-\s]?out)\b",
                re.IGNORECASE,
            ),
            re.compile(r"\bhyperscaler\s+(?:spend|capex|investment)\b", re.IGNORECASE),
        ],
    },
    "sovereign_ai_deal": {
        "strong": [
            re.compile(r"\bsovereign\s+AI\b", re.IGNORECASE),
            re.compile(
                r"\bnational\s+AI\s+(?:initiative|infrastructure|strategy)\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\b(?:Saudi\s+Arabia|UAE|United\s+Arab\s+Emirates|Singapore|France|Germany|"
                r"India|Japan|Korea|United\s+Kingdom|UK)['’]?s?\s+AI\s+"  # noqa: RUF001
                r"(?:infrastructure|cluster|build[-\s]?out|investment|deal)\b",
                re.IGNORECASE,
            ),
        ],
        "weak": [
            re.compile(r"\bnation[-\s]state\s+AI\b", re.IGNORECASE),
            re.compile(r"\bgovernment[-\s]backed\s+AI\b", re.IGNORECASE),
        ],
    },
    "export_control_change": {
        "strong": [
            re.compile(r"\bexport\s+control(s)?\b", re.IGNORECASE),
            re.compile(r"\bH20\s+chip(s)?\b", re.IGNORECASE),
            re.compile(r"\bBIS\s+rule\b", re.IGNORECASE),
            re.compile(r"\bBureau\s+of\s+Industry\s+and\s+Security\b", re.IGNORECASE),
            re.compile(r"\bentity\s+list\b", re.IGNORECASE),
            re.compile(r"\blicense\s+revocation\b", re.IGNORECASE),
            re.compile(r"\bexport\s+license\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bsemiconductor\s+restrictions?\b", re.IGNORECASE),
            re.compile(r"\bchip\s+(?:ban|restrictions?)\b", re.IGNORECASE),
        ],
    },
    "material_partnership": {
        "strong": [
            re.compile(r"\bstrategic\s+partnership\b", re.IGNORECASE),
            re.compile(r"\bexclusive\s+supply\s+agreement\b", re.IGNORECASE),
            re.compile(r"\b10[-\s]year\s+(?:contract|agreement|deal)\b", re.IGNORECASE),
            re.compile(r"\bmulti[-\s]year\s+supply\s+(?:agreement|deal)\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bpartnership\s+announced\b", re.IGNORECASE),
            re.compile(r"\bteamed\s+up\s+with\b", re.IGNORECASE),
        ],
    },
    "guidance_update": {
        "strong": [
            re.compile(r"\bguidance\s+(?:raised|cut|lowered|increased|reduced)\b", re.IGNORECASE),
            re.compile(r"\braised\s+(?:full[-\s]year\s+)?(?:outlook|guidance)\b", re.IGNORECASE),
            re.compile(r"\blowered\s+(?:full[-\s]year\s+)?(?:outlook|guidance)\b", re.IGNORECASE),
            re.compile(r"\bpreliminary\s+results\b", re.IGNORECASE),
            re.compile(r"\bpre[-\s]announces?\s+(?:results|earnings)\b", re.IGNORECASE),
        ],
        "weak": [
            re.compile(r"\bupdated?\s+guidance\b", re.IGNORECASE),
            re.compile(r"\brevised\s+outlook\b", re.IGNORECASE),
        ],
    },
}


def _classify(
    text: str, catalyst_class: CatalystClass
) -> tuple[bool, Literal["strong", "weak"] | None]:
    """Return (matched, strength) for `text` against `catalyst_class` patterns.

    Strong wins over weak."""
    for pat in _PATTERNS[catalyst_class]["strong"]:
        if pat.search(text):
            return (True, "strong")
    for pat in _PATTERNS[catalyst_class]["weak"]:
        if pat.search(text):
            return (True, "weak")
    return (False, None)


def _confidence(strength: Literal["strong", "weak"], name_match: bool) -> Confidence:
    """Confidence ladder per the WS3-A spec:
    strong + name → high
    strong alone   → medium
    weak alone     → low
    weak + name    → medium (lifted)
    """
    if strength == "strong" and name_match:
        return "high"
    if strength == "strong":
        return "medium"
    return "medium" if name_match else "low"


def _relevance_score(
    *,
    strength: Literal["strong", "weak"],
    name_match: bool,
    has_body: bool,
    industry_scope: bool,
    has_date: bool,
) -> float:
    """Heuristic 0-1 relevance score for downstream section consumers.

    Weights favour the same signals as `_confidence` but expose more shape:
    a strong subject-scoped catalyst with full body + date scores ~0.92,
    while a weak industry-scope catalyst without subject name lands ~0.35.
    """
    score = 0.30
    if strength == "strong":
        score += 0.30
    if name_match:
        score += 0.25
    elif industry_scope:
        # Industry-scope catalysts (hyperscaler capex, sovereign AI, export
        # control) are still relevant to the subject even without name match.
        score += 0.10
    if has_body:
        score += 0.10
    if has_date:
        score += 0.05
    return min(1.0, round(score, 3))


def _make_summary(title: str | None, body: str | None) -> str:
    """Build a 1-2 sentence summary from the article body, falling back to
    the title when no body content is available."""
    if body:
        # Take the first two sentences (split on ". " or newline) of the body.
        flat = " ".join(body.split())
        # Split on period+space, keep up to two segments.
        parts = re.split(r"(?<=[.!?])\s+", flat)
        joined = " ".join(parts[:2]).strip()
        if joined:
            return joined[:400]
    if title:
        return title[:400]
    return ""


@dataclass
class CatalystScanner:
    """Scans manifest entries for the seven catalyst classes.

    Parameters:
      subject_ticker: ticker symbol used to validate company-name presence
      company_names: additional aliases (full legal name, common name)
      as_of_date: optional cutoff. Events strictly after this date are kept
        with their full confidence/relevance; events on or before are still
        returned so body sections can cover them. (No demotion semantics
        like material_events — this scanner is information-additive only.)
    """

    subject_ticker: str
    company_names: list[str] = field(default_factory=list)
    as_of_date: date | None = None

    def _name_aliases(self) -> list[str]:
        bare = self.subject_ticker.split(".")[0]
        names = [self.subject_ticker, bare, *self.company_names]
        return [n for n in names if n]

    def scan(
        self,
        manifest_entries: list[ManifestEntry],
        subject_company: str | None = None,
        subject_ticker: str | None = None,
        as_of_date: date | None = None,
    ) -> list[CatalystEvent]:
        """Scan the manifest for catalyst-class events.

        The positional/keyword arguments allow callers to invoke the scanner
        with one-call ergonomics (as the WS3-A spec describes) or via the
        instance state set at construction time. Explicit arguments override
        the instance defaults for this single call.
        """
        ticker = (subject_ticker or self.subject_ticker or "").strip()
        aliases: list[str] = []
        bare = ticker.split(".")[0] if ticker else ""
        for n in (ticker, bare, subject_company, *self.company_names):
            if n and n not in aliases:
                aliases.append(n)
        # `as_of_date` is currently information-only; reserved for downstream
        # filtering by section consumers.
        _ = as_of_date or self.as_of_date

        out: list[CatalystEvent] = []
        for entry in manifest_entries:
            if not is_news_entry(entry):
                continue
            for article in iter_news_articles(entry):
                text = article_text(article)
                if not text:
                    continue
                title = article_title(article) or ""
                body = article_body(article)
                url = article_url(article)
                a_date = article_date(article)
                name_match = name_present(text, aliases)
                for catalyst_class in _PATTERNS:
                    matched, strength = _classify(text, catalyst_class)
                    if not matched or strength is None:
                        continue
                    industry_scope = catalyst_class in _INDUSTRY_SCOPE_CLASSES
                    # Subject-scoped classes require either a name match in
                    # the article OR a strong pattern; this keeps recall high
                    # for the GTC-style "NVIDIA unveils …" cases while not
                    # demoting industry-scope hyperscaler-capex catalysts.
                    if not industry_scope and not name_match and strength != "strong":
                        continue
                    conf = _confidence(strength, name_match)
                    rel = _relevance_score(
                        strength=strength,
                        name_match=name_match,
                        has_body=bool(body),
                        industry_scope=industry_scope,
                        has_date=a_date is not None,
                    )
                    out.append(
                        CatalystEvent(
                            catalyst_class=catalyst_class,
                            event_date=a_date,
                            confidence=conf,
                            title=title or catalyst_class,
                            summary=_make_summary(title, body),
                            evidence=[entry.id],
                            source_url=url,
                            relevance_score=rel,
                        )
                    )
        return out


def scan_catalysts(
    manifest_entries: list[ManifestEntry],
    *,
    subject_company: str | None = None,
    subject_ticker: str,
    as_of_date: date | datetime | str | None = None,
    company_names: list[str] | None = None,
) -> list[CatalystEvent]:
    """One-call entry point used by the runner.

    Returns the full list of detected catalysts; order is manifest order
    (earlier entries first, then per-class match order within an article)."""
    as_of: date | None
    if isinstance(as_of_date, datetime):
        as_of = as_of_date.date()
    elif isinstance(as_of_date, date):
        as_of = as_of_date
    elif isinstance(as_of_date, str):
        as_of = parse_date(as_of_date)
    else:
        as_of = None
    scanner = CatalystScanner(
        subject_ticker=subject_ticker,
        company_names=company_names or [],
        as_of_date=as_of,
    )
    return scanner.scan(
        manifest_entries=manifest_entries,
        subject_company=subject_company,
        subject_ticker=subject_ticker,
        as_of_date=as_of,
    )


def catalyst_event_to_dict(event: CatalystEvent) -> dict[str, Any]:
    """Serialise a CatalystEvent for the `catalysts_recent` Fact value."""
    return {
        "catalyst_class": event.catalyst_class,
        "event_date": event.event_date.isoformat() if event.event_date is not None else None,
        "confidence": event.confidence,
        "title": event.title,
        "summary": event.summary,
        "evidence": list(event.evidence),
        "source_url": event.source_url,
        "relevance_score": event.relevance_score,
    }
