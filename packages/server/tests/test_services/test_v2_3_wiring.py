"""Tests for the v2.3 env-based wiring helper.

These verify the assembly path without making any network calls — adapters
are constructed but not invoked.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.runner import ReportRunner
from openlia.llm.runtime.report_v2_3.slots import V23Slot
from openlia.llm.runtime.report_v2_3.stages import ClarifyStage
from openlia_server.services.v2_3_wiring import build_v2_3_runner_factory_from_env


def test_returns_none_when_env_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENLIA_V2_3_CLARIFY_MODEL", raising=False)
    assert build_v2_3_runner_factory_from_env() is None


def test_returns_none_when_only_api_key_present(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("OPENLIA_V2_3_CLARIFY_MODEL", raising=False)
    assert build_v2_3_runner_factory_from_env() is None


def test_returns_none_when_only_model_present(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENLIA_V2_3_CLARIFY_MODEL", "gpt-5.4-mini")
    assert build_v2_3_runner_factory_from_env() is None


def test_builds_factory_with_clarify_stage_when_env_complete(monkeypatch) -> None:
    """With both env vars set, the helper must produce a factory whose
    ReportRunner has a real ClarifyStage at V23Slot.CLARIFY (not a NoOp)."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENLIA_V2_3_CLARIFY_MODEL", "gpt-5.4-mini")

    factory = build_v2_3_runner_factory_from_env()
    assert factory is not None

    runner = factory()
    assert isinstance(runner, ReportRunner)

    # Reach into the runner's stage registry to confirm CLARIFY is real
    # and backed by the env-configured LLM client (not a Fake).
    clarify_stage = runner._stages[V23Slot.CLARIFY]
    assert isinstance(clarify_stage, ClarifyStage)
    assert type(clarify_stage._client).__name__ == "LLMClarifierClient"
