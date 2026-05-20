"""Tests for resolve_user_template_spec (PR 14)."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_templates import ReportTemplate
from openlia_server.services.report_template_resolver import (
    resolve_user_template_spec,
)


def _seed_user(session, *, user_id: str) -> str:
    session.add(User(id=user_id, email=f"{user_id}@example.com", display_name=user_id))
    session.commit()
    return user_id


def _seed_template(session, *, user_id: str, spec: dict) -> str:
    template_id = str(uuid.uuid4())
    session.add(
        ReportTemplate(
            id=template_id,
            user_id=user_id,
            name="t",
            template_spec_json=spec,
            source_markdown=None,
        )
    )
    session.commit()
    return template_id


def test_returns_spec_for_owned_template(db_session) -> None:
    user_id = _seed_user(db_session, user_id="u1")
    spec = {"name": "t", "global_preface": "", "body_sections": [], "synthesis_sections": []}
    tid = _seed_template(db_session, user_id=user_id, spec=spec)

    out = resolve_user_template_spec(db_session, user_id=user_id, template_id=tid)

    assert out == spec


def test_raises_404_when_template_missing(db_session) -> None:
    user_id = _seed_user(db_session, user_id="u1")

    with pytest.raises(HTTPException) as err:
        resolve_user_template_spec(db_session, user_id=user_id, template_id="does-not-exist")

    assert err.value.status_code == 404


def test_raises_404_when_template_belongs_to_another_user(db_session) -> None:
    a = _seed_user(db_session, user_id="u1")
    b = _seed_user(db_session, user_id="u2")
    spec = {"name": "t", "global_preface": "", "body_sections": [], "synthesis_sections": []}
    tid = _seed_template(db_session, user_id=a, spec=spec)

    with pytest.raises(HTTPException) as err:
        resolve_user_template_spec(db_session, user_id=b, template_id=tid)

    assert err.value.status_code == 404
