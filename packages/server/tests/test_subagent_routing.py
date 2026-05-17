"""When OPENLIA_USE_SUBAGENT_RUNNER=1 AND request.department_id is
equity_research, the runtime service must instantiate
SubagentReportRunner. Otherwise classic ReportRunner."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.subagent_runner import SubagentReportRunner
from openlia_server.services.runtime import select_report_runner_class


def test_default_returns_classic_runner_class(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENLIA_USE_SUBAGENT_RUNNER", raising=False)
    cls = select_report_runner_class(department_id="equity_research")
    assert cls is ReportRunner


def test_flag_on_for_equity_research_returns_subagent_runner_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIA_USE_SUBAGENT_RUNNER", "1")
    cls = select_report_runner_class(department_id="equity_research")
    assert cls is SubagentReportRunner


def test_flag_on_for_other_department_returns_classic_runner_class(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENLIA_USE_SUBAGENT_RUNNER", "1")
    cls = select_report_runner_class(department_id="earnings_update")
    assert cls is ReportRunner
