"""Slice 1 — GraphStore foundations.

Tracer bullet: create two entity nodes, connect them with one edge, and
traverse from the source. This verifies the SQLite-backed graph storage
layer end-to-end (table → ORM → service → query) before we layer on
canonical IDs (slice 2), polymorphic edges (slice 3), or any retrieval.
"""

from __future__ import annotations

from openlia_server.db.models.content import Report
from openlia_server.services import graph_store


def _make_report(db_session, *, report_id: str = "rep-1", subject: str = "NVDA") -> Report:
    row = Report(
        id=report_id,
        user_id="u-1",
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


def test_entity_for_ticker_normalizes_case_and_is_idempotent(db_session) -> None:
    """Tickers are case-insensitive: ``nvda`` and ``NVDA`` resolve to the
    same node so two callers don't end up with parallel rows.
    """
    a = graph_store.entity_for(db_session, kind="ticker", value="nvda")
    b = graph_store.entity_for(db_session, kind="ticker", value="NVDA")

    assert a.id == b.id == "ticker:NVDA"
    assert a.value == "NVDA"


def test_entity_for_theme_slugifies_value(db_session) -> None:
    """Themes/sectors are stored as kebab-case slugs so ``"AI Capex"`` and
    ``"ai-capex"`` resolve to the same node regardless of how a user
    phrases it in chat.
    """
    a = graph_store.entity_for(db_session, kind="theme", value="AI Capex")
    b = graph_store.entity_for(db_session, kind="theme", value="ai-capex")
    c = graph_store.entity_for(db_session, kind="theme", value="ai capex")

    assert a.id == b.id == c.id == "theme:ai-capex"


def test_mention_links_entity_to_report_and_is_idempotent(db_session) -> None:
    """``mention`` is the sugar callers use to record "this artifact talks
    about this entity." It must:

    * Create the entity if it doesn't exist (canonical lookup, slice 2).
    * Create an edge ``entity → artifact`` of type ``mentions`` referring
      directly to the artifact's existing primary key (slice 3 — no
      mirror node row in graph_entities for the report itself).
    * Be idempotent on regenerate: calling it twice with the same
      arguments must NOT create a duplicate edge, otherwise the slice 4
      report-finalize hook would multiply edges on every regeneration.
    """
    report = _make_report(db_session)

    graph_store.mention(
        db_session,
        entity_kind="ticker",
        entity_value="nvda",
        artifact_kind="report",
        artifact_id=report.id,
    )
    graph_store.mention(
        db_session,
        entity_kind="ticker",
        entity_value="NVDA",
        artifact_kind="report",
        artifact_id=report.id,
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


def test_create_entity_then_traverse_edge_returns_neighbor(db_session) -> None:
    nvda = graph_store.create_entity(db_session, kind="ticker", value="NVDA")
    semis = graph_store.create_entity(db_session, kind="theme", value="semiconductors")

    graph_store.add_edge(
        db_session,
        src_kind="entity",
        src_id=nvda.id,
        dst_kind="entity",
        dst_id=semis.id,
        edge_type="in_theme",
    )
    db_session.flush()

    out = graph_store.neighbors_of(
        db_session,
        kind="entity",
        id=nvda.id,
        edge_type="in_theme",
    )

    assert len(out) == 1
    assert out[0].dst_kind == "entity"
    assert out[0].dst_id == semis.id
    assert out[0].edge_type == "in_theme"
