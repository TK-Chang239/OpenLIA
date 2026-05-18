"""W2: per-section pre-flight call.

A tiny structured-output call per section. Declares searches + fetches + proposed_facts.
No facts are added at runtime; proposed_facts is telemetry-only.
"""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PreflightSearch(_Strict):
    query: str
    intent: str


class PreflightFetch(_Strict):
    provider: str
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class PreflightDeclaration(_Strict):
    section_id: str
    searches: list[PreflightSearch] = Field(default_factory=list)
    fetches: list[PreflightFetch] = Field(default_factory=list)
    proposed_facts: list[str] = Field(default_factory=list)


PREFLIGHT_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["searches", "fetches", "proposed_facts"],
    "properties": {
        "searches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["query", "intent"],
                "properties": {
                    "query": {"type": "string"},
                    "intent": {"type": "string"},
                },
            },
        },
        "fetches": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["provider", "tool", "args"],
                "properties": {
                    "provider": {"type": "string"},
                    "tool": {"type": "string"},
                    "args": {"type": "object"},
                },
            },
        },
        "proposed_facts": {"type": "array", "items": {"type": "string"}},
    },
}


class StructuredOutputProvider(Protocol):
    async def structured_output(self, *, prompt: str, schema: dict[str, Any]) -> dict[str, Any]: ...


_PROMPT_TEMPLATE = """You are the pre-flight planner for section {section_id}.

SUBJECT TICKER: {ticker}

SECTION BRIEF:
{section_brief}

ALREADY-FETCHED MANIFEST:
{manifest_list}

REGISTERED FACT NAMES YOU CAN ASSUME ARE COMPUTED:
{known_facts}

Declare what additional data you need to write this section well.
Output JSON with three fields:
- searches: web search queries (with brief intent labels)
- fetches: structured tool calls (provider, tool, args). When constructing fetch args
  that require a ticker symbol, use the SUBJECT TICKER above (e.g. {{"ticker": "{ticker}"}}).
- proposed_facts: NEW fact names you think should exist but aren't in the registered list above.
  These are telemetry-only — they will NOT be added at runtime. Use this to signal gaps.

Be specific. Do not declare data you already have."""


async def run_section_preflight(
    *,
    provider: StructuredOutputProvider,
    section_id: str,
    section_brief: str,
    manifest: Manifest,
    known_fact_names: list[str],
    ticker: str = "",
) -> PreflightDeclaration:
    prompt = _PROMPT_TEMPLATE.format(
        section_id=section_id,
        ticker=ticker,
        section_brief=section_brief,
        manifest_list=manifest.as_prompt_list() or "(empty)",
        known_facts="\n".join(f"- {n}" for n in sorted(known_fact_names)),
    )
    raw = await provider.structured_output(prompt=prompt, schema=PREFLIGHT_OUTPUT_SCHEMA)
    return PreflightDeclaration.model_validate({"section_id": section_id, **raw})
