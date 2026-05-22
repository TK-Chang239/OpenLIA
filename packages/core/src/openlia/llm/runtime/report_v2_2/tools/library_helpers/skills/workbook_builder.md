---
name: workbook_builder
category: output
version: 1.0.0
produces_artifacts:
  - workbook_artifact
consumes_artifacts: []
---

# workbook_builder — Multi-Sheet Excel Workbook from Helper Artifacts

## Purpose

Compose a downloadable multi-sheet `.xlsx` workbook from the helper artifacts
produced during a report run. The workbook follows institutional financial-modeling
conventions: cover sheet with TOC, dedicated tabs per analysis module, bold-header
formatting, frozen panes, and a structured assumptions tab.

Wraps `WorkbookTemplate` (`reports/workbook_template.py §2.5`). The helper maps
named artifacts to sheet names; `WorkbookTemplate` handles rendering.

Supersedes `excel_builder` (deprecated at v0.2.0).

## When to use

- Full equity research initiation — wrap DCF, comparables, sensitivity, scenarios,
  SOTP, cost of capital, and decision-layer outputs into one file.
- Earnings update — abbreviated workbook with financials and EPS walk.
- Any report where the audience needs to download, edit, and re-run the model.
- When multiple tabular artifacts must land in a single shareable file.

## When NOT to use

- Single inline table in prose — render directly in the report body; no workbook needed.
- One-pager or headline report without quantitative modeling.
- Chart-only output — use `waterfall_chart` or `chart_builder` instead.
- Ratio report with 3-5 metrics — inline table is more legible than an xlsx.

## Required prior steps

No hard prerequisites. For a well-populated workbook, run upstream helpers first:

1. `cost_of_capital_builder` → pass output as `cost_of_capital_artifact`
2. `dcf_engine` → pass output as `dcf_artifact`
3. `comparables_run` → pass output as `comparables_artifact`
4. `sensitivity_table` → pass output as `sensitivity_artifact`
5. `scenario_weighting` → pass output as `scenarios_artifact`

Any subset of the above is valid; sheets are skipped for absent artifacts.

## Inputs

| Param | Type | Required | Description |
|---|---|---|---|
| `ticker` | `str` | Yes | Ticker symbol; used in workbook metadata. |
| `company_name` | `str` | No | Display name. Defaults to ticker. |
| `currency` | `str` | No | Reporting currency (default "USD"). |
| `report_date` | `str` | No | ISO date. Defaults to today. |
| `template` | `str` | No | Template class name (see Templates section). |
| `output_path` | `str` | No | File path to write xlsx. If None, bytes returned. |
| `dcf_artifact` | `dict` | No | Output from `dcf_engine`. |
| `comparables_artifact` | `dict` | No | Output from `comparables_run`. |
| `sensitivity_artifact` | `dict` | No | Output from `sensitivity_table`. |
| `scenarios_artifact` | `dict` | No | Output from `scenario_weighting`. |
| `cost_of_capital_artifact` | `dict` | No | Output from `cost_of_capital_builder`. |
| `sotp_artifact` | `dict` | No | Output from `sotp_builder`. |
| `decision_artifact` | `dict` | No | Rating + PT + ETR from decision-layer helpers. |
| `additional_panels` | `list[dict]` | No | Extra artifact dicts (forensic, credit, etc.). |
| `sheets` | `list[dict]` | No | Low-level sheet specs `{name, source_artifacts, layout}`. |
| `artifacts` | `dict` | No | Artifact key -> helper output dict (for `sheets` use). |

## Templates

| Template name | Pre-declared sheets |
|---|---|
| `WorkbookTemplate` | None (generic; add sheets manually) |
| `EquityResearchInitiation` | Assumptions, DCF, Sensitivity, Scenarios, Comparables, SOTP, Cost of Capital, Decision, Citations |
| `EarningsUpdate` | Financials, EPS Walk, Guidance, Citations |

Use `EquityResearchInitiation` for initiation reports and `EarningsUpdate` for
quarterly update reports. Use `WorkbookTemplate` when building custom sheet layouts.

## Two calling conventions

### High-level (recommended for standard reports)

Pass named artifact dicts directly. The helper maps them to standard sheet names.

```python
result = workbook_builder.execute(
    ticker="AAPL",
    company_name="Apple",
    currency="USD",
    report_date="2026-05-21",
    template="EquityResearchInitiation",
    dcf_artifact=dcf_output,
    comparables_artifact=comps_output,
    sensitivity_artifact=sensitivity_output,
    scenarios_artifact=scenarios_output,
    output_path="/runs/2026-05-21/AAPL_initiation.xlsx",
)
```

### Low-level (for custom sheet layouts)

Pass `sheets` spec and `artifacts` dict. Each sheet spec names which artifact
keys to embed.

```python
result = workbook_builder.execute(
    ticker="AAPL",
    sheets=[
        {"name": "DCF", "source_artifacts": ["dcf"], "layout": "table"},
        {"name": "Comps", "source_artifacts": ["comps"], "layout": "table"},
    ],
    artifacts={"dcf": dcf_output, "comps": comps_output},
)
```

Both conventions can be combined: pass named artifacts for standard content and
`sheets` for custom extensions.

## Output shape

```json
{
  "file_path": "/runs/2026-05-21/AAPL_initiation.xlsx",
  "bytes": null,
  "sheets_written": ["Cover", "Assumptions", "DCF", "Comparables"],
  "sheet_count": 4,
  "total_cells": 1540,
  "file_size_bytes": 42800,
  "file_size_kb": 41.8,
  "metadata": {
    "company_name": "Apple",
    "ticker": "AAPL",
    "currency": "USD",
    "report_date": "2026-05-21",
    "sheet_count": 4,
    "sheets": [
      {"name": "Cover", "sheet_type": "cover", "row_count": 6, ...},
      ...
    ],
    "total_cells": 1540
  },
  "narrative": "Workbook produced at /runs/.../AAPL_initiation.xlsx — 4 sheet(s), 41 KB.",
  "warnings": [],
  "data_as_of": "2026-05-21"
}
```

When `output_path` is `None`, the `bytes` field contains raw xlsx bytes and
`file_path` is `null`.

## Sheet-naming conventions

- Tab names follow institutional convention: "DCF", "Comparables", "Sensitivity",
  "Scenarios", "SOTP", "Cost of Capital", "Decision", "Citations".
- Sheet names are truncated to 31 chars (Excel limit). Names longer than 31 chars
  raise a `ValueError` at `add_sheet()` time.
- Do not use characters `\ / ? * [ ]` in sheet names — Excel rejects them.

## Formula authoring rules (Phase 3)

In Phase 3, `WorkbookTemplate` will add named-range formula references. Key rules:

- **Reference named ranges, not cells.** Formulas use `=WACC`, `=TerminalGrowth`,
  not `=Assumptions!B5`. Named ranges survive user row/column insertions.
- **`IFERROR` on all cross-sheet formulas.** If the upstream sheet is empty or the
  named range doesn't exist, `IFERROR(formula, "")` prevents `#REF!` from
  cascading through the model.
- **Number formats by metric type.** Currency cells use `'#,##0.00'`; percentage
  cells use `'0.0%'`; multiple cells use `'0.0x'`.
- **Bold row headers and totals.** All section headers and total rows are bold.

## Common pitfalls

1. **output_path directory must exist.** The helper raises `OSError` if the parent
   directory doesn't exist. Create the directory before calling the helper. Do not
   rely on the helper to create directories.

2. **File-size cap.** Workbooks above 10 MB emit a warning. This is not an error
   at the helper level, but the report payload pipeline (artifact-injection §8)
   rejects attachments above 10 MB. If you're hitting this limit: reduce the
   number of embedded chart PNGs, drop older historical periods from the model
   schedule, or use the `EarningsUpdate` template instead of `EquityResearchInitiation`.

3. **Sheet name conflicts in templates.** If you pass `additional_panels` with
   `artifact_type` keys that match an existing template sheet name (e.g. "DCF"),
   `add_panel()` will emit a `ValueError`. Use a unique `sheet_name` argument to
   `add_panel()` in that case.

4. **Empty template sheets.** Pre-built templates declare sheets upfront. If you use
   `EquityResearchInitiation` but don't pass a `comparables_artifact`, the
   "Comparables" sheet will be empty. `validate()` emits a warning for empty table
   sheets. The cover TOC shows them with "0 rows"; this is expected behavior.

5. **Artifact shape mismatch.** `embed_artifact()` auto-detects shape (headers+rows,
   markdown_table, summary dict, or flat fallback). If an artifact has none of those
   shapes, only scalar top-level fields are written. Inspect `total_cells` in the
   output metadata to verify data was written as expected.

6. **bytes vs. file_path.** When `output_path` is `None`, the `bytes` field
   contains raw xlsx data. Pass this to the report payload as an attachment.
   When `output_path` is provided, `bytes` is `null` — do not cache the bytes
   in memory for large workbooks.

## Examples

### Minimal workbook (bytes only)

```python
result = workbook_builder.execute(
    ticker="MSFT",
    dcf_artifact=dcf_output,
)
# result["bytes"] contains the xlsx
# result["file_path"] is None
assert result["sheet_count"] >= 1
assert result["file_size_bytes"] > 0
```

### Initiation workbook with all modules

```python
result = workbook_builder.execute(
    ticker="NVDA",
    company_name="NVIDIA",
    currency="USD",
    report_date="2026-05-21",
    template="EquityResearchInitiation",
    dcf_artifact=dcf_out,
    comparables_artifact=comps_out,
    sensitivity_artifact=sens_out,
    scenarios_artifact=scen_out,
    cost_of_capital_artifact=wacc_out,
    sotp_artifact=sotp_out,
    decision_artifact=rating_out,
    additional_panels=[forensic_out, credit_out],
    output_path="/runs/NVDA_initiation.xlsx",
)
assert result["file_path"] == "/runs/NVDA_initiation.xlsx"
assert result["sheet_count"] >= 9
```

### EarningsUpdate with custom panel

```python
result = workbook_builder.execute(
    ticker="AMZN",
    template="EarningsUpdate",
    sheets=[
        {"name": "Revenue Bridge", "source_artifacts": ["waterfall"], "layout": "table"},
    ],
    artifacts={"waterfall": waterfall_output},
    output_path="/runs/AMZN_q1_update.xlsx",
)
```

## Related helpers

- **`waterfall_chart`**: Produces a waterfall bridge visualization (Plotly JSON +
  markdown table). Pass `waterfall_chart_output["markdown_table"]` or the full
  artifact to `embed_artifact()` for an EPS Walk or revenue bridge sheet.
- **`dcf_engine`**: Primary input for the DCF sheet.
- **`comparables_run`**: Primary input for the Comparables sheet.
- **`sensitivity_table`**: Primary input for the Sensitivity sheet.
- **`scenario_weighting`**: Primary input for the Scenarios sheet.
- **`football_field_chart`**: Chart artifact that can be embedded via `add_panel()`.
- **`excel_builder`**: Deprecated predecessor (v0.2.0). Accepts only headers+rows;
  no template support. Migrate to `workbook_builder` for new reports.
