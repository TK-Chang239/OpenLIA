"""Orchestrate T1->T5 for a given dashboard."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.macro_research.dashboards import DASHBOARDS
from openlia.macro_research.schemas import (
    DashboardResult,
    DashboardTierOutput,
    SeverityLevel,
)


class _DataProvider(Protocol):
    def fetch(self, *, requirement: str, **kwargs: Any) -> Any: ...


class _LLMClient(Protocol):
    async def run(self, *, prompt: str, **kwargs: Any) -> dict[str, Any]: ...


_SEVERITY_RANK: dict[str, int] = {"neutral": 0, "green": 1, "amber": 2, "red": 3}


def _worst(a: SeverityLevel, b: SeverityLevel) -> SeverityLevel:
    return a if _SEVERITY_RANK[a] >= _SEVERITY_RANK[b] else b


class DashboardAssembler:
    """Runs T1->T5 for one dashboard and returns a DashboardResult."""

    def __init__(
        self,
        *,
        data_provider: _DataProvider,
        llm_client: _LLMClient | None = None,
    ) -> None:
        self._data = data_provider
        self._llm = llm_client
        self._engine = FormulaEngine()

    def run(
        self,
        *,
        dashboard_slug: str,
        user_id: str,
        portfolio: dict[str, float] | None,
        t4_cached: dict[str, Any] | None,
        smart_mode: bool,
    ) -> DashboardResult:
        if dashboard_slug not in DASHBOARDS:
            raise KeyError(f"unknown dashboard: {dashboard_slug!r}")
        dashboard = DASHBOARDS[dashboard_slug]
        now = datetime.now(UTC)

        severity: SeverityLevel = "neutral"
        tiers: list[DashboardTierOutput] = []

        # --- T1 ---
        t1_data: dict[str, Any] = {}
        for req in dashboard.T1_REQUIREMENTS:
            t1_data[req] = self._data.fetch(requirement=req)
        tiers.append(DashboardTierOutput(tier="T1", data={"inputs": t1_data}, generated_at=now))

        # --- T2 ---
        flat_values = self._flatten(t1_data)
        # Merge any metrics already supplied directly by the data provider (tests pass
        # {"force_debt_money": 8} style inputs through FakeDataProvider).
        for req in dashboard.T2_FORMULAS:
            direct = self._data.fetch(requirement=req)
            if isinstance(direct, (int, float, bool)):
                flat_values.setdefault(req, direct)
        typed_values: dict[str, float | bool | str] = {}
        for key, value in flat_values.items():
            if isinstance(value, bool):
                typed_values[key] = value
            elif isinstance(value, (int, float)):
                typed_values[key] = float(value)
            elif isinstance(value, str):
                typed_values[key] = value
        context = EvaluationContext(values=typed_values)

        t2_metrics: dict[str, float] = {}
        t2_errors: list[str] = []
        for name, formula in dashboard.T2_FORMULAS.items():
            try:
                value = self._engine.evaluate(formula, context)
                t2_metrics[name] = float(value)
            except FormulaError as exc:
                t2_errors.append(f"{name}: {exc}")
        tiers.append(
            DashboardTierOutput(tier="T2", data=t2_metrics, errors=t2_errors, generated_at=now)
        )

        # --- T3 ---
        t3_out = dashboard.T3_compute(metrics=t2_metrics, portfolio=portfolio)
        tiers.append(DashboardTierOutput(tier="T3", data=t3_out, generated_at=now))
        if t3_out.get("severity"):
            severity = _worst(severity, t3_out["severity"])

        # --- T4 ---
        if dashboard.T4_PROMPT_KEY is not None:
            if t4_cached is not None:
                tiers.append(
                    DashboardTierOutput(
                        tier="T4",
                        data={
                            "assessment": t4_cached.get("assessment"),
                            "severity": t4_cached.get("severity"),
                            "stage": t4_cached.get("stage"),
                            "active_force_count": t4_cached.get("active_force_count"),
                            "cached": True,
                        },
                        generated_at=t4_cached.get("generated_at"),
                    )
                )
                if t4_cached.get("severity"):
                    severity = _worst(severity, t4_cached["severity"])
            else:
                tiers.append(
                    DashboardTierOutput(
                        tier="T4",
                        data={"assessment": None, "cached": False, "pending": True},
                        generated_at=None,
                    )
                )

        # --- T5 ---
        base_thresholds: dict[str, float] = {}
        if smart_mode:
            adjusted = dashboard.T5_smart_mode_adjustments(
                base_thresholds=base_thresholds,
                context={"smart_mode": True, "t1": t1_data, "t2": t2_metrics, "t3": t3_out},
            )
        else:
            adjusted = base_thresholds
        tiers.append(
            DashboardTierOutput(
                tier="T5",
                data={"smart_mode": smart_mode, "adjustments": adjusted},
                generated_at=now,
            )
        )

        return DashboardResult(
            slug=dashboard.slug,
            display_name=dashboard.display_name,
            severity=severity,
            tiers=tiers,
            headline=self._headline(dashboard.slug, t2_metrics, t3_out, t4_cached),
            generated_at=now,
            smart_mode_active=smart_mode,
        )

    @staticmethod
    def _flatten(data: dict[str, Any]) -> dict[str, Any]:
        """Turn {'stock_quote:TIP': {'price': 110}} -> {'TIP_price': 110,
        'debt_gdp': 120, ...} — scalars keyed by the last colon segment."""
        flat: dict[str, Any] = {}
        for key, value in data.items():
            suffix = key.split(":")[-1] if ":" in key else key
            if isinstance(value, dict):
                for sub, v in value.items():
                    flat[f"{suffix}_{sub}"] = v
            elif isinstance(value, (int, float, bool, str)):
                flat[suffix] = value
        return flat

    @staticmethod
    def _headline(
        slug: str,
        metrics: dict[str, float],
        t3: dict[str, Any],
        t4_cached: dict[str, Any] | None,
    ) -> str:
        if slug == "debt_cycle":
            return t3.get("phase", "Phase unknown")
        if slug == "four_seasons":
            return t3.get("season", "Season unknown")
        if slug == "all_weather":
            return t3.get("overall_coverage_label", "Coverage unknown")
        if slug == "world_order" and t4_cached:
            return t4_cached.get("stage", "Stage unknown")
        if slug == "five_forces" and t4_cached:
            return f"{t4_cached.get('active_force_count', 0)} active forces"
        return ""
