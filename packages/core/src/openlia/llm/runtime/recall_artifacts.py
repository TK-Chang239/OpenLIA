"""Tool surface for cross-session report recall (graph memory slice 12).

Declared in core so the runner can reference the schema and handler
protocol without importing server code. The production implementation
lives in ``openlia_server.runtime_tools.recall_artifacts`` and is
injected into ``ChatRunner`` at construction time.

Contract:

  * ``RECALL_ARTIFACTS_SCHEMA`` is the tool definition surfaced to the
    LLM. Args: ``query: str`` (natural language) and ``top_k: int``
    (max results, clamped server-side).
  * ``RecallArtifactsHandler`` is the async callable the runner invokes.
    The runner threads ``user_id`` from its own request context — the
    LLM cannot supply it, otherwise the tool would be a tenant-isolation
    hole.
  * ``dispatch_recall_artifacts`` is a thin wrapper that turns a handler
    call into a ``ToolCallResult`` with a compact, model-friendly
    payload. Empty results return ``{"results": []}`` cleanly.

The compact index pattern (id + subject + tagline + score, nothing
else) follows claude-mem: keep the recall payload tiny so the model
spends its budget on the full report only when it actually needs to
expand a row via the existing repo-read tool.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from openlia.llm.runtime.tools import ToolCallResult
from openlia.llm.types import ToolSchema

# Hard upper bound on ``top_k`` the LLM may request. Prevents the model
# from asking for the whole corpus in one call.
MAX_TOP_K = 20

RECALL_ARTIFACTS_TOOL_NAME = "recall_artifacts"

RECALL_ARTIFACTS_SCHEMA = ToolSchema(
    name=RECALL_ARTIFACTS_TOOL_NAME,
    description=(
        "Search the user's saved reports and notes by semantic similarity. "
        "Returns a compact index of up to top_k matches with id, subject, "
        "tagline, and a relevance score. Call with a natural-language query "
        "describing what you want to find. Returns nothing if no relevant "
        "artifacts are stored."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language description of what to find.",
            },
            "top_k": {
                "type": "integer",
                "description": (
                    f"Maximum number of matches to return (1..{MAX_TOP_K}). Defaults to 5."
                ),
                "minimum": 1,
                "maximum": MAX_TOP_K,
                "default": 5,
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
)


# Result row carried in the payload back to the LLM. Intentionally
# tiny — the model expands via the existing repo-read tool when it
# needs the full report body.
RecallArtifactsResult = dict[str, str | float | None]


# Handler signature: (user_id, query, top_k) -> list of compact rows.
# Implementations are server-side and must enforce per-user scoping.
RecallArtifactsHandler = Callable[
    [str | None, str, int],
    Awaitable[list[RecallArtifactsResult]],
]


def _clamp_top_k(raw: object) -> int:
    """Coerce LLM-supplied ``top_k`` into the [1, MAX_TOP_K] range.

    The model is told the bounds in the schema, but adapters strip
    ``default`` and ``minimum``/``maximum`` from some providers — clamp
    defensively here. Non-integers (str, float, None) snap to the
    default of 5.
    """
    if isinstance(raw, bool):  # bool is an int subclass; reject explicitly
        return 5
    if isinstance(raw, int):
        return max(1, min(MAX_TOP_K, raw))
    if isinstance(raw, float) and raw.is_integer():
        return max(1, min(MAX_TOP_K, int(raw)))
    return 5


async def dispatch_recall_artifacts(
    handler: RecallArtifactsHandler,
    *,
    user_id: str | None,
    arguments: dict[str, object],
    call_id: str,
) -> ToolCallResult:
    """Invoke ``handler`` with sanitized args and pack the result.

    Tenant isolation: ``user_id`` is taken from the runtime context
    only; any ``user_id`` field in ``arguments`` is ignored. The model
    cannot ask to search another user's corpus.

    Empty corpora return ``{"results": []}`` (ok=True) so the model
    sees a clean "nothing matched" signal rather than an error.
    """
    raw_query = arguments.get("query")
    if not isinstance(raw_query, str) or not raw_query.strip():
        return ToolCallResult(
            call_id=call_id,
            ok=False,
            summary="recall_artifacts requires a non-empty 'query' string.",
            payload={"error": "query must be a non-empty string"},
        )
    top_k = _clamp_top_k(arguments.get("top_k", 5))
    query = raw_query.strip()
    try:
        rows = await handler(user_id, query, top_k)
    except Exception as exc:
        return ToolCallResult(
            call_id=call_id,
            ok=False,
            summary=f"recall_artifacts failed: {exc!s}",
            payload={"error": str(exc)},
        )
    return ToolCallResult(
        call_id=call_id,
        ok=True,
        summary=(
            f"Recalled {len(rows)} artifact(s) for: {query[:60]}"
            if rows
            else f"No saved artifacts matched: {query[:60]}"
        ),
        payload={"results": list(rows)},
    )
