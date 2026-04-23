"""Prompt builder for the wizard AI review step."""

from __future__ import annotations

import json

PROMPT_HEADER = """You are reviewing a self-hosted AI investor assistant's data provider setup.
Given a list of departments (each with required data-requirement types) and a list of
configured data providers, return a JSON object mapping each department to a readiness
state. Use "ready" when every basic requirement has a confidence>=0.7 match, "gaps"
when basic requirements are all met but one or more advanced requirements are unmapped,
"disabled" when the department depends on a capability nothing ships, and "blocked"
when any basic requirement is unmet.

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
