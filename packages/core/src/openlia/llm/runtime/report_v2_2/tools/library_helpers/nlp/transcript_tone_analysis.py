"""transcript_tone_analysis — LLM-driven earnings call tone classification.

Registered name: "transcript_tone_analysis"
Category: LLM_NLP

Analyzes an earnings call transcript and classifies tone per speaker.
Returns per-speaker tone, evidence quotes, hedging/forward-looking counts,
prepared-remarks vs Q&A differential, and extraction quality.

Per helpers-design §7.1.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMRequest, Message

_SYSTEM_PROMPT = (
    "You are an expert equity research analyst specializing in earnings call analysis. "
    "Analyze the transcript precisely and return valid JSON only."
)

_USER_PROMPT_TEMPLATE = """\
Analyze this earnings call transcript. For each speaker, classify their tone:
- Management tones: confident | cautious | hedging | defensive
- Analyst tones: constructive | challenging | neutral

Detect hedging language (phrases like "we expect", "we believe", "subject to", \
"may", "could", "depending on"). Count occurrences per speaker.

Identify forward-looking statements (statements about future periods). Count per speaker.

Compare prepared-remarks tone vs Q&A tone — note any differential.

Provide 2-3 evidence quotes per speaker supporting your tone classification.
Quote text exactly; do not paraphrase.

Speakers list (if known): {speakers_list}

Return JSON matching this exact schema:
{{
  "speakers": [
    {{
      "name": "...",
      "role": "management | analyst | moderator | unknown",
      "tone": "...",
      "evidence_quotes": ["..."],
      "hedging_language_count": 0,
      "forward_looking_count": 0
    }}
  ],
  "prepared_remarks_tone": "...",
  "qa_tone": "...",
  "prepared_vs_qa_tone_differential": "...",
  "hedging_language_themes": ["..."],
  "extraction_quality": "high | medium | low"
}}

Transcript:
{transcript_text}
"""


def execute(
    transcript_text: str,
    speakers_list: list[str] | None = None,
    llm_provider: LLMProvider | None = None,
    max_tokens: int = 2048,
) -> dict[str, Any]:
    """Analyze earnings call transcript tone using LLM.

    Args:
        transcript_text: Full transcript text. May be a raw string or output from
            pdf_ingest (concatenate pages[*].text before passing).
        speakers_list: Known speaker names for disambiguation. None = auto-detect.
        llm_provider: LLMProvider instance. None = load configured default.
        max_tokens: Max tokens for LLM response. Default 2048.

    Returns:
        Dict with speakers list (name, role, tone, evidence_quotes,
        hedging_language_count, forward_looking_count),
        prepared_remarks_tone, qa_tone, prepared_vs_qa_tone_differential,
        hedging_language_themes, extraction_quality.

    Raises:
        ValueError: If transcript_text is empty.
        RuntimeError: If LLM response cannot be parsed as JSON.
    """
    if not transcript_text.strip():
        raise ValueError("transcript_text must not be empty.")

    if llm_provider is None:
        from openlia.llm.providers import get_default_provider

        llm_provider = get_default_provider()

    speakers_str = ", ".join(speakers_list) if speakers_list else "auto-detect"
    prompt = _USER_PROMPT_TEMPLATE.format(
        speakers_list=speakers_str,
        transcript_text=transcript_text,
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
            f"transcript_tone_analysis: LLM response is not valid JSON. "
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
        name="transcript_tone_analysis",
        category=Category.LLM_NLP,
        one_liner="LLM-driven per-speaker tone classification for earnings call transcripts.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Classify the tone of each speaker in an earnings call transcript. "
            "Detects hedging language, forward-looking statement counts, and "
            "prepared-remarks vs Q&A tone differential."
        ),
        when_to_use=[
            "Earnings call section of any initiation or quarterly update report.",
            "When tone_shift_qoq requires per-quarter tone baselines.",
            "Detecting management defensiveness or hedging escalation.",
        ],
        when_not_to_use=[
            "Press releases or 8-K filings — use forward_looking_statements instead.",
            "Non-earnings call text (MD&A, risk factors) — use mda_extraction.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "transcript_text": HelperParam(
                type="str",
                required=True,
                description="Full transcript text. Concatenate pdf_ingest pages if from PDF.",
            ),
            "speakers_list": HelperParam(
                type="list[str] | None",
                required=False,
                default=None,
                description="Known speaker names for disambiguation. None = auto-detect.",
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
                name="transcript_tone_output",
                type="transcript_tone_output",
                description=(
                    "speakers list, prepared_remarks_tone, qa_tone, "
                    "prepared_vs_qa_tone_differential, hedging_language_themes, "
                    "extraction_quality."
                ),
            ),
        ],
        produces_artifacts=["transcript_tone_output"],
        consumes_artifacts=[],
    ),
    skill_doc=None,
    verifier_hooks=[
        VerifierIssueType.TOMBSTONE,
        VerifierIssueType.CITATION_MISSING,
    ],
)

register_helper(_SCHEMA, execute)
