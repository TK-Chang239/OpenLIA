"""Slice 5 — UserConstruct nodes.

UserConstructs are the user-and-belief half of the cross-session memory
graph (positions, theses, concerns, watchlist items). Each construct is
anchored to an entity via an ``about`` edge so the slice-11 retrieval
path can find "what does the user believe about NVDA" with a single
1-hop query.
"""

from __future__ import annotations

from openlia_server.services import graph_store, user_constructs


def test_create_construct_persists_and_lists_back(db_session) -> None:
    construct = user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="position",
        statement="Long NVDA, services-margin thesis",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    assert construct.id is not None
    assert construct.kind == "position"
    assert construct.status == "confirmed"
    assert construct.entity_id == "ticker:NVDA"

    out = user_constructs.list_constructs(db_session, user_id="u-1")
    assert len(out) == 1
    assert out[0].id == construct.id


def test_create_construct_emits_about_edge_to_entity(db_session) -> None:
    """The slice-11 retrieval entry point will be ``neighbors_of(entity)`` —
    so a construct must be reachable from its anchor entity via an
    ``about`` edge, not just by a column FK that's invisible to the
    graph traversal API.
    """
    construct = user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="thesis",
        statement="NVDA China revenue at risk on export controls",
        entity_kind="ticker",
        entity_value="nvda",
    )

    edges = graph_store.neighbors_of(
        db_session,
        kind="entity",
        id="ticker:NVDA",
        edge_type="about",
        direction="in",
    )
    assert len(edges) == 1
    assert edges[0].src_kind == "construct"
    assert edges[0].src_id == construct.id


def test_list_constructs_filters_by_user(db_session) -> None:
    user_constructs.create_construct(
        db_session,
        user_id="u-1",
        kind="watchlist_item",
        statement="Watching for $1200 entry",
        entity_kind="ticker",
        entity_value="NVDA",
    )
    user_constructs.create_construct(
        db_session,
        user_id="u-2",
        kind="watchlist_item",
        statement="Different user's note",
        entity_kind="ticker",
        entity_value="NVDA",
    )

    own = user_constructs.list_constructs(db_session, user_id="u-1")
    assert len(own) == 1
    assert own[0].user_id == "u-1"
