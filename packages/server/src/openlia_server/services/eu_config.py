"""Per-user Earnings Update config: sections, length, custom sections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuUserConfig

DEFAULT_SECTION_IDS: tuple[str, ...] = (
    "quick_take",
    "market_reaction",
    "key_financials",
    "operational_highlights",
    "forward_guidance",
    "earnings_call",
    "risk_assessment",
    "thesis_check",
)

_VALID_LENGTHS = frozenset({"concise", "normal", "elaborative"})


@dataclass(frozen=True)
class EuConfigDTO:
    report_length: str
    enabled_section_ids: list[str]
    custom_sections: list[dict]


def get_config(db: Session, *, user_id: str) -> EuConfigDTO:
    row = db.query(EuUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return EuConfigDTO(
            report_length="normal",
            enabled_section_ids=list(DEFAULT_SECTION_IDS),
            custom_sections=[],
        )
    return EuConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids or []),
        custom_sections=list(row.custom_sections or []),
    )


def update_config(
    db: Session,
    *,
    user_id: str,
    report_length: str,
    enabled_section_ids: list[str],
    custom_sections: list[dict],
) -> EuConfigDTO:
    if report_length not in _VALID_LENGTHS:
        raise ValueError(f"invalid report_length: {report_length!r}")
    for cs in custom_sections:
        if not isinstance(cs, dict) or not cs.get("title"):
            raise ValueError("custom section requires a non-empty title")
        if not cs.get("id"):
            raise ValueError("custom section requires an id")

    row = db.query(EuUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        row = EuUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            report_length=report_length,
            enabled_section_ids=list(enabled_section_ids),
            custom_sections=list(custom_sections),
        )
        db.add(row)
    else:
        row.report_length = report_length
        row.enabled_section_ids = list(enabled_section_ids)
        row.custom_sections = list(custom_sections)
    db.commit()
    return EuConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids),
        custom_sections=list(row.custom_sections),
    )
