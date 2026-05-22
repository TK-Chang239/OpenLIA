"""mda_extraction — LLM-driven MD&A section extraction from 10-K / 10-Q.

Registered name: "mda_extraction"
Category: LLM_NLP

Extracts key business drivers, headwinds, management outlook statements,
non-GAAP reconciliation mentions, and per-segment commentary from
an MD&A text section.

Per helpers-design §7.3.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst extracting structured insights from "
    "SEC filing MD&A sections. Return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Extract structured insights from this MD&A section.

Return JSON matching this exact schema:
{{
  "company": "{company}",
  "period": "{period}",
  "key_drivers_mentioned": [
    {{
      "driver": "...",
      "direction": "positive | negative | neutral",
      "evidence_quote": "..."
    }}
  ],
  "key_headwinds_mentioned": [
    {{
      "headwind": "...",
      "magnitude_quote": "...",
      "estimated_impact": "..."
    }}
  ],
  "management_outlook_statements": ["..."],
  "non_gaap_reconciliation_mentions": ["..."],
  "segment_commentary": [
    {{
      "segment": "...",
      "growth_rate_disclosed": null,
      "narrative": "..."
    }}
  ]
}}

Set growth_rate_disclosed to a decimal (e.g. 0.32 for 32% growth) if explicitly stated,
otherwise null.

MD&A text:
{mda_text}
"""


def execute(
    mda_text: str,
    company: str = "",
    period: str = "",
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 3000,
) -> dict[str, Any]:
    """Extract structured insights from an MD&A section using LLM.

    Args:
        mda_text: MD&A section text. May come directly from pdf_ingest pages or
            as a raw string.
        company: Company name for context. Optional.
        period: Reporting period label (e.g. "Q3 FY25"). Optional.
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response.

    Returns:
        Dict with company, period, key_drivers_mentioned, key_headwinds_mentioned,
        management_outlook_statements, non_gaap_reconciliation_mentions,
        segment_commentary.

    Raises:
        ValueError: If mda_text is empty.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not mda_text.strip():
        raise ValueError("mda_text must not be empty.")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    prompt = _USER_PROMPT_TEMPLATE.format(
        company=company or "unknown",
        period=period or "unknown",
        mda_text=mda_text,
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
            f"mda_extraction: LLM response is not valid JSON. Raw response: {response.text[:500]!r}"
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
        name="mda_extraction",
        category=Category.LLM_NLP,
        one_liner="Extract key drivers, headwinds, and outlook from MD&A sections of 10-K/10-Q.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract structured business insights from the MD&A section of a 10-K or "
            "10-Q filing. Identifies drivers, headwinds, forward-looking statements, "
            "non-GAAP mentions, and segment-level commentary."
        ),
        when_to_use=[
            "Earnings analysis section of any report using SEC filing text.",
            "Feeding organic_vs_inorganic_growth or one_time_item_identification helpers.",
            "Building a qualitative overlay on top of quantitative financials.",
        ],
        when_not_to_use=[
            "Earnings call transcripts — use transcript_tone_analysis instead.",
            "Risk factor extraction — use risk_factors_extraction instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "mda_text": HelperParam(
                type="str",
                required=True,
                description="MD&A section text from filing.",
            ),
            "company": HelperParam(
                type="str",
                required=False,
                default="",
                description="Company name for context. Optional.",
            ),
            "period": HelperParam(
                type="str",
                required=False,
                default="",
                description="Reporting period label (e.g. 'Q3 FY25'). Optional.",
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
                default=3000,
                description="Max tokens for LLM response.",
            ),
        },
        outputs=[
            HelperOutput(
                name="mda_extraction_output",
                type="mda_extraction_output",
                description=(
                    "company, period, key_drivers_mentioned, key_headwinds_mentioned, "
                    "management_outlook_statements, non_gaap_reconciliation_mentions, "
                    "segment_commentary."
                ),
            ),
        ],
        produces_artifacts=["mda_extraction_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
    ],
)

register_helper(_SCHEMA, execute)
