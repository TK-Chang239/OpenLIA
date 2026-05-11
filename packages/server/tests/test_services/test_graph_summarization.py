"""Slice 11 — LLM-backed report summary indexer.

The nightly extraction job (slice 6, wired later) will call
``index_report_summary`` on each newly-saved report. The indexer asks
the user's quick-tier LLM for a structured summary (claude-mem
methodology), embeds the summary text, and persists everything via
``upsert_artifact_summary``.

Tests inject a deterministic fake summarize_fn + the fake embedding
provider, then read back the row via a direct DB query to verify the
six structured fields landed correctly. The production factory
(``make_summarize_fn``) is also tested for parser hardening — invalid
fields drop to None rather than crashing the job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openlia.llm.embeddings.fake import FakeEmbeddingProvider
from openlia.llm.types import LLMRequest, LLMResponse
from openlia_server.db.models.content import Report
from openlia_server.db.models.graph import GraphArtifactSummary
from openlia_server.services import graph_summarization
from sqlalchemy import select


def _make_report(
    db_session,
    *,
    report_id: str = "rep-1",
    subject: str = "NVDA",
    user_id: str = "u-1",
) -> Report:
    row = Report(
        id=report_id,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=f"{subject} Initiation",
        subject=subject,
        content_markdown="body",
        content_structured={},
        model_ref="anthropic_sonnet",
    )
    db_session.add(row)
    db_session.flush()
    return row


@dataclass
class _RecordingClient:
    canned_text: str
    last_request: LLMRequest | None = None

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.last_request = request
        return LLMResponse(
            text=self.canned_text,
            finish_reason="stop",
            input_tokens=0,
            output_tokens=0,
        )


def test_index_report_summary_writes_all_structured_fields(db_session) -> None:
    """Happy path: indexer persists a row with every structured field
    populated from the summarize_fn output."""
    report = _make_report(db_session)
    provider = FakeEmbeddingProvider(dim=8)

    def fake_summarize(_report: Report) -> dict[str, Any]:
        return {
            "subject": "NVDA",
            "tagline": "Services margin durable",
            "findings": [
                "Services margin up 400bps",
                "Data center beat",
            ],
            "entities_mentioned": ["ticker:NVDA", "sector:semis"],
            "tone": "bullish",
            "horizon": "medium",
        }

    row = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=fake_summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )

    db_session.refresh(row)
    assert row.subject == "NVDA"
    assert row.tagline == "Services margin durable"
    assert row.findings_text == "Services margin up 400bps\nData center beat"
    assert row.entities_mentioned == ["ticker:NVDA", "sector:semis"]
    assert row.tone == "bullish"
    assert row.horizon == "medium"
    assert row.artifact_kind == "report"
    assert row.artifact_id == "rep-1"
    assert row.user_id == "u-1"
    assert row.embedding_model == "fake-d8"
    # Embedded text concatenates subject + tagline + findings.
    assert "NVDA" in row.summary_text
    assert "Services margin durable" in row.summary_text
    assert "Services margin up 400bps" in row.summary_text


def test_index_report_summary_is_idempotent_on_repeat(db_session) -> None:
    """Re-running on the same report updates the row in place rather
    than creating a duplicate."""
    report = _make_report(db_session)
    provider = FakeEmbeddingProvider(dim=8)

    first_payload: dict[str, Any] = {
        "subject": "NVDA",
        "tagline": "initial tagline",
        "findings": ["initial finding"],
        "entities_mentioned": ["ticker:NVDA"],
        "tone": "neutral",
        "horizon": "short",
    }
    second_payload: dict[str, Any] = {
        "subject": "NVDA",
        "tagline": "revised tagline",
        "findings": ["revised finding"],
        "entities_mentioned": ["ticker:NVDA", "theme:ai-capex"],
        "tone": "bullish",
        "horizon": "long",
    }
    payloads = [first_payload, second_payload]

    def summarize(_report: Report) -> dict[str, Any]:
        return payloads.pop(0)

    first = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )
    second = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )

    assert first.id == second.id

    rows = list(
        db_session.execute(
            select(GraphArtifactSummary).where(
                GraphArtifactSummary.user_id == "u-1",
                GraphArtifactSummary.artifact_kind == "report",
                GraphArtifactSummary.artifact_id == "rep-1",
            )
        ).scalars()
    )
    assert len(rows) == 1
    only = rows[0]
    assert only.tagline == "revised tagline"
    assert only.findings_text == "revised finding"
    assert only.tone == "bullish"
    assert only.horizon == "long"


def test_index_report_summary_drops_invalid_tone_to_none(db_session) -> None:
    """A summarize_fn that hallucinates a tone outside the enum must
    not crash the indexer; the bad field drops to None."""
    report = _make_report(db_session)
    provider = FakeEmbeddingProvider(dim=8)

    def summarize(_report: Report) -> dict[str, Any]:
        return {
            "subject": "NVDA",
            "tagline": "tagline",
            "findings": ["finding"],
            "entities_mentioned": [],
            "tone": "exuberant",  # invalid
            "horizon": "medium",
        }

    row = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )

    db_session.refresh(row)
    assert row.tone is None
    assert row.horizon == "medium"


def test_index_report_summary_drops_invalid_horizon_to_none(db_session) -> None:
    report = _make_report(db_session)
    provider = FakeEmbeddingProvider(dim=8)

    def summarize(_report: Report) -> dict[str, Any]:
        return {
            "subject": "NVDA",
            "tagline": "tagline",
            "findings": ["finding"],
            "entities_mentioned": [],
            "tone": "bullish",
            "horizon": "forever",  # invalid
        }

    row = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )

    db_session.refresh(row)
    assert row.tone == "bullish"
    assert row.horizon is None


def test_index_report_summary_handles_empty_findings(db_session) -> None:
    """Empty findings list still produces a valid row — embedded text
    is just subject + tagline; findings_text is empty string."""
    report = _make_report(db_session)
    provider = FakeEmbeddingProvider(dim=8)

    def summarize(_report: Report) -> dict[str, Any]:
        return {
            "subject": "NVDA",
            "tagline": "Bare tagline",
            "findings": [],
            "entities_mentioned": [],
            "tone": None,
            "horizon": None,
        }

    row = graph_summarization.index_report_summary(
        db_session,
        user_id="u-1",
        report=report,
        summarize_fn=summarize,
        embed_provider=provider,
        embed_model_name="fake-d8",
    )

    db_session.refresh(row)
    assert row.findings_text == ""
    assert "NVDA" in row.summary_text
    assert "Bare tagline" in row.summary_text


def test_make_summarize_fn_parses_well_formed_json() -> None:
    """The production factory parses a clean JSON response into the
    structured dict the indexer expects."""
    canned = json.dumps(
        {
            "subject": "NVDA",
            "tagline": "Services margin durable",
            "findings": ["Services margin up 400bps", "DC beat"],
            "entities_mentioned": ["ticker:NVDA"],
            "tone": "bullish",
            "horizon": "medium",
        }
    )
    client = _RecordingClient(canned_text=canned)
    summarize_fn = graph_summarization.make_summarize_fn(client)

    report = Report(
        id="rep-x",
        user_id="u-1",
        department="equity_research",
        report_type="stock_initiation",
        title="NVDA",
        subject="NVDA",
        content_markdown="body",
        content_structured={},
        model_ref="m",
    )
    out = summarize_fn(report)

    assert out["subject"] == "NVDA"
    assert out["tagline"] == "Services margin durable"
    assert out["findings"] == ["Services margin up 400bps", "DC beat"]
    assert out["entities_mentioned"] == ["ticker:NVDA"]
    assert out["tone"] == "bullish"
    assert out["horizon"] == "medium"
    # The factory rendered the report into the request.
    assert client.last_request is not None
    assert client.last_request.system is not None


def test_make_summarize_fn_drops_invalid_enums_to_none() -> None:
    """Tone/horizon outside the enum drop to None; findings that aren't
    a list of strings drop to []."""
    canned = json.dumps(
        {
            "subject": "NVDA",
            "tagline": "x",
            "findings": "not-a-list",
            "entities_mentioned": [1, 2],
            "tone": "ecstatic",
            "horizon": "eternal",
        }
    )
    client = _RecordingClient(canned_text=canned)
    summarize_fn = graph_summarization.make_summarize_fn(client)

    report = Report(
        id="rep-x",
        user_id="u-1",
        department="equity_research",
        report_type="stock_initiation",
        title="NVDA",
        subject="NVDA",
        content_markdown="body",
        content_structured={},
        model_ref="m",
    )
    out = summarize_fn(report)

    assert out["tone"] is None
    assert out["horizon"] is None
    assert out["findings"] == []
    assert out["entities_mentioned"] == []


def test_make_summarize_fn_malformed_response_returns_safe_defaults() -> None:
    """Non-JSON response: factory returns safe defaults (all None /
    empty) rather than crashing the nightly job."""
    client = _RecordingClient(canned_text="this is not json")
    summarize_fn = graph_summarization.make_summarize_fn(client)

    report = Report(
        id="rep-x",
        user_id="u-1",
        department="equity_research",
        report_type="stock_initiation",
        title="NVDA",
        subject="NVDA",
        content_markdown="body",
        content_structured={},
        model_ref="m",
    )
    out = summarize_fn(report)

    assert out["subject"] is None
    assert out["tagline"] is None
    assert out["findings"] == []
    assert out["entities_mentioned"] == []
    assert out["tone"] is None
    assert out["horizon"] is None
