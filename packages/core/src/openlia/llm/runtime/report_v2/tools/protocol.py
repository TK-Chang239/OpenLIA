"""ToolHandler protocol + ToolResult envelope.

Every callable tool — helper, connector, uploaded-template handler — implements
`ToolHandler`. Results carry citation metadata so the report's citation pool can
absorb them uniformly across backends.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

Complexity = Literal["simple", "complex"]


class ToolResult(BaseModel):
    """Envelope returned by every `ToolHandler.execute` call.

    The `citations` field is non-optional and append-only-mutable: callers
    propagate it into the manifest's citation pool at tool-result time. For a
    helper that wraps a Fact, citations are the union of `source_facts`'
    citation entries. For a future web_search tool, citations are the fetched
    URL + retrieved-at timestamp. The downstream citation rendering doesn't
    care which.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    value: Any
    citations: list[Any] = []
    source_facts: list[str] = []
    metadata: dict[str, Any] = {}


@runtime_checkable
class ToolHandler(Protocol):
    """A callable tool the runtime can expose to the LLM."""

    name: str
    summary: str  # one-line description; used in manifest + tool description
    use_when: str  # contrast-set discriminator (PR 8.0 hint)
    complexity: Complexity
    input_schema: dict[str, Any]  # JSON schema for arguments
    doc_path: str | None  # populated only for `complexity="complex"` helpers

    async def execute(self, args: dict[str, Any]) -> ToolResult: ...


# ---------------------------------------------------------------------------
# A concrete dataclass-style ToolHandler. Used by the helpers adapter and by
# tests. Not the only shape — anything matching the Protocol works.
# ---------------------------------------------------------------------------


class StaticToolHandler:
    """ToolHandler whose `execute` delegates to a wrapped callable."""

    def __init__(
        self,
        *,
        name: str,
        summary: str,
        use_when: str,
        complexity: Complexity,
        input_schema: dict[str, Any],
        executor: Callable[[dict[str, Any]], Awaitable[ToolResult]],
        doc_path: str | None = None,
    ) -> None:
        self.name = name
        self.summary = summary
        self.use_when = use_when
        self.complexity = complexity
        self.input_schema = input_schema
        self.doc_path = doc_path
        self._executor = executor

    async def execute(self, args: dict[str, Any]) -> ToolResult:
        return await self._executor(args)
