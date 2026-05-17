#!/usr/bin/env python3
"""Deep-analyze a generated equity-research report.

Usage:
    python3 scripts/analyze_report.py <report_id>

Reads the report payload from the DB, joins it with dev-events.jsonl entries
for the same run, and produces a structured analysis on three axes:
    1. Formatting (schema compliance, citations, blocks present)
    2. Data accuracy / availability (data unavailable rate, hallucination smell)
    3. Analysis quality (depth, template adherence)

Plus token/cost telemetry per phase and per LLM call.
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path


EVENTS_PATH = Path.home() / ".openlia" / "dev-events.jsonl"
DB_PATH = Path.home() / ".openlia" / "openlia-v2.db"


def load_report(report_id: str) -> dict | None:
    """Load report by either the runtime r_<hex> id (via title lookup of
    latest matching ticker, fallback to most-recent) or by UUID directly."""
    if not DB_PATH.exists():
        return None
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT content_structured FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        if row is None:
            # Fall back: most recent NET-initiation if the id is the runtime id
            row = con.execute(
                "SELECT content_structured FROM reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        data = row["content_structured"]
        return json.loads(data) if isinstance(data, str) else data
    finally:
        con.close()


def load_events(report_id: str) -> list[dict]:
    if not EVENTS_PATH.exists():
        return []
    out = []
    with open(EVENTS_PATH) as f:
        for line in f:
            if report_id not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            if (e.get("payload") or {}).get("report_id") == report_id or report_id in line:
                out.append(e)
    return out


def tokens_summary(events: list[dict]) -> dict:
    in_tot = cached_tot = out_tot = 0
    calls = []
    for e in events:
        if e.get("category") != "llm.call.done":
            continue
        p = e.get("payload") or {}
        i = p.get("input_tokens") or 0
        c = p.get("cached_input_tokens") or 0
        o = p.get("output_tokens") or 0
        in_tot += i
        cached_tot += c
        out_tot += o
        calls.append({"in": i, "cached": c, "out": o, "tool": p.get("tool_name", "")})
    # gpt-5.4 pricing (approximate — adjust to reality)
    in_cost = (in_tot - cached_tot) * 1.25 / 1_000_000 + cached_tot * 0.125 / 1_000_000
    out_cost = out_tot * 10 / 1_000_000
    return {
        "calls": len(calls),
        "input_tokens": in_tot,
        "cached_input_tokens": cached_tot,
        "output_tokens": out_tot,
        "cache_hit_ratio": cached_tot / in_tot if in_tot else 0,
        "est_cost_usd": round(in_cost + out_cost, 3),
        "per_call": calls,
    }


def tool_call_summary(events: list[dict]) -> dict:
    by_tool: dict[str, int] = {}
    payload_reads = 0
    payload_misses = 0
    web_searches = 0
    web_search_queries = []
    validation_failures = 0
    validation_errors_seen: list[str] = []
    uncited_warnings = 0
    for e in events:
        cat = e.get("category", "")
        p = e.get("payload") or {}
        if cat == "report.tool_call":
            t = p.get("tool_name") or p.get("name") or "?"
            by_tool[t] = by_tool.get(t, 0) + 1
            if t == "read_payload":
                payload_reads += 1
        elif cat == "report.tool_result":
            t = p.get("tool_name") or p.get("name") or ""
            if t == "read_payload" or "read_payload" in (p.get("summary") or "").lower():
                summary = p.get("summary") or ""
                if "no match" in summary.lower() or "not found" in summary.lower():
                    payload_misses += 1
        elif cat == "report.web_search.invoked":
            web_searches += 1
            web_search_queries.append((p.get("query") or "")[:140])
        elif cat == "writing.validation_failed":
            validation_failures += 1
            for er in p.get("errors") or []:
                validation_errors_seen.append(
                    f"{er.get('path')}: {er.get('message','')[:80]}"
                )
        elif cat == "report.warning.uncited_claim":
            uncited_warnings += 1
    return {
        "tool_calls_by_name": by_tool,
        "read_payload_calls": payload_reads,
        "read_payload_misses": payload_misses,
        "web_searches": web_searches,
        "web_search_queries": web_search_queries,
        "validation_failures": validation_failures,
        "validation_error_paths": validation_errors_seen[:20],
        "uncited_warnings": uncited_warnings,
    }


# --- FORMATTING ANALYSIS ---

CITATION_RE = re.compile(r"\[(\d+)\]|\[(?:[^\]]+),\s*\"[^\"]+\",\s*\d{4}")
NUMERIC_CLAIM_RE = re.compile(r"\b(\d+(?:[.,]\d+)*\s*%?|\$\s*\d+(?:[.,]\d+)*(?:[KMB])?)\b")


def analyze_formatting(report: dict) -> dict:
    issues: list[str] = []
    notes: list[str] = []
    cover = report.get("cover") or {}
    for fld in ("title", "subtitle", "tagline"):
        if not cover.get(fld):
            issues.append(f"cover.{fld} missing or empty")
    sections = report.get("sections") or []
    section_ids = [s.get("id") for s in sections]
    expected = [
        "company_overview", "industry_overview", "products_and_services",
        "business_model", "competitive_analysis", "management_team",
        "competitive_advantages", "risk_analysis", "recent_developments",
        "historical_financials", "financial_analysis", "financial_projections",
        "valuation_analysis", "investment_recommendation",
    ]
    missing_sections = [s for s in expected if s not in section_ids]
    if missing_sections:
        issues.append(f"missing sections: {missing_sections}")
    extra_sections = [s for s in section_ids if s not in expected]
    if extra_sections:
        notes.append(f"unexpected section ids: {extra_sections}")

    # Block-type histogram
    block_types: dict[str, int] = {}
    text_blocks = 0
    chart_blocks = 0
    citation_refs: set[str] = set()
    section_word_counts: dict[str, int] = {}
    section_block_counts: dict[str, int] = {}
    sections_with_metrics: list[str] = []
    sections_with_charts: list[str] = []
    sections_with_tables: list[str] = []
    sections_without_citations: list[str] = []

    for s in sections:
        sid = s.get("id", "?")
        sec_wc = 0
        sec_has_cite = False
        for b in s.get("blocks") or []:
            bt = b.get("type", "?")
            block_types[bt] = block_types.get(bt, 0) + 1
            if bt == "text":
                content = b.get("content", "")
                sec_wc += len(content.split())
                text_blocks += 1
                # Find citation references
                for m in re.finditer(r"\[(\d+)\]", content):
                    citation_refs.add(m.group(1))
                    sec_has_cite = True
            elif "chart" in bt:
                chart_blocks += 1
                sections_with_charts.append(sid)
            elif bt == "metric_cards":
                sections_with_metrics.append(sid)
            elif bt == "table":
                sections_with_tables.append(sid)
        section_word_counts[sid] = sec_wc
        section_block_counts[sid] = len(s.get("blocks") or [])
        if not sec_has_cite and sec_wc > 0:
            sections_without_citations.append(sid)

    # Citations top-level
    top_citations = report.get("citations") or []
    citation_ids = {c.get("id") for c in top_citations}
    orphan_refs = citation_refs - citation_ids
    if orphan_refs:
        issues.append(f"text refs [{','.join(sorted(orphan_refs))[:80]}] not in citations list")

    return {
        "issues": issues,
        "notes": notes,
        "block_types": block_types,
        "section_word_counts": section_word_counts,
        "section_block_counts": section_block_counts,
        "missing_sections": missing_sections,
        "text_blocks_total": text_blocks,
        "chart_blocks_total": chart_blocks,
        "sections_with_metrics_cards": sections_with_metrics,
        "sections_with_charts": sections_with_charts,
        "sections_with_tables": sections_with_tables,
        "sections_without_citations": sections_without_citations,
        "total_citations": len(top_citations),
        "citations_referenced": len(citation_refs),
        "total_words": sum(section_word_counts.values()),
    }


def analyze_data_availability(report: dict) -> dict:
    """Look for 'data not available' patterns, empty metric values, hollow charts."""
    sections = report.get("sections") or []
    data_unavailable_phrases = [
        "data not available", "data unavailable", "n/a", "not disclosed",
        "not available", "no data", "information not", "we could not",
        "we were unable to", "no public", "undisclosed",
    ]
    findings: list[dict] = []
    empty_metric_cards: list[dict] = []
    empty_chart_data: list[dict] = []

    for s in sections:
        sid = s.get("id", "?")
        for b in s.get("blocks") or []:
            bt = b.get("type", "?")
            if bt == "text":
                content = (b.get("content") or "").lower()
                for phrase in data_unavailable_phrases:
                    if phrase in content:
                        # Get context
                        idx = content.find(phrase)
                        snippet = content[max(0, idx-60):min(len(content), idx+len(phrase)+60)]
                        findings.append({
                            "section": sid,
                            "phrase": phrase,
                            "context": snippet,
                        })
                        break
            elif bt == "metric_cards":
                for m in b.get("metrics") or []:
                    if not m.get("value") or m.get("value", "").strip().lower() in ("n/a", "—", "-", "n/d"):
                        empty_metric_cards.append({"section": sid, "label": m.get("label")})
            elif "chart" in bt:
                series = b.get("series") or []
                if not series:
                    empty_chart_data.append({"section": sid, "type": bt, "title": b.get("title", "")})
                else:
                    # Check if all data points are null/zero
                    all_empty = True
                    for sr in series:
                        for pt in sr.get("data") or []:
                            if pt and pt != 0:
                                all_empty = False
                                break
                    if all_empty:
                        empty_chart_data.append({"section": sid, "type": bt, "title": b.get("title", "")})
    return {
        "data_unavailable_text_mentions": len(findings),
        "findings_sample": findings[:10],
        "empty_metric_cards": empty_metric_cards,
        "empty_chart_data": empty_chart_data,
    }


def analyze_quality(report: dict) -> dict:
    """Surface quality signals: short sections, dense vs sparse, depth indicators."""
    sections = report.get("sections") or []
    short_sections: list[dict] = []
    no_chart_sections_that_should: set[str] = set()
    sparse_text_only: list[str] = []

    # Per style guide, these sections SHOULD have charts/visualizations
    should_have_chart = {
        "industry_overview", "products_and_services", "historical_financials",
        "financial_analysis", "financial_projections", "valuation_analysis",
    }
    should_have_table = {"competitive_analysis", "historical_financials", "valuation_analysis"}

    for s in sections:
        sid = s.get("id", "?")
        blocks = s.get("blocks") or []
        wc = 0
        block_types = []
        for b in blocks:
            block_types.append(b.get("type"))
            if b.get("type") == "text":
                wc += len(((b.get("content")) or "").split())

        if wc < 50:
            short_sections.append({"section": sid, "word_count": wc, "blocks": block_types})
        if sid in should_have_chart and not any("chart" in (t or "") for t in block_types):
            no_chart_sections_that_should.add(sid)
        if len(block_types) == 1 and block_types[0] == "text" and wc > 0:
            sparse_text_only.append(sid)

    return {
        "short_sections_lt_50_words": short_sections,
        "sections_should_have_chart_but_dont": sorted(no_chart_sections_that_should),
        "text_only_sections": sparse_text_only,
    }


def main(report_id: str) -> None:
    report = load_report(report_id)
    events = load_events(report_id)
    if not events:
        print(f"No events for {report_id}", file=sys.stderr)
        return

    out: dict = {"report_id": report_id}
    out["tokens"] = tokens_summary(events)
    out["tools"] = tool_call_summary(events)
    if report:
        out["formatting"] = analyze_formatting(report)
        out["data_availability"] = analyze_data_availability(report)
        out["quality"] = analyze_quality(report)
        # Find errors
        out["errors"] = [
            e.get("subject") for e in events if e.get("category") == "report.error"
        ]
    else:
        out["report"] = None
        out["note"] = "report not persisted to DB yet or not found"

    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: analyze_report.py <report_id>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
