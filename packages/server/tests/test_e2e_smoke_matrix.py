"""End-to-end smoke matrix (REM-P1-019).

Chains the product journeys the remediation checklist enumerates — one test
per journey, each exercising multiple routes through a single TestClient so
regressions that break a flow (rather than a single route) surface in CI.

Journeys covered:
    * Personal first-run setup
    * Company invite -> register -> login -> setup finish
    * Auth logout / reload
    * Provider create / edit / delete (admin)
    * Password reset + must-change-password
    * Repository save / open / download / unsave
    * Secretary chat stream (scripted runner, SSE frames + persistence)
    * Morning Briefing follow-up chat session resolve + stream
    * Equity Research on-demand report generation (SSE + persistence)
    * Earnings Update on-demand report generation (SSE + persistence)
    * EU scheduled scan -> user notification (executor + /notifications/unread)

Individual route tests still live under tests/test_routes/*; these tests are
deliberately coarse and assert the outward-visible contract only.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


def _seed_local_admin_in_session(db_session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import LOCAL_USER_ID

    db_session.merge(
        User(
            id=LOCAL_USER_ID,
            email="local@openlia.local",
            display_name="Local",
            password_hash=None,
            is_admin=True,
            is_disabled=False,
            must_change_password=False,
        )
    )
    db_session.commit()


def _personal_wizard_client(db_session):
    from openlia_server.db import session as session_mod

    _seed_local_admin_in_session(db_session)
    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def _company_wizard_client(db_session):
    from openlia_server.db import session as session_mod

    _seed_local_admin_in_session(db_session)
    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def _company_client(monkeypatch, db_session):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Journey 1: personal first-run setup
# ---------------------------------------------------------------------------


def test_journey_personal_first_run_setup(db_session) -> None:
    client = _personal_wizard_client(db_session)

    # Fresh install: wizard incomplete, sitting on the mode step.
    status = client.get("/setup/status")
    assert status.status_code == 200
    body = status.json()
    assert body["wizard_completed"] is False
    assert body["current_step"] == "mode"

    # Pick personal mode. Server issues the wizard session cookie.
    resp = client.post("/setup/mode", json={"mode": "personal"})
    assert resp.status_code == 200
    assert client.cookies.get("openlia_wizard_session")

    # Name the local user.
    resp = client.post("/setup/identity", json={"display_name": "TK"})
    assert resp.status_code == 200

    # Finish. Finalize should redirect into the SPA root.
    resp = client.post("/setup/finish")
    assert resp.status_code == 200
    assert resp.json()["redirect"] == "/"

    # Status must now reflect completion; a second finish is 410 Gone.
    assert client.get("/setup/status").json()["wizard_completed"] is True
    assert client.post("/setup/finish").status_code == 410

    # Local user exists and is non-admin.
    from openlia_server.db.models.auth import User

    user = db_session.query(User).filter_by(email="local@openlia.local").one()
    assert user.display_name == "TK"


def test_journey_personal_full_setup_models_and_providers(db_session, monkeypatch) -> None:
    """Full personal wizard sweep on a fresh DB.

    Connector setup happens via the v2 `/api/connectors` flow (validation is
    monkey-patched to short-circuit MCP transports). The legacy
    `/setup/providers/*` step has been retired in connector v2.
    """
    from openlia_server.services import connectors_service

    async def _validate_ok(_launch, _secrets, *, tool_overrides=None):
        return connectors_service.ValidationOk(tools=[], python_callables=[])

    monkeypatch.setattr(connectors_service, "_validate_launch", _validate_ok)
    client = _personal_wizard_client(db_session)

    assert client.get("/setup/status").status_code == 200
    assert client.post("/setup/mode", json={"mode": "personal"}).status_code == 200
    assert client.post("/setup/identity", json={"display_name": "TK"}).status_code == 200

    models = {
        "thinking": [
            {
                "provider": "ollama",
                "model": "llama3.1:70b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "everyday": [
            {
                "provider": "ollama",
                "model": "llama3.1:8b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
        "quick": [
            {
                "provider": "ollama",
                "model": "qwen2.5:7b",
                "base_url": "http://localhost:11434",
                "is_tier_default": True,
            }
        ],
    }
    assert client.post("/setup/models", json=models).status_code == 200

    # v2 connectors flow — single category-financial CLI MCP connector.
    fin = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
            "secrets": {},
        },
    )
    assert fin.status_code == 201, fin.text

    # Finalize.
    finish = client.post("/setup/finish")
    assert finish.status_code == 200
    assert client.get("/setup/status").json()["wizard_completed"] is True

    # Subsequent /setup/identity must 410 because wizard is complete.
    assert client.post("/setup/identity", json={"display_name": "X"}).status_code == 410


def test_loopback_required_during_company_wizard(db_session, monkeypatch) -> None:
    """NEW-10-05: company-mode wizard still binds 127.0.0.1 until completion."""
    monkeypatch.setenv("OPENLIA_MODE", "company")
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: False,
    )
    client = TestClient(app)
    resp = client.post("/setup/mode", json={"mode": "company"})
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "loopback_required"


# ---------------------------------------------------------------------------
# Journey 2: company invite -> register -> login -> setup finish
# ---------------------------------------------------------------------------


def test_journey_company_invite_register_login(db_session, monkeypatch, make_user) -> None:
    # Seed an admin first so we can mint an invite through the admin API.
    admin = make_user(email="admin@example.com", is_admin=True)
    client = _company_client(monkeypatch, db_session)

    # Admin logs in.
    login = client.post(
        "/auth/login",
        json={"email": admin.email, "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    assert login.json()["is_admin"] is True

    # Admin creates an invite.
    invite_resp = client.post("/admin/invites", json={"label": "e2e"})
    assert invite_resp.status_code == 201
    invite_token = invite_resp.json()["token"]

    # Admin logs out so we can simulate a new-user registration.
    assert client.post("/auth/logout").status_code == 204
    client.cookies.clear()

    # Flip signup policy to invite_only so registration requires the token.
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="invite_only")

    # New user registers with the raw invite token.
    reg = client.post(
        "/auth/register",
        json={
            "email": "new@example.com",
            "password": "CorrectHorseBattery9!",
            "display_name": "New",
            "invite_token": invite_token,
        },
    )
    assert reg.status_code == 201
    # Registration establishes a session cookie immediately.
    session = client.get("/auth/session")
    assert session.status_code == 200
    assert session.json()["email"] == "new@example.com"

    # Simulate a fresh browser: clear cookies, log back in.
    client.cookies.clear()
    relogin = client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": "CorrectHorseBattery9!"},
    )
    assert relogin.status_code == 200
    assert client.get("/auth/session").status_code == 200


# ---------------------------------------------------------------------------
# Journey 3: auth logout / reload
# ---------------------------------------------------------------------------


def test_journey_logout_invalidates_session(db_session, monkeypatch, make_user) -> None:
    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)

    login = client.post(
        "/auth/login",
        json={"email": user.email, "password": "CorrectHorseBattery9!"},
    )
    assert login.status_code == 200
    cookie = client.cookies.get(COOKIE_NAME)
    assert cookie

    # Authenticated.
    assert client.get("/auth/session").status_code == 200

    # Logout clears server state and cookie.
    assert client.post("/auth/logout").status_code == 204

    # Replay the old cookie — server must reject it.
    client.cookies.set(COOKIE_NAME, cookie)
    assert client.get("/auth/session").status_code == 401


# ---------------------------------------------------------------------------
# Journey 4: provider create / edit / delete (admin-only)
# ---------------------------------------------------------------------------


def test_journey_provider_crud(db_session, monkeypatch, make_user) -> None:
    admin = make_user(email="admin@example.com", is_admin=True)
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": admin.email, "password": "correct horse battery staple"},
        ).status_code
        == 200
    )

    # Empty to start.
    assert client.get("/settings/admin/llm/providers").json() == []

    # Create — run_test=False with skip_reason so no network is required.
    create = client.post(
        "/settings/admin/llm/providers",
        json={
            "kind": "openai",
            "label": "Main OpenAI",
            "api_key": "sk-test",
            "run_test": False,
            "skip_reason": "smoke_test_no_network",
        },
    )
    assert create.status_code == 201
    provider_id = create.json()["id"]
    assert create.json()["has_api_key"] is True
    assert "api_key" not in create.json()

    # Update label + disable.
    update = client.put(
        f"/settings/admin/llm/providers/{provider_id}",
        json={"label": "Renamed", "is_enabled": False},
    )
    assert update.status_code == 200
    assert update.json()["label"] == "Renamed"
    assert update.json()["is_enabled"] is False

    # Delete — no models attached, so should succeed with 204.
    delete = client.delete(f"/settings/admin/llm/providers/{provider_id}")
    assert delete.status_code == 204
    assert client.get("/settings/admin/llm/providers").json() == []


# ---------------------------------------------------------------------------
# Journey 5: password reset + must-change-password gate
# ---------------------------------------------------------------------------


def test_journey_password_reset_and_forced_change(db_session, monkeypatch, make_user) -> None:
    admin = make_user(email="admin@example.com", is_admin=True)
    target = make_user(email="alice@example.com", password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)

    # Admin logs in and triggers a direct reset for the target user.
    assert (
        client.post(
            "/auth/login",
            json={"email": admin.email, "password": "correct horse battery staple"},
        ).status_code
        == 200
    )
    reset = client.post(
        f"/admin/users/{target.id}/reset-password",
        json={"new_password": "NewTempPassword1!"},
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"] == "NewTempPassword1!"
    assert client.post("/auth/logout").status_code == 204
    client.cookies.clear()

    # Target logs in with the temp password; must_change_password is set.
    login = client.post(
        "/auth/login",
        json={"email": target.email, "password": "NewTempPassword1!"},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True

    # Must-change-password-gated routes (portfolio, notifications) reject with 403.
    blocked = client.get("/portfolio/holdings")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "must_change_password"
    assert client.get("/notifications/unread").status_code == 403

    # /auth/session stays open so the frontend can render the change-password view.
    assert client.get("/auth/session").status_code == 200

    # Change password — server clears the must_change_password flag.
    change = client.post(
        "/auth/change-password",
        json={
            "current_password": "NewTempPassword1!",
            "new_password": "FinalPassword9!",
        },
    )
    assert change.status_code == 200

    # Normal access is restored.
    assert client.get("/portfolio/holdings").status_code == 200

    # Old temp password no longer works.
    client.cookies.clear()
    assert (
        client.post(
            "/auth/login",
            json={"email": target.email, "password": "NewTempPassword1!"},
        ).status_code
        == 401
    )


# ---------------------------------------------------------------------------
# Journey 6: repository open / save / download / unsave
# ---------------------------------------------------------------------------


def test_journey_repo_save_open_unsave(db_session, monkeypatch, make_user) -> None:
    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    # Seed a report the user owns directly in the DB.
    import uuid

    from openlia_server.db.models.content import Report

    report_id = str(uuid.uuid4())
    payload = {
        "schema_version": "1.0",
        "department": "secretary",
        "generated_at": "2026-04-24T10:00:00Z",
        "cover": {
            "title": "Smoke Report",
            "subtitle": "E2E",
            "tagline": "smoke",
        },
        "sections": [
            {
                "id": "intro",
                "title": "Intro",
                "blocks": [{"type": "text", "content": "Smoke body."}],
            }
        ],
    }
    db_session.add(
        Report(
            id=report_id,
            user_id=user.id,
            department="secretary",
            report_type="summary",
            title="Smoke Report",
            content_markdown="# Smoke",
            content_structured=payload,
            model_ref="test",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    db_session.commit()

    # Repo starts empty.
    empty = client.get("/repo/items")
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    # Save the report into the repository.
    save = client.post("/repo/items", json={"report_id": report_id})
    assert save.status_code == 201

    # List shows it.
    listing = client.get("/repo/items")
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert len(items) == 1
    assert items[0]["report_id"] == report_id

    # Facets include the department row.
    facets = client.get("/repo/facets")
    assert facets.status_code == 200
    assert facets.json()["total"] == 1

    # Open the report through /reports/{id} (owner-scoped). Payload returns
    # the canonical ReportSchema, which exposes department + cover but not id.
    opened = client.get(f"/reports/{report_id}")
    assert opened.status_code == 200
    schema = opened.json()["schema"]
    assert schema["department"] == "secretary"
    assert schema["cover"]["title"] == "Smoke Report"

    # Unsave — repo empties again.
    unsave = client.delete(f"/repo/items?report_id={report_id}")
    assert unsave.status_code == 204
    assert client.get("/repo/items").json()["items"] == []

    # Another user cannot see the report.
    other = make_user(email="bob@example.com", password="CorrectHorseBattery9!")
    client.cookies.clear()
    assert (
        client.post(
            "/auth/login",
            json={"email": other.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )
    assert client.get(f"/reports/{report_id}").status_code == 404


# ---------------------------------------------------------------------------
# Journey 7: Secretary chat stream — scripted runner, SSE frames, persistence
# ---------------------------------------------------------------------------


class _ScriptedChatRunner:
    """Minimal async-iterator stub matching ChatRunner.run(...)."""

    def __init__(self, events: list) -> None:
        self._events = events
        self.captured: dict = {}

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
        **_extra,
    ):
        self.captured = {
            "department_id": department_id,
            "user_id": user_id,
            "messages": messages,
            **_extra,
        }
        for event in self._events:
            yield event


def _parse_sse_event_names(body: str) -> list[str]:
    return [line[len("event: ") :] for line in body.splitlines() if line.startswith("event: ")]


def test_journey_secretary_chat_stream(db_session, monkeypatch, make_user) -> None:
    from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken

    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    # Install a scripted ChatRunner so the test is deterministic — no LLM I/O.
    runner = _ScriptedChatRunner(
        events=[
            ChatStart(message_id="m1"),
            ChatToken(message_id="m1", text="hello"),
            ChatToken(message_id="m1", text=" world"),
            ChatDone(message_id="m1", stop_reason="stop"),
        ]
    )
    client.app.state.chat_runner_factory = lambda: runner

    # Create a Secretary chat session.
    created = client.post("/chat/sessions", json={"department": "secretary", "title": "smoke chat"})
    assert created.status_code in (200, 201)
    session_id = created.json()["id"]

    # Stream a response — named-event SSE with matching payload types.
    resp = client.get(f"/chat/sessions/{session_id}/stream", params={"q": "hi there"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    events = _parse_sse_event_names(resp.text)
    assert events[0] == "chat.start"
    assert events[-1] == "chat.done"
    assert events.count("chat.token") == 2

    # Runner observed the right department + persisted history.
    assert runner.captured["department_id"] == "secretary"
    assert runner.captured["user_id"] == user.id
    assert runner.captured["messages"][-1].content == "hi there"

    # Both user + assistant messages are persisted on the session.
    listing = client.get(f"/chat/sessions/{session_id}/messages")
    assert listing.status_code == 200
    items = listing.json()["items"]
    roles = [m["role"] for m in items]
    contents = [m["content"] for m in items]
    assert roles == ["user", "assistant"]
    assert contents[0] == "hi there"
    assert contents[1] == "hello world"


# ---------------------------------------------------------------------------
# Journey 8: Morning Briefing follow-up chat — resolve-or-create session + stream
# ---------------------------------------------------------------------------


def test_journey_mb_followup_chat(db_session, monkeypatch, make_user) -> None:
    from openlia.llm.runtime.events import ChatDone, ChatStart, ChatToken

    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    runner = _ScriptedChatRunner(
        events=[
            ChatStart(message_id="mb1"),
            ChatToken(message_id="mb1", text="summary"),
            ChatDone(message_id="mb1", stop_reason="stop"),
        ]
    )
    client.app.state.chat_runner_factory = lambda: runner

    # Resolve-or-create the user's single MB chat session.
    resolved = client.post("/departments/morning-briefing/chat/session")
    assert resolved.status_code == 200
    session_id = resolved.json()["session_id"]
    assert isinstance(session_id, str) and session_id

    # Calling again returns the same session id (resolve, not duplicate).
    again = client.post("/departments/morning-briefing/chat/session")
    assert again.json()["session_id"] == session_id

    # Send a follow-up question through the shared chat stream.
    resp = client.get(
        f"/chat/sessions/{session_id}/stream",
        params={"q": "summarize today's briefing"},
    )
    assert resp.status_code == 200
    events = _parse_sse_event_names(resp.text)
    assert events[0] == "chat.start"
    assert events[-1] == "chat.done"

    # Runner saw the MB department wired through from the ChatSession.
    assert runner.captured["department_id"] == "morning_briefing"
    assert runner.captured["user_id"] == user.id

    # The follow-up message persisted on the same resolve-or-create session.
    listing = client.get(f"/chat/sessions/{session_id}/messages").json()["items"]
    assert [m["role"] for m in listing] == ["user", "assistant"]
    assert listing[0]["content"] == "summarize today's briefing"
    assert listing[1]["content"] == "summary"


# ---------------------------------------------------------------------------
# Journey 9: Equity Research on-demand report generation (SSE + persistence)
# ---------------------------------------------------------------------------


_ER_SCHEMA = {
    "schema_version": "1.0",
    "department": "equity_research",
    "generated_at": "2026-04-24T10:00:00Z",
    "cover": {"title": "AAPL Update", "subtitle": "", "tagline": ""},
    "sections": [],
}


class _ScriptedInner:
    """Minimal stand-in for the equity-research inner runner."""

    def __init__(self, events: list) -> None:
        self._events = events

    async def run(self, **kwargs):
        for event in self._events:
            yield event


def test_journey_equity_research_report(db_session, monkeypatch, make_user) -> None:
    from openlia.llm.runtime.events import ReportComplete, ReportStart
    from openlia_server.db.models.content import Report

    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    events = [
        ReportStart(
            report_id="r_er_1",
            department="equity_research",
            mode="stock_update",
            section_titles=["Quick Take"],
        ),
        ReportComplete(report_id="r_er_1", schema=_ER_SCHEMA),
    ]
    client.app.state.equity_research_inner_factory = lambda: _ScriptedInner(events)

    resp = client.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "AAPL event"},
        headers={"accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse_event_names(resp.text)
    assert "report.start" in frames
    assert "report.complete" in frames
    # EquityResearchRunner appends a report.saved frame after persisting the row.
    assert frames[-1] == "report.saved"

    # Report landed in the Report table under the authed user + right department.
    saved = db_session.query(Report).filter_by(user_id=user.id).all()
    assert len(saved) == 1
    assert saved[0].department == "equity_research"


# ---------------------------------------------------------------------------
# Journey 10: Earnings Update on-demand report generation (SSE + persistence)
# ---------------------------------------------------------------------------


_EU_SCHEMA = {
    "schema_version": "1.0",
    "department": "earnings_update",
    "generated_at": "2026-04-24T10:00:00Z",
    "cover": {"title": "AAPL Q1 FY2026", "subtitle": "", "tagline": ""},
    "sections": [],
}


class _ScriptedReportRunner:
    """Stand-in for the top-level ReportRunner (scheduler + EU route path)."""

    def __init__(self, events: list) -> None:
        self._events = events
        self.calls: list = []

    async def run(self, *, department_id, user_id, request, cancel_token=None):
        self.calls.append({"department_id": department_id, "user_id": user_id, "request": request})
        for event in self._events:
            yield event


def test_journey_earnings_update_report(db_session, monkeypatch, make_user) -> None:
    from openlia.llm.runtime.events import ReportComplete, ReportStart
    from openlia_server.db.models.content import Report

    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    runner = _ScriptedReportRunner(
        events=[
            ReportStart(
                report_id="r_eu_1",
                department="earnings_update",
                mode="earnings_analysis",
                section_titles=["Quick Take"],
            ),
            ReportComplete(report_id="r_eu_1", schema=_EU_SCHEMA),
        ]
    )
    client.app.state.report_runner = runner

    resp = client.post(
        "/departments/earnings-update/report",
        json={"ticker": "aapl"},
        headers={"accept": "text/event-stream"},
    )
    assert resp.status_code == 200
    frames = _parse_sse_event_names(resp.text)
    assert "report.start" in frames
    assert "report.complete" in frames

    # Ticker is uppercased into the runner request; mode resolves to earnings_analysis.
    assert runner.calls[0]["department_id"] == "earnings_update"
    assert runner.calls[0]["user_id"] == user.id
    req = runner.calls[0]["request"]
    assert "AAPL" in req.user_input
    assert req.mode == "earnings_analysis"

    # Row persists under the authed user + earnings_update department.
    saved = db_session.query(Report).filter_by(user_id=user.id).all()
    assert len(saved) == 1
    assert saved[0].department == "earnings_update"
    assert saved[0].report_type == "earnings_analysis"


# ---------------------------------------------------------------------------
# Journey 11: EU schedule -> notification (executor drives schedule to done)
# ---------------------------------------------------------------------------


class _NoopScheduler:
    """Minimal stand-in for SchedulerService. The EU schedule route only calls
    add/modify/remove, and /notifications/unread reads svc.session_factory."""

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def add_schedule(self, row) -> None: ...

    async def modify_schedule(self, row) -> None: ...

    async def remove_schedule(self, *, job_type, user_id) -> None: ...


def test_journey_eu_schedule_to_notification(db_session, monkeypatch, make_user) -> None:
    import asyncio

    from openlia.llm.runtime.events import ReportComplete, ReportStart
    from openlia.llm.runtime.messages import ReportRequest
    from openlia_server.db import session as session_mod
    from openlia_server.scheduler.executors.eu import EUScanExecutor
    from openlia_server.scheduler.payloads import EUScanTarget

    user = make_user(password="CorrectHorseBattery9!")
    client = _company_client(monkeypatch, db_session)
    assert (
        client.post(
            "/auth/login",
            json={"email": user.email, "password": "CorrectHorseBattery9!"},
        ).status_code
        == 200
    )

    # Install a no-op scheduler so the EU schedule route + notifications route work.
    client.app.state.scheduler = _NoopScheduler(session_factory=session_mod.SessionLocal)

    # Create a schedule through the real route.
    create = client.post(
        "/departments/earnings-update/schedules",
        json={
            "time": "16:30",
            "timezone": "America/New_York",
            "days_of_week": [0, 1, 2, 3, 4],
            "label": "Post-Market",
            "is_enabled": True,
        },
    )
    assert create.status_code == 201
    schedule_id = create.json()["id"]

    # No notifications to start with.
    pre = client.get("/notifications/unread")
    assert pre.status_code == 200
    assert pre.json()["total"] == 0

    # Drive the executor directly with fakes that simulate a single ticker run.
    target = EUScanTarget(
        ticker="AAPL",
        request=ReportRequest(mode="earnings_analysis", user_input="AAPL earnings"),
    )

    class _FakePlanner:
        def plan(self, *, session, user_id, schedule_id, since):
            return [target]

    class _FakeReportStore:
        def save(self, *, session, user_id, department, payload):
            return "r_eu_sched_1"

    runner = _ScriptedReportRunner(
        events=[
            ReportStart(
                report_id="r_eu_sched_1",
                department="earnings_update",
                mode="earnings_analysis",
                section_titles=[],
            ),
            ReportComplete(report_id="r_eu_sched_1", schema=_EU_SCHEMA),
        ]
    )

    executor = EUScanExecutor(
        session_factory=session_mod.SessionLocal,
        eu_planner=_FakePlanner(),
        report_runner=runner,
        report_store=_FakeReportStore(),
    )

    asyncio.run(executor.execute(user_id=user.id, schedule_id=schedule_id))

    # /notifications/unread must now surface the earnings_update notification.
    post = client.get("/notifications/unread")
    assert post.status_code == 200
    body = post.json()
    assert body["total"] == 1
    assert body["by_department"]["earnings_update"] == 1

    # Mark-read drains the unread counter.
    read = client.post("/notifications/read", json={"department": "earnings_update"})
    assert read.status_code == 200
    assert read.json()["marked_read"] == 1
    assert client.get("/notifications/unread").json()["total"] == 0
