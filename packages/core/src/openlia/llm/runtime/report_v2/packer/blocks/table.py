from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.packer.blocks.registry import register_block
from openlia.reports.schema import TableBlock, TableHeader


def _slug(label: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in label.strip().lower()).strip("_")


def _normalize_headers(raw: list[Any]) -> list[TableHeader]:
    """Accept either list[dict] with {key,label,...} or list[str] of labels."""
    out: list[TableHeader] = []
    for h in raw:
        if isinstance(h, str):
            out.append(TableHeader(key=_slug(h) or "col", label=h))
        elif isinstance(h, dict):
            h = dict(h)
            label = h.get("label") or h.get("name") or h.get("title") or h.get("key") or "Column"
            key = h.get("key") or _slug(label)
            h["label"] = label
            h["key"] = key
            out.append(TableHeader(**h))
        else:
            raise ValueError(f"unsupported header entry: {h!r}")
    return out


def _infer_headers_from_rows(rows: list[dict[str, Any]]) -> list[TableHeader]:
    seen: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for k in row:
            if k not in seen:
                seen.append(k)
    return [TableHeader(key=k, label=k.replace("_", " ").title()) for k in seen]


def _normalize_rows(rows: list[Any], headers: list[TableHeader]) -> list[dict[str, Any]]:
    """Accept list[dict] (canonical) or list[list] (positional, zipped with headers)."""
    out: list[dict[str, Any]] = []
    keys = [h.key for h in headers]
    for row in rows:
        if isinstance(row, dict):
            out.append(row)
        elif isinstance(row, list):
            # Zip positional row with header keys; pad/truncate to header length.
            d: dict[str, Any] = {}
            for i, k in enumerate(keys):
                d[k] = row[i] if i < len(row) else ""
            out.append(d)
        else:
            raise ValueError(f"unsupported row type: {type(row).__name__}")
    return out


def _assemble(*, data: dict[str, Any], citation_ids: list[int], manifest_resolver) -> TableBlock:
    # Accept "columns" or "cols" as alias for "headers".
    raw_headers = data.get("headers")
    if raw_headers is None:
        for alias in ("columns", "cols", "fields"):
            if alias in data:
                raw_headers = data[alias]
                break
    raw_rows = data.get("rows", [])
    # Header inference only works for list[dict] rows.
    dict_rows = [r for r in raw_rows if isinstance(r, dict)]
    if raw_headers is None and dict_rows:
        headers = _infer_headers_from_rows(dict_rows)
    elif raw_headers is None:
        raise KeyError("headers")
    else:
        headers = _normalize_headers(list(raw_headers))

    rows = _normalize_rows(list(raw_rows), headers)
    sources = list(data.get("sources", []))
    title = data.get("title") or "Table"
    return TableBlock(
        type="table",
        title=title,
        headers=headers,
        rows=rows,
        source_ids=manifest_resolver(sources or citation_ids),
    )


register_block(
    "table",
    assembler=_assemble,
    schema={
        "type": "object",
        "required": ["title", "headers", "rows"],
    },
)
