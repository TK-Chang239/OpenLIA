"""Per-user Morning Briefing config: sections, topics, custom sections, length, reference portfolio toggle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from openlia_server.db.models.departments import MbUserConfig

STANDARD_SECTION_IDS: tuple[str, ...] = (
    "executive_summary",
    "global_macro",
    "country_news",
    "market_news",
    "sector_news",
    "stock_news",
    "upcoming_preview",
)

_VALID_LENGTHS = frozenset({"concise", "normal", "elaborative"})
_STANDARD_SECTION_SET = frozenset(STANDARD_SECTION_IDS)


@dataclass(frozen=True)
class MbConfigDTO:
    report_length: str
    enabled_section_ids: list[str]
    section_topics: dict[str, list[dict]]
    custom_sections: list[dict]
    reference_portfolio: bool


def get_config(db: Session, *, user_id: str) -> MbConfigDTO:
    row = db.query(MbUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return MbConfigDTO(
            report_length="normal",
            enabled_section_ids=list(STANDARD_SECTION_IDS),
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    return MbConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids or []),
        section_topics=dict(row.section_topics or {}),
        custom_sections=list(row.custom_sections or []),
        reference_portfolio=bool(row.reference_portfolio),
    )


def update_config(
    db: Session,
    *,
    user_id: str,
    report_length: str,
    enabled_section_ids: list[str],
    section_topics: dict[str, list[dict]],
    custom_sections: list[dict],
    reference_portfolio: bool,
) -> MbConfigDTO:
    if report_length not in _VALID_LENGTHS:
        raise ValueError(f"invalid report_length: {report_length!r}")

    for sid in enabled_section_ids:
        if sid not in _STANDARD_SECTION_SET:
            raise ValueError(f"unknown section id: {sid!r}")

    for sid, topics in section_topics.items():
        if sid not in _STANDARD_SECTION_SET:
            raise ValueError(f"unknown section id in topics: {sid!r}")
        for t in topics:
            if not isinstance(t, dict) or not t.get("topic"):
                raise ValueError(
                    f"topic entry requires non-empty 'topic' in section {sid!r}"
                )

    for cs in custom_sections:
        if not isinstance(cs, dict) or not cs.get("title"):
            raise ValueError("custom section requires a non-empty title")
        if not cs.get("id"):
            raise ValueError("custom section requires an id")

    row = db.query(MbUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        row = MbUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            report_length=report_length,
            enabled_section_ids=list(enabled_section_ids),
            section_topics=dict(section_topics),
            custom_sections=list(custom_sections),
            reference_portfolio=bool(reference_portfolio),
        )
        db.add(row)
    else:
        row.report_length = report_length
        row.enabled_section_ids = list(enabled_section_ids)
        row.section_topics = dict(section_topics)
        row.custom_sections = list(custom_sections)
        row.reference_portfolio = bool(reference_portfolio)
    db.commit()
    return MbConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids),
        section_topics=dict(row.section_topics),
        custom_sections=list(row.custom_sections),
        reference_portfolio=bool(row.reference_portfolio),
    )
