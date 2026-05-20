"""Industry-mode overlay loader and deep-merge (WS9).

The base facts framework lives at
`openlia.llm.runtime.report_v2.frameworks/stock_initiation.facts.json`.
Industry overlays live at
`openlia.reports.frameworks.report_mode_overrides/stock_initiation.{mode}.json`
and contain sparse keys merged onto the base via `deep_merge`:

  - scalar leaves: right (overlay) wins
  - list leaves: extension (concat unique-preserving-order)
  - dict leaves: recurse

Overlay schema (sparse keys, all optional):
  - report_mode_label: str
  - cover_instructions_override: str
  - facts: dict[section_id, list[str]]      # per-section fact-name extensions
  - section_emphasis: dict[section_id, str] # appended to base brief
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, Literal

ReportMode = Literal["generic", "saas", "semis", "distressed"]


def deep_merge(base: Any, overlay: Any) -> Any:
    """Right-overrides-left at scalar leaves; list extension at list leaves;
    dict recurse at dict leaves. `overlay` of None returns `base` unchanged.

    Lists merge by extension preserving order; duplicates are de-duplicated
    while keeping the first occurrence (base entries come first, overlay
    entries append). This matches the WS9 spec for `consumer` fact lists.
    """
    if overlay is None:
        return base
    if isinstance(base, dict) and isinstance(overlay, dict):
        out: dict[str, Any] = {}
        for k, v in base.items():
            if k in overlay:
                out[k] = deep_merge(v, overlay[k])
            else:
                out[k] = v
        for k, v in overlay.items():
            if k not in base:
                out[k] = v
        return out
    if isinstance(base, list) and isinstance(overlay, list):
        seen: set[Any] = set()
        out_list: list[Any] = []
        for item in (*base, *overlay):
            # Use a stable key for set membership when possible; fall back to
            # appending unhashable items unconditionally.
            try:
                key = item
                if key in seen:
                    continue
                seen.add(key)
            except TypeError:
                out_list.append(item)
                continue
            out_list.append(item)
        return out_list
    # Scalar or type-mismatch: overlay wins.
    return overlay


def load_overlay(mode: ReportMode) -> dict[str, Any]:
    """Load the overlay JSON for `mode`. Returns {} for the empty generic case."""
    path = (
        resources.files("openlia.reports.frameworks.report_mode_overrides")
        / f"stock_initiation.{mode}.json"
    )
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"overlay {mode!r} root must be a JSON object")
    return data


def apply_facts_overlay(
    framework: dict[str, list[str]],
    overlay: dict[str, Any],
) -> dict[str, list[str]]:
    """Apply an overlay's `facts` block onto the base facts framework.

    Base framework shape: {section_id: [fact_name, ...]}.
    Overlay `facts` shape: {section_id: [fact_name, ...]}.
    Returns a new dict; does not mutate inputs."""
    facts_overlay = overlay.get("facts") or {}
    if not isinstance(facts_overlay, dict):
        raise ValueError("overlay 'facts' must be a mapping")
    merged = deep_merge(framework, facts_overlay)
    # deep_merge of dict[str, list[str]] preserves the right shape.
    return merged  # type: ignore[no-any-return]


def overlay_section_emphasis(overlay: dict[str, Any]) -> dict[str, str]:
    """Pull the per-section emphasis strings appended to the base brief.

    Returns {} when the overlay omits the key. The runner concatenates the
    emphasis string onto the base section brief separated by a blank line."""
    val = overlay.get("section_emphasis")
    if val is None:
        return {}
    if not isinstance(val, dict):
        raise ValueError("overlay 'section_emphasis' must be a mapping")
    out: dict[str, str] = {}
    for k, v in val.items():
        if not isinstance(v, str):
            raise ValueError(f"section_emphasis[{k!r}] must be a string")
        out[k] = v
    return out


def report_mode_label(overlay: dict[str, Any]) -> str | None:
    """Return the human-readable label from the overlay (e.g. for the cover)."""
    val = overlay.get("report_mode_label")
    return val if isinstance(val, str) else None
