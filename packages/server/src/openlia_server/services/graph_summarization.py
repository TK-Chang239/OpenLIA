"""Slice 11 — LLM-backed report summary indexer.

The nightly extraction job (slice 6, wired later) calls
``index_report_summary`` on each newly-saved report. The indexer asks
the model assigned to the ``graph_summarization`` system role for a
structured summary in the claude-mem style, embeds the summary text,
and persists the result via ``upsert_artifact_summary``.

Production code uses ``make_summarize_fn(client)`` to build the
summarize callable from any LLM client implementing the
``openlia.llm.types`` ``generate`` contract. Tests inject a
deterministic fake so they don't have to mock the model.

Parser hardening follows the slice-8 extractor pattern: any field
outside its declared enum drops to ``None``, malformed lists drop to
``[]``, and non-JSON responses return safe defaults. The nightly job
must never crash on a single bad LLM response.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any, Protocol

from openlia.llm.embeddings import EmbeddingProvider
from openlia.llm.types import LLMRequest, LLMResponse, Message, ResponseFormat
from sqlalchemy.orm import Session

from openlia_server.db.models.content import Report
from openlia_server.db.models.graph import GraphArtifactSummary
from openlia_server.services.graph_vectors import upsert_artifact_summary

SummarizeFn = Callable[[Report], dict[str, Any]]


class _ClientLike(Protocol):
    def generate(self, request: LLMRequest) -> LLMResponse: ...


_VALID_TONES: frozenset[str] = frozenset({"bullish", "bearish", "neutral"})
_VALID_HORIZONS: frozenset[str] = frozenset({"short", "medium", "long"})


SYSTEM_PROMPT = """You summarize a financial report into a structured
record so a future session can recall it by topic, tone, and horizon.

CRITICAL OUTPUT CONTRACT — read carefully:
- Your entire response MUST be a single JSON object.
- Any prose, preamble, code fences, or trailing commentary will be
  discarded as a protocol violation.
- If you are uncertain about a field, leave it null. Empty lists are
  fine. A wrong tag is worse than a missing one.

Schema:

{
  "subject": "<short noun phrase — usually a ticker or theme>",
  "tagline": "<one-sentence thesis or headline finding>",
  "findings": [
    "<short bullet — concrete claim or number>",
    "..."
  ],
  "entities_mentioned": [
    "ticker:NVDA",
    "sector:semiconductors",
    "theme:ai-capex",
    "macro_regime:risk-off"
  ],
  "tone": "bullish" | "bearish" | "neutral" | null,
  "horizon": "short" | "medium" | "long" | null
}

Field rules (every invalid field drops to null; the whole record never
crashes the indexer):
- ``subject`` MUST be a non-empty string.
- ``tagline`` MUST be a non-empty string.
- ``findings`` MUST be a list of 1-3 short strings. Each bullet is a
  concrete claim ("Services margin up 400bps"), not a paragraph.
- ``entities_mentioned`` MUST be a list of canonical ids in the form
  ``kind:value`` where kind is one of ticker, sector, theme,
  macro_regime. Tickers UPPERCASE; sectors/themes/macro_regimes
  kebab-case.
- ``tone`` MUST be one of: bullish, bearish, neutral. Else null.
- ``horizon`` MUST be one of: short, medium, long. Else null.

When in doubt, leave it out. The cost of a missed tag is one less
filter signal; the cost of a wrong tag is a permanently miscategorized
report.
"""


def index_report_summary(
    db: Session,
    *,
    user_id: str,
    report: Report,
    summarize_fn: SummarizeFn,
    embed_provider: EmbeddingProvider,
    embed_model_name: str,
) -> GraphArtifactSummary:
    """LLM-summarize a report and persist the artifact summary row.

    The summarizer is injected so tests can pass a deterministic fake
    instead of running a real LLM. Production wiring uses
    ``make_summarize_fn(client)``.
    """
    raw = summarize_fn(report)

    subject = raw.get("subject") if isinstance(raw.get("subject"), str) else None
    tagline = raw.get("tagline") if isinstance(raw.get("tagline"), str) else None
    findings = _coerce_findings(raw.get("findings"))
    entities_mentioned = _coerce_string_list(raw.get("entities_mentioned"))
    tone = raw.get("tone") if raw.get("tone") in _VALID_TONES else None
    horizon = raw.get("horizon") if raw.get("horizon") in _VALID_HORIZONS else None

    findings_text = "\n".join(findings)
    summary_text = f"{subject or ''}\n{tagline or ''}\n{findings_text}".strip("\n")

    return upsert_artifact_summary(
        db,
        user_id=user_id,
        artifact_kind="report",
        artifact_id=report.id,
        summary_text=summary_text,
        provider=embed_provider,
        model_name=embed_model_name,
        subject=subject,
        tagline=tagline,
        findings_text=findings_text,
        entities_mentioned=entities_mentioned,
        tone=tone,
        horizon=horizon,
    )


def make_summarize_fn(client: _ClientLike) -> SummarizeFn:
    """Build a production ``SummarizeFn`` from any LLM client.

    Mirrors ``graph_extraction_llm.make_extract_fn``: renders the
    report into the request, asks for JSON, parses the response, and
    drops invalid fields to safe defaults so a single bad LLM turn
    can't crash the nightly job.
    """

    def _summarize(report: Report) -> dict[str, Any]:
        rendered = _render_report(report)
        request = LLMRequest(
            messages=[Message(role="user", content=rendered)],
            system=SYSTEM_PROMPT,
            response_format=ResponseFormat(kind="json_object"),
            max_tokens=2048,
            temperature=0.0,
        )
        response = client.generate(request)
        return _parse(response.text)

    return _summarize


def _render_report(report: Report) -> str:
    subject = report.subject or ""
    title = report.title or ""
    body = report.content_markdown or ""
    return f"# {title}\n\nSubject: {subject}\n\n---\n\n{body}"


def _parse(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return _safe_defaults()
    if not isinstance(data, dict):
        return _safe_defaults()

    subject = data.get("subject") if isinstance(data.get("subject"), str) else None
    tagline = data.get("tagline") if isinstance(data.get("tagline"), str) else None
    findings = _coerce_findings(data.get("findings"))
    entities = _coerce_string_list(data.get("entities_mentioned"))
    tone = data.get("tone") if data.get("tone") in _VALID_TONES else None
    horizon = data.get("horizon") if data.get("horizon") in _VALID_HORIZONS else None

    return {
        "subject": subject,
        "tagline": tagline,
        "findings": findings,
        "entities_mentioned": entities,
        "tone": tone,
        "horizon": horizon,
    }


def _safe_defaults() -> dict[str, Any]:
    return {
        "subject": None,
        "tagline": None,
        "findings": [],
        "entities_mentioned": [],
        "tone": None,
        "horizon": None,
    }


def _coerce_findings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v.strip() != ""]


def _coerce_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v for v in value if isinstance(v, str) and v.strip() != ""]
