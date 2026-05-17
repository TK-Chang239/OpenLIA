"""run_wrapped_revision re-anchors the source chat session on success
and fans a notification event; leaves chat unchanged on failure."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportError
from openlia_server.services.revision_wrapper import run_wrapped_revision


class _StubPresence:
    def __init__(self) -> None:
        self.events = []

    def fanout(self, user_id, event):
        self.events.append((user_id, event))


class _StubReport:
    def __init__(self, status="complete"):
        self.status = status


class _StubChat:
    def __init__(self):
        self.attached_report_id = "r_source"


class _StubSession:
    def __init__(self, row, chat):
        self._row = row
        self._chat = chat
        self.committed = False

    def get(self, model, _id):
        # Return chat when looking up ChatSession, row otherwise.
        if "ChatSession" in str(model):
            return self._chat
        return self._row

    def commit(self):
        self.committed = True

    def close(self):
        pass


def _factory(row, chat):
    def f():
        class CM:
            def __enter__(self_inner):
                return _StubSession(row, chat)

            def __exit__(self_inner, *a):
                return False

        return CM()

    return f


@pytest.mark.asyncio
async def test_re_anchors_chat_on_success() -> None:
    row = _StubReport(status="complete")
    chat = _StubChat()
    presence = _StubPresence()

    async def runner():
        yield ReportComplete(report_id="r_new", schema={"cover": {"title": "x"}})

    await run_wrapped_revision(
        runner_coro=runner(),
        new_report_id="r_new",
        source_chat_session_id="sess_test",
        user_id="u_1",
        db_session_factory=_factory(row, chat),
        presence=presence,
        registry=object(),
    )
    assert chat.attached_report_id == "r_new"
    # Event fanned out.
    assert any(e[1]["type"] == "chat.attached_report_changed" for e in presence.events)


@pytest.mark.asyncio
async def test_does_not_re_anchor_on_failure() -> None:
    row = _StubReport(status="failed")
    chat = _StubChat()  # attached_report_id = "r_source"
    presence = _StubPresence()

    async def runner():
        yield ReportError(report_id="r_new", error_class="x", message="y")

    await run_wrapped_revision(
        runner_coro=runner(),
        new_report_id="r_new",
        source_chat_session_id="sess_test",
        user_id="u_1",
        db_session_factory=_factory(row, chat),
        presence=presence,
        registry=object(),
    )
    assert chat.attached_report_id == "r_source"  # unchanged
    assert not any(e[1]["type"] == "chat.attached_report_changed" for e in presence.events)
