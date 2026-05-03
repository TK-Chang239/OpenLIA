"""Tests for the guardrail_log service — writer + reader/filter."""

from __future__ import annotations

import hashlib

from openlia.safety.output_moderation import ActionTier, ModerationMatch
from openlia_server.services.guardrail_log import (
    list_events,
    record_persona_refusal,
    record_tripwire_match,
)


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def test_record_tripwire_match_writes_row(db_session) -> None:
    match = ModerationMatch(
        category="leaked_prompt",
        action=ActionTier.REPLACE,
        pattern="# Who you are",
        matched_text="# Who you are\nLia",
        message="I don't share my underlying instructions.",
    )
    record_tripwire_match(
        db_session,
        session_id="sess-1",
        user_id="user-1",
        department_id="equity_research",
        match=match,
        user_input_hash=_hash("hello"),
        response_excerpt="some response",
        model_ref="anthropic/claude-opus-4-7",
    )
    db_session.commit()

    rows = list_events(db_session, since_days=7)
    assert len(rows) == 1
    r = rows[0]
    assert r.event_type == "tripwire_flag"
    assert r.category == "leaked_prompt"
    assert r.action_taken == "replaced"
    assert r.tripwire_pattern == "# Who you are"


def test_record_persona_refusal_writes_row(db_session) -> None:
    record_persona_refusal(
        db_session,
        session_id="sess-2",
        user_id=None,
        department_id="secretary",
        clause_id="no_advice",
        user_input_hash=_hash("buy AAPL?"),
        response_excerpt="I won't tell you to buy or sell — I'll lay out the read.",
        model_ref="ollama/llama3:8b",
    )
    db_session.commit()

    rows = list_events(db_session, since_days=7, category="no_advice")
    assert len(rows) == 1
    assert rows[0].event_type == "persona_refusal"
    assert rows[0].user_id is None
    assert rows[0].action_taken == "logged"


def test_list_events_filters_by_category_and_since(db_session) -> None:
    record_persona_refusal(
        db_session, session_id="s1", user_id="u1", department_id="d1",
        clause_id="no_advice", user_input_hash=_hash("a"),
        response_excerpt="", model_ref=None,
    )
    record_persona_refusal(
        db_session, session_id="s2", user_id="u1", department_id="d1",
        clause_id="out_of_scope", user_input_hash=_hash("b"),
        response_excerpt="", model_ref=None,
    )
    db_session.commit()

    only_advice = list_events(db_session, since_days=7, category="no_advice")
    assert len(only_advice) == 1
    assert only_advice[0].category == "no_advice"
