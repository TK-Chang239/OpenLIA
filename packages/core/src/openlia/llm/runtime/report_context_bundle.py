"""ReportContextBundle — persisted alongside a generated report so a
later chat session can answer follow-ups without re-fetching from
external APIs.

Storage: gzipped JSON on the filesystem. Default location
``~/.openlia/report_bundles/{report_id}.json.gz`` (caller chooses path).

Size cap: bundles exceeding ``BUNDLE_DEFAULT_MAX_BYTES`` (5 MiB) get the
largest ``payload_refs`` entries dropped until the compressed size fits.
``plan`` and ``section_drafts`` are always kept (they are small and load-
bearing for narrative reconstruction). Dropped keys are recorded in
``generation_meta['bundle_truncated']`` so the omission is observable.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.section_draft import SectionDraft

BUNDLE_DEFAULT_MAX_BYTES = 5 * 1024 * 1024


@dataclass
class ReportContextBundle:
    plan: ReportPlan
    fetched_data: dict[str, Any] = field(default_factory=dict)
    section_drafts: list[SectionDraft] = field(default_factory=list)
    payload_refs: dict[str, dict[str, Any]] = field(default_factory=dict)
    generation_meta: dict[str, Any] = field(default_factory=dict)


def _to_jsonable(bundle: ReportContextBundle) -> dict[str, Any]:
    return {
        "plan": bundle.plan.model_dump(),
        "fetched_data": bundle.fetched_data,
        "section_drafts": [d.model_dump() for d in bundle.section_drafts],
        # Shallow copy so persist_bundle truncation does not mutate the caller's dict.
        "payload_refs": dict(bundle.payload_refs),
        "generation_meta": dict(bundle.generation_meta),
    }


def _from_jsonable(data: dict[str, Any]) -> ReportContextBundle:
    return ReportContextBundle(
        plan=ReportPlan.model_validate(data["plan"]),
        fetched_data=data.get("fetched_data") or {},
        section_drafts=[SectionDraft.model_validate(d) for d in data.get("section_drafts") or []],
        payload_refs=data.get("payload_refs") or {},
        generation_meta=data.get("generation_meta") or {},
    )


def _compressed_size(data: dict[str, Any]) -> int:
    return len(gzip.compress(json.dumps(data, default=str).encode("utf-8")))


def persist_bundle(
    bundle: ReportContextBundle,
    *,
    path: Path,
    max_bytes: int = BUNDLE_DEFAULT_MAX_BYTES,
) -> list[str]:
    """Write ``bundle`` to ``path`` as gzipped JSON.

    If the compressed size exceeds ``max_bytes``, drop the largest
    ``payload_refs`` entries one by one until the bundle fits. Record
    the dropped keys in ``generation_meta['bundle_truncated']``. Returns
    the list of dropped keys (empty if no truncation occurred).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _to_jsonable(bundle)
    truncated: list[str] = []
    # Order payload_refs by approximate serialized size, descending.
    if _compressed_size(data) > max_bytes:
        ref_sizes = sorted(
            (
                (key, len(json.dumps(value, default=str)))
                for key, value in bundle.payload_refs.items()
            ),
            key=lambda x: x[1],
            reverse=True,
        )
        for key, _size in ref_sizes:
            if _compressed_size(data) <= max_bytes:
                break
            if key in data["payload_refs"]:
                del data["payload_refs"][key]
                truncated.append(key)
        data["generation_meta"]["bundle_truncated"] = truncated
    blob = gzip.compress(json.dumps(data, default=str).encode("utf-8"))
    path.write_bytes(blob)
    return truncated


def load_bundle(path: Path) -> ReportContextBundle:
    """Read a bundle from disk. Raises FileNotFoundError if absent."""
    raw = gzip.decompress(path.read_bytes())
    data = json.loads(raw.decode("utf-8"))
    return _from_jsonable(data)
