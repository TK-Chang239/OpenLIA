"""
Vendored from alirezarezvani/claude-skills (MIT License).
Original: (new file — not vendored from upstream)
Vendored on 2026-05-21 for OpenLIA report_v2 library helpers.

Adapted to expose a HelperSchema via SCHEMA module-level constant and an
execute(**params) entry point.
"""

from __future__ import annotations

import io
from typing import Any

from openpyxl import Workbook

from openlia.llm.runtime.report_v2.tools.library_helpers import (
    HelperParam,
    HelperSchema,
    register_library_helper,
)

SCHEMA = HelperSchema(
    name="make_excel",
    description="Build an xlsx workbook from tabular data and return raw bytes.",
    params={
        "sheets": HelperParam(
            type="list",
            description="List of sheet specs. Each: {name, headers: list[str], rows: list[list]}.",
            required=True,
        ),
    },
)


def execute(**params: Any) -> dict[str, Any]:
    """Build xlsx workbook.

    Params:
        sheets: list of {name, headers, rows} dicts
    """
    wb = Workbook()
    wb.remove(wb.active)

    for sheet_spec in params["sheets"]:
        ws = wb.create_sheet(title=sheet_spec["name"])
        ws.append(sheet_spec["headers"])
        for row in sheet_spec["rows"]:
            ws.append(row)

    buf = io.BytesIO()
    wb.save(buf)
    return {"format": "xlsx", "bytes": buf.getvalue()}


register_library_helper("make_excel", execute, SCHEMA)
