"""Per-department resolve service (Phase B step 1).

`propose_specs_for_department` takes a department_id and aggregates the
inventory across every validated connector whose category overlaps the
department's required + optional categories. Per (department, need) it
picks the best resolved spec across connectors, tagging each proposal
with the chosen `connector_id`. Unsatisfied needs are surfaced as
`unsatisfiable=True` rather than dropped.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from openlia.connectors.types import (
    Category,
    ConnectorStatus,
    NeedParameter,
    RunnerNeed,
)
from openlia_server.db.models.connectors import Connector
from openlia_server.services import runner_specs_service
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession


class _StubLlm:
    """Returns a scripted payload per (need_id, connector_id) call.

    The resolver embeds the need_id in the prompt, but doesn't reveal a
    connector_id; we route by counting calls instead.
    """

    def __init__(self, by_need: dict[str, dict[str, Any]] | None = None) -> None:
        self._by_need = by_need or {}
        self.calls: list[str] = []

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        self.calls.append(prompt)
        for need_id, payload in self._by_need.items():
            if f"id: {need_id}\n" in prompt:
                return payload
        return {}


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._PROPOSALS.clear()
    runner_specs_service._DEPT_PROPOSALS.clear()
    yield
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._PROPOSALS.clear()
    runner_specs_service._DEPT_PROPOSALS.clear()


def _seed_connector(
    session: DBSession,
    *,
    cid: str | None = None,
    provider_id: str = "eodhd",
    category: str = "financial",
    cached_tools: list[dict] | None = None,
) -> Connector:
    row = Connector(
        id=cid or str(uuid.uuid4()),
        provider_id=provider_id,
        display_name=provider_id.upper(),
        source="cli_mcp",
        category=category,
        launch={
            "modes": [
                {
                    "kind": "cli_mcp",
                    "argv": [f"{provider_id}-mcp"],
                    "env_keys": [f"{provider_id.upper()}_API_KEY"],
                }
            ]
        },
        secrets={},
        cached_tools=cached_tools
        or [
            {
                "name": "get_quote",
                "description": "Quote tool",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
        status=ConnectorStatus.VALIDATED.value,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@pytest.mark.asyncio
async def test_returns_empty_when_no_needs_registered(
    engine: Engine, db_session: DBSession
) -> None:
    _seed_connector(db_session)
    llm = _StubLlm()

    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="ghost_dept", llm_client=llm
    )

    assert proposals == []
    assert llm.calls == []


@pytest.mark.asyncio
async def test_factory_receives_per_connector_clone_path(
    engine: Engine, db_session: DBSession, tmp_path, monkeypatch
) -> None:
    """When a factory variant is supplied, it must be called once per connector
    in scope with that connector's grounding clone path (or None)."""
    from openlia_server.services import grounding_service

    monkeypatch.setattr(grounding_service, "_clones_root", lambda: tmp_path / "clones")

    conn_no_repo = _seed_connector(db_session, provider_id="a")
    # Simulate a clone already on disk for connector b.
    conn_with_repo = _seed_connector(db_session, provider_id="b")
    clone_dir = grounding_service.path_for(conn_with_repo.id)
    clone_dir.mkdir(parents=True, exist_ok=True)

    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="q",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    seen_paths: list = []

    class _RecordingLlm:
        async def generate_json(self, *, prompt: str) -> dict[str, Any]:
            return {
                "tool_name": "get_quote",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }

    def factory(connector_root):
        seen_paths.append(connector_root)
        return _RecordingLlm()

    await runner_specs_service.propose_specs_for_department(
        db_session,
        department_id="macro_research",
        llm_client_factory=factory,
    )

    # Each in-scope connector contributes a candidate, so the factory is
    # invoked once per connector with that connector's grounding path
    # (or None when no clone exists). Ordering follows insertion order.
    assert len(seen_paths) == 2
    assert seen_paths[0] is None
    assert seen_paths[1] == clone_dir
    _ = conn_no_repo


@pytest.mark.asyncio
async def test_resolves_single_connector_and_tags_connector_id(
    engine: Engine, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="latest trade",
                    parameters=[
                        NeedParameter(
                            name="ticker",
                            description="ticker",
                            type="str",
                            required=True,
                        )
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    llm = _StubLlm(
        by_need={
            "real_time_quote": {
                "tool_name": "get_quote",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": "upper"}},
                "constants": {},
            }
        }
    )

    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="macro_research", llm_client=llm
    )

    assert len(proposals) == 1
    p = proposals[0]
    assert p.department_id == "macro_research"
    assert p.need_id == "real_time_quote"
    assert p.connector_id == conn.id
    assert p.unsatisfiable is False
    assert p.proposed_spec["tool_name"] == "get_quote"


@pytest.mark.asyncio
async def test_skips_connectors_whose_category_does_not_overlap(
    engine: Engine, db_session: DBSession
) -> None:
    # Financial connector — but dept wants only news/social.
    _seed_connector(db_session, category="financial")
    runner_specs_service.set_dept_needs_for_testing(
        {
            "retail_sentiment": [
                RunnerNeed(
                    id="reddit_posts",
                    description="posts",
                    parameters=[],
                    shape="list",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"retail_sentiment": ({Category.SOCIAL}, set())}
    )
    llm = _StubLlm()

    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="retail_sentiment", llm_client=llm
    )

    # No overlapping connector -> single unsatisfiable proposal, no LLM call.
    assert len(proposals) == 1
    assert proposals[0].unsatisfiable is True
    assert proposals[0].connector_id is None
    assert llm.calls == []


@pytest.mark.asyncio
async def test_picks_first_connector_that_resolves(engine: Engine, db_session: DBSession) -> None:
    """Two financial connectors both match the dept. Each that produces a
    valid spec contributes one candidate to the dept's proposal list, so the
    review page can show alternatives."""
    conn_a = _seed_connector(
        db_session,
        provider_id="connector_a",
        cached_tools=[
            {
                "name": "tool_a",
                "description": "A",
                "input_schema": {
                    "type": "object",
                    "properties": {"sym": {"type": "string"}},
                },
            }
        ],
    )
    conn_b = _seed_connector(
        db_session,
        provider_id="connector_b",
        cached_tools=[
            {
                "name": "tool_b",
                "description": "B",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
    )
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="quote",
                    parameters=[
                        NeedParameter(
                            name="ticker",
                            description="t",
                            type="str",
                            required=True,
                        )
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    class _OrderedLlm:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_json(self, *, prompt: str) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                return {
                    "tool_name": "tool_a",
                    "param_bindings": {"ticker": {"to_arg": "sym", "transform": None}},
                    "constants": {},
                }
            return {
                "tool_name": "tool_b",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }

    llm = _OrderedLlm()
    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="macro_research", llm_client=llm
    )

    assert len(proposals) == 2
    by_connector = {p.connector_id: p for p in proposals}
    assert by_connector[conn_a.id].proposed_spec["tool_name"] == "tool_a"
    assert by_connector[conn_b.id].proposed_spec["tool_name"] == "tool_b"
    # Both connectors are tried so each contributes a candidate.
    assert llm.calls == 2


@pytest.mark.asyncio
async def test_falls_through_to_next_connector_on_resolver_error(
    engine: Engine, db_session: DBSession
) -> None:
    conn_a = _seed_connector(
        db_session,
        provider_id="connector_a",
        cached_tools=[
            {
                "name": "tool_a",
                "description": "A",
                "input_schema": {
                    "type": "object",
                    "properties": {"sym": {"type": "string"}},
                },
            }
        ],
    )
    conn_b = _seed_connector(
        db_session,
        provider_id="connector_b",
        cached_tools=[
            {
                "name": "tool_b",
                "description": "B",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
    )
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="quote",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    class _OrderedLlm:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_json(self, *, prompt: str) -> dict[str, Any]:
            self.calls += 1
            if self.calls == 1:
                # Picks a tool that doesn't exist in connector A's inventory ->
                # ResolverError, service should try connector B.
                return {
                    "tool_name": "nonexistent",
                    "param_bindings": {},
                    "constants": {},
                }
            return {
                "tool_name": "tool_b",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }

    llm = _OrderedLlm()
    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="macro_research", llm_client=llm
    )

    assert len(proposals) == 1
    assert proposals[0].connector_id == conn_b.id
    assert proposals[0].proposed_spec["tool_name"] == "tool_b"
    assert llm.calls == 2
    _ = conn_a


@pytest.mark.asyncio
async def test_unsatisfiable_when_all_connectors_fail(
    engine: Engine, db_session: DBSession
) -> None:
    _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="exotic",
                    description="not in inventory",
                    parameters=[],
                    shape="list",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    # LLM picks a tool name nothing in inventory has.
    llm = _StubLlm(by_need={"exotic": {"tool_name": "wat", "param_bindings": {}, "constants": {}}})

    proposals = await runner_specs_service.propose_specs_for_department(
        db_session, department_id="macro_research", llm_client=llm
    )

    assert len(proposals) == 1
    p = proposals[0]
    assert p.unsatisfiable is True
    assert p.connector_id is None
    assert p.error is not None


@pytest.mark.asyncio
async def test_resolve_logs_tool_call_events_when_factory_used(
    engine: Engine, db_session: DBSession
) -> None:
    """Per-resolve event log captures tool calls so the wizard can stream a
    live tool-call log to the user."""
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="q",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                ),
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    from openlia.llm.types import ToolCall

    class _ToolFiringLlm:
        def __init__(self) -> None:
            self.listener: object = None

        async def generate_json(self, *, prompt: str) -> dict[str, Any]:
            assert self.listener is not None
            self.listener(ToolCall(id="c1", name="read_file", arguments={"path": "tools.py"}))
            return {
                "tool_name": "get_quote",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }

    def factory(connector_root, *, tool_call_listener=None):
        client = _ToolFiringLlm()
        client.listener = tool_call_listener
        return client

    await runner_specs_service.propose_specs_for_department(
        db_session,
        department_id="macro_research",
        llm_client_factory=factory,
    )

    events = runner_specs_service.get_resolve_events("macro_research")
    assert len(events) == 1
    e = events[0]
    assert e["type"] == "tool_call"
    assert e["name"] == "read_file"
    assert e["arguments"] == {"path": "tools.py"}
    assert e["need_id"] == "quote"
    assert e["connector_id"] == conn.id


@pytest.mark.asyncio
async def test_propose_spec_for_need_re_resolves_only_that_row(
    engine: Engine, db_session: DBSession
) -> None:
    """propose_spec_for_need re-resolves a single (dept, need) pair without
    touching the other cached proposals for the department."""
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="quote",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                ),
                RunnerNeed(
                    id="other_need",
                    description="other",
                    parameters=[],
                    shape="list",
                ),
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    # Pre-seed two proposals so we can verify only the targeted one mutates.
    existing_other = runner_specs_service.ProposedSpec(
        department_id="macro_research",
        need_id="other_need",
        proposed_spec={"tool_name": "stable", "param_bindings": {}, "constants": {}},
        canary_value=None,
        canary_ok=False,
        shape_match=False,
        error=None,
        connector_id=conn.id,
        unsatisfiable=False,
    )
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="real_time_quote",
            proposed_spec={"tool_name": "old", "param_bindings": {}, "constants": {}},
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error=None,
            connector_id=conn.id,
            unsatisfiable=False,
        ),
        existing_other,
    ]
    llm = _StubLlm(
        by_need={
            "real_time_quote": {
                "tool_name": "get_quote",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }
        }
    )

    updated = await runner_specs_service.propose_spec_for_need(
        db_session,
        department_id="macro_research",
        need_id="real_time_quote",
        llm_client=llm,
    )

    assert len(updated) == 1
    assert updated[0].need_id == "real_time_quote"
    assert updated[0].proposed_spec["tool_name"] == "get_quote"
    cached = runner_specs_service.get_dept_proposed_specs("macro_research")
    cached_by_need: dict[str, list[runner_specs_service.ProposedSpec]] = {}
    for p in cached:
        cached_by_need.setdefault(p.need_id, []).append(p)
    assert cached_by_need["real_time_quote"][0].proposed_spec["tool_name"] == "get_quote"
    # Untouched.
    assert cached_by_need["other_need"][0] is existing_other


@pytest.mark.asyncio
async def test_propose_spec_for_need_excludes_blocked_connectors(
    engine: Engine, db_session: DBSession
) -> None:
    """exclude_connector_ids forces the resolver to skip the specified
    connectors. Used by the 'Try a different connector' button when the
    auto-pick was wrong."""
    conn_a = _seed_connector(
        db_session,
        provider_id="connector_a",
        cached_tools=[
            {
                "name": "tool_a",
                "description": "A",
                "input_schema": {
                    "type": "object",
                    "properties": {"sym": {"type": "string"}},
                },
            }
        ],
    )
    conn_b = _seed_connector(
        db_session,
        provider_id="connector_b",
        cached_tools=[
            {
                "name": "tool_b",
                "description": "B",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
    )
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="quote",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                ),
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    # Seed the cache as if conn_a was previously the chosen one.
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="quote",
            proposed_spec={"tool_name": "tool_a"},
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error=None,
            connector_id=conn_a.id,
            unsatisfiable=False,
        )
    ]
    llm = _StubLlm(
        by_need={
            "quote": {
                "tool_name": "tool_b",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }
        }
    )

    updated = await runner_specs_service.propose_spec_for_need(
        db_session,
        department_id="macro_research",
        need_id="quote",
        llm_client=llm,
        exclude_connector_ids={conn_a.id},
    )

    assert len(updated) == 1
    assert updated[0].connector_id == conn_b.id
    assert updated[0].proposed_spec["tool_name"] == "tool_b"


@pytest.mark.asyncio
async def test_propose_spec_for_need_unsatisfiable_when_all_excluded(
    engine: Engine, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="quote",
                    description="q",
                    parameters=[],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    llm = _StubLlm(by_need={})

    updated = await runner_specs_service.propose_spec_for_need(
        db_session,
        department_id="macro_research",
        need_id="quote",
        llm_client=llm,
        exclude_connector_ids={conn.id},
    )
    assert len(updated) == 1
    assert updated[0].unsatisfiable is True
    assert updated[0].connector_id is None


@pytest.mark.asyncio
async def test_propose_spec_for_need_returns_unsatisfiable_when_all_fail(
    engine: Engine, db_session: DBSession
) -> None:
    _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(id="exotic", description="x", parameters=[], shape="list"),
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    llm = _StubLlm(by_need={"exotic": {"tool_name": "wat", "param_bindings": {}, "constants": {}}})

    updated = await runner_specs_service.propose_spec_for_need(
        db_session,
        department_id="macro_research",
        need_id="exotic",
        llm_client=llm,
    )
    assert len(updated) == 1
    assert updated[0].unsatisfiable is True


@pytest.mark.asyncio
async def test_propose_spec_for_need_404_for_unknown_need(
    engine: Engine, db_session: DBSession
) -> None:
    runner_specs_service.set_dept_needs_for_testing({"macro_research": []})
    runner_specs_service.set_dept_categories_for_testing({"macro_research": (set(), set())})

    class _Llm:
        async def generate_json(self, *, prompt: str) -> dict:
            return {}

    with pytest.raises(KeyError):
        await runner_specs_service.propose_spec_for_need(
            db_session,
            department_id="macro_research",
            need_id="ghost",
            llm_client=_Llm(),
        )


def test_approve_dept_spec_persists_with_connector_from_proposal(
    engine: Engine, db_session: DBSession
) -> None:
    """approve_dept_spec keys off (department_id, need_id) and uses the
    connector chosen during dept-level resolve — caller doesn't pass it."""
    conn = _seed_connector(db_session)
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="real_time_quote",
            proposed_spec={
                "need_id": "real_time_quote",
                "access_mode": "cli_mcp",
                "tool_name": "get_quote",
                "module": None,
                "instance_factory": None,
                "method": None,
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": "upper"}},
                "constants": {},
                "shape": "dict",
            },
            canary_value={"price": 1.0},
            canary_ok=True,
            shape_match=True,
            error=None,
            connector_id=conn.id,
            unsatisfiable=False,
        )
    ]

    row = runner_specs_service.approve_dept_spec(
        db_session, department_id="macro_research", need_id="real_time_quote"
    )

    assert row.connector_id == conn.id
    assert row.access_mode == "cli_mcp"
    assert row.spec["tool_name"] == "get_quote"


def test_approve_dept_spec_404_when_no_proposal(engine: Engine, db_session: DBSession) -> None:
    with pytest.raises(KeyError):
        runner_specs_service.approve_dept_spec(
            db_session, department_id="macro_research", need_id="ghost"
        )


def test_approve_dept_spec_rejects_unsatisfiable(engine: Engine, db_session: DBSession) -> None:
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="exotic",
            proposed_spec={},
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error="not in inventory",
            connector_id=None,
            unsatisfiable=True,
        )
    ]
    with pytest.raises(ValueError):
        runner_specs_service.approve_dept_spec(
            db_session, department_id="macro_research", need_id="exotic"
        )


@pytest.mark.asyncio
async def test_caches_proposals_per_department(engine: Engine, db_session: DBSession) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="t",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    llm = _StubLlm(
        by_need={
            "real_time_quote": {
                "tool_name": "get_quote",
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            }
        }
    )

    await runner_specs_service.propose_specs_for_department(
        db_session, department_id="macro_research", llm_client=llm
    )
    cached = runner_specs_service.get_dept_proposed_specs("macro_research")

    assert len(cached) == 1
    assert cached[0].connector_id == conn.id
