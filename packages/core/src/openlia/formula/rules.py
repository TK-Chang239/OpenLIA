"""Rule, RuleSet, evaluate_ruleset and compute_streak — engine surface for panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.formula.derived import (
    RESERVED_NAMES,
    compute_derived_scalars,
    compute_derived_series,
)
from openlia.formula.engine import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    _collect_identifiers,
)
from openlia.formula.parser import Expression, parse


@dataclass(frozen=True)
class Rule:
    status: str
    formula: str
    label: str = ""


@dataclass(frozen=True)
class RuleSet:
    rules: tuple[Rule, ...]
    params: dict[str, Any] = field(default_factory=dict)
    streak_condition: str | None = None


@dataclass
class PanelResult:
    status: str
    matched_rule_index: int | None
    label: str
    resolved_values: dict[str, Any]
    derived_scalars: dict[str, float | None]
    warnings: list[str] = field(default_factory=list)


_DEFAULT_NO_MATCH_STATUS = "green"
_DEFAULT_NO_MATCH_LABEL = "No rule matched"


class _MissingFallbackDict(dict):
    """str.format_map source that leaves unknown placeholders intact."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _coerce_rules(rules: list[dict[str, Any]] | tuple[Rule, ...]) -> tuple[Rule, ...]:
    out: list[Rule] = []
    for r in rules:
        if isinstance(r, Rule):
            out.append(r)
        else:
            out.append(
                Rule(
                    status=str(r["status"]),
                    formula=str(r.get("formula", "true")),
                    label=str(r.get("label", "")),
                )
            )
    return tuple(out)


def evaluate_ruleset(
    ruleset: RuleSet | dict[str, Any],
    raw_series: dict[str, list[float]],
    scalars: dict[str, Any] | None = None,
    *,
    params: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    engine: FormulaEngine | None = None,
) -> PanelResult:
    if isinstance(ruleset, dict):
        rules = _coerce_rules(ruleset.get("rules", []))
        rs_params = dict(ruleset.get("params") or {})
        streak_condition = ruleset.get("streak_condition")
    else:
        rules = ruleset.rules
        rs_params = dict(ruleset.params)
        streak_condition = ruleset.streak_condition

    final_params: dict[str, Any] = dict(rs_params)
    if params:
        final_params.update(params)
    scalars = dict(scalars or {})

    # Validate that callers do not shadow reserved names.
    for name in RESERVED_NAMES:
        if name in scalars:
            raise FormulaError(
                f"reserved derived scalar {name!r} cannot be set in scalars",
                identifier=name,
            )
        if name in final_params:
            raise FormulaError(
                f"reserved derived scalar {name!r} cannot be set in params",
                identifier=name,
            )

    derived = compute_derived_scalars(raw_series)
    warnings: list[str] = []

    streak_days: int | None = None
    needs_streak = any("streak_days" in r.formula for r in rules)
    if needs_streak:
        if not streak_condition:
            raise FormulaError(
                "rule references 'streak_days' but ruleset has no streak_condition",
                identifier="streak_days",
            )
        try:
            streak_days = compute_streak(
                streak_condition,
                raw_series,
                scalars=scalars,
                params=final_params,
                events=events,
            )
        except FormulaError as exc:
            warnings.append(f"streak: {exc}")
            streak_days = 0

    eng = engine or FormulaEngine()
    ctx = _build_context(
        raw_series=raw_series,
        scalars=scalars,
        params=final_params,
        derived=derived,
        events=events,
        streak_days=streak_days,
    )
    accumulated_resolved: dict[str, Any] = {}

    for idx, rule in enumerate(rules):
        try:
            tree = parse(rule.formula)
            result = eng.evaluate(tree, ctx)
            accumulated_resolved.update(_resolve_referenced(tree, ctx))
            warnings.extend(getattr(eng, "last_warnings", []) or [])
            if bool(result):
                label = _interpolate_label(rule.label, ctx, streak_days=streak_days)
                derived_out = dict(derived)
                if streak_days is not None:
                    derived_out["streak_days"] = float(streak_days)
                return PanelResult(
                    status=rule.status,
                    matched_rule_index=idx,
                    label=label,
                    resolved_values=accumulated_resolved,
                    derived_scalars=derived_out,
                    warnings=warnings,
                )
        except FormulaError as exc:
            warnings.append(f"rule {idx}: {exc}")
            continue

    derived_out = dict(derived)
    if streak_days is not None:
        derived_out["streak_days"] = float(streak_days)
    return PanelResult(
        status=_DEFAULT_NO_MATCH_STATUS,
        matched_rule_index=None,
        label=_DEFAULT_NO_MATCH_LABEL,
        resolved_values=accumulated_resolved,
        derived_scalars=derived_out,
        warnings=warnings,
    )


def _build_context(
    *,
    raw_series: dict[str, list[float]],
    scalars: dict[str, Any],
    params: dict[str, Any],
    derived: dict[str, float | None],
    events: list[dict[str, Any]] | None,
    streak_days: int | None,
) -> EvaluationContext:
    values: dict[str, float | bool | str | None] = {}
    for k, v in params.items():
        values[k] = _coerce(v)
    for k, v in scalars.items():
        values[k] = _coerce(v)
    for k, v in derived.items():
        values[k] = v
    if streak_days is not None:
        values["streak_days"] = float(streak_days)
    history = {k: list(v) for k, v in raw_series.items()}
    return EvaluationContext(values=values, history=history, events=list(events or []))


def _coerce(v: Any) -> float | bool | str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return v
    return v


def _resolve_referenced(tree: Expression, ctx: EvaluationContext) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for name in _collect_identifiers(tree):
        if name in ctx.values:
            resolved[name] = ctx.values[name]
    return resolved


def _interpolate_label(
    template: str,
    ctx: EvaluationContext,
    *,
    streak_days: int | None,
) -> str:
    source: dict[str, Any] = dict(ctx.values)
    if streak_days is not None:
        source["streak_days"] = streak_days
    try:
        return template.format_map(_MissingFallbackDict(source))
    except (IndexError, ValueError):
        return template


def compute_streak(
    streak_condition: str | Expression,
    raw_series: dict[str, list[float]],
    scalars: dict[str, Any] | None = None,
    *,
    params: dict[str, Any] | None = None,
    events: list[dict[str, Any]] | None = None,
    engine: FormulaEngine | None = None,
) -> int:
    """Backtest `streak_condition` newest-first; return consecutive-true tail count.

    Recomputes reserved derived scalars (`ma200`, `atr_14`, `std_20`, ...) as
    of each historical bar so MA-relative conditions are evaluated against
    the historical threshold, not today's.
    """

    closes = raw_series.get("price") or []
    if not closes:
        return 0
    eng = engine or FormulaEngine()
    tree = parse(streak_condition) if isinstance(streak_condition, str) else streak_condition

    derived_full = compute_derived_series(raw_series)
    scalars = dict(scalars or {})
    params = dict(params or {})
    n = len(closes)
    count = 0

    for i in range(n - 1, -1, -1):
        per_bar_values: dict[str, float | bool | str | None] = {}
        for k, v in params.items():
            per_bar_values[k] = _coerce(v)
        for k, v in scalars.items():
            per_bar_values[k] = _coerce(v)
        # Override scalars with per-bar reserved derived values.
        for name, series in derived_full.items():
            per_bar_values[name] = series[i] if i < len(series) else None
        # Rebuild the trailing series window for any history-aware function.
        bar_history = {k: list(v[: i + 1]) for k, v in raw_series.items()}
        ctx = EvaluationContext(
            values=per_bar_values,
            history=bar_history,
            events=list(events or []),
        )
        try:
            result = eng.evaluate(tree, ctx)
        except FormulaError:
            break
        if bool(result):
            count += 1
        else:
            break

    return count
