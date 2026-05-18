"""W2 aggregator: dedupe pre-flight declarations across sections, then execute centrally."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

from openlia.llm.runtime.report_v2.manifest.baseline import ToolDispatcher
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.manifest.preflight import PreflightDeclaration


class WebSearchProvider(Protocol):
    async def search(self, query: str) -> list[dict[str, Any]]: ...


@dataclass
class AggregatedWork:
    searches: list[str]
    search_intents: dict[str, list[str]]  # query -> [section_ids that asked]
    fetches: list[tuple[str, str, dict[str, Any]]]  # (provider, tool, args)
    proposed_facts: dict[str, list[str]] = field(default_factory=dict)  # section_id -> [fact_names]


def _fetch_key(provider: str, tool: str, args: dict[str, Any]) -> str:
    return f"{provider}::{tool}::{json.dumps(args, sort_keys=True)}"


def aggregate_declarations(declarations: list[PreflightDeclaration]) -> AggregatedWork:
    searches: dict[str, list[str]] = {}
    fetches_keyed: dict[str, tuple[str, str, dict[str, Any]]] = {}
    proposed: dict[str, list[str]] = {}

    for d in declarations:
        for s in d.searches:
            searches.setdefault(s.query, []).append(d.section_id)
        for f in d.fetches:
            key = _fetch_key(f.provider, f.tool, f.args)
            fetches_keyed.setdefault(key, (f.provider, f.tool, f.args))
        if d.proposed_facts:
            proposed[d.section_id] = list(d.proposed_facts)

    return AggregatedWork(
        searches=list(searches.keys()),
        search_intents=searches,
        fetches=list(fetches_keyed.values()),
        proposed_facts=proposed,
    )


async def execute_aggregated(
    *,
    work: AggregatedWork,
    manifest: Manifest,
    dispatcher: ToolDispatcher,
    websearch: WebSearchProvider,
) -> Manifest:
    now = datetime.now(UTC).isoformat()

    async def _do_fetch(
        provider: str, tool: str, args: dict[str, Any]
    ) -> tuple[str, str, dict[str, Any], Any]:
        try:
            payload = await dispatcher.dispatch(provider, tool, args)
        except Exception:
            payload = None
        return provider, tool, args, payload

    async def _do_search(query: str) -> tuple[str, Any]:
        try:
            results = await websearch.search(query)
        except Exception:
            results = None
        return query, results

    fetch_tasks = [_do_fetch(p, t, a) for (p, t, a) in work.fetches]
    search_tasks = [_do_search(q) for q in work.searches]
    fetch_results = await asyncio.gather(*fetch_tasks) if fetch_tasks else []
    search_results = await asyncio.gather(*search_tasks) if search_tasks else []

    for provider, tool, args, payload in fetch_results:
        if payload is None:
            continue
        ticker_part = args.get("ticker") or args.get("query") or ""
        identifier = f"{tool}/{ticker_part}" if ticker_part else tool
        manifest.append(
            kind="fetch",
            provider=provider,
            identifier=identifier,
            raw_payload=payload,
            retrieved_at=now,
        )
    for query, results in search_results:
        if results is None:
            continue
        manifest.append(
            kind="search",
            provider="websearch",
            identifier=query,
            raw_payload=results,
            retrieved_at=now,
        )
    return manifest
