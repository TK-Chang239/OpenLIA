"""Bootstrap must not seed signup_policy (Plan 1a P0-1a-04).

signup_policy belongs to the setup wizard's finalize() handler in
services.wizard, not to Plan 1a's bootstrap. This test freezes that
boundary so a future refactor cannot silently re-introduce the layer
inversion.
"""

from __future__ import annotations

from openlia_server.db.models.auth import SignupPolicy
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_bootstrap_does_not_seed_signup_policy(
    engine, db_session: Session, monkeypatch, tmp_path, db_url: str
) -> None:
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    monkeypatch.setenv("OPENLIA_DB_URL", db_url)

    from openlia_server.db import bootstrap as bs

    bs.bootstrap()

    # Use a fresh session to read post-bootstrap state.
    from openlia_server.db import session as sess

    with sess.SessionLocal() as s:
        rows = list(s.execute(select(SignupPolicy)).scalars())
    assert rows == [], "bootstrap must not seed signup_policy"


def test_wizard_finalize_seeds_signup_policy(db_session: Session, create_tables) -> None:
    from openlia_server.services import wizard as wiz

    wiz.finalize(db_session, mode="personal")
    db_session.flush()

    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.id == 1
    assert row.mode == "closed"


def test_wizard_finalize_company_mode_seeds_invite_only(db_session: Session, create_tables) -> None:
    from openlia_server.services import wizard as wiz

    wiz.finalize(db_session, mode="company")
    db_session.flush()

    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.mode == "invite_only"
