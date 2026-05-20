"""Semantic validation (5A). Five enumerated checks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    ParsedSection,
    TextSegment,
)


@dataclass(frozen=True)
class ValidationFinding:
    check: str
    section_id: str
    detail: str
    severity: str = "error"  # "error" hard-fails; "warning" telemetry-only


_TOMBSTONE_RE = re.compile(
    r"\b(no data available|n/a|tbd|data not provided|unable to determine|data unavailable)\b",
    re.IGNORECASE,
)

# CJK ideographs (CJK Unified, CJK Ext-A, CJK Compatibility) — counted as
# one "word" each since Chinese prose has no inter-character whitespace.
_CJK_RE = re.compile(r"[一-鿿㐀-䶿豈-﫿]")


def _count_prose_words(text: str) -> int:
    """Count semantic units in mixed Latin/CJK prose.

    Each CJK ideograph counts as one unit; remaining (non-CJK) text is
    split on whitespace. ``"600 字" → 2`` words, ``"hello 你好" → 3``.
    """
    cjk = len(_CJK_RE.findall(text))
    latin = len(_CJK_RE.sub(" ", text).split())
    return cjk + latin


_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?\s*(?:%|bn|b|m|k|x|usd|\$)", re.IGNORECASE)
# Accept single ([1]) and multi-id ([1, 2, 3]) citation markers.
_CITATION_RE = re.compile(r"\[\d+(?:\s*,\s*\d+)*\]")
_YEAR_RE = re.compile(r"^(19|20)\d{2}$")

_CITATION_PROXIMITY_TOKENS = 12

_NUMERIC_CLAIM_RE = re.compile(
    r"\b([\w\s-]{3,40}?)\s+of\s+(\d+(?:[.,]\d+)?\s*%?)",
    re.IGNORECASE,
)

# First-person advocacy patterns banned under the no-advocacy policy.
# The report reports what sources said; it does not author judgments.
# Third-person attributed language with a citation is fine — that's why
# the check is bounded to first-person constructions only.
_ADVOCACY_RE = re.compile(
    r"\b(?:"
    r"we\s+(?:recommend|initiate|rate|view\s+this|view\s+the|believe|expect|forecast|are\s+(?:buyers|sellers)\s+of)"
    r"|our\s+(?:rating|view|call|recommendation|price\s+target|target\s+price|thesis|stance)"
    r"|investment\s+(?:thesis|case)\b(?!\s+(?:as\s+described|presented|outlined|laid\s+out|by\s+the\s+company))"
    r")\b",
    re.IGNORECASE,
)


def _section_id(parsed: ParsedSection) -> str:
    return str(parsed.frontmatter.get("section_id", "?"))


def _prose_text(parsed: ParsedSection) -> str:
    return " ".join(s.text for s in parsed.segments if isinstance(s, TextSegment))


def word_count_minimum(parsed: ParsedSection, *, target: int) -> list[ValidationFinding]:
    prose = _prose_text(parsed)
    n = _count_prose_words(prose)
    if n < int(target * 0.7):
        return [
            ValidationFinding(
                check="word_count_minimum",
                section_id=_section_id(parsed),
                detail=f"section word count {n} below 70% of target {target}",
            )
        ]
    return []


def tombstone_regex(parsed: ParsedSection) -> list[ValidationFinding]:
    findings = []
    for seg in parsed.segments:
        if isinstance(seg, TextSegment) and _TOMBSTONE_RE.search(seg.text):
            findings.append(
                ValidationFinding(
                    check="tombstone_regex",
                    section_id=_section_id(parsed),
                    detail="tombstone phrase in prose",
                )
            )
    return findings


def advocacy_language(parsed: ParsedSection) -> list[ValidationFinding]:
    """Flag first-person advocacy ("we recommend", "our rating", "investment
    thesis"). Third-person attributed language with a citation
    ("JPMorgan rates Buy [c12]") is not flagged — only the first-person
    constructions that signal the report itself is making the call."""
    findings: list[ValidationFinding] = []
    for seg in parsed.segments:
        if not isinstance(seg, TextSegment):
            continue
        match = _ADVOCACY_RE.search(seg.text)
        if match:
            findings.append(
                ValidationFinding(
                    check="advocacy_language",
                    section_id=_section_id(parsed),
                    detail=f"first-person advocacy phrase: {match.group(0)!r}",
                )
            )
    return findings


def quantitative_claim_near_citation(parsed: ParsedSection) -> list[ValidationFinding]:
    findings = []
    for seg in parsed.segments:
        if not isinstance(seg, TextSegment):
            continue
        tokens = seg.text.split()
        for i, tok in enumerate(tokens):
            stripped = tok.strip(".,;:")
            if not _NUMBER_RE.fullmatch(stripped):
                continue
            # Years (1900-2099) are not financial claims; skip them.
            if _YEAR_RE.match(stripped):
                continue
            window_start = max(0, i - _CITATION_PROXIMITY_TOKENS)
            window_end = min(len(tokens), i + _CITATION_PROXIMITY_TOKENS + 1)
            window = " ".join(tokens[window_start:window_end])
            if not _CITATION_RE.search(window):
                findings.append(
                    ValidationFinding(
                        check="quantitative_claim_near_citation",
                        section_id=_section_id(parsed),
                        detail=f"numeric claim {tok!r} without nearby citation",
                    )
                )
                break  # one finding per text segment avoids spam
    return findings


def fetched_but_unused(parsed: ParsedSection, *, facts_slice: dict) -> list[ValidationFinding]:
    """Flag facts in the slice that never appear in prose or block YAML dumps."""
    prose = _prose_text(parsed).lower()
    block_dumps = " ".join(
        json.dumps(s.data).lower() for s in parsed.segments if isinstance(s, FencedBlockSegment)
    )
    haystack = prose + " " + block_dumps
    findings = []
    for name in facts_slice:
        needle = name.replace("_", " ").lower()
        if needle not in haystack and name.lower() not in haystack:
            findings.append(
                ValidationFinding(
                    check="fetched_but_unused",
                    section_id=_section_id(parsed),
                    detail=f"fact in slice but not referenced: {name}",
                    severity="warning",
                )
            )
    return findings


def cross_section_numeric_consistency(
    sections: list[ParsedSection],
) -> list[ValidationFinding]:
    """Extract <subject> of <number> claims across sections; flag mismatched values."""
    by_subject: dict[str, list[tuple[str, str]]] = {}
    for s in sections:
        sid = _section_id(s)
        for seg in s.segments:
            if not isinstance(seg, TextSegment):
                continue
            for m in _NUMERIC_CLAIM_RE.finditer(seg.text):
                subject = " ".join(m.group(1).lower().split())
                value = m.group(2).replace(" ", "").rstrip("%")
                by_subject.setdefault(subject, []).append((sid, value))

    findings = []
    for subject, entries in by_subject.items():
        seen_values = {v for _, v in entries}
        if len(seen_values) > 1:
            findings.append(
                ValidationFinding(
                    check="cross_section_numeric_consistency",
                    section_id=",".join(sid for sid, _ in entries),
                    detail=f"subject {subject!r}: conflicting values {sorted(seen_values)}",
                )
            )
    return findings


def validate_section(
    parsed: ParsedSection,
    *,
    facts_slice: dict,
    target_word_count: int,
) -> list[ValidationFinding]:
    """Run all five per-section checks (NOT cross-section)."""
    return [
        *word_count_minimum(parsed, target=target_word_count),
        *tombstone_regex(parsed),
        *advocacy_language(parsed),
        *quantitative_claim_near_citation(parsed),
        *fetched_but_unused(parsed, facts_slice=facts_slice),
    ]
