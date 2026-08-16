import io
import zipfile

import pytest

SAMPLE = """---
name: viaapi
description: Installed via API.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("viaapi/SKILL.md", SAMPLE)
    return buf.getvalue()


def _zip_named(name: str) -> bytes:
    md = SAMPLE.replace("viaapi", name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(f"{name}/SKILL.md", md)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _hermetic_skills_root(monkeypatch, tmp_path):
    """Point the filesystem (system-scope) store at a throwaway dir so
    system-scope installs never touch the developer's real ~/.openlia and
    never collide across re-runs."""
    monkeypatch.setenv("OPENLIA_SKILLS_ROOT", str(tmp_path / "skills-root"))


@pytest.fixture
def client_authed(client, user_factory, login_as):
    user = user_factory()
    login_as(user)
    return client


def _make_admin(user_factory, db_session):
    admin = user_factory()
    admin.is_admin = True
    db_session.add(admin)
    db_session.commit()
    return admin


def test_install_zip_lists_and_disables(client_authed):
    files = {"file": ("viaapi.zip", _zip(), "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200, r.text
    assert r.json()["skill_id"] == "viaapi"

    r = client_authed.get("/api/skills")
    assert r.status_code == 200
    assert any(s["skill_id"] == "viaapi" for s in r.json()["items"])

    r = client_authed.patch("/api/skills/viaapi", json={"enabled": False})
    assert r.status_code == 200
    listing = client_authed.get("/api/skills").json()["items"]
    assert next(s for s in listing if s["skill_id"] == "viaapi")["enabled"] is False

    r = client_authed.get("/api/skills/viaapi/body")
    assert r.status_code == 200
    assert "Body." in r.json()["body"]

    r = client_authed.delete("/api/skills/viaapi")
    assert r.status_code == 204


def test_install_rejects_bad_skill_md(client_authed):
    files = {"file": ("bad.zip", b"not a zip", "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 400


def test_user_scoped_skills_isolated_per_user(client, user_factory, login_as):
    """Company mode: one user's user-scoped install is invisible to and
    non-mutable by another user (DatabaseSkillStore keys by user_id)."""
    user1 = user_factory()
    user2 = user_factory()

    login_as(user1)
    r = client.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files={"file": ("s.zip", _zip_named("u1only"), "application/zip")},
    )
    assert r.status_code == 200, r.text
    assert any(s["skill_id"] == "u1only" for s in client.get("/api/skills").json()["items"])

    # user2 sees nothing belonging to user1
    login_as(user2)
    assert all(s["skill_id"] != "u1only" for s in client.get("/api/skills").json()["items"])
    # and cannot delete a skill scoped to another user
    assert client.delete("/api/skills/u1only").status_code == 404

    # user1's skill is untouched
    login_as(user1)
    assert any(s["skill_id"] == "u1only" for s in client.get("/api/skills").json()["items"])


def test_non_admin_cannot_toggle_system_skill(client, user_factory, db_session, login_as):
    """PATCH fallback onto a system-scope skill is admin-gated."""
    admin = _make_admin(user_factory, db_session)
    login_as(admin)
    r = client.post(
        "/api/skills/install",
        data={"scope": "system", "source_type": "zip"},
        files={"file": ("s.zip", _zip_named("syskill"), "application/zip")},
    )
    assert r.status_code == 200, r.text

    # a non-admin cannot globally disable it
    login_as(user_factory())
    assert client.patch("/api/skills/syskill", json={"enabled": False}).status_code == 403

    # the system skill stays enabled and an admin can still toggle it
    login_as(admin)
    items = client.get("/api/skills").json()["items"]
    assert next(s for s in items if s["skill_id"] == "syskill")["enabled"] is True
    assert client.patch("/api/skills/syskill", json={"enabled": False}).status_code == 200


def test_non_admin_cannot_install_from_folder(client, user_factory, login_as, tmp_path):
    """A server-filesystem folder install is admin-only for every scope."""
    login_as(user_factory())
    r = client.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "folder", "folder_path": str(tmp_path)},
    )
    assert r.status_code == 403


def test_admin_can_install_from_folder(client, user_factory, db_session, login_as, tmp_path):
    src = tmp_path / "myskill"
    src.mkdir()
    (src / "SKILL.md").write_text(SAMPLE.replace("viaapi", "folderskill"))
    login_as(_make_admin(user_factory, db_session))
    r = client.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "folder", "folder_path": str(src)},
    )
    assert r.status_code == 200, r.text
    assert r.json()["skill_id"] == "folderskill"
