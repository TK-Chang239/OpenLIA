"""Panic Thermometer dashboard orchestrator."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.formula.requirements import extract_requirements
from openlia.panic_thermometer.composite import compute_composite
from openlia.panic_thermometer.panels import PANELS
from sqlalchemy.orm import Session

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


def _build_context(
    *,
    scalars: dict[str, Any],
    raw_series: dict[str, list[float]],
    params: dict[str, Any],
) -> tuple[EvaluationContext, dict[str, Any]]:
    """Merge scalars + params into EvaluationContext.values; raw_series into history.

    Returns (context, merged_values_for_resolution_audit).
    """
    values: dict[str, float | bool | str] = {}
    for k, v in params.items():
        if isinstance(v, (int, float, bool, str)):
            values[k] = v if isinstance(v, (bool, str)) else float(v)
    for k, v in scalars.items():
        if v is None:
            continue
        if isinstance(v, bool):
            values[k] = v
        elif isinstance(v, (int, float)):
            values[k] = float(v)
        elif isinstance(v, str):
            values[k] = v
    history = {k: list(v) for k, v in raw_series.items()}
    # Derived: streak_days is computed later per-panel; leave unset here.
    return EvaluationContext(values=values, history=history), values


def _evaluate_formula(
    engine: FormulaEngine,
    formula: str,
    *,
    scalars: dict[str, Any],
    raw_series: dict[str, list[float]],
    params: dict[str, Any],
    extra_values: dict[str, Any] | None = None,
) -> tuple[float | bool, dict[str, Any]]:
    ctx, values = _build_context(scalars=scalars, raw_series=raw_series, params=params)
    if extra_values:
        for k, v in extra_values.items():
            if isinstance(v, bool):
                ctx.values[k] = v
            elif isinstance(v, (int, float)):
                ctx.values[k] = float(v)
            elif isinstance(v, str):
                ctx.values[k] = v
            values[k] = v
    result = engine.evaluate(formula, ctx)
    # Resolve the identifiers referenced in the formula back to their values for UI.
    resolved: dict[str, Any] = {}
    try:
        refs = extract_requirements(formula)
        for ref in refs:
            name = getattr(ref, "name", None) or str(ref)
            if name in values:
                resolved[name] = values[name]
    except Exception:
        pass
    return result, resolved


def _compute_streak_days(
    streak_condition: str | None,
    *,
    engine: FormulaEngine,
    raw_series: dict[str, list[float]],
    scalars: dict[str, Any],
    params: dict[str, Any],
) -> int:
    """Backtest `streak_condition` over the trailing close series.

    Returns the number of most-recent consecutive True evaluations.
    If no `price` series is available, returns 0. Per-day context uses the
    day's close as `price` and the scalar/param values as-is.
    """
    if not streak_condition:
        return 0
    price_series = raw_series.get("price") or raw_series.get("tip_price") or []
    if not price_series:
        return 0
    # Evaluate newest-first. For each trailing index, replace scalars["price"].
    count = 0
    for p in reversed(price_series):
        try:
            local_scalars = dict(scalars)
            local_scalars["price"] = float(p)
            result, _ = _evaluate_formula(
                engine,
                streak_condition,
                scalars=local_scalars,
                raw_series=raw_series,
                params=params,
            )
            if bool(result):
                count += 1
            else:
                break
        except FormulaError:
            break
    return count


def _evaluate_ruleset(
    engine: FormulaEngine,
    *,
    rules: list[dict[str, Any]],
    streak_condition: str | None,
    scalars: dict[str, Any],
    raw_series: dict[str, list[float]],
    params: dict[str, Any],
) -> RulesetPreviewResult:
    """Evaluate rules in order; first True wins."""
    streak_days = _compute_streak_days(
        streak_condition,
        engine=engine,
        raw_series=raw_series,
        scalars=scalars,
        params=params,
    )
    derived = {"streak_days": streak_days}
    warnings: list[str] = []
    accumulated_resolved: dict[str, Any] = {}
    for idx, rule in enumerate(rules):
        formula = rule.get("formula") or "true"
        try:
            result, resolved = _evaluate_formula(
                engine,
                formula,
                scalars=scalars,
                raw_series=raw_series,
                params=params,
                extra_values={"streak_days": streak_days},
            )
            accumulated_resolved.update(resolved)
            if bool(result):
                label_raw = rule.get("label") or ""
                try:
                    # Interpolate {name} tokens from merged context.
                    label = label_raw.format(**{**scalars, **params, **derived})
                except Exception:
                    label = label_raw
                return RulesetPreviewResult(
                    status=rule["status"],
                    matched_rule_index=idx,
                    label=label,
                    resolved_values=accumulated_resolved,
                    derived_scalars=derived,
                    warnings=warnings,
                )
        except FormulaError as exc:
            warnings.append(f"rule {idx}: {exc}")
            continue
    # No rule matched — return a fallback green status.
    return RulesetPreviewResult(
        status="green",
        matched_rule_index=-1,
        label="No rule matched",
        resolved_values=accumulated_resolved,
        derived_scalars=derived,
        warnings=warnings,
    )


def _panel_result_dict(
    panel_id: str,
    *,
    status: str,
    label: str,
    resolved_values: dict[str, Any],
    derived_scalars: dict[str, Any],
    extras: dict[str, Any],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "status": status,
        "label": label,
        "resolved_values": resolved_values,
        "derived_scalars": derived_scalars,
        "extras": extras,
        "warnings": warnings,
    }


_EXTRA_SCALAR_KEYS = frozenset(
    {
        "matched_progress_headlines",
        "matched_escalation_headlines",
        "matched_phrase",
        "matched_headline",
        "matched_date",
        "days_since_fomc",
        "days_elapsed",
        "days_remaining",
    }
)


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
                result = _evaluate_ruleset(
                    self.engine,
                    rules=entry["rules"],
                    streak_condition=entry.get("streak_condition"),
                    scalars=built.scalars,
                    raw_series=built.raw_series,
                    params=entry.get("params", {}),
                )
                extras = {k: v for k, v in built.scalars.items() if k in _EXTRA_SCALAR_KEYS}
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status=result.status,
                    label=result.label,
                    resolved_values=result.resolved_values,
                    derived_scalars=result.derived_scalars,
                    extras=extras,
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
                    warnings=[msg],
                )
                panel_statuses[panel_id] = "disabled"

        composite = compute_composite(panel_statuses, cfg.composite_settings)
        return DashboardPayload(
            panels=panels_out,
            composite={
                "level": composite.level,
                "score": composite.score,
                "red_count": composite.red_count,
                "mode": composite.mode,
            },
            generated_at=datetime.now(UTC).isoformat(),
            warnings=all_warnings,
        )

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
        try:
            value, resolved = _evaluate_formula(
                self.engine,
                formula,
                scalars=cached["scalars"],
                raw_series=cached["raw_series"],
                params=merged_params,
            )
        except FormulaError:
            raise
        return FormulaTestResult(value=value, resolved_values=resolved, warnings=[])

    def preview_ruleset(
        self,
        user_id: str,
        panel_id: str,
        ruleset_dict: dict[str, Any],
    ) -> RulesetPreviewResult:
        cached = self._cache.get((user_id, panel_id))
        if cached is None:
            raise ValueError("no cached panel data - run dashboard once first")
        return _evaluate_ruleset(
            self.engine,
            rules=ruleset_dict.get("rules", []),
            streak_condition=ruleset_dict.get("streak_condition"),
            scalars=cached["scalars"],
            raw_series=cached["raw_series"],
            params=ruleset_dict.get("params") or cached["params"],
        )

    def parse_formula(self, formula: str) -> list[str]:
        """Parse-only validation. Raises FormulaError on bad syntax.

        Returns identifier names referenced in the formula.
        """
        from openlia.formula.parser import parse as _parse

        _parse(formula)
        try:
            refs = extract_requirements(formula)
            return [getattr(r, "name", None) or str(r) for r in refs]
        except Exception:
            return []
