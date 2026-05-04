"""User preferences service — display, notifications, theme, language."""

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs

Theme = Literal["system", "light", "dark"]
DisplayLang = Literal["en", "zh-TW"]
ReportLang = Literal["en", "zh-TW", "both"]

_VALID_THEMES = {"system", "light", "dark"}
_VALID_DISPLAY_LANG = {"en", "zh-TW"}
_VALID_REPORT_LANG = {"en", "zh-TW", "both"}


def get_or_create(db: Session, *, user_id: str) -> UserPrefs:
    prefs = db.query(UserPrefs).filter_by(user_id=user_id).one_or_none()
    if prefs is None:
        prefs = UserPrefs(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


_UNSET: object = object()


def update(
    db: Session,
    *,
    user_id: str,
    theme: str | None = None,
    notify_inapp: bool | None = None,
    notify_email: bool | None = None,
    display_language: str | None = None,
    response_language: str | None = None,
    report_language: str | None = None,
    preferred_model_id: object = _UNSET,
) -> UserPrefs:
    if theme is not None and theme not in _VALID_THEMES:
        raise ValueError(f"invalid theme: {theme}")
    if display_language is not None and display_language not in _VALID_DISPLAY_LANG:
        raise ValueError(f"invalid display_language: {display_language}")
    if response_language is not None and response_language not in _VALID_DISPLAY_LANG:
        raise ValueError(f"invalid response_language: {response_language}")
    if report_language is not None and report_language not in _VALID_REPORT_LANG:
        raise ValueError(f"invalid report_language: {report_language}")

    prefs = get_or_create(db, user_id=user_id)
    if theme is not None:
        prefs.theme = theme
    if notify_inapp is not None:
        prefs.notify_inapp = notify_inapp
    if notify_email is not None:
        prefs.notify_email = notify_email
    if display_language is not None:
        prefs.display_language = display_language
    if response_language is not None:
        prefs.response_language = response_language
    if report_language is not None:
        prefs.report_language = report_language
    if preferred_model_id is not _UNSET:
        # ``None`` clears the override; any other str sets it. The route
        # validator confirms the model exists/is enabled before reaching here.
        prefs.preferred_model_id = preferred_model_id  # type: ignore[assignment]
    db.flush()
    return prefs
