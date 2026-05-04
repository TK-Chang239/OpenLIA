"""End-to-end smoke: install a skill via /api/skills, verify the registry
refresh propagates to build_chat_system_prompt, and verify the install is
recorded in /api/admin/skills/audit."""

from __future__ import annotations

import asyncio
import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from openlia.llm.runtime.chat import build_chat_system_prompt

SAMPLE = """---
name: e2e-skill
display_name: E2E Skill
description: Smoke test skill.
version: "1.0.0"
departments: [secretary]
---

E2E body content.
"""


def _zip(name: str = "e2e-skill", body_text: str = SAMPLE) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{name}/SKILL.md", body_text)
    return buf.getvalue()


@pytest.fixture
def skills_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point OPENLIA_SKILLS_ROOT at a per-test directory."""
    root = tmp_path / "skills"
    root.mkdir()
    monkeypatch.setenv("OPENLIA_SKILLS_ROOT", str(root))
    return root


@pytest.fixture
def authed_personal_client(
    skills_root: Path,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> TestClient:
    """Personal-mode TestClient using the autouse-seeded LOCAL_USER_ID admin."""
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod

    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


def test_install_then_appears_in_secretary_chat_prompt(
    authed_personal_client: TestClient,
) -> None:
    files = {"file": ("e2e.zip", _zip(), "application/zip")}
    r = authed_personal_client.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200, r.text

    from openlia_server.middleware.auth import LOCAL_USER_ID

    registry = authed_personal_client.app.state.skills_registry
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(registry.refresh_user(LOCAL_USER_ID))
    finally:
        loop.close()

    prompt = build_chat_system_prompt(
        department_id="secretary",
        user_id=LOCAL_USER_ID,
        registry=registry,
    )
    assert "e2e-skill" in prompt
    assert "Smoke test skill." in prompt


def test_audit_log_records_install(
    authed_personal_client: TestClient,
) -> None:
    audited_body = SAMPLE.replace("e2e-skill", "audited").replace("E2E Skill", "Audited Skill")
    files = {
        "file": (
            "audited.zip",
            _zip(name="audited", body_text=audited_body),
            "application/zip",
        ),
    }
    r = authed_personal_client.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200, r.text

    audit = authed_personal_client.get("/api/admin/skills/audit").json()["items"]
    assert any(e["event_type"] == "skill_installed" and e["skill_id"] == "audited" for e in audit)
