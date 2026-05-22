"""workbook_builder — multi-sheet Excel workbook from helper artifacts.

Registered name: "workbook_builder"

Composes a multi-sheet xlsx workbook from artifacts produced by other helpers.
Uses WorkbookTemplate (reports/workbook_template.py §2.5) as the underlying
rendering engine.

This is the v2.2 replacement for the excel_builder helper (PR 0.2).
excel_builder is deprecated at version 0.2.0 and will be removed in a future PR.

Design ref: planning/2026-05-22-helpers-design-supplement.md §13
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    SkillDocRef,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

# Skills doc path (relative to this file) — declared for discoverability
_SKILL_DOC = Path(__file__).parent / "skills" / "workbook_builder.md"

# File-size cap: warn above 10 MB
_FILE_SIZE_WARN_BYTES = 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _resolve_template(
    template_name: str, ticker: str, company_name: str, currency: str, report_date: str
) -> Any:
    """Instantiate a WorkbookTemplate from a template name."""
    from openlia.reports.workbook_template import (
        EarningsUpdate,
        EquityResearchInitiation,
        WorkbookTemplate,
    )

    templates: dict[str, type[WorkbookTemplate]] = {
        "EquityResearchInitiation": EquityResearchInitiation,
        "EarningsUpdate": EarningsUpdate,
        "WorkbookTemplate": WorkbookTemplate,
        "default": WorkbookTemplate,
    }
    cls = templates.get(template_name, WorkbookTemplate)
    return cls(
        company_name=company_name,
        ticker=ticker,
        currency=currency,
        report_date=report_date,
    )


def _sheets_from_spec(
    wb: Any,
    sheets: list[dict[str, Any]],
    artifacts: dict[str, Any],
) -> list[str]:
    """Populate sheets according to the sheets spec.

    Each sheet spec: {name, source_artifacts, layout}
    - name: tab name
    - source_artifacts: list of artifact keys to embed on this sheet
    - layout: "table" | "chart" | "narrative"

    Returns list of sheet names written.
    """
    written: list[str] = []
    for sheet_spec in sheets:
        name: str = sheet_spec["name"]
        layout: str = sheet_spec.get("layout", "table")
        source_keys: list[str] = sheet_spec.get("source_artifacts", [])

        # Add sheet if not already declared by the template
        if name not in wb._sheets:
            from openlia.reports.workbook_template import SheetType

            sheet_type: SheetType = "table" if layout in ("table", "chart") else "narrative"
            wb.add_sheet(name, sheet_type=sheet_type)  # type: ignore[arg-type]

        for key in source_keys:
            artifact = artifacts.get(key)
            if artifact is not None:
                wb.embed_artifact(name, artifact)

        written.append(name)
    return written


# ---------------------------------------------------------------------------
# execute()
# ---------------------------------------------------------------------------


def execute(
    *,
    ticker: str,
    company_name: str | None = None,
    currency: str = "USD",
    report_date: str | None = None,
    sheets: list[dict[str, Any]] | None = None,
    artifacts: dict[str, Any] | None = None,
    template: str = "WorkbookTemplate",
    output_path: str | None = None,
    # High-level artifact convenience params (supplement §13)
    dcf_artifact: dict[str, Any] | None = None,
    comparables_artifact: dict[str, Any] | None = None,
    sensitivity_artifact: dict[str, Any] | None = None,
    scenarios_artifact: dict[str, Any] | None = None,
    cost_of_capital_artifact: dict[str, Any] | None = None,
    sotp_artifact: dict[str, Any] | None = None,
    decision_artifact: dict[str, Any] | None = None,
    additional_panels: list[dict[str, Any]] | None = None,
    data_as_of: str | None = None,
    source_provenance: list[str] | None = None,
    **_extra: Any,
) -> dict[str, Any]:
    """Compose a multi-sheet xlsx workbook from helper artifacts.

    Two calling conventions:

    **High-level (supplement §13):** Pass named artifact dicts directly.
    The helper maps them to standard sheet names following institutional
    financial-modeling convention.

        result = execute(
            ticker="AAPL",
            company_name="Apple",
            currency="USD",
            report_date="2026-05-21",
            template="EquityResearchInitiation",
            dcf_artifact=dcf_output,
            comparables_artifact=comps_output,
            output_path="/runs/AAPL.xlsx",
        )

    **Low-level:** Pass ``sheets`` (list of {name, source_artifacts, layout})
    and ``artifacts`` (dict mapping artifact keys to helper output dicts).

        result = execute(
            ticker="AAPL",
            sheets=[
                {"name": "DCF", "source_artifacts": ["dcf"], "layout": "table"},
            ],
            artifacts={"dcf": dcf_output},
        )

    Both conventions can be combined.

    Args:
        ticker: Ticker symbol; used in workbook metadata.
        company_name: Company display name (defaults to ticker).
        currency: Reporting currency label.
        report_date: ISO date string. Defaults to today.
        sheets: Low-level sheet spec list.
        artifacts: Dict of artifact key -> helper output dict (for low-level use).
        template: WorkbookTemplate class name. One of: "WorkbookTemplate" (generic),
            "EquityResearchInitiation", "EarningsUpdate".
        output_path: File path to write the .xlsx. If None, bytes are returned.
        dcf_artifact: Output from dcf_engine.
        comparables_artifact: Output from comparables_run.
        sensitivity_artifact: Output from sensitivity_table.
        scenarios_artifact: Output from scenario_weighting.
        cost_of_capital_artifact: Output from cost_of_capital_builder.
        sotp_artifact: Output from sotp_builder.
        decision_artifact: Output from decision-layer helpers.
        additional_panels: List of arbitrary artifact dicts to embed as extra sheets.
        data_as_of: ISO date for provenance.
        source_provenance: Upstream citation IDs.

    Returns:
        dict with file_path (or None), bytes (if no output_path), sheets_written,
        sheet_count, total_cells, file_size_bytes, metadata, warnings.

    Raises:
        OSError: If output_path is provided but not writable.
        ValueError: On invalid sheet spec or unknown template.
    """
    _company = company_name or ticker
    _report_date = report_date or datetime.date.today().isoformat()

    wb = _resolve_template(template, ticker, _company, currency, _report_date)

    warnings: list[str] = []

    # High-level artifact injection
    if dcf_artifact is not None:
        wb.add_dcf(dcf_artifact)
    if comparables_artifact is not None:
        wb.add_comparables(comparables_artifact)
    if sensitivity_artifact is not None:
        wb.add_sensitivity(sensitivity_artifact)
    if scenarios_artifact is not None:
        wb.add_scenarios(scenarios_artifact)
    if cost_of_capital_artifact is not None:
        wb.embed_artifact("Cost of Capital", cost_of_capital_artifact)
    if sotp_artifact is not None:
        wb.add_sotp(sotp_artifact)
    if decision_artifact is not None:
        wb.add_decision(decision_artifact)
    if additional_panels:
        for panel in additional_panels:
            wb.add_panel(panel)

    # Low-level sheet specs
    if sheets:
        _artifacts = artifacts or {}
        _sheets_from_spec(wb, sheets, _artifacts)

    # Validate
    template_warnings = wb.validate()
    warnings.extend(template_warnings)

    # Render
    xlsx_bytes = wb.to_bytes()
    file_size = len(xlsx_bytes)

    if file_size > _FILE_SIZE_WARN_BYTES:
        warnings.append(
            f"Workbook is {file_size // 1024 // 1024:.1f} MB — "
            "exceeds 10 MB recommendation. Consider reducing embedded chart resolution."
        )

    # Write to file or return bytes
    file_path: str | None = None
    if output_path is not None:
        out = Path(output_path)
        parent = out.parent
        if not parent.exists():
            raise OSError(
                f"Output directory {str(parent)!r} does not exist. "
                "Create it before calling workbook_builder."
            )
        if parent.exists() and not os.access(str(parent), os.W_OK):
            raise OSError(
                f"Output path {output_path!r} is not writable. Check directory permissions."
            )
        wb.save(output_path)
        file_path = output_path

    meta = wb.metadata()
    sheets_written = [s["name"] for s in meta["sheets"]]

    narrative = (
        f"Workbook produced"
        f"{(' at ' + file_path) if file_path else ' (bytes only)'}. "
        f"{meta['sheet_count']} sheet(s), {file_size // 1024} KB."
    )

    return {
        "file_path": file_path,
        "bytes": xlsx_bytes if output_path is None else None,
        "sheets_written": sheets_written,
        "sheet_count": meta["sheet_count"],
        "total_cells": meta["total_cells"],
        "file_size_bytes": file_size,
        "file_size_kb": round(file_size / 1024, 1),
        "metadata": meta,
        "narrative": narrative,
        "warnings": warnings,
        "data_as_of": data_as_of or _report_date,
        "source_provenance": source_provenance or [],
        "applied_at": datetime.datetime.now(datetime.UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = HelperSchema(
    version="1.0.0",
    directory=DirectoryEntry(
        name="workbook_builder",
        category=Category.OUTPUT,
        one_liner=(
            "Compose a multi-sheet xlsx workbook from helper artifacts. "
            "v2.2 replacement for excel_builder."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Build an institutional-convention xlsx workbook from the outputs of "
            "other helpers (DCF, comps, scenarios, sensitivity, SOTP, decision layer). "
            "The result is a downloadable spreadsheet companion to the prose report. "
            "Uses WorkbookTemplate for sheet layout, formatting, and TOC."
        ),
        when_to_use=[
            "Equity research initiation — full workbook with DCF, comps, and scenario tabs.",
            "Earnings update — abbreviated workbook with financials and EPS walk.",
            "When the audience needs to edit assumptions and see downstream effects.",
            "When multiple tabular artifacts must be packaged into a single file.",
        ],
        when_not_to_use=[
            "When only a single inline table in markdown is needed — render in prose.",
            "When the report is a one-pager without quantitative modeling.",
            "For chart-only output — use chart_builder or waterfall_chart instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                description="Ticker symbol; used in workbook metadata.",
                required=True,
            ),
            "company_name": HelperParam(
                type="str",
                default=None,
                description="Company display name. Defaults to ticker.",
                required=False,
            ),
            "currency": HelperParam(
                type="str",
                default="USD",
                description="Reporting currency label shown in workbook header.",
                required=False,
            ),
            "report_date": HelperParam(
                type="str",
                default=None,
                description="ISO date string. Defaults to today.",
                required=False,
            ),
            "sheets": HelperParam(
                type="list[dict]",
                default=None,
                description=(
                    "Low-level sheet specs: {name, source_artifacts, layout}. "
                    "Use alongside the 'artifacts' dict. Optional if high-level "
                    "artifact params (dcf_artifact etc.) are provided."
                ),
                required=False,
            ),
            "artifacts": HelperParam(
                type="dict",
                default=None,
                description=(
                    "Dict mapping artifact key -> helper output dict. "
                    "Referenced by sheets[].source_artifacts."
                ),
                required=False,
            ),
            "template": HelperParam(
                type="str",
                default="WorkbookTemplate",
                description=(
                    "WorkbookTemplate class name: 'WorkbookTemplate' (generic), "
                    "'EquityResearchInitiation', or 'EarningsUpdate'."
                ),
                required=False,
            ),
            "output_path": HelperParam(
                type="str",
                default=None,
                description=(
                    "File path to write the .xlsx. If None, bytes returned in 'bytes' key."
                ),
                required=False,
            ),
            "dcf_artifact": HelperParam(
                type="dict",
                default=None,
                description="Output from dcf_engine.",
                required=False,
            ),
            "comparables_artifact": HelperParam(
                type="dict",
                default=None,
                description="Output from comparables_run.",
                required=False,
            ),
            "sensitivity_artifact": HelperParam(
                type="dict",
                default=None,
                description="Output from sensitivity_table.",
                required=False,
            ),
            "scenarios_artifact": HelperParam(
                type="dict",
                default=None,
                description="Output from scenario_weighting.",
                required=False,
            ),
            "sotp_artifact": HelperParam(
                type="dict",
                default=None,
                description="Output from sotp_builder.",
                required=False,
            ),
            "decision_artifact": HelperParam(
                type="dict",
                default=None,
                description="Rating + price target + ETR from decision-layer helpers.",
                required=False,
            ),
            "additional_panels": HelperParam(
                type="list[dict]",
                default=None,
                description=(
                    "Arbitrary artifact dicts to embed as extra sheets "
                    "(e.g. forensic, credit, dividend safety)."
                ),
                required=False,
            ),
        },
        outputs=[
            HelperOutput(
                name="workbook_artifact",
                type="workbook_artifact",
                description=(
                    "Multi-sheet xlsx workbook. file_path if output_path provided; "
                    "bytes if no output_path. Includes sheet_count, total_cells, "
                    "file_size_bytes metadata."
                ),
            ),
        ],
        produces_artifacts=["workbook_artifact"],
        consumes_artifacts=[],
    ),
    skill_doc=SkillDocRef(
        path="skills/workbook_builder.md",
        estimated_tokens=1600,
    ),
    verifier_hooks=[
        VerifierIssueType.BLOCK_SHAPE,
        VerifierIssueType.BLOCK_ARTIFACT_TOO_LARGE,
    ],
)

register_helper(_SCHEMA, execute)
