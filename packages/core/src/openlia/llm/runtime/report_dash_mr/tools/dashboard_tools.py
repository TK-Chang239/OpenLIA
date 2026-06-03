"""Output + quant tools for the dashboard engine. emit_dashboard validates
the model's payload against the typed contract and finalizes the run; the
quant tool wraps the deterministic core classifier so the model never
invents the computed numbers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from openlia.macro_research.payloads import DebtCycleData
from openlia.macro_research.quant.classification import (
    DebtCycleInputs,
    classify_debt_cycle,
)

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ...report_v2_3.schemas import ComputedSource

PAYLOAD_MODEL_BY_SLUG: dict[str, type[BaseModel]] = {"debt_cycle": DebtCycleData}


def implemented_dashboard_slugs() -> frozenset[str]:
    """Slugs the engine can actually generate — the single source of truth.

    Backed by ``PAYLOAD_MODEL_BY_SLUG``. Scheduling and on-demand refresh
    gate against this so they never queue a dashboard the engine cannot
    produce.
    """
    return frozenset(PAYLOAD_MODEL_BY_SLUG)


def build_emit_dashboard_tool(workspace: Any, payload_model: type[BaseModel]) -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        raw = args.get("payload")
        if not isinstance(raw, dict):
            raise ToolExecutionError(
                "emit_dashboard requires a `payload` object matching the dashboard schema."
            )
        try:
            validated = payload_model.model_validate(raw)
        except ValidationError as exc:
            raise ToolExecutionError(
                f"Invalid {payload_model.__name__} payload: "
                f"{exc.errors(include_url=False, include_context=False)}"
            ) from exc
        workspace.set_payload(validated)
        return ToolResult(
            payload={"ok": True, "dashboard": payload_model.__name__},
            provenance=ComputedSource(method="emit_dashboard", derived_from=["(workspace)"]),
            summary=f"Emitted {payload_model.__name__}.",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="emit_dashboard",
            description=(
                "Emit the final, complete dashboard as a single JSON object in `payload`, "
                "matching the dashboard schema in the system prompt. Call once, last, after "
                "gathering data and classifying. Every numeric field must trace to a tool "
                "result or classify_debt_cycle output."
            ),
            parameters={
                "type": "object",
                "properties": {"payload": {"type": "object"}},
                "required": ["payload"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


def build_classify_debt_cycle_tool() -> ResearchTool:
    def _execute(args: dict[str, Any]) -> ToolResult:
        try:
            out = classify_debt_cycle(
                DebtCycleInputs(
                    debt_gdp=float(args["debt_gdp"]),
                    interest_revenue=float(args["interest_revenue"]),
                    tips_real_yield=float(args["tips_real_yield"]),
                    dxy=float(args["dxy"]),
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "classify_debt_cycle requires numeric debt_gdp, interest_revenue, "
                f"tips_real_yield, dxy. {exc}"
            ) from exc
        return ToolResult(
            payload={
                "phase": out.phase,
                "severity": out.severity,
                "indicator_statuses": out.indicator_statuses,
                "monetary_space": out.monetary_space,
            },
            provenance=ComputedSource(method="classify_debt_cycle", derived_from=["(inputs)"]),
            summary=f"phase={out.phase} severity={out.severity}",
        )

    return ResearchTool(
        descriptor=ToolDescriptor(
            name="classify_debt_cycle",
            description=(
                "Deterministic Dalio debt-cycle phase + RAG classification from the four "
                "indicators. Pass the latest values you gathered; use the returned phase, "
                "severity, indicator_statuses, and monetary_space verbatim in the payload."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "debt_gdp": {"type": "number", "description": "Govt gross debt as % of GDP"},
                    "interest_revenue": {
                        "type": "number",
                        "description": "Federal interest as % of revenue",
                    },
                    "tips_real_yield": {"type": "number", "description": "10y TIPS real yield, %"},
                    "dxy": {"type": "number", "description": "US dollar index level"},
                },
                "required": ["debt_gdp", "interest_revenue", "tips_real_yield", "dxy"],
                "additionalProperties": False,
            },
        ),
        execute=_execute,
    )


# Per-slug deterministic classify-tool builders. A slug present here gets its
# classifier tool added to the catalog alongside emit_dashboard. New dashboards
# register their builder here.
CLASSIFY_TOOL_BY_SLUG: dict[str, Callable[[], ResearchTool]] = {
    "debt_cycle": build_classify_debt_cycle_tool,
}
