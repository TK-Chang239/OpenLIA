"""tone_shift_qoq — QoQ tone shift analysis across earnings call transcripts.

Registered name: "tone_shift_qoq"
Category: LLM_NLP

Compares tone between the current quarter transcript and prior quarter transcript.
Returns overall shift direction, per-speaker/topic key shifts, hedging language
change percent, and a narrative summary.

Per helpers-design §7.2.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst. "
    "Compare two earnings call transcripts and detect tone shifts. "
    "Return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Compare the current quarter earnings call transcript to the prior quarter transcript.
Identify tone shifts between the two periods.

Return JSON matching this exact schema:
{{
  "current_quarter": "{current_quarter}",
  "prior_quarter": "{prior_quarter}",
  "overall_tone_shift": "more cautious | unchanged | more confident",
  "key_shifts": [
    {{
      "speaker_role": "CEO | CFO | management | analyst",
      "topic": "...",
      "shift_direction": "more cautious | more confident | unchanged",
      "evidence_current": "...",
      "evidence_prior": "..."
    }}
  ],
  "hedging_language_change_pct": 0.0,
  "narrative": "..."
}}

Current quarter ({current_quarter}) transcript:
{current_text}

Prior quarter ({prior_quarter}) transcript:
{prior_text}
"""


def execute(
    current_text: str,
    prior_text: str,
    current_quarter: str = "",
    prior_quarter: str = "",
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Compare transcript tone QoQ using LLM.

    Args:
        current_text: Current quarter transcript text.
        prior_text: Prior quarter transcript text.
        current_quarter: Label for the current quarter (e.g. "Q1 FY26"). Optional.
        prior_quarter: Label for the prior quarter (e.g. "Q4 FY25"). Optional.
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response.

    Returns:
        Dict with current_quarter, prior_quarter, overall_tone_shift, key_shifts,
        hedging_language_change_pct, narrative.

    Raises:
        ValueError: If either transcript text is empty.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not current_text.strip():
        raise ValueError("current_text must not be empty.")
    if not prior_text.strip():
        raise ValueError("prior_text must not be empty.")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    prompt = _USER_PROMPT_TEMPLATE.format(
        current_quarter=current_quarter or "current",
        prior_quarter=prior_quarter or "prior",
        current_text=current_text,
        prior_text=prior_text,
    )

    request = LLMRequest(
        messages=[Message(role="user", content=prompt)],
        system=_SYSTEM_PROMPT,
        max_tokens=max_tokens,
        temperature=0.0,
    )

    response = asyncio.run(llm_provider.generate(request))

    try:
        result: dict[str, Any] = json.loads(response.text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"tone_shift_qoq: LLM response is not valid JSON. Raw response: {response.text[:500]!r}"
        ) from exc

    return result


from openlia.llm.runtime.report_v2_2 import (  # noqa: E402
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
    VerifierIssueType,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper  # noqa: E402

_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="tone_shift_qoq",
        category=Category.LLM_NLP,
        one_liner="QoQ tone shift analysis comparing current and prior quarter transcripts.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Detect whether management tone shifted between the current and prior "
            "earnings call. Identifies specific speaker/topic shifts with evidence "
            "quotes and quantifies hedging language change."
        ),
        when_to_use=[
            "When analyzing management tone trajectory over multiple quarters.",
            "Corroborate guidance_tracker findings with tone evidence.",
            "Detect early warning of business deterioration via tone caution increase.",
        ],
        when_not_to_use=[
            "Single transcript with no prior period available — use transcript_tone_analysis.",
            "Non-comparable periods (e.g. annual vs quarterly calls).",
        ],
    ),
    contract=MechanicalContract(
        params={
            "current_text": HelperParam(
                type="str",
                required=True,
                description="Current quarter transcript text.",
            ),
            "prior_text": HelperParam(
                type="str",
                required=True,
                description="Prior quarter transcript text.",
            ),
            "current_quarter": HelperParam(
                type="str",
                required=False,
                default="",
                description="Label for current quarter (e.g. 'Q1 FY26'). Optional.",
            ),
            "prior_quarter": HelperParam(
                type="str",
                required=False,
                default="",
                description="Label for prior quarter (e.g. 'Q4 FY25'). Optional.",
            ),
            "llm_provider": HelperParam(
                type="LLMProvider | None",
                required=False,
                default=None,
                description="LLMProvider instance. None = use configured default.",
            ),
            "max_tokens": HelperParam(
                type="int",
                required=False,
                default=2048,
                description="Max tokens for LLM response.",
            ),
        },
        outputs=[
            HelperOutput(
                name="tone_shift_qoq_output",
                type="tone_shift_qoq_output",
                description=(
                    "current_quarter, prior_quarter, overall_tone_shift, key_shifts list, "
                    "hedging_language_change_pct, narrative."
                ),
            ),
        ],
        produces_artifacts=["tone_shift_qoq_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
    ],
)

register_helper(_SCHEMA, execute)
