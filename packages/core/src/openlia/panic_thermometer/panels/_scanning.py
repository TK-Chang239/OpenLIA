"""Shared news-scanning helpers for the keyword-driven PT panels.

The Fed-language and diplomacy panels detect sentiment by scanning recent
news. Two precision rules live here so both panels share them:

- **word-boundary matching** — ``re.search`` with ``\\b`` so a keyword like
  ``patient`` does not match ``impatient`` and ``strike`` does not match
  substrings of unrelated words.
- **corroboration** is left to the caller: these helpers return *every*
  matching article so a panel can require N distinct matches before treating a
  category as a real signal, instead of flipping on a single stray mention.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any


def article_text(article: dict[str, Any]) -> str:
    """Headline + summary, the text a keyword scan runs over."""
    return f"{article.get('headline', '')} {article.get('summary', '')}"


def keyword_hit(text: str, keywords: Sequence[str]) -> str | None:
    """Return the first whole-word keyword present in ``text`` (case-insensitive)."""
    low = text.lower()
    for kw in keywords:
        if not kw:
            continue
        if re.search(rf"\b{re.escape(kw.lower())}\b", low):
            return kw
    return None


def matching_articles(
    articles: Sequence[dict[str, Any]], keywords: Sequence[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Return ``(matched_keyword, article)`` for every article whose text matches."""
    out: list[tuple[str, dict[str, Any]]] = []
    for article in articles:
        hit = keyword_hit(article_text(article), keywords)
        if hit:
            out.append((hit, article))
    return out
