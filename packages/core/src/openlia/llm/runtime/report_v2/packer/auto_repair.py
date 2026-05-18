"""Soft fixes applied before declaring a hard fail."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

_CUTOFF = 0.7


@dataclass
class RepairOutcome:
    markdown: str
    fixes_applied: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_FENCE_TAG_RE = re.compile(r"^```([\w:]+)$", re.MULTILINE)
_TAG_SPLITTER = re.compile(r"[_:\s]+")


def _tag_tokens(tag: str) -> frozenset[str]:
    return frozenset(t for t in _TAG_SPLITTER.split(tag.lower()) if t)


def _best_match(tag: str, known_tags: list[str]) -> str | None:
    """Return the best known tag for an unknown tag, or None if below threshold.

    Two-pass:
    1. difflib character similarity (handles minor typos).
    2. Jaccard similarity on word tokens (handles word-reorder across separators).
    """
    # Pass 1: character-level via difflib
    dm = difflib.get_close_matches(tag, known_tags, n=1, cutoff=_CUTOFF)
    if dm:
        return dm[0]

    # Pass 2: token-set Jaccard (handles combo_chart -> chart:combo style swaps)
    tag_tokens = _tag_tokens(tag)
    best_score = 0.0
    best_candidate: str | None = None
    for candidate in known_tags:
        candidate_tokens = _tag_tokens(candidate)
        union = tag_tokens | candidate_tokens
        if not union:
            continue
        score = len(tag_tokens & candidate_tokens) / len(union)
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_score >= _CUTOFF:
        return best_candidate
    return None


def repair_section(markdown: str, *, known_tags: list[str]) -> RepairOutcome:
    out = RepairOutcome(markdown=markdown)
    out = _rename_block_tags(out, known_tags=known_tags)
    return out


def _rename_block_tags(outcome: RepairOutcome, *, known_tags: list[str]) -> RepairOutcome:
    new_md = outcome.markdown
    known = set(known_tags)
    used = set(_FENCE_TAG_RE.findall(new_md))
    for tag in used:
        if tag in known:
            continue
        best = _best_match(tag, known_tags)
        if best:
            new_md = re.sub(rf"^```{re.escape(tag)}$", f"```{best}", new_md, flags=re.MULTILINE)
            outcome.fixes_applied.append(f"rename_block_tag: {tag} -> {best}")
        else:
            outcome.warnings.append(f"unknown_block_tag: {tag}")
    outcome.markdown = new_md
    return outcome
