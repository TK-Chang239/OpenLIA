"""Equity Research orchestrator — config + ReportRunner + reports service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

from openlia.departments.equity_research import EquityResearchDepartment
from openlia.llm.runtime.events import ReportComplete, SseEvent
from openlia.llm.runtime.messages import Attachment, ReportRequest
from openlia.reports.validator import validate_report_payload
from sqlalchemy.orm import Session

from openlia_server.services import reports as reports_svc
from openlia_server.services.equity_research_config import (
    EquityResearchConfigService,
)

_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


@dataclass(frozen=True)
class ReportSavedEvent:
    TYPE = "report.saved"
    report_id: str


class _InnerRunner(Protocol):
    def run(
        self,
        *,
        department_id: str,
        user_id: str,
        request: ReportRequest,
        attachments: list[Attachment] | None = ...,
        model_id_override: str | None = ...,
        disabled_connector_ids: tuple[str, ...] = ...,
        disabled_skill_ids: tuple[str, ...] = ...,
    ) -> AsyncIterator[SseEvent]: ...


class EquityResearchRunner:
    def __init__(
        self,
        *,
        db_session: Session,
        inner: _InnerRunner,
    ) -> None:
        self._db = db_session
        self._inner = inner
        self._config = EquityResearchConfigService(db_session)
        self._dept = EquityResearchDepartment()

    async def run_report(
        self,
        *,
        user_id: str,
        mode: str,
        user_input: str,
        session_id: str | None,
        attachments: list[Attachment] | None = None,
        model_id_override: str | None = None,
        disabled_connector_ids: tuple[str, ...] = (),
        disabled_skill_ids: tuple[str, ...] = (),
    ) -> AsyncIterator[SseEvent | ReportSavedEvent]:
        if mode not in self._dept.valid_modes:
            raise ValueError(f"unknown equity_research mode: {mode!r}")

        cfg = self._config.get_config(user_id)
        active = self._config.resolve_active(cfg, mode=mode, user_id=user_id)

        custom_section_dicts = [
            {
                "id": c.id,
                "title": c.title,
                "instructions": c.description or "",
                "blocks": [],
            }
            for c in active.custom_sections
        ]

        request = ReportRequest(
            mode=active.mode,
            user_input=user_input,
            enabled_sections=list(active.enabled_section_ids),
            custom_sections=custom_section_dicts,
            length=_LENGTH_MAP.get(active.report_length, "standard"),
            user_template_text=active.template_text,
            user_template_name=active.template_name,
            web_search_budget_override=active.web_search_budget,
        )

        last_complete: ReportComplete | None = None
        async for ev in self._inner.run(
            department_id=self._dept.name,
            user_id=user_id,
            request=request,
            attachments=attachments,
            model_id_override=model_id_override,
            disabled_connector_ids=disabled_connector_ids,
            disabled_skill_ids=disabled_skill_ids,
        ):
            if isinstance(ev, ReportComplete):
                last_complete = ev
            yield ev

        if last_complete is not None:
            schema_obj = validate_report_payload(last_complete.schema)
            report_id = reports_svc.create_report(
                self._db,
                user_id=user_id,
                department=self._dept.name,
                mode=active.mode,
                schema=schema_obj,
                source_session_id=session_id,
            )
            self._db.commit()
            yield ReportSavedEvent(report_id=report_id)
