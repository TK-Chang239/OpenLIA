"""Per-user EU v2 settings: defaults + connector toggles."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from openlia_server.db.models.report_eu import EuV2Settings

_VALID_LENGTHS = {"concise", "normal", "elaborative"}
_VALID_EFFORTS = {None, "medium", "high"}

_DEFAULT_PROVIDER_KIND = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_TEMPLATE_ID = "eu_default"
_DEFAULT_LANGUAGE = "en"
_DEFAULT_LENGTH = "normal"


@dataclass(frozen=True)
class EuSettingsDTO:
    user_id: str
    provider_kind: str
    model: str
    template_id: str
    language: str
    length: str
    reasoning_effort: str | None
    financial_enabled: bool
    calendar_enabled: bool
    web_search_enabled: bool


def _row_to_dto(row: EuV2Settings) -> EuSettingsDTO:
    return EuSettingsDTO(
        user_id=row.user_id,
        provider_kind=row.provider_kind,
        model=row.model,
        template_id=row.template_id,
        language=row.language,
        length=row.length,
        reasoning_effort=row.reasoning_effort,
        financial_enabled=row.financial_enabled,
        calendar_enabled=row.calendar_enabled,
        web_search_enabled=row.web_search_enabled,
    )


def get_settings(db: Session, *, user_id: str) -> EuSettingsDTO:
    """Return the user's settings row, or defaults when absent."""
    row = db.get(EuV2Settings, user_id)
    if row is None:
        return EuSettingsDTO(
            user_id=user_id,
            provider_kind=_DEFAULT_PROVIDER_KIND,
            model=_DEFAULT_MODEL,
            template_id=_DEFAULT_TEMPLATE_ID,
            language=_DEFAULT_LANGUAGE,
            length=_DEFAULT_LENGTH,
            reasoning_effort=None,
            financial_enabled=True,
            calendar_enabled=True,
            web_search_enabled=False,
        )
    return _row_to_dto(row)


def update_settings(
    db: Session,
    *,
    user_id: str,
    provider_kind: str,
    model: str,
    template_id: str,
    language: str,
    length: str,
    reasoning_effort: str | None,
    financial_enabled: bool,
    calendar_enabled: bool,
    web_search_enabled: bool,
) -> EuSettingsDTO:
    """Upsert the user's settings row and return the resulting DTO.

    Raises ``ValueError`` for invalid ``length`` or ``reasoning_effort``.
    """
    if length not in _VALID_LENGTHS:
        raise ValueError(f"length must be one of {sorted(_VALID_LENGTHS)!r}, got {length!r}")
    if reasoning_effort not in _VALID_EFFORTS:
        raise ValueError(
            f"reasoning_effort must be one of {sorted(str(e) for e in _VALID_EFFORTS)!r},"
            f" got {reasoning_effort!r}"
        )

    now = datetime.now(UTC)
    row = db.get(EuV2Settings, user_id)
    if row is None:
        row = EuV2Settings(
            user_id=user_id,
            provider_kind=provider_kind,
            model=model,
            template_id=template_id,
            language=language,
            length=length,
            reasoning_effort=reasoning_effort,
            financial_enabled=financial_enabled,
            calendar_enabled=calendar_enabled,
            web_search_enabled=web_search_enabled,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.provider_kind = provider_kind
        row.model = model
        row.template_id = template_id
        row.language = language
        row.length = length
        row.reasoning_effort = reasoning_effort
        row.financial_enabled = financial_enabled
        row.calendar_enabled = calendar_enabled
        row.web_search_enabled = web_search_enabled
        row.updated_at = now

    db.commit()
    return _row_to_dto(row)
