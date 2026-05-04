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


@pytest.fixture
def client_authed(client, user_factory, login_as):
    user = user_factory()
    login_as(user)
    return client


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
