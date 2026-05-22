"""v2.2 wrapper for the chart_builder helper (registered as "make_chart" in report_v2).

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

Note: the report_v2 helper registers under the name "make_chart"; the v2.2 wrapper
registers under the canonical file name "chart_builder" to align with the file-based
naming convention used across the 8 migrated helpers.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.chart_builder import (
    execute as _impl,
)
from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="chart_builder",
        category=Category.OUTPUT,
        one_liner="Render a matplotlib chart (line/bar/scatter) and return as inline SVG.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Render financial or operational data series as an inline SVG chart using matplotlib."
        ),
        when_to_use=[
            "Visualizing time-series revenue, earnings, or price data.",
            "Creating bar charts for period-over-period comparisons.",
            "Producing scatter plots for correlation analysis.",
        ],
        when_not_to_use=[
            "When you need a formatted spreadsheet — use excel_builder instead.",
            "When the chart data is already available as an existing artifact — "
            "use rendered_artifact fidelity projection instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "chart_type": HelperParam(
                type="str",
                description="Chart type: line, bar, scatter, heatmap.",
                required=True,
            ),
            "series": HelperParam(
                type="list",
                description=(
                    "Data series. Each element is {label, x, y} or just a list of values."
                ),
                required=True,
            ),
            "x_label": HelperParam(
                type="str",
                default="",
                description="X axis label.",
                required=False,
            ),
            "y_label": HelperParam(
                type="str",
                default="",
                description="Y axis label.",
                required=False,
            ),
            "title": HelperParam(
                type="str",
                default="",
                description="Chart title.",
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="chart_artifact",
                type="chart_artifact",
                description="Inline SVG string with format='svg_inline' and svg key.",
            ),
        ],
        produces_artifacts=["chart_artifact"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
