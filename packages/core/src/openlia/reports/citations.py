"""Server-side normalization of inline citations into numbered footnotes.

The LLM emits citations inline as bracket tuples in prose text:

    [source, "title", YYYY-MM-DD, url]     # web
    [tool_name(key_params)]                # provider tool call

`normalize_report` walks a v2 ReportSchema payload, extracts every inline
citation, deduplicates them, assigns sequential ids in encounter order,
rewrites the prose to use `[N]` markers (which the frontend renders as
clickable superscript), and populates `report.citations`.

Idempotent: a second pass finds only `[N]` markers and ignores them.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse

# Matches a citation bracket: anything inside `[...]` that isn't itself
# already a `[N]` or `[N,M,...]` footnote marker (those get left alone).
_BRACKET = re.compile(r"\[(?!\s*\d+(?:\s*,\s*\d+)*\s*\])([^\[\]]+)\]")

# Provider form: identifier(args) — no quoted strings, no commas outside parens.
_PROVIDER = re.compile(r"^([a-z_][a-z0-9_]*)\(([^)]*)\)$")


def _normalize_url(url: str) -> str:
    """Canonicalize a URL for dedup: lowercase host, strip query/fragment,
    strip trailing slash. Adds https:// if scheme missing.
    """
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    u = urlparse(candidate)
    host = u.netloc.lower()
    path = u.path.rstrip("/")
    return urlunparse((u.scheme or "https", host, path, "", "", ""))


_PROVIDER_LABEL_PREFIXES = {
    "get_fundamentals_data": "EODHD fundamentals",
    "get_historical_stock_prices": "EODHD historical prices",
    "eodhd__financial_news": "EODHD financial news",
    "flashalpha_quote": "Flashalpha quote",
}


def _provider_label(tool: str, params: str) -> str:
    prefix = _PROVIDER_LABEL_PREFIXES.get(tool)
    args = params.strip()
    if prefix:
        return f"{prefix} — {args}" if args else prefix
    return f"{tool}({params})"


def _parse_malformed(body: str) -> dict:
    """Fallback: an unrecognizable citation still becomes a footnote.

    Dedup key is the raw bracket text (verbatim). Title falls back to
    the same raw text so the bottom list shows what the LLM was
    trying to attribute.
    """
    cleaned = body.strip()
    return {
        "source": None,
        "title": cleaned,
        "date": None,
        "url": None,
        "normalized_url": f"malformed:{cleaned}",
    }


def _parse_provider(body: str) -> dict | None:
    m = _PROVIDER.match(body.strip())
    if not m:
        return None
    tool, params = m.group(1), m.group(2).strip()
    return {
        "source": tool,
        "title": _provider_label(tool, params),
        "date": None,
        "url": None,
        "normalized_url": f"provider:{tool}({params})",
    }


def _parse_web_tuple(body: str) -> dict | None:
    """Tolerant parse of a comma-separated web citation tuple.

    Expected: `source, "title", YYYY-MM-DD, url` (4 fields).
    Tolerates: 3 fields (no title), unquoted title, swapped order
    of date/url, quoted strings containing commas.

    Returns dict with keys {source, title, date, url, normalized_url}
    or None if no URL-looking field is found.
    """
    # Pull out quoted string first (it's the title and may contain commas).
    title: str | None = None
    m = re.search(r'"([^"]+)"', body)
    if m:
        title = m.group(1)
        body = body[: m.start()] + body[m.end() :]

    parts = [p.strip() for p in body.split(",") if p.strip()]

    url_idx: int | None = None
    for i, p in enumerate(parts):
        if re.search(r"https?://", p) or re.search(r"[a-z]+\.[a-z]{2,}", p, re.I):
            url_idx = i
            break
    if url_idx is None:
        return None
    url_raw = parts.pop(url_idx)

    date: str | None = None
    for i, p in enumerate(parts):
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p):
            date = p
            parts.pop(i)
            break
    # "Month DD, YYYY" survives as two split tokens — try to reglue.
    if date is None:
        for i in range(len(parts) - 1):
            if re.fullmatch(r"[A-Z][a-z]+\s+\d{1,2}", parts[i]) and re.fullmatch(
                r"\d{4}", parts[i + 1]
            ):
                date = f"{parts[i]}, {parts[i + 1]}"
                parts.pop(i + 1)
                parts.pop(i)
                break

    source = ", ".join(parts).strip() or None
    normalized = _normalize_url(url_raw)

    return {
        "source": source,
        "title": title,
        "date": date,
        "url": normalized,
        "normalized_url": normalized,
    }


def normalize_report(payload: dict[str, Any]) -> dict[str, Any]:
    """Walk a v2 report payload, normalize all inline citations to `[N]`
    markers, populate `payload['citations']`.

    Returns the mutated payload (also mutates in place — caller may pass
    a deep copy if isolation is needed).
    """
    citations: list[dict] = []
    by_key: dict[str, str] = {}
    # body-as-emitted -> new numeric cid. Lets us translate source_ids
    # arrays (which the writer sometimes fills with raw bracket bodies
    # like "c1" or "eodhd__get_fundamentals_data(NET.US)") to the same
    # ids the rewrite step assigned.
    raw_body_to_cid: dict[str, str] = {}

    def _intern(parsed: dict) -> str:
        key = parsed["normalized_url"]
        if key in by_key:
            return by_key[key]
        cid = str(len(citations) + 1)
        by_key[key] = cid
        citations.append(
            {
                "id": cid,
                "title": parsed.get("title"),
                "source": parsed.get("source"),
                "url": parsed.get("url"),
                "date": parsed.get("date"),
            }
        )
        return cid

    def _intern_body(body: str) -> str:
        """Translate a raw bracket body (or whatever the writer put in
        source_ids) into a numeric citation id. Caches by raw body so
        the same string used twice maps to the same id."""
        body = body.strip()
        if body in raw_body_to_cid:
            return raw_body_to_cid[body]
        # Already numeric (e.g., "1", "2") — pass through.
        if body.isdigit():
            raw_body_to_cid[body] = body
            return body
        # Common writer shorthand: "c1", "c2" — the leading 'c' is just
        # a prefix the model invents; the numeric tail is the citation
        # index. Pass the tail through so we don't intern a fake.
        m = re.fullmatch(r"c(\d+)", body)
        if m:
            cid = m.group(1)
            raw_body_to_cid[body] = cid
            return cid
        parsed = _parse_provider(body) or _parse_web_tuple(body) or _parse_malformed(body)
        cid = _intern(parsed)
        raw_body_to_cid[body] = cid
        return cid

    def _rewrite(text: str) -> str:
        def _sub(m: re.Match[str]) -> str:
            body = m.group(1)
            cid = _intern_body(body)
            return f"[{cid}]"

        return _BRACKET.sub(_sub, text)

    # Citation-bearing string fields per block type. The writer may emit
    # raw [provider(args)] or web-tuple brackets in any of these; we walk
    # them all so footnote coverage matches the visible report, not just
    # the prose paragraphs.
    _STRING_FIELDS = {
        "text": ("content",),
        "key_finding": ("content", "title"),
        "pull_quote": ("content", "quote", "attribution"),
        "quote": ("content", "quote", "attribution"),
        "bullet_list": ("title",),  # items handled below
        "comparison_split": ("title",),  # nested left/right items handled below
        "table": ("title", "caption", "footnote"),
        "metric_cards": ("title",),
        "callout": ("content", "title"),
    }

    def _rewrite_block(block: dict) -> None:
        btype = block.get("type")
        for field in _STRING_FIELDS.get(btype, ()):
            v = block.get(field)
            if isinstance(v, str) and v:
                block[field] = _rewrite(v)
        # bullet_list items
        if btype == "bullet_list":
            items = block.get("items") or []
            block["items"] = [_rewrite(it) if isinstance(it, str) else it for it in items]
        # comparison_split: left + right blocks each have title + items
        if btype == "comparison_split":
            for side in ("left", "right"):
                sd = block.get(side) or {}
                if isinstance(sd, dict):
                    if isinstance(sd.get("title"), str):
                        sd["title"] = _rewrite(sd["title"])
                    items = sd.get("items") or []
                    sd["items"] = [_rewrite(it) if isinstance(it, str) else it for it in items]
        # metric_cards: each metric's label/value
        if btype == "metric_cards":
            for m in block.get("metrics") or []:
                if isinstance(m, dict):
                    for fld in ("label", "value", "delta", "context", "tag"):
                        v = m.get(fld)
                        if isinstance(v, str) and v:
                            m[fld] = _rewrite(v)
        # table cells (rows is a list of dicts, values may be strings)
        if btype == "table":
            for row in block.get("rows") or []:
                if isinstance(row, dict):
                    for k, v in list(row.items()):
                        if isinstance(v, str) and v:
                            row[k] = _rewrite(v)

    def _remap_source_ids(seq: list) -> list[str]:
        """Translate every entry in source_ids through _intern_body so a
        block's source_ids match the numeric citation ids the rewrite
        pass produced. Keeps unique order."""
        out: list[str] = []
        seen: set[str] = set()
        for entry in seq:
            if not isinstance(entry, str):
                continue
            cid = _intern_body(entry)
            if cid not in seen:
                seen.add(cid)
                out.append(cid)
        return out

    def _normalize_block_source_ids(block: dict) -> None:
        if isinstance(block.get("source_ids"), list):
            block["source_ids"] = _remap_source_ids(block["source_ids"])
        btype = block.get("type")
        if btype == "metric_cards":
            for m in block.get("metrics") or []:
                if isinstance(m, dict) and isinstance(m.get("source_ids"), list):
                    m["source_ids"] = _remap_source_ids(m["source_ids"])

    for section in payload.get("sections", []):
        for block in section.get("blocks", []):
            _rewrite_block(block)
            _normalize_block_source_ids(block)

    # Rail.quick_stats are Metric objects with label/value strings.
    rail = payload.get("rail")
    if isinstance(rail, dict):
        # The model occasionally hallucinates source_ids on the Rail itself —
        # that field doesn't exist on the Rail schema (only verdict /
        # quick_stats / sparkline are valid). Strip it so we never produce
        # validation errors on this known drift point.
        rail.pop("source_ids", None)
        for m in rail.get("quick_stats") or []:
            if isinstance(m, dict):
                for fld in ("label", "value", "delta", "context", "tag"):
                    v = m.get(fld)
                    if isinstance(v, str) and v:
                        m[fld] = _rewrite(v)

    payload["citations"] = citations

    # Second pass: harvest [N] refs from each block's visible strings and
    # auto-fill that block's source_ids when empty. The writer leaves
    # source_ids = [] on Metric / KeyFinding / etc. far too often; this
    # closes the gap so the validator's "no source_ids" warning fires
    # only when there really is no inline attribution either.
    _REF_RE = re.compile(r"\[(\d+)\]")

    def _collect_refs(*texts: Any) -> list[str]:
        seen: list[str] = []
        for t in texts:
            if not isinstance(t, str):
                continue
            for m in _REF_RE.finditer(t):
                cid = m.group(1)
                if cid not in seen:
                    seen.append(cid)
        return seen

    def _autofill_source_ids(block: dict) -> None:
        btype = block.get("type")
        # Direct source_ids on the block itself (key_finding, pull_quote, quote)
        if "source_ids" in block and not block.get("source_ids"):
            texts = [block.get("content"), block.get("quote"), block.get("title")]
            if btype == "bullet_list":
                texts.extend(block.get("items") or [])
            refs = _collect_refs(*texts)
            if refs:
                block["source_ids"] = refs
        # metric_cards: each metric has its own source_ids
        if btype == "metric_cards":
            for m in block.get("metrics") or []:
                if isinstance(m, dict) and not m.get("source_ids"):
                    refs = _collect_refs(m.get("label"), m.get("value"), m.get("context"))
                    if refs:
                        m["source_ids"] = refs

    for section in payload.get("sections", []):
        for block in section.get("blocks", []):
            _autofill_source_ids(block)

    if isinstance(rail, dict):
        for m in rail.get("quick_stats") or []:
            if isinstance(m, dict):
                if isinstance(m.get("source_ids"), list):
                    m["source_ids"] = _remap_source_ids(m["source_ids"])
                if not m.get("source_ids"):
                    refs = _collect_refs(m.get("label"), m.get("value"), m.get("context"))
                    if refs:
                        m["source_ids"] = refs

    # Third pass: structural cleanup. Charts with no data are a known
    # writer drift — the model declares the chart it wishes existed but
    # leaves series empty. An empty chart renders as a blank box and is
    # worse than no block at all, so we drop them.
    _CHART_TYPES = {
        "line_chart",
        "bar_chart",
        "area_chart",
        "pie_chart",
        "candlestick_chart",
        "waterfall_chart",
        "scatter_plot",
        "heatmap",
        "treemap",
        "combo_chart",
        "stacked_bar_chart",
    }
    for section in payload.get("sections", []):
        kept_blocks: list[dict] = []
        for block in section.get("blocks", []):
            btype = block.get("type")
            if btype in _CHART_TYPES:
                series = block.get("series") or []
                # Treat a chart as empty if it declares no series OR every
                # declared series has no data points. Either way the chart
                # would render blank.
                non_empty = False
                for sr in series:
                    if not isinstance(sr, dict):
                        continue
                    data = sr.get("data") or sr.get("values") or []
                    if any(pt is not None for pt in data):
                        non_empty = True
                        break
                # pie_chart uses a flat slices structure instead of series
                if btype == "pie_chart":
                    slices = block.get("slices") or []
                    non_empty = bool(slices) or non_empty
                if not non_empty:
                    continue  # drop the empty chart
            kept_blocks.append(block)
        section["blocks"] = kept_blocks

    return payload
