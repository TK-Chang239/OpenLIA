"""v2.2 wrapper for the excel_builder helper (registered as "make_excel" in report_v2).

Imports the implementation from report_v2 (no duplication) and declares a
HelperSchema per the v2.2 four-tier contract.

Note: the report_v2 helper registers under the name "make_excel"; the v2.2 wrapper
registers under the canonical file name "excel_builder" to align with the file-based
naming convention used across the 8 migrated helpers.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.tools.library_helpers.excel_builder import (
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
        name="excel_builder",
        category=Category.OUTPUT,
        one_liner="Build a multi-sheet xlsx workbook from tabular data and return raw bytes.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Construct an xlsx workbook with one or more named sheets, each populated "
            "from a headers + rows spec, and return the raw bytes for attachment."
        ),
        when_to_use=[
            "When the report requires a downloadable spreadsheet alongside markdown prose.",
            "When tabular data from multiple helpers needs to be packaged into one file.",
        ],
        when_not_to_use=[
            "When only an inline table in markdown is needed — render directly in prose.",
            "When a chart is needed — use chart_builder instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "sheets": HelperParam(
                type="list",
                description=(
                    "List of sheet specs. Each: {name: str, headers: list[str], rows: list[list]}."
                ),
                required=True,
            ),
        },
        outputs=[
            HelperOutput(
                name="workbook_artifact",
                type="workbook_artifact",
                description="Raw xlsx bytes with format='xlsx' and bytes key.",
            ),
        ],
        produces_artifacts=["workbook_artifact"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[],
)

register_helper(_SCHEMA, _impl)
