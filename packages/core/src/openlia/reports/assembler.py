from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload


class ReportAssemblyError(ValueError):
    """Raised when assembly cannot produce a publishable report.

    Currently used to reject blocks that still contain unsubstituted
    `{{tool:...}}` placeholders so an in-flight tool-call value never
    leaks into a published report.
    """


_TOOL_PLACEHOLDER_RE = re.compile(r"^\s*\{\{\s*tool\s*:[^}]*\}\}\s*$")


def _assert_no_tool_placeholders(node: Any, path: str = "") -> None:
    if isinstance(node, str):
        if _TOOL_PLACEHOLDER_RE.match(node):
            raise ReportAssemblyError(
                f"unsubstituted tool placeholder at {path or '<root>'}: {node!r}"
            )
        return
    if isinstance(node, dict):
        for k, v in node.items():
            _assert_no_tool_placeholders(v, f"{path}.{k}" if path else str(k))
        return
    if isinstance(node, list):
        for i, v in enumerate(node):
            _assert_no_tool_placeholders(v, f"{path}[{i}]")
        return


@dataclass(frozen=True)
class PageFurnitureConfig:
    header_left: str
    header_right_by_department: dict[str, str]
    footer_left_fmt: str
    footer_center: str
    footer_right: str
    disclaimer: str
    default_header_right: str = "OpenLIA Report"


def _strip_instructions(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_instructions(v) for k, v in node.items() if k != "instructions"}
    if isinstance(node, list):
        return [_strip_instructions(item) for item in node]
    return node


def _build_furniture(
    config: PageFurnitureConfig,
    department: str,
    now: datetime,
) -> dict[str, Any]:
    date = now.date().isoformat()
    header_right = config.header_right_by_department.get(
        department,
        config.default_header_right,
    )
    return {
        "header": {"left": config.header_left, "right": header_right},
        "footer": {
            "left": config.footer_left_fmt.format(date=date),
            "center": config.footer_center,
            "right": config.footer_right,
        },
        "disclaimer": config.disclaimer,
    }


def assemble_report(
    payload: dict[str, Any],
    *,
    department: str,
    furniture: PageFurnitureConfig,
    now: datetime,
) -> ReportSchema:
    stripped = _strip_instructions(deepcopy(payload))
    stripped.pop("page_furniture", None)
    stripped["page_furniture"] = _build_furniture(furniture, department, now)
    stripped.setdefault("schema_version", "2.0")
    stripped.setdefault("department", department)
    stripped.setdefault("generated_at", now.isoformat())
    _assert_no_tool_placeholders(stripped)
    return validate_report_payload(stripped)
