"""Slice 4 — deterministic graph indexing on report write.

When a report is finalized, its structured fields (today: ``subject``,
which is typically a ticker for stock reports) are translated into
``entity → report`` ``mentions`` edges. These tests exercise the public
``save_report`` service so the contract holds end-to-end and isn't
silently bypassed by anyone calling the lower-level ORM constructor.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia_server.services import graph_store
from openlia_server.services import reports as reports_svc


def test_save_report_with_ticker_subject_creates_mentions_edge(db_session) -> None:
    report = reports_svc.save_report(
        db_session,
        user_id="u-1",
        department="equity_research",
        report_type="stock_initiation",
        title="NVDA Initiation",
        subject="NVDA",
        content_markdown="body",
        content_structured=_minimal_report_payload("NVDA Initiation"),
        model_ref="anthropic_sonnet",
    )

    edges = graph_store.neighbors_of(
        db_session,
        kind="entity",
        id="ticker:NVDA",
        edge_type="mentions",
    )
    assert len(edges) == 1
    assert edges[0].dst_kind == "report"
    assert edges[0].dst_id == report.id


def test_save_report_normalizes_lowercase_ticker_subject(db_session) -> None:
    """Subjects entered lowercase still resolve to the canonical ``ticker:NVDA``
    node — slice 2's normalization must apply at the indexing seam too,
    or else two reports with different casings would fork into rival
    nodes and break later retrieval.
    """
    reports_svc.save_report(
        db_session,
        user_id="u-1",
        department="equity_research",
        report_type="stock_update",
        title="nvda update",
        subject="nvda",
        content_markdown="body",
        content_structured=_minimal_report_payload("nvda update"),
        model_ref="anthropic_sonnet",
    )

    edges = graph_store.neighbors_of(
        db_session,
        kind="entity",
        id="ticker:NVDA",
        edge_type="mentions",
    )
    assert len(edges) == 1


def test_save_report_with_no_subject_is_a_no_op(db_session) -> None:
    """Some report types (e.g. macro batches) have no single subject. The
    hook must skip cleanly rather than emitting an edge to an empty
    entity ID."""
    reports_svc.save_report(
        db_session,
        user_id="u-1",
        department="macro_research",
        report_type="t4_assessment",
        title="Macro snapshot",
        subject=None,
        content_markdown="body",
        content_structured=_minimal_report_payload("Macro snapshot"),
        model_ref="anthropic_sonnet",
    )

    # No entity should have been created and no mentions edge emitted.
    assert graph_store.get_entity(db_session, kind="ticker", value="") is None


def _minimal_report_payload(title: str) -> dict:
    """Smallest payload that satisfies ``validate_report_schema``."""
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "generated_at": datetime(2026, 5, 10, tzinfo=UTC).isoformat(),
        "cover": {
            "title": title,
            "subtitle": "",
            "tagline": "",
        },
        "sections": [
            {
                "id": "summary",
                "title": "Summary",
                "blocks": [{"type": "text", "content": "body"}],
            }
        ],
    }
