"""customer_concentration_extraction — extract customer concentration disclosures.

Registered name: "customer_concentration_extraction"
Category: LLM_NLP

Extracts customer concentration disclosures from 10-K Item 1 and/or Item 14
text. Returns top customer percent, top-3/top-10 percents, named customers,
geographic/industry concentration, source quote, and risk framing.

Risk framing thresholds (per design §7.7):
- top_customer > 10%: "high"
- top_3 > 30%: "high"
- otherwise: "moderate" or "low" (LLM judgment)

Per helpers-design §7.7.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst extracting customer concentration "
    "disclosures from 10-K filings. Return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Extract customer concentration disclosures from this 10-K text.

Return JSON matching this exact schema:
{{
  "disclosed": true,
  "top_customer_pct_of_revenue": null,
  "top_3_customers_pct": null,
  "top_10_customers_pct": null,
  "named_customers": [],
  "geographic_concentration_pct_by_region": {{}},
  "industry_concentration_pct_by_industry": {{}},
  "source_quote": "",
  "risk_framing": "low | moderate | high"
}}

Rules:
- Set disclosed=false if no customer concentration data is mentioned.
- Set percentages as decimals (e.g. 0.18 for 18%). Set null if not disclosed.
- risk_framing: use "high" if top_customer_pct > 0.10 OR top_3_customers_pct > 0.30;
  use "low" if top_customer_pct < 0.05 AND top_3_customers_pct < 0.10; otherwise "moderate".
- If no geographic/industry concentration is disclosed, use empty dicts.
- source_quote: exact verbatim quote from the text that supports the concentration figure.

10-K text:
{text}
"""


def execute(
    text: str,
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Extract customer concentration disclosures from 10-K text using LLM.

    Args:
        text: 10-K Item 1 and/or Item 14 text (or full 10-K text).
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response.

    Returns:
        Dict with disclosed, top_customer_pct_of_revenue, top_3_customers_pct,
        top_10_customers_pct, named_customers, geographic_concentration_pct_by_region,
        industry_concentration_pct_by_industry, source_quote, risk_framing.

    Raises:
        ValueError: If text is empty.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not text.strip():
        raise ValueError("text must not be empty.")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    prompt = _USER_PROMPT_TEMPLATE.format(text=text)

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
            f"customer_concentration_extraction: LLM response is not valid JSON. "
            f"Raw response: {response.text[:500]!r}"
        ) from exc

    # Apply deterministic risk framing override based on thresholds
    top_cust = result.get("top_customer_pct_of_revenue")
    top_3 = result.get("top_3_customers_pct")

    if (top_cust is not None and top_cust > 0.10) or (top_3 is not None and top_3 > 0.30):
        result["risk_framing"] = "high"
    elif (top_cust is not None and top_cust < 0.05) and (top_3 is None or top_3 < 0.10):
        result["risk_framing"] = "low"
    elif "risk_framing" not in result:
        result["risk_framing"] = "moderate"

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
        name="customer_concentration_extraction",
        category=Category.LLM_NLP,
        one_liner="Extract customer concentration disclosures from 10-K with risk framing.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract customer concentration data from 10-K Item 1 and Item 14. "
            "Produces top customer %, top-3/top-10 percentages, named customers, "
            "geographic and industry concentration, and risk framing "
            "(high if top customer > 10% or top-3 > 30%)."
        ),
        when_to_use=[
            "Business quality section of any initiation or annual update report.",
            "Flagging revenue concentration risk for enterprise SaaS or B2B companies.",
            "Supplement to saas_kpi_panel_output customer concentration field.",
        ],
        when_not_to_use=[
            "Consumer-facing businesses with no meaningful customer concentration.",
            "When concentration data is already in a structured financial dataset.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "text": HelperParam(
                type="str",
                required=True,
                description="10-K Item 1 and/or Item 14 text (or full 10-K text).",
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
                name="customer_concentration_output",
                type="customer_concentration_output",
                description=(
                    "disclosed, top_customer_pct_of_revenue, top_3_customers_pct, "
                    "top_10_customers_pct, named_customers, "
                    "geographic_concentration_pct_by_region, "
                    "industry_concentration_pct_by_industry, source_quote, risk_framing."
                ),
            ),
        ],
        produces_artifacts=["customer_concentration_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
        VerifierIssueType.NUMERIC_INCONSISTENCY,
    ],
)

register_helper(_SCHEMA, execute)
