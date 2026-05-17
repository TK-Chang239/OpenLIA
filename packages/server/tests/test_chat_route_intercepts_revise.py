# packages/server/tests/test_chat_route_intercepts_revise.py
"""When the chat LLM emits a revise_report tool call, the chat route
must intercept it (not pass to ToolDispatcher.dispatch). Instead the
route POSTs internally to /reports/{source}/revise and returns a
synthetic tool result to the model."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToolCallResult, ChatToolCallStart
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.report_context_bundle import ReportContextBundle, persist_bundle
from openlia.llm.runtime.section_draft import SectionDraft


def _write_bundle(bundle_dir: Path, report_id: str) -> None:
    plan = ReportPlan.model_validate(
        {
            "company_thesis": "thesis",
            "cross_section_themes": ["t1", "t2"],
            "sections": [
                {
                    "section_id": "company_overview",
                    "title": "Overview",
                    "narrative_goal": "g",
                    "key_questions": ["q1", "q2", "q3"],
                    "target_depth": "standard",
                    "word_budget": 100,
                    "data_paths": [],
                    "cross_refs": [],
                }
            ],
        }
    )
    draft = SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": [{"type": "text", "content": "Body."}],
            "citations_used": [],
            "word_count": 1,
            "open_questions": [],
        }
    )
    bundle = ReportContextBundle(
        plan=plan,
        fetched_data={},
        section_drafts=[draft],
        payload_refs={},
        generation_meta={},
    )
    persist_bundle(bundle, path=bundle_dir / f"{report_id}.json.gz")


class _ReviseToolChatRunner:
    """Fake ChatRunner that emits a single revise_report tool call then stops."""

    def __init__(self) -> None:
        self.call_id = f"call_{uuid.uuid4().hex[:8]}"
        self.captured: dict[str, Any] = {}

    async def run(  # type: ignore[return]
        self, *, department_id: str, user_id: str | None, messages, **kwargs
    ) -> AsyncIterator:
        self.captured["department_id"] = department_id
        self.captured["user_id"] = user_id
        msg_id = f"m_{uuid.uuid4().hex[:8]}"
        yield ChatStart(message_id=msg_id)
        yield ChatToolCallStart(
            message_id=msg_id,
            call_id=self.call_id,
            tool_name="revise_report",
            args_preview='{"revision_brief":"fix it"}',
        )
        yield ChatToolCallResult(
            message_id=msg_id,
            call_id=self.call_id,
            ok=True,
            summary="revision_started",
        )
        yield ChatDone(message_id=msg_id, stop_reason="tool_use")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _bundle_dir(tmp_path):
    d = tmp_path / "bundles"
    d.mkdir()
    return d


@pytest.fixture
def _personal_app(db_session, monkeypatch, _bundle_dir):
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User

    user = User(
        id="local",
        email="local@openlia.local",
        display_name="Local",
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    monkeypatch.setenv("OPENLIA_REPORT_BUNDLE_DIR", str(_bundle_dir))
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")
    return create_app(db_session_factory=session_mod.SessionLocal)


@pytest.fixture
def test_client(_personal_app) -> TestClient:
    with TestClient(_personal_app) as c:
        yield c


def _seed_report(db_session) -> Any:
    from openlia_server.db.models.content import Report

    report_id = f"r_{uuid.uuid4().hex[:12]}"
    r = Report(
        id=report_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Source Report",
        content_markdown="# Source",
        content_structured={"cover": {"title": "Source"}, "sections": []},
        model_ref="gpt-4",
        status="complete",
    )
    db_session.add(r)
    db_session.commit()
    return r


def _seed_session(db_session, report_id: str) -> Any:
    from openlia_server.db.models.content import ChatSession

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Bound chat",
        is_pinned=False,
        is_archived=False,
        attached_report_id=report_id,
    )
    db_session.add(sess)
    db_session.commit()
    return sess


@pytest.fixture
def seeded_bound_chat_with_revise_tool_call(db_session, _bundle_dir):
    """A chat session bound to a report; the fake runner emits revise_report.
    A valid bundle is written so the pre-flight check passes."""
    report = _seed_report(db_session)
    _write_bundle(_bundle_dir, report.id)
    return _seed_session(db_session, report.id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_revise_report_tool_call_does_not_hit_tool_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_bound_chat_with_revise_tool_call,
) -> None:
    """Test harness seeds a chat session bound to a report with a fake
    LLM provider that emits a revise_report tool call on the next
    message. The chat route should intercept it."""
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")

    runner = _ReviseToolChatRunner()
    test_client.app.state.chat_runner_factory = lambda: runner

    session_id = seeded_bound_chat_with_revise_tool_call.id
    resp = test_client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"content": "Save this as a final version please"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # The response includes a marker that revision was started.
    assert body.get("revision_started") is True
    assert "new_report_id" in body


def test_intercept_only_when_flag_on(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_bound_chat_with_revise_tool_call,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)

    runner = _ReviseToolChatRunner()
    test_client.app.state.chat_runner_factory = lambda: runner

    session_id = seeded_bound_chat_with_revise_tool_call.id
    resp = test_client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"content": "Save this as a final version please"},
    )
    # When flag is off, revise_report shouldn't be in the tool list to
    # begin with — but if the LLM emits it anyway, it falls through to
    # the standard "unknown tool" path.
    assert resp.json().get("revision_started") is not True
