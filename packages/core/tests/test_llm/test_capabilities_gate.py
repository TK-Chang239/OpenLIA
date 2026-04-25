"""NEW-4-23: evaluate_requirements vs DepartmentRequirements."""

from __future__ import annotations

from openlia.llm.capabilities import capabilities_for, evaluate_requirements
from openlia.llm.department_requirements import requirements_for
from openlia.llm.types import Capabilities, Capability, DepartmentRequirements


def test_ready_for_anthropic_sonnet_equity_research() -> None:
    caps = capabilities_for(provider_kind="anthropic", model="claude-sonnet-4")
    report = evaluate_requirements(caps, requirements_for("equity_research"))
    assert report.status == "ready"
    assert report.missing_required == []


def test_blocked_for_ollama_codellama_equity_research() -> None:
    # codellama is not in the capability map and falls back to Capabilities()
    # whose tool_calling=False -> blocks an equity_research requirement.
    caps = capabilities_for(provider_kind="ollama", model="codellama:13b")
    report = evaluate_requirements(caps, requirements_for("equity_research"))
    assert report.status == "blocked"
    assert Capability.TOOL_CALLING in report.missing_required


def test_amber_when_only_preferred_missing() -> None:
    caps = Capabilities(streaming=True, tool_calling=True, structured_output=True)
    reqs = DepartmentRequirements(
        required=[Capability.STREAMING, Capability.TOOL_CALLING],
        preferred=[Capability.WEB_SEARCH],
    )
    report = evaluate_requirements(caps, reqs)
    assert report.status == "amber"
    assert Capability.WEB_SEARCH in report.missing_preferred


def test_blocked_when_min_context_tokens_unmet() -> None:
    caps = Capabilities(streaming=True, max_context_tokens=4_000)
    reqs = DepartmentRequirements(
        required=[Capability.STREAMING],
        min_context_tokens=8_000,
    )
    report = evaluate_requirements(caps, reqs)
    assert report.status == "blocked"
    assert report.insufficient_context_tokens == 8_000


def test_all_shipped_dept_tier_default_pairs_are_ready() -> None:
    pairs = [
        ("secretary", "anthropic", "claude-haiku-4"),
        ("equity_research", "anthropic", "claude-sonnet-4"),
        ("earnings_update", "openai", "gpt-5.4"),
        ("morning_briefing", "gemini", "gemini-3.1-flash"),
        ("retail_sentiment", "openai", "gpt-5.4-mini"),
        ("macro_research", "anthropic", "claude-sonnet-4"),
        ("panic_thermometer", "openai", "gpt-5.4-mini"),
    ]
    for dept, kind, model in pairs:
        caps = capabilities_for(provider_kind=kind, model=model)
        report = evaluate_requirements(caps, requirements_for(dept))
        assert report.status in ("ready", "amber"), f"{dept}/{kind}:{model} -> {report}"
