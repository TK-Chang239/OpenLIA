"""Persistent cache wrapper for ConnectorAdapter calls.

Wraps any ConnectorAdapter with a CacheStore to avoid redundant upstream
calls. Per-tool cacheability is read from ToolMeta.cacheable; the adapter-
level cacheable flag is informational only.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from openlia.llm.runtime.report_v2.connectors.base import (
    ConnectorAdapter,
    ToolKind,
    ToolMeta,
    ToolResult,
)


@runtime_checkable
class CacheStore(Protocol):
    def get(self, key: str) -> Any | None: ...
    def upsert(self, key: str, result: ToolResult, **meta: Any) -> None: ...


def build_cache_key(adapter_name: str, tool: str, params: dict) -> str:
    """Build a canonical cache key.

    Format: <adapter>:<tool>:<ticker_or_underscore>:<fiscal_period_or_hash>

    When fiscal_period is absent, hash sorted-JSON of params with sha256
    (first 12 chars).
    """
    ticker = params.get("ticker") or params.get("symbol") or "_"
    fiscal_period = params.get("fiscal_period") or params.get("period")

    if fiscal_period:
        period_part = str(fiscal_period)
    else:
        raw = json.dumps(params, sort_keys=True, default=str)
        period_part = hashlib.sha256(raw.encode()).hexdigest()[:12]

    return f"{adapter_name}:{tool}:{ticker}:{period_part}"


class CacheWrappedAdapter:
    """ConnectorAdapter wrapper that caches cacheable tool calls."""

    def __init__(self, inner: ConnectorAdapter, store: CacheStore) -> None:
        self._inner = inner
        self._store = store
        self._tool_meta: dict[str, ToolMeta] | None = None

    @property
    def name(self) -> str:
        return self._inner.name

    @property
    def tool_kind(self) -> ToolKind:
        return self._inner.tool_kind

    @property
    def cacheable(self) -> bool:
        return self._inner.cacheable

    def list_tools(self) -> list[ToolMeta]:
        return self._inner.list_tools()

    def _tool_meta_map(self) -> dict[str, ToolMeta]:
        if self._tool_meta is None:
            self._tool_meta = {m.name: m for m in self._inner.list_tools()}
        return self._tool_meta

    def call(self, tool: str, params: dict, force_refresh: bool = False) -> ToolResult:
        meta_map = self._tool_meta_map()
        tool_meta = meta_map.get(tool)
        is_cacheable = tool_meta is not None and tool_meta.cacheable

        if not is_cacheable:
            return self._inner.call(tool, params)

        key = build_cache_key(self.name, tool, params)

        if not force_refresh:
            hit = self._store.get(key)
            if hit is not None:
                content = getattr(hit, "content_text", None) or getattr(hit, "content", None)
                raw_metadata = getattr(hit, "raw_metadata", None) or getattr(hit, "metadata", {})
                return ToolResult(
                    content=content,
                    metadata=raw_metadata if isinstance(raw_metadata, dict) else {},
                    served_from_cache=True,
                )

        result = self._inner.call(tool, params)
        self._store.upsert(
            key,
            result,
            adapter_name=self.name,
            tool=tool,
            retrieved_at=datetime.now(UTC).isoformat(),
        )
        return ToolResult(
            content=result.content,
            metadata=result.metadata,
            served_from_cache=False,
        )
