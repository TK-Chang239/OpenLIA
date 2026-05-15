"""Per-user Equity Research configuration service.

Provides CRUD + defaults + resolve_active for ErUserConfig rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from openlia.reports.frameworks.loader import CustomSection, load_framework
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import ErTemplate, ErUserConfig

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
    selected_template_id_by_mode: dict[ReportMode, str]
    # Per-mode override for the LLM web-search budget. Modes absent from
    # this map use the framework's `web_search_budget_default`. Phase 5f.
    web_search_budgets_by_mode: dict[ReportMode, int] = field(default_factory=dict)


@dataclass(frozen=True)
class ActiveReportConfig:
    mode: ReportMode
    report_length: ReportLength
    enabled_section_ids: tuple[str, ...]
    custom_sections: tuple[CustomSection, ...]
    template_id: str | None = None
    template_name: str | None = None
    template_text: str | None = None
    # Resolved per-mode budget for this report run, or None to defer to
    # the framework default at the runtime layer.
    web_search_budget: int | None = None


def _framework_section_ids(mode: ReportMode) -> set[str]:
    data = load_framework(mode)
    return {s["id"] for s in data.get("sections", [])}


def _framework_section_id_list(mode: ReportMode) -> list[str]:
    data = load_framework(mode)
    return [s["id"] for s in data.get("sections", [])]


def _default_sections_by_mode() -> dict[ReportMode, list[str]]:
    return {mode: _framework_section_id_list(mode) for mode in _VALID_MODES}


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

    raw_selected = row.selected_template_id_by_mode or {}
    selected_by_mode: dict[ReportMode, str] = {}
    for mode in _VALID_MODES:
        selected_by_mode[mode] = str(raw_selected.get(mode, "default") or "default")

    raw_budgets = row.web_search_budgets_by_mode or {}
    budgets_by_mode: dict[ReportMode, int] = {}
    for mode_key, v in raw_budgets.items():
        if mode_key in _VALID_MODES and isinstance(v, int) and not isinstance(v, bool) and v > 0:
            budgets_by_mode[mode_key] = v  # type: ignore[index]

    return ErConfigDTO(
        report_mode=row.report_mode,  # type: ignore[arg-type]
        report_length=row.report_length,  # type: ignore[arg-type]
        sections_by_mode=sections_by_mode,
        custom_sections_by_mode=custom_by_mode,
        selected_template_id_by_mode=selected_by_mode,
        web_search_budgets_by_mode=budgets_by_mode,
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
        report_mode: ReportMode | None = None,
        report_length: ReportLength | None = None,
        sections_by_mode: dict[str, list[str]] | None = None,
        custom_sections_by_mode: dict[str, list[CustomSectionDTO]] | None = None,
        selected_template_id_by_mode: dict[str, str] | None = None,
        web_search_budgets_by_mode: dict[str, int] | None = None,
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

        if selected_template_id_by_mode is not None:
            merged_selected = dict(row.selected_template_id_by_mode or {})
            for mode_key, sel in selected_template_id_by_mode.items():
                _validate_mode_key(mode_key)
                merged_selected[mode_key] = sel or "default"
            row.selected_template_id_by_mode = merged_selected

        if web_search_budgets_by_mode is not None:
            # Validate first so a single bad value doesn't half-write.
            for mode_key, v in web_search_budgets_by_mode.items():
                _validate_mode_key(mode_key)
                if not isinstance(v, int) or isinstance(v, bool) or v <= 0:
                    raise ValueError(
                        f"web_search budget for {mode_key!r} must be a positive int, "
                        f"got {v!r}"
                    )
            merged_budgets = dict(row.web_search_budgets_by_mode or {})
            merged_budgets.update(web_search_budgets_by_mode)
            row.web_search_budgets_by_mode = merged_budgets

        self._db.flush()
        return _row_to_dto(row)

    def resolve_active(
        self,
        cfg: ErConfigDTO,
        *,
        mode: ReportMode,
        user_id: str | None = None,
    ) -> ActiveReportConfig:
        _validate_mode_key(mode)
        budget = cfg.web_search_budgets_by_mode.get(mode)
        selected_id = cfg.selected_template_id_by_mode.get(mode, "default")
        if selected_id and selected_id != "default":
            row = self._db.get(ErTemplate, selected_id)
            if row is not None and _user_can_see(row, user_id):
                return ActiveReportConfig(
                    mode=mode,
                    report_length=cfg.report_length,
                    enabled_section_ids=(),
                    custom_sections=(),
                    template_id=row.id,
                    template_name=row.name,
                    template_text=row.extracted_text,
                    web_search_budget=budget,
                )

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
            web_search_budget=budget,
        )


def _user_can_see(row: ErTemplate, user_id: str | None) -> bool:
    if row.owner_scope == "global":
        return True
    return row.owner_scope == "user" and row.owner_user_id == user_id
