"""Wrapper for revision tasks: delegates to run_wrapped_report for
standard persistence + notifications, then re-anchors the source
chat session on successful completion."""

from __future__ import annotations

from openlia_server.services.report_wrapper import run_wrapped_report


async def run_wrapped_revision(
    *,
    runner_coro,
    new_report_id: str,
    source_chat_session_id: str,
    user_id: str,
    db_session_factory,
    presence,
    registry,
) -> None:
    await run_wrapped_report(
        runner_coro=runner_coro,
        report_id=new_report_id,
        user_id=user_id,
        db_session_factory=db_session_factory,
        presence=presence,
        registry=registry,
    )
    # Re-anchor only on success.
    from openlia_server.db.models.content import ChatSession, Report

    with db_session_factory() as session:
        row = session.get(Report, new_report_id)
        if row is None or row.status != "complete":
            return
        chat = session.get(ChatSession, source_chat_session_id)
        if chat is None:
            return
        chat.attached_report_id = new_report_id
        session.commit()
    presence.fanout(
        user_id,
        {
            "type": "chat.attached_report_changed",
            "session_id": source_chat_session_id,
            "new_report_id": new_report_id,
        },
    )
