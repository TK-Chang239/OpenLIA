"""forward_looking_statements — extract and classify forward-looking statements.

Registered name: "forward_looking_statements"
Category: LLM_NLP

Extracts forward-looking statements from a filing or transcript with hedging
language analysis. Each statement is classified by category, confidence indicator,
qualifiers, time horizon, metric, and value range.

Per helpers-design §7.5.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

_VALID_SOURCES = frozenset({"earnings_call", "10-Q", "10-K", "press_release", "other"})
_VALID_CATEGORIES = frozenset(
    {"guidance", "outlook", "risk_factor_qualifier", "strategic_statement"}
)
_VALID_CONFIDENCE = frozenset({"high", "moderate", "low"})

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst identifying forward-looking statements "
    "and hedging language in financial filings and earnings call transcripts. "
    "Return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Extract all forward-looking statements from this text. A forward-looking statement
is any claim about future events, results, plans, or expectations.

For each statement, classify:
- category: guidance | outlook | risk_factor_qualifier | strategic_statement
- confidence_indicator: high | moderate | low
  (high = specific numbers/ranges, moderate = directional with qualifiers, low = vague)
- qualifiers: list of hedging words/phrases used (e.g. "expect", "may", "subject to")
- time_horizon: specific period if stated (e.g. "Q2 FY26", "FY26", "long-term")
- metric: financial metric referenced if applicable (e.g. "revenue", "EPS", null)
- value_range: [low, high] in base units if a numeric range is stated, otherwise null

Return JSON matching this schema:
{{
  "source": "{source}",
  "statements": [
    {{
      "text": "...",
      "category": "guidance | outlook | risk_factor_qualifier | strategic_statement",
      "confidence_indicator": "high | moderate | low",
      "qualifiers": ["..."],
      "time_horizon": "...",
      "metric": null,
      "value_range": null
    }}
  ]
}}

Text:
{text}
"""


def execute(
    text: str,
    source: str = "other",
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 3000,
) -> dict[str, Any]:
    """Extract forward-looking statements from filing or transcript text using LLM.

    Args:
        text: Filing or transcript text to analyze.
        source: Source document type. One of: earnings_call, 10-Q, 10-K,
            press_release, other.
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response.

    Returns:
        Dict with source and statements list (text, category, confidence_indicator,
        qualifiers, time_horizon, metric, value_range).

    Raises:
        ValueError: If text is empty or source is not a recognized value.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not text.strip():
        raise ValueError("text must not be empty.")

    if source not in _VALID_SOURCES:
        raise ValueError(f"source must be one of {sorted(_VALID_SOURCES)}; got {source!r}")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    prompt = _USER_PROMPT_TEMPLATE.format(source=source, text=text)

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
            f"forward_looking_statements: LLM response is not valid JSON. "
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
        name="forward_looking_statements",
        category=Category.LLM_NLP,
        one_liner=(
            "Extract forward-looking statements with hedging language analysis "
            "from filings or transcripts."
        ),
    ),
    selection=SelectionGuidance(
        purpose=(
            "Identify all forward-looking statements in a filing or transcript. "
            "Classifies each by category (guidance/outlook/qualifier/strategic), "
            "confidence level, hedging qualifiers, time horizon, and metric/value range."
        ),
        when_to_use=[
            "Guidance extraction before feeding guidance_tracker.",
            "Qualitative risk framing overlay for any report section.",
            "Comparing forward-looking language density QoQ alongside tone_shift_qoq.",
        ],
        when_not_to_use=[
            "When a specific guidance-vs-actual track record is needed — use guidance_tracker.",
            "Historical financial analysis — use quantitative helpers instead.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "text": HelperParam(
                type="str",
                required=True,
                description="Filing or transcript text to analyze.",
            ),
            "source": HelperParam(
                type="str",
                required=False,
                default="other",
                description=(
                    "Source document type: earnings_call | 10-Q | 10-K | press_release | other."
                ),
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
                name="forward_looking_statements_output",
                type="forward_looking_statements_output",
                description=(
                    "source, statements list (text, category, confidence_indicator, "
                    "qualifiers, time_horizon, metric, value_range)."
                ),
            ),
        ],
        produces_artifacts=["forward_looking_statements_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
    ],
)

register_helper(_SCHEMA, execute)
