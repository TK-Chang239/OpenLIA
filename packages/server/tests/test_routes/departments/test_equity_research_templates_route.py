"""HTTP tests for /departments/equity-research/templates."""

from __future__ import annotations

import io

import pytest

LONG_TEXT = ("Equity research template body. " * 30).strip()


@pytest.fixture(autouse=True)
def _storage_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENLIA_ATTACHMENTS_DIR", str(tmp_path / "attachments"))


def _upload(
    company_client,
    *,
    name: str = "my",
    scope: str = "user",
    modes: str = "stock_initiation",
):
    files = {"file": ("my.md", io.BytesIO(LONG_TEXT.encode("utf-8")), "text/markdown")}
    data = {"name": name, "scope": scope, "compatible_modes": modes}
    return company_client.post(
        "/departments/equity-research/templates",
        files=files,
        data=data,
    )


def test_list_templates_empty(company_client, auth_user):
    r = company_client.get("/departments/equity-research/templates")
    assert r.status_code == 200
    assert r.json() == {"templates": []}


def test_upload_persists_user_template(company_client, auth_user):
    r = _upload(company_client, name="V1", modes="stock_initiation,stock_update")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "V1"
    assert body["owner_scope"] == "user"
    assert body["owner_user_id"] == auth_user.id
    assert body["compatible_modes"] == ["stock_initiation", "stock_update"]
    assert body["estimated_tokens"] > 0


def test_upload_rejects_short_file(company_client, auth_user):
    files = {"file": ("x.md", io.BytesIO(b"too short"), "text/markdown")}
    r = company_client.post(
        "/departments/equity-research/templates",
        files=files,
        data={"name": "x", "scope": "user", "compatible_modes": "stock_initiation"},
    )
    assert r.status_code == 400
    assert "too short" in r.json()["detail"].lower()


def test_upload_global_rejected_for_non_admin(company_client, auth_user):
    r = _upload(company_client, scope="global")
    assert r.status_code == 403


def test_upload_global_allowed_for_admin(company_client, db_session, make_user):
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import sessions

    admin = make_user(email="admin@example.com", is_admin=True)
    created = sessions.create_session(db_session, user_id=admin.id, persistent=False)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    r = _upload(company_client, scope="global")
    assert r.status_code == 201
    assert r.json()["owner_scope"] == "global"


def test_get_extracted_text_round_trip(company_client, auth_user):
    tid = _upload(company_client).json()["id"]
    r = company_client.get(f"/departments/equity-research/templates/{tid}/extracted_text")
    assert r.status_code == 200
    assert r.json()["extracted_text"] == LONG_TEXT


def test_download_raw_returns_bytes(company_client, auth_user):
    tid = _upload(company_client).json()["id"]
    r = company_client.get(f"/departments/equity-research/templates/{tid}/raw")
    assert r.status_code == 200
    assert r.content == LONG_TEXT.encode("utf-8")


def test_patch_template_updates_metadata(company_client, auth_user):
    tid = _upload(company_client, name="orig").json()["id"]
    r = company_client.patch(
        f"/departments/equity-research/templates/{tid}",
        json={"name": "renamed", "compatible_modes": ["sector_research"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "renamed"
    assert body["compatible_modes"] == ["sector_research"]


def test_delete_template_cascades_selection(company_client, auth_user):
    tid = _upload(company_client).json()["id"]
    company_client.put(
        "/departments/equity-research/config",
        json={"selected_template_id_by_mode": {"stock_initiation": tid}},
    )
    company_client.delete(f"/departments/equity-research/templates/{tid}")
    cfg = company_client.get("/departments/equity-research/config").json()
    assert cfg["selected_template_id_by_mode"]["stock_initiation"] == "default"


def test_other_user_cannot_view_private_template(company_client, db_session, make_user, auth_user):
    """A second user logging in cannot see u1's private upload."""
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import sessions

    tid = _upload(company_client).json()["id"]
    other = make_user(email="other@example.com")
    created = sessions.create_session(db_session, user_id=other.id, persistent=False)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    listing = company_client.get("/departments/equity-research/templates").json()
    assert all(t["id"] != tid for t in listing["templates"])
    r = company_client.get(f"/departments/equity-research/templates/{tid}")
    assert r.status_code == 404
