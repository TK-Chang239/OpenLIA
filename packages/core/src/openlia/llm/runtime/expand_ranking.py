"""Ranking for `request_additional_tools` candidate selection.

Pure function: returns top-K candidates by IDF-weighted token overlap
between the LLM's `reason` and each candidate's name + description.
Category hint is an additive scoring boost, not a hard filter.

Constants:
  SCORE_FLOOR = 0.05         # candidates below this are dropped
  MIN_RESULTS = 3            # soft threshold; caller decides what to do below it
  CATEGORY_BOOST = 0.3       # additive bonus for category match
  NAME_BOOST = 2.0           # multiplier on name-token overlap

No inverted index — linear scan over ~120 tools is sub-ms.

EXPLICIT NON-GOAL: not a JSONPath/embedding/BM25 engine. Keep it simple.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable
from typing import Any

SCORE_FLOOR = 0.05
MIN_RESULTS = 3
CATEGORY_BOOST = 0.3
NAME_BOOST = 2.0
DEFAULT_TOP_K = 8

# Name prefix/suffix noise stripped before tokenization.
_NAME_PREFIXES = ("get_", "fetch_", "list_", "search_", "find_")
_NAME_SUFFIXES = ("_data", "_list", "_history", "_v1", "_v2", "_info")

# Stopwords skipped during tokenization.
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "for",
        "to",
        "in",
        "on",
        "at",
        "by",
        "and",
        "or",
        "is",
        "are",
        "be",
        "with",
        "from",
        "i",
        "me",
        "my",
        "you",
        "need",
        "want",
        "get",
        "show",
        "give",
    }
)


def rank_candidates(
    candidates: list[dict[str, Any]],
    *,
    reason: str,
    category_hint: str | None,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """Return the top-K candidate tools best matching `reason`.

    Candidates are dicts with keys: `name`, `description`, optional `category`.
    Returns a list of the same dicts (subset), or [] if nothing scored above
    the floor. If 1 or 2 candidates are above the floor, returns them anyway
    (caller decides what to do with weak matches). Returns [] only when zero
    candidates are above the floor.
    """
    if top_k <= 0:
        return []
    query_tokens = _tokenize_query(reason)
    if not query_tokens:
        return []

    idf = _idf_for_corpus(candidates)
    scored: list[tuple[float, dict[str, Any]]] = []
    for c in candidates:
        name_text = _strip_name_noise(str(c.get("name", "")))
        desc_text = str(c.get("description", ""))
        name_tokens = _tokenize(name_text)
        desc_tokens = _tokenize(desc_text)
        score = NAME_BOOST * _idf_overlap(query_tokens, name_tokens, idf) + _idf_overlap(
            query_tokens, desc_tokens, idf
        )
        if category_hint and c.get("category") == category_hint:
            score += CATEGORY_BOOST
        scored.append((score, c))

    above_floor = [(s, c) for s, c in scored if s >= SCORE_FLOOR]
    if len(above_floor) == 0:
        return []
    # Deterministic tiebreaker: prefer higher score, then alphabetical name.
    above_floor.sort(key=lambda x: (-x[0], str(x[1].get("name", ""))))
    return [c for _, c in above_floor[:top_k]]


def _tokenize_query(text: str) -> list[str]:
    """Same as _tokenize but kept as a named entry point for readability."""
    return _tokenize(text)


def _tokenize(text: str) -> list[str]:
    """Lowercase + split on non-alphanumeric. Drop stopwords + len < 2."""
    if not text:
        return []
    parts = re.split(r"[^A-Za-z0-9]+", text.lower())
    return [p for p in parts if len(p) >= 2 and p not in _STOPWORDS]


def _strip_name_noise(name: str) -> str:
    """Remove conventional get_/fetch_/list_/etc. and _data/_list/_v2/etc.

    Applied only to the `name` field, never to descriptions. The point is to
    surface the meaningful tokens — `get_company_news` -> `company_news`.
    Internal underscores are preserved; the tokenizer handles them later.
    """
    lowered = name.lower()
    for p in _NAME_PREFIXES:
        if lowered.startswith(p):
            lowered = lowered[len(p) :]
            break
    for s in _NAME_SUFFIXES:
        if lowered.endswith(s):
            lowered = lowered[: -len(s)]
            break
    return lowered


def _idf_for_corpus(candidates: list[dict[str, Any]]) -> dict[str, float]:
    """Compute IDF over the candidate corpus.

    For each unique token, IDF = log((N + 1) / (df + 1)) + 1 (smooth).
    Tokens that appear in many candidates get lower weight.
    """
    n = len(candidates)
    if n == 0:
        return {}
    df: dict[str, int] = {}
    for c in candidates:
        name_text = _strip_name_noise(str(c.get("name", "")))
        desc_text = str(c.get("description", ""))
        seen: set[str] = set()
        for tok in _tokenize(name_text):
            seen.add(tok)
        for tok in _tokenize(desc_text):
            seen.add(tok)
        for tok in seen:
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log((n + 1) / (count + 1)) + 1.0 for tok, count in df.items()}


def _idf_overlap(
    query: Iterable[str],
    candidate_tokens: list[str],
    idf: dict[str, float],
) -> float:
    """Sum of IDF weights for tokens appearing in both query and candidate."""
    cand_set = set(candidate_tokens)
    return sum(idf.get(t, 1.0) for t in query if t in cand_set)
