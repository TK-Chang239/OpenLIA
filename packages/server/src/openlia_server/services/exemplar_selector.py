"""Deterministic exemplar selector for fix-chats.

Pure-Python regex/keyword classifier. Inspects the user's latest chat
message and returns the names of exemplar files that should be
conditionally injected into the system prompt.

No LLM call, no DB. Same call-site pattern as
``services.graph_retrieval.retrieve_memory_block``: near-zero per-turn
cost when nothing matches.

Categories and their triggers:

    snapshot       — "snapshot", "tape", "movers", "what's the market
                     doing", "what's leading / lagging", "premarket",
                     "afterhours".
    single_stock   — ticker mentions in stock-context phrasing
                     ("thoughts on $X", "read on X", "view on X",
                     "what do you think about $X", or "$TICKER" with
                     the dollar sigil).
    continuation   — "reformat", "redo", "do that", "expand", "tighten",
                     "shorten", "same thing for", "make it a
                     {snapshot,table,list,shorter,longer}".

Always-on general baseline is rendered unconditionally by Secretary's
system prompt (see ``prompts/shared/exemplars/general.yaml.j2``); the
selector returns only the *conditional* set.
"""

from __future__ import annotations

import re
from typing import Final

# Canonical render order. Keeps prompt-cache prefixes stable across
# requests that match the same set.
_CANONICAL_ORDER: Final[tuple[str, ...]] = ("snapshot", "single_stock", "continuation")


def _compile(*patterns: str) -> list[re.Pattern[str]]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_SNAPSHOT_PATTERNS: Final[list[re.Pattern[str]]] = _compile(
    r"\bmarket\s+snapshot\b",
    r"\bsnapshot\b",
    r"\bshow\s+me\s+the\s+tape\b",
    r"\btape\b(?!\s*recorder)",
    r"\bmovers\b",
    r"\bwhat'?s\s+(?:the\s+)?market\s+doing\b",
    r"\bwhat'?s\s+leading\b",
    r"\bwhat'?s\s+lagging\b",
    r"\bpremarket\b",
    r"\bafter[-\s]?hours\b",
)

# Stock-context phrasing requires a cue word ("thoughts on", "read on",
# "view on", "what do you think about") or the explicit "$TICKER" sigil.
# This avoids false-positives on plain uppercase words like "ETF", "CPI",
# "IT", "USD", which appear in everyday market questions.
_STOCK_CUE = r"(?:thoughts?|read|view|opinion|take|what\s+do\s+you\s+think)\s+(?:on|about|of)"
_TICKER_BARE = r"[A-Z]{1,5}"
_TICKER_WITH_SIGIL = r"\$" + _TICKER_BARE

_SINGLE_STOCK_PATTERNS: Final[list[re.Pattern[str]]] = _compile(
    rf"\b{_STOCK_CUE}\s+\$?{_TICKER_BARE}\b",
    # "$TICKER" anywhere — even without a cue word — is intentional;
    # users routinely shorthand "$NVDA?" as the whole message.
    rf"{_TICKER_WITH_SIGIL}\b",
)

_CONTINUATION_PATTERNS: Final[list[re.Pattern[str]]] = _compile(
    r"\breformat\b",
    r"\bredo\b",
    r"\bdo\s+(?:that|it)\s+again\b",
    r"\bdo\s+that\b",
    r"\bsame\s+thing\s+for\b",
    r"\bexpand\s+(?:on\s+)?(?:this|that|it)\b",
    r"\btighten\s+(?:this|that|it)?\b",
    r"\bshorten\s+(?:this|that|it)?\b",
    r"\bmake\s+it\s+(?:a\s+)?(?:snapshot|table|list|shorter|longer)\b",
)

_CATEGORY_PATTERNS: Final[dict[str, list[re.Pattern[str]]]] = {
    "snapshot": _SNAPSHOT_PATTERNS,
    "single_stock": _SINGLE_STOCK_PATTERNS,
    "continuation": _CONTINUATION_PATTERNS,
}


def select_exemplars(message: str) -> list[str]:
    """Return the canonical-ordered list of exemplar names matched by `message`.

    Empty list when nothing matches. The always-on general exemplar is
    rendered unconditionally and is not included in the return value.
    """
    if not message:
        return []
    matched = {
        name
        for name, patterns in _CATEGORY_PATTERNS.items()
        if any(p.search(message) for p in patterns)
    }
    return [name for name in _CANONICAL_ORDER if name in matched]
