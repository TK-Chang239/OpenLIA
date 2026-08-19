"""Panic Thermometer dashboard orchestrator."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.formula import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    evaluate_ruleset,
)
from openlia.panic_thermometer.composite import compute_composite
from openlia.panic_thermometer.panels import PANELS
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import PtTriggerEvent
from openlia_server.scheduler.registry import NotificationType
from openlia_server.scheduler.services import notifications as notifications_svc
from openlia_server.services.pt_config import PtConfigService


class DataDispatcher(Protocol):
    def fetch(
        self,
        *,
        requirement: str,
        panel_id: str,
        params: dict[str, Any],
    ) -> Any: ...


@dataclass
class DashboardPayload:
    panels: dict[str, dict[str, Any]]
    composite: dict[str, Any]
    generated_at: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class FormulaTestResult:
    value: float | bool | None
    resolved_values: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


@dataclass
class RulesetPreviewResult:
    status: str
    matched_rule_index: int
    label: str
    resolved_values: dict[str, Any]
    derived_scalars: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def _panel_result_dict(
    panel_id: str,
    *,
    status: str,
    label: str,
    resolved_values: dict[str, Any],
    derived_scalars: dict[str, Any],
    extras: dict[str, Any],
    warnings: list[str],
    raw_series: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "status": status,
        "label": label,
        "resolved_values": resolved_values,
        "derived_scalars": derived_scalars,
        # Full panel scalar readings (survey levels, matched headlines, keyword
        # flags, ...) so the viewer can render real values, not a whitelist.
        "extras": extras,
        # Named numeric arrays (price/tip/value series) that back the charts.
        "raw_series": raw_series if raw_series is not None else {},
        # Effective panel params (thresholds, targets, tickers) for the UI.
        "params": params if params is not None else {},
        "warnings": warnings,
    }


def _filter_engine_scalars(scalars: dict[str, Any]) -> dict[str, Any]:
    """Drop non-engine-friendly values (lists, dicts, etc.)."""
    out: dict[str, Any] = {}
    for k, v in scalars.items():
        if v is None or isinstance(v, (bool, int, float, str)):
            out[k] = v
    return out


@dataclass
class PtRunner:
    session_factory: Callable[[], Session]
    dispatcher: DataDispatcher
    engine: FormulaEngine = field(default_factory=FormulaEngine)
    _cache: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)

    def _config_service(self) -> PtConfigService:
        return PtConfigService(session_factory=self.session_factory)

    def compute_dashboard(self, user_id: str) -> DashboardPayload:
        cfg = self._config_service().get_or_create_for_user(user_id)
        panel_statuses: dict[str, str] = {}
        panels_out: dict[str, dict[str, Any]] = {}
        all_warnings: list[str] = []

        for entry in cfg.panel_config:
            panel_id = entry["panel_id"]
            panel = PANELS[panel_id]
            if entry.get("enabled", True) is False:
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status="disabled",
                    label="Panel disabled",
                    resolved_values={},
                    derived_scalars={},
                    extras={},
                    params=entry.get("params", {}),
                    warnings=[],
                )
                panel_statuses[panel_id] = "disabled"
                continue

            override = entry.get("manual_override")
            if override and override.get("status"):
                note = (override.get("note") or "").strip()
                label = f"Manual override: {note}" if note else "Manual override"
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status=override["status"],
                    label=label,
                    resolved_values={},
                    derived_scalars={},
                    extras={"override": override},
                    params=entry.get("params", {}),
                    warnings=[],
                )
                panel_statuses[panel_id] = override["status"]
                continue

            payloads: dict[str, Any] = {}
            fetch_warnings: list[str] = []
            for req in panel.required_requirements:
                try:
                    payloads[req] = self.dispatcher.fetch(
                        requirement=req,
                        panel_id=panel_id,
                        params=entry.get("params", {}),
                    )
                except Exception as exc:
                    fetch_warnings.append(f"{panel_id}: {req} fetch failed: {exc}")
                    payloads[req] = None
            for req in panel.optional_requirements:
                try:
                    payloads[req] = self.dispatcher.fetch(
                        requirement=req,
                        panel_id=panel_id,
                        params=entry.get("params", {}),
                    )
                except Exception as exc:
                    fetch_warnings.append(f"{panel_id}: optional {req} fetch failed: {exc}")
                    payloads[req] = None

            built = panel.build_context(panel_config=entry, payloads=payloads)
            self._cache[(user_id, panel_id)] = {
                "scalars": built.scalars,
                "raw_series": built.raw_series,
                "params": entry.get("params", {}),
                "streak_condition": entry.get("streak_condition"),
                "rules": entry["rules"],
            }

            try:
                result = evaluate_ruleset(
                    {
                        "rules": entry["rules"],
                        "streak_condition": entry.get("streak_condition"),
                    },
                    built.raw_series,
                    _filter_engine_scalars(built.scalars),
                    params=entry.get("params", {}),
                    engine=self.engine,
                )
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status=result.status,
                    label=result.label,
                    resolved_values=result.resolved_values,
                    derived_scalars=result.derived_scalars,
                    extras=dict(built.scalars),
                    raw_series=built.raw_series,
                    params=entry.get("params", {}),
                    warnings=result.warnings + fetch_warnings + built.warnings,
                )
                panel_statuses[panel_id] = result.status
            except FormulaError as exc:
                msg = f"{panel_id}: formula error: {exc}"
                all_warnings.append(msg)
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status="disabled",
                    label="Configuration error",
                    resolved_values={},
                    derived_scalars={},
                    extras={},
                    params=entry.get("params", {}),
                    warnings=[msg],
                )
                panel_statuses[panel_id] = "disabled"

        composite = compute_composite(panel_statuses, cfg.composite_settings)
        composite_dict = {
            "level": composite.level,
            "score": composite.score,
            "red_count": composite.red_count,
            "mode": composite.mode,
        }
        self._record_level_transition(
            user_id=user_id,
            composite=composite_dict,
            panel_statuses=panel_statuses,
        )
        return DashboardPayload(
            panels=panels_out,
            composite=composite_dict,
            generated_at=datetime.now(UTC).isoformat(),
            warnings=all_warnings,
        )

    def _record_level_transition(
        self,
        *,
        user_id: str,
        composite: dict[str, Any],
        panel_statuses: dict[str, str],
    ) -> None:
        """Insert a PtTriggerEvent + notification when composite level changes."""

        with self.session_factory() as session:
            try:
                stmt = (
                    select(PtTriggerEvent)
                    .where(PtTriggerEvent.user_id == user_id)
                    .order_by(desc(PtTriggerEvent.occurred_at))
                    .limit(1)
                )
                latest = session.execute(stmt).scalar_one_or_none()
                new_level = composite["level"]
                if latest is not None and latest.level_to == new_level:
                    return

                from_level = latest.level_to if latest is not None else None
                now = datetime.now(UTC)
                event = PtTriggerEvent(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    level_from=from_level,
                    level_to=new_level,
                    occurred_at=now,
                    payload_json={
                        "composite": composite,
                        "panel_statuses": panel_statuses,
                    },
                )
                session.add(event)

                message = (
                    f"Panic level: {from_level} -> {new_level}"
                    if from_level
                    else f"Panic level: {new_level}"
                )
                notifications_svc.insert(
                    session,
                    user_id=user_id,
                    type=NotificationType.PANIC_LEVEL_CHANGE,
                    department="panic_thermometer",
                    message=message,
                    job_run_id=None,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def cached_panel_inputs(self, user_id: str, panel_id: str) -> dict[str, Any] | None:
        return self._cache.get((user_id, panel_id))

    def test_formula(
        self,
        user_id: str,
        panel_id: str,
        formula: str,
        *,
        params_override: dict[str, Any],
    ) -> FormulaTestResult:
        cached = self._cache.get((user_id, panel_id))
        if cached is None:
            raise ValueError("no cached panel data - run dashboard once first")
        merged_params = {**cached["params"], **params_override}
        ctx = EvaluationContext.from_raw_series(
            cached["raw_series"],
            _filter_engine_scalars(cached["scalars"]),
            merged_params,
        )
        result = self.engine.evaluate_safe(formula, ctx)
        # Resolve identifiers referenced for UI display.
        from openlia.formula import parse_formula as _parse

        parsed = _parse(formula)
        resolved: dict[str, Any] = {}
        for name in parsed.identifiers:
            if name in ctx.values:
                resolved[name] = ctx.values[name]
        return FormulaTestResult(
            value=result.value,
            resolved_values=resolved,
            warnings=result.warnings,
        )

    def preview_ruleset(
        self,
        user_id: str,
        panel_id: str,
        ruleset_dict: dict[str, Any],
    ) -> RulesetPreviewResult:
        cached = self._cache.get((user_id, panel_id))
        if cached is None:
            raise ValueError("no cached panel data - run dashboard once first")
        params = ruleset_dict.get("params") or cached["params"]
        result = evaluate_ruleset(
            {
                "rules": ruleset_dict.get("rules", []),
                "streak_condition": ruleset_dict.get("streak_condition"),
            },
            cached["raw_series"],
            _filter_engine_scalars(cached["scalars"]),
            params=params,
            engine=self.engine,
        )
        return RulesetPreviewResult(
            status=result.status,
            matched_rule_index=result.matched_rule_index
            if result.matched_rule_index is not None
            else -1,
            label=result.label,
            resolved_values=result.resolved_values,
            derived_scalars=result.derived_scalars,
            warnings=result.warnings,
        )

    def parse_formula(self, formula: str) -> list[str]:
        """Parse-only validation. Raises FormulaError on bad syntax.

        Returns identifier names referenced in the formula.
        """
        from openlia.formula import parse_formula as _parse

        return _parse(formula).identifiers
