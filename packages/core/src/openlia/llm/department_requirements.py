"""Per-department LLM capability requirements.

Spec: planning/specs/systems/llm-provider-design.md §Department Requirements Manifest.

Each department declares the capabilities its prompts/tools depend on. The
runtime check in `capabilities.evaluate_requirements` compares a resolved
model's `Capabilities` against these manifests to produce a Ready/Amber/Blocked
status used by Wizard Step 6 Review and Settings -> Models per-department row.
"""

from __future__ import annotations

from openlia.llm.types import Capability, DepartmentRequirements

DEPARTMENT_REQUIREMENTS: dict[str, DepartmentRequirements] = {
    "secretary": DepartmentRequirements(
        required=[Capability.STREAMING, Capability.TOOL_CALLING],
        preferred=[Capability.STRUCTURED_OUTPUT],
        min_context_tokens=8_000,
        min_output_tokens=1_024,
    ),
    "equity_research": DepartmentRequirements(
        required=[
            Capability.STREAMING,
            Capability.TOOL_CALLING,
            Capability.STRUCTURED_OUTPUT,
        ],
        preferred=[Capability.WEB_SEARCH],
        min_context_tokens=64_000,
        min_output_tokens=4_096,
    ),
    "earnings_update": DepartmentRequirements(
        required=[
            Capability.STREAMING,
            Capability.TOOL_CALLING,
            Capability.STRUCTURED_OUTPUT,
        ],
        preferred=[Capability.WEB_SEARCH],
        min_context_tokens=32_000,
        min_output_tokens=2_048,
    ),
    "morning_briefing": DepartmentRequirements(
        required=[Capability.STREAMING, Capability.TOOL_CALLING],
        preferred=[Capability.STRUCTURED_OUTPUT, Capability.WEB_SEARCH],
        min_context_tokens=16_000,
        min_output_tokens=2_048,
    ),
    "retail_sentiment": DepartmentRequirements(
        # report_dash_rs is a web-search tool-use dashboard engine (sibling of
        # macro_research): it drives classify/emit tool calls and leans on
        # native web search, so TOOL_CALLING is required and WEB_SEARCH preferred.
        required=[
            Capability.STREAMING,
            Capability.TOOL_CALLING,
            Capability.STRUCTURED_OUTPUT,
        ],
        preferred=[Capability.WEB_SEARCH],
        min_context_tokens=32_000,
        min_output_tokens=2_048,
    ),
    "macro_research": DepartmentRequirements(
        required=[
            Capability.STREAMING,
            Capability.TOOL_CALLING,
            Capability.STRUCTURED_OUTPUT,
        ],
        preferred=[Capability.WEB_SEARCH],
        min_context_tokens=64_000,
        min_output_tokens=4_096,
    ),
    "panic_thermometer": DepartmentRequirements(
        required=[Capability.STREAMING, Capability.STRUCTURED_OUTPUT],
        preferred=[Capability.TOOL_CALLING],
        min_context_tokens=8_000,
        min_output_tokens=1_024,
    ),
}


def requirements_for(department_id: str) -> DepartmentRequirements:
    """Return the DepartmentRequirements for a known department, raising on unknown ids."""
    try:
        return DEPARTMENT_REQUIREMENTS[department_id]
    except KeyError as exc:
        raise KeyError(f"No DepartmentRequirements registered for {department_id!r}") from exc
