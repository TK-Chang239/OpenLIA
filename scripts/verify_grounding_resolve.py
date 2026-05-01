"""Phase D verification: end-to-end agentic resolve with grounding.

Walks through the full new flow against the live `openlia-v2.db`:

1. Ensure the EODHD remote_mcp connector has source_repo_url set.
2. Run ensure_clone so the agentic resolver has a real local repo to read.
3. Hydrate dept registries.
4. Call propose_specs_for_department('macro_research') with the agentic
   thinking-tier factory.
5. Print each (need, connector, tool, constants) and flag whether the
   adapter LLM emitted the real EODHD slug (e.g. `debt_percent_gdp`)
   versus a hallucination.

Usage:
    OPENLIA_DB_URL=sqlite:///$HOME/.openlia/openlia-v2.db \
        uv run python scripts/verify_grounding_resolve.py [eodhd-mcp-connector-id]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from sqlalchemy import select


EODHD_REMOTE_MCP_PROVIDER = "eodhd"
EODHD_GITHUB_URL = "https://github.com/EodHistoricalData/EODHD-MCP-Server"
EODHD_DEFAULT_BRANCH = "main"

# Real EODHD slugs we expect the LLM to surface after reading
# `app/tools/get_macro_indicator.py` (ALLOWED_INDICATORS set).
KNOWN_GOOD_INDICATORS = {
    "real_interest_rate",
    "population_total",
    "population_growth_annual",
    "inflation_consumer_prices_annual",
    "consumer_price_index",
    "gdp_current_usd",
    "gdp_per_capita_usd",
    "gdp_growth_annual",
    "debt_percent_gdp",
    "net_trades_goods_services",
    "inflation_gdp_deflator_annual",
    "agriculture_value_added_percent_gdp",
    "industry_value_added_percent_gdp",
    "services_value_added_percent_gdp",
    "exports_of_goods_services_percent_gdp",
    "imports_of_goods_services_percent_gdp",
    "gross_capital_formation_percent_gdp",
    "net_migration",
    "gni_usd",
    "gni_per_capita_usd",
    "gni_ppp_usd",
    "gni_per_capita_ppp_usd",
    "income_share_lowest_twenty",
    "life_expectancy",
    "fertility_rate",
    "prevalence_hiv_total",
    "co2_emissions_tons_per_capita",
    "surface_area_km",
    "poverty_poverty_lines_percent_population",
    "revenue_excluding_grants_percent_gdp",
}


def _resolve_eodhd_connector_id(session, override: str | None) -> str:
    from openlia_server.db.models.connectors import Connector

    if override:
        row = session.get(Connector, override)
        if row is None:
            raise SystemExit(f"connector {override!r} not found")
        return row.id

    rows = list(
        session.execute(
            select(Connector).where(
                Connector.provider_id == EODHD_REMOTE_MCP_PROVIDER,
                Connector.source == "remote_mcp",
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        raise SystemExit(
            f"no remote_mcp connector with provider_id={EODHD_REMOTE_MCP_PROVIDER!r}; "
            "pass an explicit connector id"
        )
    return rows[0].id


def _ensure_grounding_url(session, connector_id: str) -> None:
    from openlia_server.db.models.connectors import Connector

    row = session.get(Connector, connector_id)
    if row is None:
        raise SystemExit(f"connector {connector_id!r} vanished")
    changed = False
    if not row.source_repo_url:
        row.source_repo_url = EODHD_GITHUB_URL
        changed = True
    if not row.source_repo_revision:
        row.source_repo_revision = EODHD_DEFAULT_BRANCH
        changed = True
    if changed:
        session.commit()
        print(f"[setup] set source_repo_url for {connector_id}")
    else:
        print(f"[setup] grounding URL already configured: {row.source_repo_url}")


def _ensure_clone(session, connector_id: str) -> Path | None:
    from openlia_server.services import grounding_service

    target = grounding_service.path_for(connector_id)
    if target.exists():
        print(f"[clone ] reusing existing clone at {target}")
        return target
    print(f"[clone ] cloning into {target} ...")
    return grounding_service.ensure_clone(session, connector_id=connector_id)


def _flag_constants(spec: dict) -> str:
    constants = spec.get("constants") or {}
    if not constants:
        return "no constants"
    parts = []
    for k, v in constants.items():
        try:
            marker = "✓" if v in KNOWN_GOOD_INDICATORS else "?"
        except TypeError:
            marker = "?"
        parts.append(f"{marker} {k}={v!r}")
    return "; ".join(parts)


async def _run() -> int:
    override = sys.argv[1] if len(sys.argv) > 1 else None

    # Late imports so OPENLIA_DB_URL is honored.
    from openlia.connectors.adapter import canary as _canary_mod
    from openlia.connectors.adapter.canary import CanaryResult
    from openlia_server.db import session as session_mod
    from openlia_server.db.bootstrap import resolve_db_url
    from openlia_server.services import runner_specs_service
    from openlia_server.services.adapter_llm_client import (
        AdapterLlmNotConfigured,
        make_agentic_resolver_factory,
    )

    # Verification focus is on RESOLVE accuracy, not on canary execution
    # (which would require a live remote_mcp endpoint + API key). Stub
    # run_canary so the script returns a deterministic no-op result.
    async def _noop_canary(*, spec, transport, sample_args):  # type: ignore[no-untyped-def]
        return CanaryResult(value=None, ok=False, shape_match=False, error="canary skipped")

    _canary_mod.run_canary = _noop_canary
    runner_specs_service.run_canary = _noop_canary  # imported into the module's namespace

    # Instrument AgenticResolverClient so we can prove tool-use is firing.
    from openlia_server.services import agentic_resolver_client as _arc

    _orig_dispatch = _arc.AgenticResolverClient._dispatch
    tool_call_log: list[tuple[str, dict]] = []

    def _spy_dispatch(self, call):  # type: ignore[no-untyped-def]
        tool_call_log.append((call.name, dict(call.arguments)))
        return _orig_dispatch(self, call)

    _arc.AgenticResolverClient._dispatch = _spy_dispatch  # type: ignore[assignment]
    globals()["_TOOL_CALL_LOG"] = tool_call_log

    session_mod.configure_engine(resolve_db_url())
    factory = session_mod.SessionLocal

    with factory() as session:
        connector_id = _resolve_eodhd_connector_id(session, override)
        _ensure_grounding_url(session, connector_id)
        clone = _ensure_clone(session, connector_id)
        if clone is None:
            print("[clone ] FAILED — see grounding_status / last_error on the row")
            return 1

    runner_specs_service.hydrate_dept_registries()
    needs = runner_specs_service._DEPT_NEEDS.get("macro_research") or []
    only_need = os.environ.get("VERIFY_ONLY_NEED")
    if only_need:
        needs = [n for n in needs if n.id == only_need]
        runner_specs_service._DEPT_NEEDS["macro_research"] = needs
    print(f"[resolv] macro_research will resolve {len(needs)} need(s)")

    agentic_factory = make_agentic_resolver_factory(factory)

    with factory() as session:
        try:
            proposals = await runner_specs_service.propose_specs_for_department(
                session,
                department_id="macro_research",
                llm_client_factory=agentic_factory,
            )
        except AdapterLlmNotConfigured as exc:
            print(f"[resolv] adapter LLM not configured: {exc}")
            return 1

    print()
    print(f"=== {len(proposals)} proposals ===")
    print()
    matched = 0
    unsatisfiable = 0
    for p in proposals:
        if p.unsatisfiable:
            unsatisfiable += 1
            print(f"  [UNSAT] {p.need_id}  ({p.error or 'no covering connector'})")
            continue
        spec = p.proposed_spec
        callee = spec.get("tool_name") or spec.get("method") or "?"
        constants_summary = _flag_constants(spec)
        for v in (spec.get("constants") or {}).values():
            try:
                if v in KNOWN_GOOD_INDICATORS:
                    matched += 1
                    break
            except TypeError:
                continue
        print(
            f"  [{p.connector_id[:8] if p.connector_id else '--------'}] "
            f"{p.need_id} -> {callee} | {constants_summary}"
        )

    print()
    print(
        f"summary: {matched} need(s) emitted a known-good EODHD slug, "
        f"{unsatisfiable} unsatisfiable, {len(proposals) - matched - unsatisfiable} other"
    )
    log = globals().get("_TOOL_CALL_LOG", [])
    print(f"agentic tool calls observed: {len(log)}")
    for name, args in log[:10]:
        snippet = json.dumps(args)[:120]
        print(f"  - {name} {snippet}")
    return 0 if matched > 0 or unsatisfiable == len(proposals) else 2


if __name__ == "__main__":
    if "OPENLIA_DB_URL" not in os.environ:
        os.environ["OPENLIA_DB_URL"] = (
            f"sqlite:///{os.path.expanduser('~')}/.openlia/openlia-v2.db"
        )
    sys.exit(asyncio.run(_run()))
