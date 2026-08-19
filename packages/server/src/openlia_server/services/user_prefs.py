"""User preferences service — display, notifications, theme, language, timezone."""

from __future__ import annotations

import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs

# Snapshot basket (fix-chats Q5/Q6). Top-movers sector ETFs stay hardcoded
# in snapshot_format.yaml.j2 — only these four sections are user-editable.
DEFAULT_MARKET_BASKET: dict[str, list[str]] = {
    "tape": ["SPY", "QQQ", "DIA", "IWM"],
    "risk": ["VIX", "HYG", "TLT"],
    "macro": ["DXY", "GLD", "USO"],
    "crypto": ["BTC"],
}

_BASKET_SECTIONS = frozenset(DEFAULT_MARKET_BASKET.keys())
_TICKER_RE = re.compile(r"^[A-Z0-9.^-]{1,10}$")
_MAX_TICKERS_PER_SECTION = 12

Theme = Literal["system", "light", "dark"]
DisplayLang = Literal["en", "zh-TW"]
ReportLang = Literal["en", "zh-TW", "both"]
TimezoneSource = Literal["auto", "manual"]

_VALID_THEMES = {"system", "light", "dark"}
_VALID_DISPLAY_LANG = {"en", "zh-TW"}
_VALID_REPORT_LANG = {"en", "zh-TW", "both"}
_VALID_TZ_SOURCES = {"auto", "manual"}


def resolve_report_language(db: Session, *, user_id: str, explicit: str | None = None) -> str:
    """Report-language resolution shared by the report engines.

    Precedence: an explicit per-department choice, else the user's global
    ``report_language`` pref (Settings > General), else ``en``.

    The global pref may be ``both`` (bilingual), which only the legacy report
    runner understands — the modern engines (v3 / EU v2 / MB) take a single
    ``Language``, so ``both`` resolves to ``en`` here.
    """
    if explicit is not None:
        return explicit
    stored = db.query(UserPrefs.report_language).filter_by(user_id=user_id).scalar()
    if stored in ("en", "zh-TW"):
        return stored
    return "en"


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


_HHMM_RE = __import__("re").compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def set_graph_extraction_time(db: Session, *, user_id: str, time: str) -> UserPrefs:
    """Set the user-preferred wall-clock time (in their timezone) at
    which the nightly graph-extraction job runs. ``time`` is ``"HH:MM"``
    24-hour. Invalid input raises ``ValueError``."""
    if not _HHMM_RE.match(time):
        raise ValueError(f"invalid HH:MM time: {time!r}")
    prefs = get_or_create(db, user_id=user_id)
    prefs.graph_extraction_time = time
    db.flush()
    return prefs


def get_market_basket(db: Session, *, user_id: str) -> dict[str, list[str]]:
    """Return the user's snapshot basket, falling back to DEFAULT_MARKET_BASKET.

    Used by chat_stream to inject the basket into Secretary's system prompt
    at request time. The fallback is a fresh dict per call so callers can
    safely mutate the return value.
    """
    prefs = db.query(UserPrefs).filter_by(user_id=user_id).one_or_none()
    if prefs is None or prefs.default_market_basket is None:
        return {k: list(v) for k, v in DEFAULT_MARKET_BASKET.items()}
    return {k: list(v) for k, v in prefs.default_market_basket.items()}


def set_market_basket(
    db: Session,
    *,
    user_id: str,
    basket: dict[str, list[str]],
) -> UserPrefs:
    """Validate + persist the user's snapshot basket.

    Validation:
      - Sections must be exactly tape / risk / macro / crypto.
      - Each section: non-empty list of 1-12 tickers.
      - Ticker form: ^[A-Z0-9.^-]{1,10}$ (after trim + uppercase).
    """
    if not isinstance(basket, dict):
        raise ValueError("basket must be a mapping of section → tickers")
    sections = frozenset(basket.keys())
    missing = _BASKET_SECTIONS - sections
    if missing:
        raise ValueError(f"missing section(s): {sorted(missing)}")
    extra = sections - _BASKET_SECTIONS
    if extra:
        raise ValueError(f"unknown section(s): {sorted(extra)}")
    normalized: dict[str, list[str]] = {}
    for section, tickers in basket.items():
        if not isinstance(tickers, list) or not tickers:
            raise ValueError(f"section {section!r} is empty")
        if len(tickers) > _MAX_TICKERS_PER_SECTION:
            raise ValueError(
                f"too many tickers in {section!r}: {len(tickers)} > {_MAX_TICKERS_PER_SECTION}"
            )
        norm: list[str] = []
        for t in tickers:
            if not isinstance(t, str):
                raise ValueError(f"invalid ticker in {section!r}: {t!r} not a string")
            cleaned = t.strip().upper()
            if not _TICKER_RE.match(cleaned):
                raise ValueError(f"invalid ticker {t!r} in section {section!r}")
            norm.append(cleaned)
        normalized[section] = norm
    prefs = get_or_create(db, user_id=user_id)
    prefs.default_market_basket = normalized
    db.flush()
    return prefs


def set_timezone(
    db: Session,
    *,
    user_id: str,
    timezone: str,
    source: TimezoneSource,
) -> UserPrefs:
    """Persist the user's timezone with override semantics.

    ``source='manual'`` (user picked it in Settings) always wins. A
    subsequent ``source='auto'`` (browser drift) is ignored when the
    stored row is already manual. Browser→server flow can call this on
    every login without worrying about clobbering the user's choice.
    """
    if source not in _VALID_TZ_SOURCES:
        raise ValueError(f"invalid timezone source: {source!r}")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"invalid IANA timezone: {timezone!r}") from exc

    prefs = get_or_create(db, user_id=user_id)
    if prefs.timezone_source == "manual" and source == "auto":
        return prefs
    prefs.timezone = timezone
    prefs.timezone_source = source
    db.flush()
    return prefs
