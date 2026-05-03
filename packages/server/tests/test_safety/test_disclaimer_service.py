"""Disclaimer acceptance — company-mode storage."""

from __future__ import annotations

from openlia_server.db.models.safety import UserDisclaimerAcceptance
from openlia_server.services import disclaimer as svc


def test_record_acceptance_inserts_row(db_session) -> None:
    svc.record_acceptance(db_session, user_id="u1", version="1.0.0")
    db_session.commit()
    assert svc.has_accepted(db_session, user_id="u1", version="1.0.0") is True
    assert svc.has_accepted(db_session, user_id="u1", version="2.0.0") is False


def test_record_acceptance_idempotent(db_session) -> None:
    svc.record_acceptance(db_session, user_id="u2", version="1.0.0")
    svc.record_acceptance(db_session, user_id="u2", version="1.0.0")
    db_session.commit()
    rows = db_session.query(UserDisclaimerAcceptance).filter_by(user_id="u2").all()
    assert len(rows) == 1
