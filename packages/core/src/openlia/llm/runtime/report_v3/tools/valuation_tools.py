"""Deterministic valuation tools — pure-math DCF / Comps / Sensitivity.

These are v3-native rewrites of the v2.3 ``valuation/`` engines that
take direct numeric inputs instead of ``BundleFact`` references. The
math is the same; the schema dependency is gone, which means the
model passes values directly and the tool returns values directly —
no fact_id indirection.

Each call appends one entry to the v3 ledger so the model can cite
``dcf_1`` / ``comps_1`` / ``sens_1`` in the report body. Provenance
records the input parameters so a reviewer can re-run the math.
"""

from __future__ import annotations

import statistics
from typing import Any

from ...report_v2_3.research import (
    ResearchTool,
    ToolDescriptor,
    ToolExecutionError,
    ToolResult,
)
from ...report_v2_3.schemas import ComputedSource
from ..ledger import CitationLedger

# ---------------------------------------------------------------------------
# DCF
# ---------------------------------------------------------------------------


def _run_dcf_math(args: dict[str, Any]) -> dict[str, Any]:
    revenue_base = float(args["revenue_base"])
    growth_path = [float(g) for g in args["revenue_growth_path"]]
    margin_path = [float(m) for m in args["margin_path"]]
    wacc = float(args["wacc"])
    terminal_growth = float(args["terminal_growth"])
    tax_rate = float(args.get("tax_rate", 0.21))
    net_debt = float(args.get("net_debt", 0.0))
    shares_outstanding = float(args.get("shares_outstanding", 0.0))

    if len(growth_path) != len(margin_path):
        raise ToolExecutionError("revenue_growth_path and margin_path must have equal length.")
    if not growth_path:
        raise ToolExecutionError("revenue_growth_path must be non-empty.")
    if wacc <= terminal_growth:
        raise ToolExecutionError(
            f"wacc ({wacc}) must exceed terminal_growth ({terminal_growth}) "
            f"for Gordon-growth terminal value."
        )

    revenues: list[float] = []
    fcfs: list[float] = []
    rev = revenue_base
    for growth, margin in zip(growth_path, margin_path, strict=True):
        rev = rev * (1.0 + growth)
        revenues.append(rev)
        fcfs.append(rev * margin * (1.0 - tax_rate))

    discount = 1.0 + wacc
    pv_explicit = sum(fcf / (discount ** (year + 1)) for year, fcf in enumerate(fcfs))
    horizon = len(fcfs)
    terminal_fcf = fcfs[-1] * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / (discount**horizon)

    enterprise_value = pv_explicit + pv_terminal
    equity_value = enterprise_value - net_debt
    fair_value_per_share = equity_value / shares_outstanding if shares_outstanding > 0 else None

    return {
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "fair_value_per_share": fair_value_per_share,
        "horizon_years": horizon,
        "projected_revenues": revenues,
        "projected_fcfs": fcfs,
    }


_DCF_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "revenue_base": {
            "type": "number",
            "description": "Most recent annual revenue, in same units as outputs (e.g. USD).",
        },
        "revenue_growth_path": {
            "type": "array",
            "items": {"type": "number"},
            "description": "Per-year growth rates (e.g. 0.25 = 25%). Length = projection horizon.",
        },
        "margin_path": {
            "type": "array",
            "items": {"type": "number"},
            "description": (
                "Per-year FCF margins as fraction of revenue. Same length as growth path."
            ),
        },
        "wacc": {"type": "number", "description": "Weighted average cost of capital (e.g. 0.10)."},
        "terminal_growth": {
            "type": "number",
            "description": "Perpetual growth in Gordon-growth terminal value. Must be < wacc.",
        },
        "tax_rate": {
            "type": "number",
            "description": "Effective tax rate (e.g. 0.21). Default 0.21.",
        },
        "net_debt": {
            "type": "number",
            "description": (
                "Net debt (debt - cash) to bridge enterprise value to equity. Default 0."
            ),
        },
        "shares_outstanding": {
            "type": "number",
            "description": "Share count for per-share output. If 0, per-share value is null.",
        },
    },
    "required": [
        "revenue_base",
        "revenue_growth_path",
        "margin_path",
        "wacc",
        "terminal_growth",
    ],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Comps
# ---------------------------------------------------------------------------


def _run_comps_math(args: dict[str, Any]) -> dict[str, Any]:
    peer_multiples = args["peer_multiples"]  # dict[str, list[float]]
    subject_metrics = args["subject_metrics"]  # dict[str, float]
    if not isinstance(peer_multiples, dict) or not isinstance(subject_metrics, dict):
        raise ToolExecutionError(
            "peer_multiples and subject_metrics must be objects keyed by multiple name."
        )

    implied: dict[str, float] = {}
    medians: dict[str, float] = {}
    for multiple, peers in peer_multiples.items():
        peer_values = [float(v) for v in peers if isinstance(v, (int, float))]
        if not peer_values:
            continue
        median_multiple = statistics.median(peer_values)
        subject_value = subject_metrics.get(multiple)
        if subject_value is None:
            continue
        medians[multiple] = median_multiple
        implied[multiple] = median_multiple * float(subject_value)

    return {
        "implied_value_by_multiple": implied,
        "median_multiple_by_name": medians,
        "n_peers_by_multiple": {
            m: len([v for v in peers if isinstance(v, (int, float))])
            for m, peers in peer_multiples.items()
        },
    }


_COMPS_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "peer_multiples": {
            "type": "object",
            "description": (
                "Map of multiple name (e.g. 'ev_ebitda', 'pe') to a list of peer values. "
                "v3 takes the median of each list."
            ),
            "additionalProperties": {"type": "array", "items": {"type": "number"}},
        },
        "subject_metrics": {
            "type": "object",
            "description": (
                "Map of multiple name to the subject's corresponding metric "
                "(EBITDA for ev_ebitda, EPS for pe, etc.). "
                "Median peer multiple x subject metric = implied value."
            ),
            "additionalProperties": {"type": "number"},
        },
    },
    "required": ["peer_multiples", "subject_metrics"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


def _run_sensitivity_math(args: dict[str, Any]) -> dict[str, Any]:
    base = dict(args["base"])
    row_driver = str(args["row_driver"])
    col_driver = str(args["col_driver"])
    row_values = [float(v) for v in args["row_values"]]
    col_values = [float(v) for v in args["col_values"]]

    grid: list[list[float | None]] = []
    for row_value in row_values:
        row: list[float | None] = []
        for col_value in col_values:
            tweaked = dict(base)
            tweaked[row_driver] = row_value
            tweaked[col_driver] = col_value
            result = _run_dcf_math(tweaked)
            row.append(result.get("fair_value_per_share"))
        grid.append(row)

    return {
        "row_driver": row_driver,
        "col_driver": col_driver,
        "row_values": row_values,
        "col_values": col_values,
        "fair_value_per_share_grid": grid,
    }


_SENSITIVITY_PARAMETERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "base": {
            "type": "object",
            "description": (
                "Base DCF inputs (same shape as run_dcf). Two fields get overridden per cell."
            ),
        },
        "row_driver": {
            "type": "string",
            "description": "Name of the DCF field varied across rows (e.g. 'wacc').",
        },
        "col_driver": {
            "type": "string",
            "description": "Name of the DCF field varied across columns (e.g. 'terminal_growth').",
        },
        "row_values": {"type": "array", "items": {"type": "number"}},
        "col_values": {"type": "array", "items": {"type": "number"}},
    },
    "required": ["base", "row_driver", "col_driver", "row_values", "col_values"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# Tool factory
# ---------------------------------------------------------------------------


def build_valuation_tools(*, ledger: CitationLedger) -> list[ResearchTool]:
    """Return run_dcf, run_comps, run_sensitivity ledger-aware tools."""

    def _make_tool(
        *,
        name: str,
        description: str,
        parameters: dict[str, Any],
        runner: Any,
    ) -> ResearchTool:
        def _execute(args: dict[str, Any]) -> ToolResult:
            try:
                result = runner(args)
            except ToolExecutionError:
                raise
            except Exception as exc:
                raise ToolExecutionError(f"{name} failed: {exc!s}") from exc

            provenance = ComputedSource(
                method=name,
                # v3 doesn't carry a BundleFact graph, so derived_from
                # just records the parameter names the model passed in.
                # The placeholder satisfies the v2.3 ComputedSource
                # min_length validator without inventing fake fact ids.
                derived_from=sorted(args.keys()) or ["(no_inputs)"],
            )
            entry = ledger.append(
                tool_name=name,
                arguments=dict(args),
                result_summary=f"{name} computed",
                provenance=_provenance_to_dict(provenance),
            )
            return ToolResult(
                payload={
                    "source_id": entry.source_id,
                    "result": result,
                },
                provenance=provenance,
                summary=f"{name} -> {entry.source_id}",
            )

        return ResearchTool(
            descriptor=ToolDescriptor(
                name=name,
                description=description,
                parameters=parameters,
            ),
            execute=_execute,
        )

    return [
        _make_tool(
            name="run_dcf",
            description=(
                "Run a 2-stage discounted cash flow. Project FCFs over the "
                "explicit horizon, then Gordon-growth terminal value. Returns "
                "enterprise_value, equity_value, fair_value_per_share. Cite the "
                "returned source_id in any prose that uses these numbers."
            ),
            parameters=_DCF_PARAMETERS,
            runner=_run_dcf_math,
        ),
        _make_tool(
            name="run_comps",
            description=(
                "Apply median peer multiples to subject metrics. Returns implied "
                "value per multiple plus the median peer multiple and peer counts."
            ),
            parameters=_COMPS_PARAMETERS,
            runner=_run_comps_math,
        ),
        _make_tool(
            name="run_sensitivity",
            description=(
                "Sweep a base DCF over two driver values (e.g. wacc x "
                "terminal_growth). Returns a 2D grid of fair_value_per_share. "
                "Use to show how robust the DCF is to assumption changes."
            ),
            parameters=_SENSITIVITY_PARAMETERS,
            runner=_run_sensitivity_math,
        ),
    ]


def _provenance_to_dict(provenance: Any) -> dict[str, Any]:
    if hasattr(provenance, "model_dump"):
        try:
            return provenance.model_dump(mode="json")
        except Exception:
            pass
    return {"raw": str(provenance)}
