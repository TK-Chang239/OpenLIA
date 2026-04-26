"""Prompt builder for the wizard AI review step.

The provider payload includes each provider's `declared_capabilities` (from
the in-process adapter catalog). For providers whose `kind` is not in the
catalog, payload entries carry `unknown: true`. The header tells the LLM to
ground mappings in `declared_capabilities` for known providers and cap
confidence at 0.5 for unknown ones — without that grounding, the LLM
hallucinates support based on the provider's name alone.
"""

from __future__ import annotations

import json

PROMPT_HEADER = """You are reviewing a self-hosted AI investor assistant's data provider setup.
Given a list of departments (each with required data-requirement types) and a list of
configured data providers, return a JSON object mapping each department to a readiness
state.

Grounding rules (MANDATORY):
- When a provider entry has a non-empty `declared_capabilities` list, you MUST only map
  a requirement to that provider if the requirement type appears verbatim in
  `declared_capabilities`. Do not infer support from the provider's name or category.
- When a provider entry has an empty `declared_capabilities` list and `unknown` is
  false, that provider satisfies no requirements (registry stub) — never map to it.
- When `unknown` is true, the provider's adapter is not registered locally; you may use
  general knowledge of the service named in `kind`, but cap confidence at 0.5 and add a
  short note explaining the inference.

Use "ready" when every basic requirement has a confidence>=0.7 match, "gaps" when basic
requirements are all met but one or more advanced requirements are unmapped, "disabled"
when the department depends on a capability nothing ships, and "blocked" when any basic
requirement is unmet.

Respond ONLY with JSON matching the schema:
{
  "summary": str,
  "departments": [
    {
      "id": str,
      "state": "ready" | "gaps" | "disabled" | "blocked",
      "note": str | null,
      "basic": [{"type": str, "provider": str | null, "confidence": float}],
      "advanced": [{"type": str, "provider": str | null, "confidence": float}],
      "unmet": [str]
    }
  ]
}
"""


def build_review_prompt(
    departments: list[tuple[str, list[str]]],
    providers: list[dict[str, object]],
) -> str:
    body = {
        "departments": [{"id": d, "basic_requirements": reqs} for d, reqs in departments],
        "providers": providers,
    }
    return f"{PROMPT_HEADER}\nINPUT:\n{json.dumps(body, indent=2)}"
