"""Posting a message to a chat session whose attached_report_id points
at an existing report+bundle works as a regular chat call, with
read_payload available as a tool. If the bundle is missing or the
report is tombstoned, the response indicates a locked chat (HTTP 200
with a 'locked: true' marker rather than an error)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.plan_schema import ReportPlan
from openlia.llm.runtime.report_context_bundle import ReportContextBundle, persist_bundle
from openlia.llm.runtime.section_draft import SectionDraft

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
        payload_refs={"r_abc_01": {"ticker": "MSFT", "price": 190.5}},
        generation_meta={},
    )
    persist_bundle(bundle, path=bundle_dir / f"{report_id}.json.gz")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _bundle_dir(tmp_path: Path) -> Path:
    d = tmp_path / "bundles"
    d.mkdir()
    return d


@pytest.fixture
def _personal_app(db_session, monkeypatch, _bundle_dir: Path):
    """Personal-mode app with bundle_dir wired via env var."""
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


def _seed_session(db_session, report_id: str) -> Any:
    from openlia_server.db.models.content import ChatSession

    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Bound chat",
        is_pinned=False,
        is_archived=False,
        attached_report_id=report_id,
    )
    db_session.add(session)
    db_session.commit()
    return session


def _seed_report(db_session) -> Any:
    from openlia_server.db.models.content import Report

    report = Report(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        report_type="summary",
        title="Test Report",
        content_markdown="# Test",
        content_structured={},
        model_ref="gpt-4",
    )
    db_session.add(report)
    db_session.commit()
    return report


@pytest.fixture
def seeded_session_with_missing_bundle(db_session, _bundle_dir: Path):
    """Session bound to a report; bundle file does NOT exist on disk."""
    report = _seed_report(db_session)
    # Intentionally do NOT write a bundle file.
    return _seed_session(db_session, report.id)


@pytest.fixture
def seeded_session_with_bundle(db_session, _bundle_dir: Path):
    """Session bound to a report; valid bundle exists on disk."""
    report = _seed_report(db_session)
    _write_bundle(_bundle_dir, report.id)
    return _seed_session(db_session, report.id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_message_to_locked_chat_returns_locked_marker(
    test_client: TestClient, seeded_session_with_missing_bundle
) -> None:
    session_id = seeded_session_with_missing_bundle.id
    resp = test_client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"content": "What's up?"},
    )
    # Endpoint accepts the request but returns the locked marker.
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("locked") is True
    assert "can no longer be fetched" in body.get("lock_message", "").lower()


def test_message_to_bound_chat_with_bundle_streams_normally(
    test_client: TestClient, seeded_session_with_bundle
) -> None:
    session_id = seeded_session_with_bundle.id
    resp = test_client.post(
        f"/chat/sessions/{session_id}/messages",
        json={"content": "Summarize the report."},
        timeout=10,
    )
    assert resp.status_code == 200
    # Standard chat response shape — does not include locked: true.
    body = resp.json()
    assert body.get("locked") is not True
