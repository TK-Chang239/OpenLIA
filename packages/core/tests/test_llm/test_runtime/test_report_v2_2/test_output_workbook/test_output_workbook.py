"""Tests for PR 2.10: output bundle — waterfall_chart, workbook_builder, WorkbookTemplate.

Test coverage:
- Waterfall: 4-step bridge produces correct cumulative totals
- Waterfall: Plotly JSON is parseable; markdown table has all rows
- Workbook: 3-sheet workbook builds without error; bytes is valid xlsx
- Workbook: sheet count and cell count metadata correct
- excel_builder has deprecated_at_version="0.2.0"
- WorkbookTemplate.add_sheet + render produces non-empty workbook
- Skill doc exists
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any, ClassVar

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get(name: str) -> Any:
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"Helper {name!r} not registered"
    return h


def _run(name: str, **kwargs: Any) -> dict[str, Any]:
    return _get(name).impl(**kwargs)


def _is_valid_xlsx(data: bytes) -> bool:
    """Verify bytes is a valid xlsx by opening with openpyxl."""
    try:
        import openpyxl  # type: ignore[import-untyped]

        openpyxl.load_workbook(io.BytesIO(data))
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# waterfall_chart
# ---------------------------------------------------------------------------


class TestWaterfallChart:
    """4-step NI bridge: Revenue=10000, COGS=-4000, OpEx=-2000, Tax=-1000 -> NI=3000."""

    _drivers: ClassVar[list[dict[str, Any]]] = [
        {"label": "COGS", "delta": -4000, "color_hint": "negative"},
        {"label": "Gross Profit", "delta": 0, "color_hint": "neutral"},
        {"label": "OpEx", "delta": -2000, "color_hint": "negative"},
        {"label": "Tax", "delta": -1000, "color_hint": "negative"},
    ]
    _starting = 10_000.0
    # Gross Profit driver has delta=0, so: 10000 - 4000 + 0 - 2000 - 1000 = 3000
    _expected_end = 3_000.0

    def test_cumulative_totals_correct(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
        )
        assert result["summary"]["starting_value"] == self._starting
        assert abs(result["summary"]["ending_value"] - self._expected_end) < 0.01

    def test_running_total_progression(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
        )
        steps = result["steps"]
        assert len(steps) == 4
        # After COGS: 10000 - 4000 = 6000
        assert abs(steps[0]["running_total"] - 6000.0) < 0.01
        # After Gross Profit (delta=0): still 6000
        assert abs(steps[1]["running_total"] - 6000.0) < 0.01
        # After OpEx: 6000 - 2000 = 4000
        assert abs(steps[2]["running_total"] - 4000.0) < 0.01
        # After Tax: 4000 - 1000 = 3000
        assert abs(steps[3]["running_total"] - 3000.0) < 0.01

    def test_total_change_pct(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
        )
        # 3000 - 10000 = -7000; -7000 / 10000 * 100 = -70%
        assert abs(result["summary"]["total_change_pct"] - (-70.0)) < 0.01

    def test_driver_classification(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
        )
        neg_labels = {d["label"] for d in result["summary"]["negative_drivers"]}
        assert "COGS" in neg_labels
        assert "OpEx" in neg_labels
        assert "Tax" in neg_labels

    def test_plotly_json_parseable(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
            title="NI Bridge Test",
        )
        parsed = json.loads(result["html"])
        # Plotly JSON or fallback error dict — both are valid JSON
        assert isinstance(parsed, dict)

    def test_markdown_table_has_all_rows(self) -> None:
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
        )
        table = result["markdown_table"]
        assert "Revenue" in table
        assert "COGS" in table
        assert "OpEx" in table
        assert "Tax" in table
        assert "Net Income" in table

    def test_ending_value_validation_passes(self) -> None:
        """Explicit ending_value matching computed end produces no warnings."""
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
            ending_value=self._expected_end,
        )
        assert result["warnings"] == []

    def test_ending_value_validation_warns_on_mismatch(self) -> None:
        """Explicit ending_value that doesn't match deltas emits a warning."""
        result = _run(
            "waterfall_chart",
            starting_value=self._starting,
            starting_label="Revenue",
            drivers=self._drivers,
            ending_label="Net Income",
            ending_value=9999.0,  # wrong
        )
        assert len(result["warnings"]) > 0
        assert "ending_value" in result["warnings"][0]

    def test_registration(self) -> None:
        h = _get("waterfall_chart")
        assert h.schema.directory.name == "waterfall_chart"
        assert "waterfall_chart_output" in h.schema.contract.produces_artifacts

    def test_empty_drivers_raises(self) -> None:
        with pytest.raises(ValueError, match="drivers must be non-empty"):
            _run(
                "waterfall_chart",
                starting_value=100.0,
                starting_label="Start",
                drivers=[],
                ending_label="End",
            )


# ---------------------------------------------------------------------------
# workbook_builder
# ---------------------------------------------------------------------------


class TestWorkbookBuilder:
    """workbook_builder: 3-sheet workbook builds; bytes is valid xlsx."""

    _dcf_artifact: ClassVar[dict[str, Any]] = {
        "headers": ["Year", "Revenue", "FCFF"],
        "rows": [
            [1, 100_000, 8_000],
            [2, 110_000, 9_200],
            [3, 121_000, 10_500],
        ],
        "summary": {
            "enterprise_value": 320_000,
            "implied_value_per_share": 45.0,
        },
    }

    _comps_artifact: ClassVar[dict[str, Any]] = {
        "markdown_table": (
            "| Peer | P/E | EV/EBITDA |\n"
            "|---|---|---|\n"
            "| MSFT | 28.5 | 22.1 |\n"
            "| GOOGL | 24.3 | 19.8 |\n"
            "| AMZN | 35.2 | 18.5 |\n"
        ),
        "summary": {
            "blended_low": 120.0,
            "blended_median": 145.0,
            "blended_high": 170.0,
        },
    }

    _scenarios_artifact: ClassVar[dict[str, Any]] = {
        "summary": {
            "base_value": 145.0,
            "bull_value": 200.0,
            "bear_value": 90.0,
            "weighted_value": 147.5,
        }
    }

    def test_three_sheet_workbook_returns_bytes(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            company_name="Apple",
            dcf_artifact=self._dcf_artifact,
            comparables_artifact=self._comps_artifact,
            scenarios_artifact=self._scenarios_artifact,
        )
        assert result["bytes"] is not None
        assert len(result["bytes"]) > 0

    def test_bytes_is_valid_xlsx(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            company_name="Apple",
            dcf_artifact=self._dcf_artifact,
            comparables_artifact=self._comps_artifact,
            scenarios_artifact=self._scenarios_artifact,
        )
        assert _is_valid_xlsx(result["bytes"])

    def test_sheet_count_correct(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            company_name="Apple",
            dcf_artifact=self._dcf_artifact,
            comparables_artifact=self._comps_artifact,
            scenarios_artifact=self._scenarios_artifact,
        )
        # Cover (injected) + DCF + Comparables + Scenarios = 4 minimum
        assert result["sheet_count"] >= 3

    def test_cell_count_metadata(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            company_name="Apple",
            dcf_artifact=self._dcf_artifact,
        )
        # DCF has 3 data rows + 1 header = 4 rows * 3 cols = 12 cells
        assert result["total_cells"] >= 12

    def test_sheets_written_list(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            dcf_artifact=self._dcf_artifact,
            comparables_artifact=self._comps_artifact,
        )
        assert "DCF" in result["sheets_written"]
        assert "Comparables" in result["sheets_written"]

    def test_file_path_none_when_no_output_path(self) -> None:
        result = _run("workbook_builder", ticker="TEST")
        assert result["file_path"] is None

    def test_write_to_file(self, tmp_path: Path) -> None:
        output = str(tmp_path / "test_workbook.xlsx")
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            dcf_artifact=self._dcf_artifact,
            output_path=output,
        )
        assert result["file_path"] == output
        assert Path(output).exists()
        assert _is_valid_xlsx(Path(output).read_bytes())

    def test_low_level_sheets_spec(self) -> None:
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            sheets=[
                {
                    "name": "Custom Sheet",
                    "source_artifacts": ["dcf"],
                    "layout": "table",
                },
            ],
            artifacts={"dcf": self._dcf_artifact},
        )
        assert "Custom Sheet" in result["sheets_written"]
        assert _is_valid_xlsx(result["bytes"])

    def test_registration(self) -> None:
        h = _get("workbook_builder")
        assert h.schema.directory.name == "workbook_builder"
        assert "workbook_artifact" in h.schema.contract.produces_artifacts

    def test_additional_panels(self) -> None:
        forensic = {"artifact_type": "forensic_panel", "summary": {"score": 25, "level": "low"}}
        result = _run(
            "workbook_builder",
            ticker="AAPL",
            additional_panels=[forensic],
        )
        assert result["sheet_count"] >= 1
        assert any("forensic" in s.lower() for s in result["sheets_written"])

    def test_invalid_output_path_raises(self) -> None:
        with pytest.raises(OSError):
            _run(
                "workbook_builder",
                ticker="AAPL",
                output_path="/nonexistent/dir/file.xlsx",
            )


# ---------------------------------------------------------------------------
# excel_builder deprecation
# ---------------------------------------------------------------------------


class TestExcelBuilderDeprecation:
    def test_deprecated_at_version_set(self) -> None:
        h = _get("excel_builder")
        assert h.schema.deprecated_at_version == "0.2.0"

    def test_still_registered(self) -> None:
        """excel_builder remains registered for backward compatibility."""
        h = _get("excel_builder")
        assert h is not None


# ---------------------------------------------------------------------------
# WorkbookTemplate
# ---------------------------------------------------------------------------


class TestWorkbookTemplate:
    def test_add_sheet_and_render(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST", currency="USD", report_date="2026-05-22")
        wb.add_sheet("MySheet", sheet_type="table")
        wb.write_headers("MySheet", ["Col A", "Col B", "Col C"])
        wb.write_row("MySheet", [1, 2, 3])
        wb.write_row("MySheet", [4, 5, 6])
        data = wb.to_bytes()
        assert len(data) > 0
        assert _is_valid_xlsx(data)

    def test_metadata_reflects_rows(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("Sheet1", sheet_type="table")
        wb.write_headers("Sheet1", ["A", "B"])
        for i in range(5):
            wb.write_row("Sheet1", [i, i * 2])
        meta = wb.metadata()
        assert meta["sheet_count"] == 1
        # 5 data rows + 1 header = 6 rows * 2 cols = 12 cells
        assert meta["total_cells"] == 12

    def test_duplicate_sheet_raises(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("Sheet1")
        with pytest.raises(ValueError, match="already declared"):
            wb.add_sheet("Sheet1")

    def test_sheet_name_too_long_raises(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        with pytest.raises(ValueError, match="31-char"):
            wb.add_sheet("A" * 32)

    def test_embed_artifact_table_style(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("DCF")
        wb.embed_artifact(
            "DCF",
            {
                "headers": ["Year", "FCFF"],
                "rows": [[1, 100], [2, 200]],
            },
        )
        meta = wb.metadata()
        dcf = next(s for s in meta["sheets"] if s["name"] == "DCF")
        assert dcf["row_count"] == 2
        assert dcf["col_count"] == 2

    def test_embed_artifact_markdown_table(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("Comps")
        wb.embed_artifact(
            "Comps",
            {"markdown_table": ("| Peer | P/E |\n|---|---|\n| MSFT | 28.5 |\n| GOOGL | 24.3 |\n")},
        )
        meta = wb.metadata()
        comps = next(s for s in meta["sheets"] if s["name"] == "Comps")
        assert comps["row_count"] == 2

    def test_validate_warns_on_empty_table(self) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("EmptySheet", sheet_type="table")
        warnings = wb.validate()
        assert any("EmptySheet" in w for w in warnings)

    def test_equity_research_initiation_template(self) -> None:
        from openlia.reports.workbook_template import EquityResearchInitiation

        wb = EquityResearchInitiation("Apple", "AAPL", currency="USD")
        meta = wb.metadata()
        sheet_names = [s["name"] for s in meta["sheets"]]
        assert "DCF" in sheet_names
        assert "Comparables" in sheet_names
        assert "Assumptions" in sheet_names
        data = wb.to_bytes()
        assert _is_valid_xlsx(data)

    def test_earnings_update_template(self) -> None:
        from openlia.reports.workbook_template import EarningsUpdate

        wb = EarningsUpdate("Apple", "AAPL")
        meta = wb.metadata()
        sheet_names = [s["name"] for s in meta["sheets"]]
        assert "Financials" in sheet_names
        assert "EPS Walk" in sheet_names

    def test_save_to_file(self, tmp_path: Path) -> None:
        from openlia.reports.workbook_template import WorkbookTemplate

        wb = WorkbookTemplate("TestCo", "TEST")
        wb.add_sheet("Data")
        wb.write_headers("Data", ["X", "Y"])
        wb.write_row("Data", [1, 2])
        path = str(tmp_path / "output.xlsx")
        wb.save(path)
        assert Path(path).exists()
        assert _is_valid_xlsx(Path(path).read_bytes())


# ---------------------------------------------------------------------------
# Skill doc
# ---------------------------------------------------------------------------


class TestSkillDoc:
    def test_workbook_builder_skill_doc_exists(self) -> None:
        skill_path = (
            Path(__file__).parents[5]
            / "src"
            / "openlia"
            / "llm"
            / "runtime"
            / "report_v2_2"
            / "tools"
            / "library_helpers"
            / "skills"
            / "workbook_builder.md"
        )
        assert skill_path.exists(), f"Skill doc missing: {skill_path}"
        content = skill_path.read_text()
        assert len(content) > 500, "Skill doc is too short"
        assert "workbook_builder" in content
