"""Server-side ``recall_artifacts`` tool implementation (slice 12).

The runner-facing handler is built once at startup (or per-request via
``RefreshingChatRunner``) with two seams injected from above:

* ``db_session_factory`` — opens a fresh ``Session`` per call so the
  tool never reuses a stale session across turns or threads.
* ``provider`` — the user's configured ``EmbeddingProvider``, the same
  instance the rest of the graph subsystem uses. The factory does not
  construct providers itself — see slice-9 wiring decisions.

The compact result shape (``id``, ``subject``, ``tagline``, ``score``)
matches the contract declared in
``openlia.llm.runtime.recall_artifacts``. The full report body is left
behind — the model expands it via the existing repo-read tool only
when it actually needs to.
"""

from __future__ import annotations

from collections.abc import Callable

from openlia.llm.embeddings import EmbeddingProvider
from openlia.llm.runtime.recall_artifacts import (
    RecallArtifactsHandler,
    RecallArtifactsResult,
)
from sqlalchemy.orm import Session

from openlia_server.services.graph_vectors import recall_artifacts as recall_artifacts_svc


class _MissingUserError(RuntimeError):
    """Raised when the runner invokes the handler without a user_id.

    The tool is meaningless without a user binding — every recall is
    scoped to the caller's corpus. Surfacing as an error rather than
    silently returning ``[]`` makes the misconfiguration visible.
    """


def build_recall_artifacts_handler(
    *,
    db_session_factory: Callable[[], Session],
    provider: EmbeddingProvider,
    top_k_default: int = 5,
) -> RecallArtifactsHandler:
    """Wrap ``services.graph_vectors.recall_artifacts`` as an async
    callable the ``ChatRunner`` can invoke directly.

    ``user_id`` is sourced exclusively from the runtime context that
    ``ChatRunner`` threads in — the LLM's tool-call arguments cannot
    influence which user's corpus gets searched (see
    ``dispatch_recall_artifacts``).

    The wrapped service is synchronous SQLAlchemy; we call it directly
    from the async handler because each invocation opens a short-lived
    session and the recall path is in-process (no network). If recall
    grows expensive enough to block the event loop in practice, the
    call can be moved to ``asyncio.to_thread`` without changing this
    contract.
    """
    del top_k_default  # reserved for future plumbing; clamp lives in core

    async def _handler(
        user_id: str | None, query: str, top_k: int
    ) -> list[RecallArtifactsResult]:
        if user_id is None:
            raise _MissingUserError("recall_artifacts requires a bound user context")
        db = db_session_factory()
        try:
            rows = recall_artifacts_svc(
                db,
                user_id=user_id,
                query_text=query,
                provider=provider,
                top_k=top_k,
            )
        finally:
            db.close()
        # Compact projection only — claude-mem pattern: id + subject +
        # tagline + score. The full summary_text and embedding stay out
        # of the model's window; the existing repo-read tool expands a
        # row when the model decides it wants the body.
        return [
            {
                "id": row.artifact_id,
                "subject": row.subject,
                "tagline": row.tagline,
                "score": float(score),
            }
            for row, score in rows
        ]

    return _handler
