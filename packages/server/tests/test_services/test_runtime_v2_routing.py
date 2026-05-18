"""Tests for select_report_runner_class routing to WavedReportRunnerHost.

V2 is default-on for equity_research since 2026-05-18. Tests cover the
default-on path, the explicit-disable path (OPENLIA_REPORT_V2_ENABLED=false),
and interactions with the subagent flag.
"""

from __future__ import annotations

import importlib


def _fresh_select(monkeypatch, env: dict[str, str]):
    """Import select_report_runner_class in a fresh env state."""
    # Patch the env vars.
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    # Clear all V2/subagent flags not explicitly set.
    for flag in ("OPENLIA_REPORT_V2_ENABLED", "OPENLIA_USE_SUBAGENT_RUNNER"):
        if flag not in env:
            monkeypatch.delenv(flag, raising=False)

    # Re-import after patching.
    import openlia_server.services.runtime as svc

    importlib.reload(svc)
    return svc.select_report_runner_class


class TestSelectReportRunnerClass:
    def test_flag_on_equity_research_returns_waved_host(self, monkeypatch) -> None:
        """OPENLIA_REPORT_V2_ENABLED=true + equity_research -> WavedReportRunnerHost."""
        select = _fresh_select(monkeypatch, {"OPENLIA_REPORT_V2_ENABLED": "true"})
        from openlia_server.services.runtime_report_v2 import WavedReportRunnerHost

        result = select(department_id="equity_research")
        assert result is WavedReportRunnerHost

    def test_flag_on_case_insensitive(self, monkeypatch) -> None:
        """OPENLIA_REPORT_V2_ENABLED=True (mixed case) also routes to WavedReportRunnerHost."""
        select = _fresh_select(monkeypatch, {"OPENLIA_REPORT_V2_ENABLED": "True"})
        from openlia_server.services.runtime_report_v2 import WavedReportRunnerHost

        result = select(department_id="equity_research")
        assert result is WavedReportRunnerHost

    def test_flag_unset_equity_research_defaults_to_waved(self, monkeypatch) -> None:
        """No flag set -> WavedReportRunnerHost for equity_research (default-on)."""
        select = _fresh_select(monkeypatch, {})
        from openlia_server.services.runtime_report_v2 import WavedReportRunnerHost

        result = select(department_id="equity_research")
        assert result is WavedReportRunnerHost

    def test_other_dept_always_returns_report_runner(self, monkeypatch) -> None:
        """Other departments always get classic ReportRunner regardless of flag."""
        select = _fresh_select(monkeypatch, {"OPENLIA_REPORT_V2_ENABLED": "true"})
        from openlia.llm.runtime.report import ReportRunner

        result = select(department_id="macro_research")
        assert result is ReportRunner

    def test_subagent_flag_works_only_when_v2_explicitly_disabled(self, monkeypatch) -> None:
        """OPENLIA_USE_SUBAGENT_RUNNER=1 plus explicit v2-disable -> SubagentReportRunner."""
        select = _fresh_select(
            monkeypatch,
            {
                "OPENLIA_USE_SUBAGENT_RUNNER": "1",
                "OPENLIA_REPORT_V2_ENABLED": "false",
            },
        )
        from openlia.llm.runtime.subagent_runner import SubagentReportRunner

        result = select(department_id="equity_research")
        assert result is SubagentReportRunner

    def test_v2_flag_takes_priority_over_subagent_flag(self, monkeypatch) -> None:
        """V2 flag wins over subagent flag when both are set."""
        select = _fresh_select(
            monkeypatch,
            {
                "OPENLIA_REPORT_V2_ENABLED": "true",
                "OPENLIA_USE_SUBAGENT_RUNNER": "1",
            },
        )
        from openlia_server.services.runtime_report_v2 import WavedReportRunnerHost

        result = select(department_id="equity_research")
        assert result is WavedReportRunnerHost

    def test_flag_false_string_does_not_route_to_waved(self, monkeypatch) -> None:
        """OPENLIA_REPORT_V2_ENABLED=false -> classic ReportRunner."""
        select = _fresh_select(monkeypatch, {"OPENLIA_REPORT_V2_ENABLED": "false"})
        from openlia.llm.runtime.report import ReportRunner

        result = select(department_id="equity_research")
        assert result is ReportRunner
