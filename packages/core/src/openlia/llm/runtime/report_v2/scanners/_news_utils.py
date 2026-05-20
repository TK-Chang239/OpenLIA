"""Shared helpers for news-entry scanning (used by WS3 Part A + Part B).

The material-events scanner (Part B) and the catalyst-pack scanner (Part A)
both operate over manifest entries that carry news / EDGAR / press-release
payloads. The helpers below centralise the parsing and detection primitives
so each scanner only contributes its own taxonomy/regexes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from openlia.llm.runtime.report_v2.types import ManifestEntry


def parse_date(value: Any) -> date | None:
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


def iter_news_articles(entry: ManifestEntry) -> list[dict[str, Any]]:
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


def is_news_entry(entry: ManifestEntry) -> bool:
    """Heuristic — entry identifier or provider implies news content."""
    ident = (entry.identifier or "").lower()
    return (
        "news" in ident or "financial_news" in ident or entry.provider.lower() in {"news", "edgar"}
    )


def article_text(article: dict[str, Any]) -> str:
    """Concatenate the text fields the scanners read over (title + body)."""
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


def article_title(article: dict[str, Any]) -> str | None:
    """Return a non-empty title or headline string, if present."""
    for key in ("title", "headline"):
        v = article.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def article_body(article: dict[str, Any]) -> str | None:
    """Return a non-empty body / content / summary string, if present."""
    for key in ("content", "body", "summary", "description"):
        v = article.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def article_url(article: dict[str, Any]) -> str | None:
    """Return a link / URL string from the article payload, if present."""
    for key in ("link", "url", "source_url"):
        v = article.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def article_date(article: dict[str, Any]) -> date | None:
    """Return the article's publication date as a `date`, or None."""
    return parse_date(article.get("date") or article.get("published_at"))


def name_present(text: str, names: list[str]) -> bool:
    """Case-insensitive substring match on any of the supplied identifiers."""
    if not names:
        return False
    low = text.lower()
    return any(name.lower() in low for name in names if name)
