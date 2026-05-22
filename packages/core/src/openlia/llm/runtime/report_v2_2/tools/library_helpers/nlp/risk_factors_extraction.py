"""risk_factors_extraction — LLM-driven Item 1A risk factor extraction from 10-K.

Registered name: "risk_factors_extraction"
Category: LLM_NLP

Extracts and categorizes risk factors from a 10-K Item 1A section.
Risk categories: operational, financial, governance, macro, regulatory, competitive.
Optional YoY change detection when prior-year text is provided.

Per helpers-design §7.4.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

# Closed enum per design spec
_VALID_CATEGORIES = frozenset(
    {"operational", "financial", "governance", "macro", "regulatory", "competitive"}
)

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst extracting and categorizing risk factors "
    "from 10-K Item 1A sections. Return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Extract and categorize all risk factors from this 10-K Item 1A section.

Categories (use exactly these values):
operational | financial | governance | macro | regulatory | competitive

{prior_instructions}

Return JSON matching this exact schema:
{{
  "total_risk_count": 0,
  "risks": [
    {{
      "title": "...",
      "category": "operational | financial | governance | macro | regulatory | competitive",
      "text_excerpt": "...",
      "first_appeared_year": null,
      "language_changed_from_prior_year": false,
      "language_change_summary": null
    }}
  ],
  "categories_breakdown": {{
    "operational": 0,
    "financial": 0,
    "governance": 0,
    "macro": 0,
    "regulatory": 0,
    "competitive": 0
  }},
  "new_risks_this_year": [],
  "removed_risks_from_prior_year": []
}}

Set language_changed_from_prior_year to true only when prior_year_text is provided
and language materially changed. Set first_appeared_year to null if unknown.

Item 1A text:
{risk_text}

{prior_year_section}
"""


def execute(
    risk_text: str,
    prior_year_text: str | None = None,
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 4000,
) -> dict[str, Any]:
    """Extract and categorize risk factors from 10-K Item 1A using LLM.

    Args:
        risk_text: Item 1A text from the current 10-K.
        prior_year_text: Item 1A text from the prior year 10-K (optional).
            When provided, enables YoY change detection.
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response.

    Returns:
        Dict with total_risk_count, risks list (title, category, text_excerpt,
        first_appeared_year, language_changed_from_prior_year, language_change_summary),
        categories_breakdown, new_risks_this_year, removed_risks_from_prior_year.

    Raises:
        ValueError: If risk_text is empty.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not risk_text.strip():
        raise ValueError("risk_text must not be empty.")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    if prior_year_text:
        prior_instructions = (
            "Prior year text is provided below. Identify new risks (in current but not prior) "
            "and removed risks (in prior but not current). Flag language changes."
        )
        prior_year_section = f"Prior year Item 1A text:\n{prior_year_text}"
    else:
        prior_instructions = (
            "No prior year text provided. "
            "Set new_risks_this_year and removed_risks_from_prior_year to []."
        )
        prior_year_section = ""

    prompt = _USER_PROMPT_TEMPLATE.format(
        prior_instructions=prior_instructions,
        risk_text=risk_text,
        prior_year_section=prior_year_section,
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
            f"risk_factors_extraction: LLM response is not valid JSON. "
            f"Raw response: {response.text[:500]!r}"
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
        name="risk_factors_extraction",
        category=Category.LLM_NLP,
        one_liner="Extract and categorize Item 1A risk factors from 10-K with optional YoY diff.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract all risk factors from a 10-K Item 1A section. Categorizes into "
            "operational, financial, governance, macro, regulatory, competitive. "
            "When prior-year text is provided, detects new/removed risks and language changes."
        ),
        when_to_use=[
            "Risk section of any equity initiation or annual update report.",
            "Flagging elevated regulatory or macro risk YoY.",
            "Feeding into forward_looking_statements for comprehensive risk framing.",
        ],
        when_not_to_use=[
            "10-Q risk sections (abbreviated; prefer 10-K annual).",
            "Earnings call transcripts — use transcript_tone_analysis instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "risk_text": HelperParam(
                type="str",
                required=True,
                description="Item 1A text from the current 10-K.",
            ),
            "prior_year_text": HelperParam(
                type="str | None",
                required=False,
                default=None,
                description="Item 1A text from prior year 10-K for YoY diff. Optional.",
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
                default=4000,
                description="Max tokens for LLM response.",
            ),
        },
        outputs=[
            HelperOutput(
                name="risk_factors_extraction_output",
                type="risk_factors_extraction_output",
                description=(
                    "total_risk_count, risks list (title, category, text_excerpt, "
                    "first_appeared_year, language_changed_from_prior_year, "
                    "language_change_summary), categories_breakdown, "
                    "new_risks_this_year, removed_risks_from_prior_year."
                ),
            ),
        ],
        produces_artifacts=["risk_factors_extraction_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
    ],
)

register_helper(_SCHEMA, execute)
