"""sensitivity_table — generic 2-variable sensitivity matrix.

Registered name: "sensitivity_table"

Computes a NxM grid of output values by evaluating a callable f(var1, var2)
over all combinations of two input axes. Emits Plotly HTML heatmap + Markdown
table fallback.

Design ref: planning/2026-05-21-equity-research-helpers-design.md §3.2
"""

from __future__ import annotations

import datetime
import json
from collections.abc import Callable
from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _compute_matrix(
    fn: Callable[[float, float], float],
    var1_values: list[float],
    var2_values: list[float],
) -> list[list[float]]:
    """Return NxM matrix: rows = var1, cols = var2."""
    return [[fn(v1, v2) for v2 in var2_values] for v1 in var1_values]


def _format_val(v: float, precision: int = 2) -> str:
    return f"{v:.{precision}f}"


def _build_markdown_table(
    matrix: list[list[float]],
    var1_label: str,
    var1_values: list[float],
    var2_label: str,
    var2_values: list[float],
    precision: int = 2,
) -> str:
    header = f"| {var1_label} \\ {var2_label} |" + "".join(
        f" {_format_val(v, precision)} |" for v in var2_values
    )
    separator = "|---|" + "---|" * len(var2_values)
    rows = []
    for v1, row in zip(var1_values, matrix, strict=False):
        cells = "".join(f" {_format_val(c, precision)} |" for c in row)
        rows.append(f"| {_format_val(v1, precision)} |{cells}")
    return "\n".join([header, separator, *rows])


def _build_plotly_html(
    matrix: list[list[float]],
    var1_label: str,
    var1_values: list[float],
    var2_label: str,
    var2_values: list[float],
    title: str = "Sensitivity Matrix",
) -> str:
    try:
        import plotly.graph_objects as go  # type: ignore[import-untyped]

        fig = go.Figure(
            data=go.Heatmap(
                z=matrix,
                x=[str(round(v, 4)) for v in var2_values],
                y=[str(round(v, 4)) for v in var1_values],
                colorscale="RdYlGn",
                text=[[f"{c:.2f}" for c in row] for row in matrix],
                texttemplate="%{text}",
                showscale=True,
            )
        )
        fig.update_layout(
            title=title,
            xaxis_title=var2_label,
            yaxis_title=var1_label,
            margin={"l": 60, "r": 20, "t": 50, "b": 50},
        )
        return fig.to_json()
    except ImportError:
        return json.dumps({"error": "plotly not installed"})


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    base_fn: Callable[[float, float], float] | None = None,
    var1_name: str,
    var1_values: list[float],
    var2_name: str,
    var2_values: list[float],
    base_var1: float | None = None,
    base_var2: float | None = None,
    title: str = "Sensitivity Matrix",
    value_precision: int = 2,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    # pre-computed matrix (for callers that already computed values)
    precomputed_matrix: list[list[float]] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compute a 2-variable sensitivity matrix.

    Either provide:
      - base_fn: callable f(var1, var2) -> float  (will be evaluated on the grid), OR
      - precomputed_matrix: list[list[float]] of shape len(var1_values) x len(var2_values).

    Args:
        base_fn: Function to evaluate. Signature: f(var1: float, var2: float) -> float.
        var1_name: Label for axis 1 (rows).
        var1_values: Values for axis 1.
        var2_name: Label for axis 2 (columns).
        var2_values: Values for axis 2.
        base_var1: Base value for var1 (used to identify base row).
        base_var2: Base value for var2 (used to identify base column).
        title: Chart title.
        value_precision: Decimal places in markdown table.
        precomputed_matrix: Pre-computed NxM matrix (alternative to base_fn).
    """
    if not var1_values:
        raise ValueError("var1_values must be non-empty")
    if not var2_values:
        raise ValueError("var2_values must be non-empty")

    if precomputed_matrix is not None:
        if len(precomputed_matrix) != len(var1_values):
            raise ValueError(
                f"precomputed_matrix has {len(precomputed_matrix)} rows but "
                f"var1_values has {len(var1_values)} entries"
            )
        matrix = precomputed_matrix
    elif base_fn is not None:
        matrix = _compute_matrix(base_fn, var1_values, var2_values)
    else:
        raise ValueError("Either base_fn or precomputed_matrix must be provided")

    # Base value lookup
    base_value: float | None = None
    if base_var1 is not None and base_var2 is not None and base_fn is not None:
        base_value = base_fn(base_var1, base_var2)
    elif base_var1 is not None and base_var2 is not None:
        # Find closest in grid
        try:
            r = min(range(len(var1_values)), key=lambda i: abs(var1_values[i] - base_var1))
            c = min(range(len(var2_values)), key=lambda i: abs(var2_values[i] - base_var2))
            base_value = matrix[r][c]
        except (IndexError, ValueError):
            base_value = None

    markdown = _build_markdown_table(
        matrix, var1_name, var1_values, var2_name, var2_values, value_precision
    )
    plotly_html = _build_plotly_html(matrix, var1_name, var1_values, var2_name, var2_values, title)

    return {
        "var1_name": var1_name,
        "var1_values": var1_values,
        "var2_name": var2_name,
        "var2_values": var2_values,
        "base_value": base_value,
        "matrix": matrix,
        "markdown_table": markdown,
        "html": plotly_html,
        "title": title,
        "data_as_of": data_as_of or datetime.date.today().isoformat(),
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="sensitivity_table",
        category=Category.DCF,
        one_liner="Generic 2-variable sensitivity matrix with Plotly heatmap and markdown table.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Compute and render a 2-variable sensitivity matrix for any callable. "
            "Primary use: WACC x terminal growth grid for dcf_engine output. "
            "Also used for any pair of continuous inputs (e.g., margin x multiple)."
        ),
        when_to_use=[
            "Sensitivity section of a DCF report (WACC x terminal growth).",
            "Any 2-variable assumption grid for comparables, DDM, or other helpers.",
        ],
        when_not_to_use=[
            "Single-variable sweeps — use tornado_diagram for ranked impact.",
            "Probability-weighted scenarios — use scenario_weighting.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "var1_name": HelperParam(
                type="str",
                description="Label for axis 1 (row axis).",
                required=True,
            ),
            "var1_values": HelperParam(
                type="list[float]",
                description="Values for axis 1.",
                required=True,
            ),
            "var2_name": HelperParam(
                type="str",
                description="Label for axis 2 (column axis).",
                required=True,
            ),
            "var2_values": HelperParam(
                type="list[float]",
                description="Values for axis 2.",
                required=True,
            ),
            "base_fn": HelperParam(
                type="Callable[[float, float], float]",
                default=None,
                description="Function f(var1, var2) -> float to evaluate on the grid.",
                required=False,
            ),
            "precomputed_matrix": HelperParam(
                type="list[list[float]]",
                default=None,
                description="Pre-computed NxM matrix; alternative to base_fn.",
                required=False,
            ),
            "base_var1": HelperParam(
                type="float",
                default=None,
                description="Base value for var1 to identify base row.",
                required=False,
            ),
            "base_var2": HelperParam(
                type="float",
                default=None,
                description="Base value for var2 to identify base column.",
                required=False,
            ),
            "title": HelperParam(
                type="str",
                default="Sensitivity Matrix",
                description="Chart title.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="sensitivity_matrix",
                type="sensitivity_matrix",
                description="2D matrix, markdown table, and Plotly HTML heatmap.",
            ),
        ],
        produces_artifacts=["sensitivity_matrix"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
    ],
)

register_helper(_SCHEMA, execute)
