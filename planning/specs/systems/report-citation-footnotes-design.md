# Report Citation Footnotes — Design Spec

**Branch:** `fix/equity-research-citations-footnotes`
**Date:** 2026-05-16
**Scope:** All report-producing departments (equity research, earnings update, macro research, morning briefing, panic thermometer)

---

## Problem

Reports currently emit raw inline citation tuples directly in prose text:

> "Apple's Q1 2026 revenue was $95.4B [get_fundamentals_data(AAPL.US)], driven by services strength [Reuters, 2026-05-12, reuters.com/article-foo]."

This is verbose, repetitive across long reports, and visually messy. The user-visible report should use numbered footnotes (`[1]`, `[2]`) inline with a deduplicated, numbered source list at the bottom. Clicking `[N]` should scroll to source N at the bottom of the report.

## Current state (what already exists)

The frontend is *already wired* for numbered footnotes:

| Component | Status |
|---|---|
| `frontend/src/components/report/CitationsSection.tsx` | Renders `<ol>` of citations at bottom, each `<li id="cite-{id}">` |
| `frontend/src/components/report/CitationsRail.tsx` | Side-panel mirror of the bottom list |
| `frontend/src/components/report/CitationRefs.tsx` | Renders block-level `[N]` anchors linking to `#cite-{id}` |
| `frontend/src/components/report/blocks/TextBlock.tsx` | **Already parses inline `[N]` markers** inside `content` via regex `\[(\d+(?:\s*,\s*\d+)*)\]` and renders `<sup>[N]</sup>` with `#cite-{id}` anchors |
| `frontend/src/api/reports.ts` | `Citation = {id, title, source?, url?, date?}` and `ReportSchema.citations: Citation[]` |
| `packages/core/src/openlia/reports/schema.py` (L393) | Pydantic `Citation` model (mirrors TS) |

**The frontend works.** The gap is purely:
1. The LLM emits the old inline `[source, date, url]` text — never populates `report.citations` or `[N]` markers.
2. `Citation.title` is required (Python and TS); some citations have no scrape-able title.
3. No server-side normalizer converts old format → new format.
4. Prompt (`two_source_discipline.yaml.j2`) tells the LLM the old format.

---

## Design decisions (locked)

| # | Decision |
|---|---|
| Q1 | **Hybrid path** — LLM is told to emit citations; server normalizes/renumbers. (Effectively Q11 collapses this: server is canonical.) |
| Q2 | **Inline `[N]` markers inside `TextBlock.content`** — already supported by frontend. |
| Q3 | **Both web and provider citations become numbered footnotes.** |
| Q4 | **Web identity = normalized URL** (strip query/fragment, lowercase host, strip trailing slash). **Provider identity = `(tool_name, key_params_tuple)`**. First-encountered title/source/date win on collision. |
| Q5 | **Prompt format adds article title:** `[source, "title", YYYY-MM-DD, url]` for web; `[tool_name(key_params)]` for provider. Provider footnote title becomes a human label like `"EODHD fundamentals — AAPL.US"`. |
| Q6 | **Order of first appearance** (walk sections top-to-bottom, assign IDs `"1"`, `"2"`, ... in encounter order). |
| Q7 | **All departments** — single update to shared `two_source_discipline.yaml.j2`. |
| Q8 | **Final-pass normalization** — runs once after assembly, before validation/persist. (Streaming UX not user-visible.) |
| Q9 | **No backfill of existing reports** — clean cutoff. Old reports continue to render with raw inline text. |
| Q10 | **TextBlock**: inline `[N]` (existing). **KeyFinding/PullQuote/Quote/MetricCards**: keep block-level `source_ids` (existing). **TableBlock**: add table-level `source_ids: list[str]` rendered below the table. **Chart blocks**: add `source_ids: list[str]` rendered as caption. |
| Q11 | **Always renumber server-side** — LLM-assigned `[N]` and `citations[]` entries are advisory; server is canonical. |
| Q12+13 | **Malformed citations also get numbers.** Missing title is normal — fallback chain: `title` → `url` (hostname+path) → `source · date` → raw bracket text. Dedup key: normalized URL when present; raw bracket text when not. |
| Q14 | **Inline marker style**: `[N]` superscript (already rendered by `TextBlock.tsx`). **No back-link** from bottom entry to first mention in v1. |
| Q15 | **Prompt simplifies to**: "emit full tuple every time, no shorthand, no numbering — server handles dedup/numbering." |

---

## File-level changes

### 1. `packages/core/src/openlia/reports/schema.py`

**Change A — Citation.title becomes optional (L393-398):**
```python
class Citation(_Strict):
    id: str
    title: str | None = None        # was: str (required)
    source: str | None = None
    url: str | None = None
    date: str | None = None
```

**Change B — TableBlock gets source_ids (L74-81):**
```python
class TableBlock(_Strict):
    type: Literal["table"]
    title: str
    headers: Annotated[list[TableHeader], Field(min_length=1)]
    rows: Annotated[list[dict[str, Any]], Field(min_length=1)]
    cell_format: dict[str, CellFormat] = Field(default_factory=dict)
    footnotes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)   # NEW
    options: dict[str, Any] = Field(default_factory=dict)
```

**Change C — Chart blocks (LineChartBlock, BarChartBlock, AreaChartBlock, PieChartBlock, CandlestickChartBlock, WaterfallChartBlock, ScatterPlotBlock, HeatmapBlock, TreemapBlock, ComboChartBlock — search the file) each get:**
```python
    source_ids: list[str] = Field(default_factory=list)   # NEW
```

### 2. New module: `packages/core/src/openlia/reports/citations.py`

Pure stdlib module (no FastAPI). Provides:

```python
from dataclasses import dataclass, field
import re
from urllib.parse import urlparse, urlunparse

@dataclass(frozen=True)
class _ParsedCitation:
    kind: str                # "web" | "provider" | "malformed"
    dedup_key: str           # canonical identity for dedup
    title: str | None
    source: str | None
    date: str | None
    url: str | None
    raw: str                 # original bracket contents, for fallback display

# Patterns
_WEB_PATTERN = re.compile(r"\[([^\[\]]+)\]")  # any bracket group
# Provider pattern: tool_name( args )  (no commas outside parens, no quotes)
_PROVIDER_NAME = re.compile(r"^([a-z_][a-z0-9_]*)\(([^)]*)\)$")

def _normalize_url(url: str) -> str:
    """Lowercase host, strip query/fragment, strip trailing slash."""
    u = urlparse(url if "://" in url else f"https://{url}")
    host = u.netloc.lower()
    path = u.path.rstrip("/")
    return urlunparse((u.scheme or "https", host, path, "", "", ""))

def _parse_one(raw: str) -> _ParsedCitation:
    """Parse a single bracket's inner contents.

    Tries provider form first (`tool_name(params)`), then web tuple.
    On total failure, returns malformed with dedup_key = raw.
    """
    body = raw.strip()

    # 1. Provider tool call?
    m = _PROVIDER_NAME.match(body)
    if m:
        tool, params = m.group(1), m.group(2).strip()
        # Title: "EODHD fundamentals — AAPL.US" (best-effort label)
        return _ParsedCitation(
            kind="provider",
            dedup_key=f"{tool}({params})",
            title=_provider_label(tool, params),
            source=tool,
            date=None,
            url=None,
            raw=body,
        )

    # 2. Web tuple? Tolerant: detect URL (last field containing '.'),
    #    detect date (ISO YYYY-MM-DD OR "Mon DD, YYYY"), quoted title,
    #    source = whatever remains.
    parsed = _parse_web_tuple(body)
    if parsed is not None:
        return parsed

    # 3. Malformed — still emit a citation with raw text as title fallback.
    return _ParsedCitation(
        kind="malformed",
        dedup_key=body,            # raw text identity
        title=None, source=None, date=None, url=None,
        raw=body,
    )

def _parse_web_tuple(body: str) -> _ParsedCitation | None:
    """Tolerant web-tuple parser.

    Strategy:
      1. URL detection: rightmost token containing a TLD-ish pattern OR scheme.
      2. Date detection: ISO `\d{4}-\d{2}-\d{2}` OR `[A-Z][a-z]+ \d{1,2},? \d{4}`.
      3. Title detection: anything in matched `"..."` quotes.
      4. Source: whatever's left after stripping the above (joined).

    Returns None if no URL AND no date AND no quoted title found
    (caller will mark malformed).
    """
    ...  # see implementation notes below

def _provider_label(tool: str, params: str) -> str:
    """Human-readable label for provider footnotes.

    Examples:
      get_fundamentals_data(AAPL.US) -> "EODHD fundamentals — AAPL.US"
      eodhd__financial_news(s=AAPL.US,...) -> "EODHD financial news — AAPL.US"
      flashalpha_quote(NVDA) -> "Flashalpha quote — NVDA"

    Pure heuristic; falls back to "{tool}({params})" if no mapping matches.
    """
    ...

# ─── Public API ─────────────────────────────────────────────────────────────

@dataclass
class NormalizationResult:
    citations: list[dict]     # ready for ReportSchema.citations
    replacements: dict[str, str]   # raw bracket text -> "[N]"
    malformed_count: int

def normalize_report(payload: dict) -> dict:
    """Walk a v2 ReportSchema dict, extract all inline citation tuples,
    dedupe, assign sequential IDs in encounter order, replace bracket
    text in prose with `[N]` markers, and populate `citations[]`.

    Order of walk for ID assignment:
      sections[0].blocks[0] -> sections[0].blocks[1] -> ... -> sections[1] -> ...

    Within each block, walk in declaration order; for prose blocks,
    walk left-to-right through the content string.

    Block-level `source_ids` fields (KeyFinding, PullQuote, Quote,
    MetricCards.metrics[].source_ids, TableBlock, chart blocks):
      - Treated as already-numbered references.
      - We DON'T trust their numbering — instead, we look up each
        ID in the LLM's `citations[]` (if any) to recover the tuple,
        then reassign canonical IDs.
      - If `citations[]` is empty/missing, block-level source_ids
        become "[?]" malformed citations (rare; the LLM shouldn't
        emit source_ids without also emitting citations[]).

    Idempotent: running twice on the same payload is a no-op (the
    second pass finds only `[N]` markers, which it ignores).
    """
    ...
```

### 3. `packages/core/src/openlia/reports/assembler.py`

Wire the normalizer into the final pass:

```python
from openlia.reports.citations import normalize_report

def assemble_report(
    payload: dict[str, Any],
    *,
    department: str,
    furniture: PageFurnitureConfig,
    now: datetime,
) -> ReportSchema:
    stripped = _strip_instructions(deepcopy(payload))
    stripped.pop("page_furniture", None)
    stripped["page_furniture"] = _build_furniture(furniture, department, now)
    stripped.setdefault("schema_version", "2.0")
    stripped.setdefault("department", department)
    stripped.setdefault("generated_at", now.isoformat())
    _assert_no_tool_placeholders(stripped)
    stripped = normalize_report(stripped)        # NEW
    return validate_report_payload(stripped)
```

This is the single insertion point. Normalization is universal across departments because every report passes through `assemble_report`.

### 4. `packages/core/src/openlia/prompts/shared/two_source_discipline.yaml.j2`

**Replace L55-68 (the "Citation format" section).** New text:

```yaml
### Citation format

Every concrete claim must be cited inline. Emit the **full citation tuple every time** — do not number, do not abbreviate for repeat sources. The server deduplicates and assigns footnote numbers automatically.

- Web citation: `[source, "Article title", YYYY-MM-DD, url]`
  Example: "Apple beat Q1 estimates [Reuters, "Apple beats Q1 expectations on services strength", 2026-05-12, reuters.com/business/apple-q1]."
- Provider citation: `[tool_name(key_params)]`
  Example: "Apple's Q1 2026 revenue was $95.4B [get_fundamentals_data(AAPL.US)]."
- Provider news endpoint rows (e.g., `eodhd__financial_news`): cite the row's source, title, date, and url — not the endpoint itself.
  Good: "Apple won an EU appeal [Reuters, "Apple wins EU appeal on App Store ruling", 2026-05-12, reuters.com/...]."
  Bad:  "Apple won an EU appeal [eodhd__financial_news(s=AAPL.US,...)]."
- No source available: "Data not available as of {{ current_date }}." (no citation)

Do not blend formats. Do not pre-number with `[1]`, `[2]` — the server numbers in order of first appearance. Do not write `(see above)` or `[ibid]` for repeats — re-emit the full tuple every time.
```

**Drop the "Anti-patterns" example for `read_payload`** unchanged (still valid). **Update the example without title** to include a title where applicable.

### 5. Frontend — minimal changes

**`frontend/src/api/reports.ts`** (L67-73): make `title` optional:
```ts
export interface Citation {
  id: string;
  title?: string | null;   // was: title: string;
  source?: string | null;
  url?: string | null;
  date?: string | null;
}
```

**`frontend/src/components/report/CitationsSection.tsx`** — fallback chain when `title` is missing:
```tsx
function displayTitle(c: Citation): string {
  if (c.title) return c.title;
  if (c.url) {
    try {
      const u = new URL(c.url.startsWith('http') ? c.url : `https://${c.url}`);
      return `${u.hostname}${u.pathname}`.replace(/\/$/, '');
    } catch { return c.url; }
  }
  if (c.source && c.date) return `${c.source} · ${c.date}`;
  if (c.source) return c.source;
  return '(source)';
}
```

Apply same logic in `CitationsRail.tsx` (`composePreview` already handles missing source/date; just add the title fallback).

**Optional: `TableBlock` and chart-block components**
Render a small "Sources:" caption under the block when `source_ids` is non-empty, using `<CitationRefs ids={source_ids} />`. Defer if not strictly needed for v1 — `TableBlock.source_ids` and chart `source_ids` are schema-supported but the visual addition is cosmetic.

### 6. Tests

**New: `packages/core/tests/test_citation_normalizer.py`** covering:
- URL normalization: trailing slash, query, fragment, host case all collapse to one.
- Provider dedup: `get_fundamentals_data(AAPL.US)` cited 5× → one footnote.
- Mixed: web + provider in same prose, numbered in encounter order.
- Order: section 2 introduces source first → `[1]` in section 2 even if section 1 cites later.
- Malformed: `[per CEO commentary]` → gets a number, title = raw, no URL.
- Missing title field (3-tuple legacy): `[Reuters, 2026-05-12, reuters.com/...]` → title falls back to URL slug.
- Quoted title with internal commas: `[Reuters, "Apple beats, hits record", 2026-05-12, reuters.com/...]` → title parsed correctly.
- Date variants: `2026-05-12` and `May 12, 2026` both recognized as dates.
- Idempotency: `normalize_report(normalize_report(x)) == normalize_report(x)`.
- `TableBlock.source_ids` and chart `source_ids` round-trip through normalization (referenced IDs get renumbered).

**Update: existing `test_prompt_contents.py`** assertions for `two_source_discipline.yaml.j2` to match new format spec.

**Frontend test additions** to `CitationsSection.test.tsx`:
- Title fallback: missing title with URL → renders hostname+path.
- Title fallback: missing title and URL → renders raw fallback text.

---

## Build sequence

1. **Schema changes** (`schema.py`) — make `Citation.title` optional, add `source_ids` to `TableBlock` and chart blocks. Run existing tests; fix anything that breaks because `title` was assumed required.
2. **Normalizer module** (`citations.py`) — TDD. Start with `_normalize_url`, then `_parse_one`, then `normalize_report` on a hand-built payload. All test fixtures live in the test file.
3. **Wire into assembler** (`assembler.py`) — one-line insertion. Verify existing report-assembly tests still pass (the LLM payloads in fixtures should now produce numbered citations).
4. **Update prompt** (`two_source_discipline.yaml.j2`) — replace citation-format section. Update `test_prompt_contents.py` assertions. Smoke-test that prompt rendering still works.
5. **Frontend type + display** (`reports.ts`, `CitationsSection.tsx`, `CitationsRail.tsx`) — make `title` optional, add fallback chain, render tests.
6. **End-to-end smoke** — generate a stock-initiation report in dev; verify:
   - Prose contains `[N]` superscript markers, not raw `[source, date, url]` text.
   - Bottom list has deduped, numbered sources.
   - Clicking `[N]` scrolls to source N.
   - Provider citations have human labels ("EODHD fundamentals — AAPL.US"), no URL link.

---

## Non-goals (v1)

- **No backfill of existing reports** — clean cutoff.
- **No back-links** from citation list to first mention (browser back button suffices).
- **No per-cell or per-row table citations** — table-level only.
- **No tooltip preview** on hover over `[N]`.
- **No structured `data_quality_warnings`** surfaced in the schema — malformed citations become footnotes; only server logs see the "malformed" diagnostic.
- **No `read_payload` recovery** — `[read_payload(...)]` citations are treated as malformed (numbered with raw text as title). Memory 6113 already tightened the prompt against this; if it recurs, fix it in the prompt rather than the normalizer.

---

## Risks

| Risk | Mitigation |
|---|---|
| LLM emits malformed tuple variants we didn't anticipate (e.g., field order swap, missing brackets, unescaped quotes inside title) | Lenient `_parse_web_tuple` (URL/date/title detection regardless of order); anything truly unparseable becomes a malformed citation (still gets a number, raw text as title). Log a warning per occurrence so we can find new patterns. |
| Schema `Citation.title` becoming optional breaks existing tests that build Citations with `title="..."` | Optional, default None — existing constructions still work. Only validation that *requires* title would break; search and fix. |
| Walk order ambiguity (e.g., MetricCards has both `source_ids` and per-metric `source_ids`) | Spec: walk per-metric `source_ids` in metric declaration order. Document in `citations.py` docstring. |
| Old prompt text still cached or rendered in some code path | Single source: `two_source_discipline.yaml.j2`. `test_prompt_contents.py` enforces what's in the rendered output. |
| Frontend `TextBlock.tsx` inline `[N]` parser regex `\[(\d+(?:\s*,\s*\d+)*)\]` collides with legitimate prose like "see Table [1]" | Already a constraint in the existing system. Normalizer never produces non-citation brackets in TextBlock content. If the LLM writes "see Table [1]" in prose with no actual citation at id 1, the anchor is a dead link — acceptable. |

---

## Open questions (none — design is locked)

All decisions Q1-Q15 resolved. Ready to implement.
