"""data_context injection into the dashboard system prompt.

A generic server-side data channel: when ``RunRequest.data_context`` is set,
``build_system_prompt`` injects a "# Provided inputs for this run" block stating
the data is authoritative ground truth. When None, the block is absent.
"""

from openlia.llm.runtime.report_dash_mr.prompts import build_system_prompt
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest


def _req(data_context: str | None) -> RunRequest:
    return RunRequest(
        dashboard_slug="debt_cycle",
        subject="Debt Cycle",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
        data_context=data_context,
    )


def test_data_context_block_present_when_set() -> None:
    prompt = build_system_prompt(_req("ZZ_TOKEN"))
    assert "Provided inputs for this run" in prompt
    assert "ZZ_TOKEN" in prompt


def test_data_context_block_absent_when_none() -> None:
    prompt = build_system_prompt(_req(None))
    assert "Provided inputs for this run" not in prompt
