"""Route tests for /reports/{id}/download and /chat/attachments/{id}/download."""

from __future__ import annotations

import uuid


def test_download_report_returns_markdown(client, user_factory, login_as, report_factory):
    u = user_factory()
    login_as(u)
    r = report_factory(user_id=u.id, title="My Report", content_markdown="# Hello\n\nContent.")
    resp = client.get(f"/reports/{r.id}/download")
    assert resp.status_code == 200
    assert b"# Hello" in resp.content
    assert "filename=" in resp.headers["content-disposition"]
    assert "My Report" in resp.headers["content-disposition"]


def test_download_report_forbids_other_users(client, user_factory, login_as, report_factory):
    a = user_factory()
    b = user_factory()
    r = report_factory(user_id=a.id)
    login_as(b)
    assert client.get(f"/reports/{r.id}/download").status_code == 403


def test_download_report_404_when_missing(client, user_factory, login_as):
    login_as(user_factory())
    assert client.get(f"/reports/{uuid.uuid4()}/download").status_code == 404


def test_download_attachment_404_when_missing(client, user_factory, login_as):
    login_as(user_factory())
    assert client.get(f"/chat/attachments/{uuid.uuid4()}/download").status_code == 404
