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
    r"\b(no data available|n/?a|tbd|data not provided|unable to determine|data unavailable)\b",
    re.IGNORECASE,
)

_NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:%|bn|b|m|k|x|usd|\$)?\b", re.IGNORECASE)
_CITATION_RE = re.compile(r"\[(\d+)\]")

_CITATION_PROXIMITY_TOKENS = 12

_NUMERIC_CLAIM_RE = re.compile(
    r"\b([\w\s-]{3,40}?)\s+of\s+(\d+(?:[.,]\d+)?\s*%?)",
    re.IGNORECASE,
)


def _section_id(parsed: ParsedSection) -> str:
    return str(parsed.frontmatter.get("section_id", "?"))


def _prose_text(parsed: ParsedSection) -> str:
    return " ".join(s.text for s in parsed.segments if isinstance(s, TextSegment))


def word_count_minimum(parsed: ParsedSection, *, target: int) -> list[ValidationFinding]:
    prose = _prose_text(parsed)
    n = len(prose.split())
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


def quantitative_claim_near_citation(parsed: ParsedSection) -> list[ValidationFinding]:
    findings = []
    for seg in parsed.segments:
        if not isinstance(seg, TextSegment):
            continue
        tokens = seg.text.split()
        for i, tok in enumerate(tokens):
            if not _NUMBER_RE.fullmatch(tok.strip(".,;:")):
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


def fetched_but_unused(
    parsed: ParsedSection, *, facts_slice: dict
) -> list[ValidationFinding]:
    """Flag facts in the slice that never appear in prose or block YAML dumps."""
    prose = _prose_text(parsed).lower()
    block_dumps = " ".join(
        json.dumps(s.data).lower()
        for s in parsed.segments
        if isinstance(s, FencedBlockSegment)
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
    """Run all four per-section checks (NOT cross-section)."""
    return [
        *word_count_minimum(parsed, target=target_word_count),
        *tombstone_regex(parsed),
        *quantitative_claim_near_citation(parsed),
        *fetched_but_unused(parsed, facts_slice=facts_slice),
    ]
