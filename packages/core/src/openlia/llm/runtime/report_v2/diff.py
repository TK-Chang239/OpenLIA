"""Structured diff between two ReportSchema instances (classic vs waved)."""

from __future__ import annotations

from typing import Any

from openlia.reports.schema import (
    BulletListBlock,
    ComparisonSplitBlock,
    KeyFindingBlock,
    PullQuoteBlock,
    QuoteBlock,
    ReportSchema,
    TextBlock,
)

_WORD_COUNT_TOLERANCE = 0.20


def _section_word_count(section: Any) -> int:
    """Sum words across text-bearing blocks in a section."""
    n = 0
    for b in section.blocks:
        if isinstance(b, TextBlock):
            n += len(b.content.split())
        elif isinstance(b, KeyFindingBlock):
            n += len((b.content or "").split())
        elif isinstance(b, PullQuoteBlock):
            n += len(b.text.split())
        elif isinstance(b, QuoteBlock):
            n += len(b.text.split())
        elif isinstance(b, BulletListBlock):
            for item in b.items:
                n += len(str(item).split())
        elif isinstance(b, ComparisonSplitBlock):
            for col in (b.left, b.right):
                for it in col.items:
                    n += len(str(it).split())
    return n


def _cover_metric_map(report: ReportSchema) -> dict[str, str]:
    """Return {Metric.label: Metric.value} dict for cover key_metrics."""
    return {m.label: m.value for m in report.cover.key_metrics}


def diff_reports(classic: ReportSchema, waved: ReportSchema) -> dict[str, Any]:
    """Diff two ReportSchema instances and return a structured comparison dict.

    Keys:
        section_count       — match, classic, waved
        citation_count      — match, classic, waved
        cover_metric_values — match, mismatches {label: (classic_val, waved_val)}
        section_word_counts — match (within ±20% tolerance), per_section
    """
    out: dict[str, Any] = {}

    # Section count
    out["section_count"] = {
        "match": len(classic.sections) == len(waved.sections),
        "classic": len(classic.sections),
        "waved": len(waved.sections),
    }

    # Citation count
    out["citation_count"] = {
        "match": len(classic.citations) == len(waved.citations),
        "classic": len(classic.citations),
        "waved": len(waved.citations),
    }

    # Cover metric value drift
    cm_a = _cover_metric_map(classic)
    cm_b = _cover_metric_map(waved)
    mismatches = {
        k: (cm_a.get(k), cm_b.get(k)) for k in set(cm_a) | set(cm_b) if cm_a.get(k) != cm_b.get(k)
    }
    out["cover_metric_values"] = {
        "match": not mismatches,
        "mismatches": mismatches,
    }

    # Section word counts (±20% tolerance per shared section id)
    wc_match = True
    wc_per_section: dict[str, dict[str, int]] = {}
    by_id_a = {s.id: s for s in classic.sections}
    by_id_b = {s.id: s for s in waved.sections}
    shared_ids = set(by_id_a) & set(by_id_b)
    for sid in shared_ids:
        wa = _section_word_count(by_id_a[sid])
        wb = _section_word_count(by_id_b[sid])
        wc_per_section[sid] = {"classic": wa, "waved": wb}
        if wa == 0 and wb == 0:
            continue
        denom = max(wa, wb)
        if abs(wa - wb) / denom > _WORD_COUNT_TOLERANCE:
            wc_match = False
    out["section_word_counts"] = {"match": wc_match, "per_section": wc_per_section}

    return out
