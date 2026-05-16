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

    def _rewrite(text: str) -> str:
        def _sub(m: re.Match[str]) -> str:
            body = m.group(1)
            parsed = _parse_provider(body) or _parse_web_tuple(body) or _parse_malformed(body)
            cid = _intern(parsed)
            return f"[{cid}]"

        return _BRACKET.sub(_sub, text)

    for section in payload.get("sections", []):
        for block in section.get("blocks", []):
            if block.get("type") == "text":
                block["content"] = _rewrite(block["content"])

    payload["citations"] = citations
    return payload
