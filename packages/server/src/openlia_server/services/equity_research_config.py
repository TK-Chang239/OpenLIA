"""Per-user Equity Research configuration service.

Provides CRUD + defaults + resolve_active for ErUserConfig rows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from openlia.reports.frameworks.loader import CustomSection, load_framework
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import ErUserConfig

ReportMode = Literal["stock_initiation", "stock_update", "sector_research"]
ReportLength = Literal["concise", "normal", "elaborative"]

_VALID_MODES: tuple[ReportMode, ...] = (
    "stock_initiation",
    "stock_update",
    "sector_research",
)
_VALID_LENGTHS: tuple[ReportLength, ...] = ("concise", "normal", "elaborative")


@dataclass(frozen=True)
class CustomSectionDTO:
    id: str
    title: str
    description: str | None


@dataclass(frozen=True)
class ErConfigDTO:
    report_mode: ReportMode
    report_length: ReportLength
    sections_by_mode: dict[ReportMode, list[str]]
    custom_sections_by_mode: dict[ReportMode, list[CustomSectionDTO]]


@dataclass(frozen=True)
class ActiveReportConfig:
    mode: ReportMode
    report_length: ReportLength
    enabled_section_ids: tuple[str, ...]
    custom_sections: tuple[CustomSection, ...]


def _framework_section_ids(mode: ReportMode) -> set[str]:
    data = load_framework(mode)
    return {s["id"] for s in data.get("sections", [])}


def _default_sections_by_mode() -> dict[ReportMode, list[str]]:
    return {mode: sorted(_framework_section_ids(mode)) for mode in _VALID_MODES}


def _default_custom_sections_by_mode() -> dict[ReportMode, list[CustomSectionDTO]]:
    return {mode: [] for mode in _VALID_MODES}


def _validate_mode_key(mode: str) -> None:
    if mode not in _VALID_MODES:
        raise ValueError(f"unknown mode {mode!r}")


def _row_to_dto(row: ErUserConfig) -> ErConfigDTO:
    sections_by_mode: dict[ReportMode, list[str]] = {}
    raw_sections = row.sections_by_mode or {}
    for mode in _VALID_MODES:
        sections_by_mode[mode] = list(raw_sections.get(mode, []))

    custom_by_mode: dict[ReportMode, list[CustomSectionDTO]] = {}
    raw_custom = row.custom_sections_by_mode or {}
    for mode in _VALID_MODES:
        items = raw_custom.get(mode, [])
        custom_by_mode[mode] = [
            CustomSectionDTO(
                id=item["id"],
                title=item["title"],
                description=item.get("description"),
            )
            for item in items
        ]

    return ErConfigDTO(
        report_mode=row.report_mode,  # type: ignore[arg-type]
        report_length=row.report_length,  # type: ignore[arg-type]
        sections_by_mode=sections_by_mode,
        custom_sections_by_mode=custom_by_mode,
    )


def _custom_dto_to_json(items: list[CustomSectionDTO]) -> list[dict]:
    return [{"id": item.id, "title": item.title, "description": item.description} for item in items]


class EquityResearchConfigService:
    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def _get_or_create_row(self, user_id: str) -> ErUserConfig:
        row = self._db.query(ErUserConfig).filter(ErUserConfig.user_id == user_id).one_or_none()
        if row is not None:
            return row

        default_sections = _default_sections_by_mode()
        default_custom = _default_custom_sections_by_mode()
        row = ErUserConfig(
            id=str(uuid4()),
            user_id=user_id,
            report_mode="stock_initiation",
            report_length="normal",
            sections_by_mode=default_sections,
            custom_sections_by_mode={mode: [] for mode in default_custom},
        )
        self._db.add(row)
        self._db.flush()
        return row

    def get_config(self, user_id: str) -> ErConfigDTO:
        row = self._get_or_create_row(user_id)
        return _row_to_dto(row)

    def update_config(
        self,
        user_id: str,
        *,
        report_mode: ReportMode | None,
        report_length: ReportLength | None,
        sections_by_mode: dict[str, list[str]] | None,
        custom_sections_by_mode: dict[str, list[CustomSectionDTO]] | None,
    ) -> ErConfigDTO:
        if report_mode is not None and report_mode not in _VALID_MODES:
            raise ValueError(f"unknown mode {report_mode!r}")
        if report_length is not None and report_length not in _VALID_LENGTHS:
            raise ValueError(f"invalid report_length {report_length!r}")

        if sections_by_mode is not None:
            for mode_key, ids in sections_by_mode.items():
                _validate_mode_key(mode_key)
                known = _framework_section_ids(mode_key)  # type: ignore[arg-type]
                unknown = [sid for sid in ids if sid not in known]
                if unknown:
                    raise ValueError(f"unknown section id(s) for {mode_key}: {sorted(unknown)}")

        if custom_sections_by_mode is not None:
            for mode_key in custom_sections_by_mode:
                _validate_mode_key(mode_key)

        row = self._get_or_create_row(user_id)

        if report_mode is not None:
            row.report_mode = report_mode
        if report_length is not None:
            row.report_length = report_length

        if sections_by_mode is not None:
            merged = dict(row.sections_by_mode or {})
            for mode_key, ids in sections_by_mode.items():
                merged[mode_key] = list(ids)
            row.sections_by_mode = merged

        if custom_sections_by_mode is not None:
            merged_custom = dict(row.custom_sections_by_mode or {})
            for mode_key, items in custom_sections_by_mode.items():
                merged_custom[mode_key] = _custom_dto_to_json(items)
            row.custom_sections_by_mode = merged_custom

        self._db.flush()
        return _row_to_dto(row)

    def resolve_active(self, cfg: ErConfigDTO, *, mode: ReportMode) -> ActiveReportConfig:
        _validate_mode_key(mode)
        enabled = tuple(cfg.sections_by_mode.get(mode, []))
        customs = tuple(
            CustomSection(id=c.id, title=c.title, description=c.description)
            for c in cfg.custom_sections_by_mode.get(mode, [])
        )
        return ActiveReportConfig(
            mode=mode,
            report_length=cfg.report_length,
            enabled_section_ids=enabled,
            custom_sections=customs,
        )
