"""resolve_report_language: explicit department choice > global
user_prefs.report_language > en; 'both' clamps to en for modern engines."""

from __future__ import annotations

from openlia_server.db.models.config import UserPrefs
from openlia_server.services.eu_v2_settings import get_settings
from openlia_server.services.user_prefs import resolve_report_language


def _set_global(db_session, user_id: str, report_language: str) -> None:
    db_session.add(UserPrefs(user_id=user_id, report_language=report_language))
    db_session.commit()


def test_explicit_choice_wins(db_session, make_user):
    user = make_user(email="explicit@example.com")
    _set_global(db_session, user.id, "zh-TW")
    assert resolve_report_language(db_session, user_id=user.id, explicit="en") == "en"


def test_global_pref_used_when_no_explicit_choice(db_session, make_user):
    user = make_user(email="global@example.com")
    _set_global(db_session, user.id, "zh-TW")
    assert resolve_report_language(db_session, user_id=user.id) == "zh-TW"


def test_defaults_to_en_without_prefs_row(db_session, make_user):
    user = make_user(email="fresh@example.com")
    assert resolve_report_language(db_session, user_id=user.id) == "en"


def test_both_clamps_to_en(db_session, make_user):
    """'both' (bilingual) is legacy-runner-only; modern engines get en."""
    user = make_user(email="both@example.com")
    _set_global(db_session, user.id, "both")
    assert resolve_report_language(db_session, user_id=user.id) == "en"


def test_eu_settings_default_follows_global_pref(db_session, make_user):
    """A user who never saved EU settings inherits the global report language."""
    user = make_user(email="eu@example.com")
    _set_global(db_session, user.id, "zh-TW")
    dto = get_settings(db_session, user_id=user.id)
    assert dto.language == "zh-TW"
