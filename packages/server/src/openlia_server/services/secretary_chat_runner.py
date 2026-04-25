"""Secretary chat-runner adapter.

Wraps the shared `RefreshingChatRunner` (Phase 5) for the Secretary HTTP
route. Handles a thin extra responsibility on top of the generic chat
runner: when an LLM tool-call result references `save_report_to_repo`
(NEW-13-09), the route's stream loop performs the side-effect via
`services.repo.save_to_repo` and emits a `chat.tool_call.result` event
with the new repo-item id.

The actual chat loop continues to live in `openlia.llm.runtime.chat`;
this file only adds a small post-processing helper used by the route
when persisting tool-call effects.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session as DBSession

from openlia_server.services import repo as repo_svc


class SaveReportToRepoError(RuntimeError):
    pass


def handle_save_report_to_repo(
    db: DBSession,
    *,
    user_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Execute the `save_report_to_repo` tool-call.

    The tool args come from the LLM. We trust nothing: every value is
    coerced and the report ownership is enforced by `services.repo`.
    """
    report_id = arguments.get("report_id")
    if not isinstance(report_id, str) or not report_id:
        raise SaveReportToRepoError("report_id must be a non-empty string")
    try:
        item = repo_svc.save_to_repo(db, user_id=user_id, report_id=report_id)
    except LookupError as exc:
        raise SaveReportToRepoError(str(exc)) from exc
    return {"ok": True, "repo_item_id": item.id}


def build_secretary_persistence_handlers(
    *,
    db_session_factory: Callable[[], DBSession],
    user_id: str,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """Return the tool-name → handler map that the route applies on
    successful tool calls. Each handler opens its own DB session so it
    cannot leak the request session and so commit/rollback is local.
    """

    def _save(args: dict[str, Any]) -> dict[str, Any]:
        db = db_session_factory()
        try:
            return handle_save_report_to_repo(db, user_id=user_id, arguments=args)
        finally:
            db.close()

    return {"save_report_to_repo": _save}
