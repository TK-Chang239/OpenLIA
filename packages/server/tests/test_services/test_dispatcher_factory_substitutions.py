"""Tests for `{ENV_VAR_NAME}` substitution in remote_mcp and cli_mcp launch dicts.

Built-in templates declare URLs with placeholder formatting (e.g.
`https://mcp.firecrawl.dev/{api_key}/v2/mcp` or
`https://financialmodelingprep.com/mcp?apikey={api_key}`). When
_build_transport persists a connector at install, those placeholders
must be replaced with the real secret values from `secrets`. Otherwise
the literal `{api_key}` reaches the upstream server, list_tools may
work without auth, and call_tool returns 401 — silent breakage.

The substitution is keyed by .env-style variable names: every
`{NAME}` in the URL, any header value, or any cli_mcp argv token is
replaced by `secrets[NAME]` when present.
"""

from __future__ import annotations

from openlia_server.services.dispatcher_factory import _build_transport


def test_build_transport_substitutes_api_key_placeholder_in_remote_mcp_url() -> None:
    mode = {
        "kind": "remote_mcp",
        "url": "https://mcp.firecrawl.dev/{FIRECRAWL_API_KEY}/v2/mcp",
        "headers": {},
    }
    secrets = {"FIRECRAWL_API_KEY": "fc-abc123"}
    t = _build_transport("c1", mode, secrets)
    assert t._mode.url == "https://mcp.firecrawl.dev/fc-abc123/v2/mcp"  # type: ignore[attr-defined]


def test_build_transport_substitutes_placeholder_in_remote_mcp_header() -> None:
    mode = {
        "kind": "remote_mcp",
        "url": "https://api.example.com/mcp",
        "headers": {"Authorization": "Bearer {TOKEN}"},
    }
    secrets = {"TOKEN": "tk-xyz"}
    t = _build_transport("c1", mode, secrets)
    assert t._mode.headers["Authorization"] == "Bearer tk-xyz"  # type: ignore[attr-defined]


def test_build_transport_leaves_url_unchanged_when_no_placeholders() -> None:
    mode = {
        "kind": "remote_mcp",
        "url": "https://api.example.com/mcp",
        "headers": {},
    }
    t = _build_transport("c1", mode, {"OTHER_KEY": "irrelevant"})
    assert t._mode.url == "https://api.example.com/mcp"  # type: ignore[attr-defined]


def test_hydrate_spec_round_trips_result_reducer() -> None:
    """Specs persist `result_reducer` as a string in the spec JSON;
    the hydrator must read it back so reducer-driven specs
    (FMP cpi_yoy / gdp_yoy) keep applying the reduction after
    every dispatcher rebuild.
    """
    from dataclasses import dataclass

    from openlia_server.services.dispatcher_factory import _hydrate_spec

    @dataclass
    class _StubRow:
        department_id: str
        need_id: str
        access_mode: str
        spec: dict

    row = _StubRow(
        department_id="macro_research",
        need_id="cpi_yoy",
        access_mode="remote_mcp",
        spec={
            "need_id": "cpi_yoy",
            "access_mode": "remote_mcp",
            "tool_name": "economics",
            "constants": {"endpoint": "economics-indicators", "name": "inflationRate"},
            "param_bindings": {},
            "shape": "float",
            "result_path": [],
            "result_reducer": "latest_value_by_date",
        },
    )
    hydrated = _hydrate_spec(row)
    assert hydrated.result_reducer == "latest_value_by_date"


def test_hydrate_spec_round_trips_result_path() -> None:
    """RunnerCallableSpec rows persist `result_path` as a JSON list (because
    `dataclasses.asdict` flattens tuples). The hydrator must read it back
    and convert to tuple, or else specs with non-empty result_path lose
    their reduction step on every dispatcher build — runners get the raw
    transport result instead of the schema-targeted field.
    """
    from dataclasses import dataclass

    from openlia_server.services.dispatcher_factory import _hydrate_spec

    @dataclass
    class _StubRow:
        department_id: str
        need_id: str
        access_mode: str
        spec: dict

    row = _StubRow(
        department_id="macro_research",
        need_id="usd_fx_reserve_share",
        access_mode="python_lib",
        spec={
            "need_id": "usd_fx_reserve_share",
            "access_mode": "python_lib",
            "method": "Firecrawl.scrape",
            "constants": {"url": "https://x", "formats": []},
            "param_bindings": {},
            "shape": "float",
            "result_path": ["json", "usd_share_pct"],
        },
    )
    hydrated = _hydrate_spec(row)
    assert hydrated.result_path == ("json", "usd_share_pct")


def test_hydrate_spec_round_trips_field_map() -> None:
    """Specs persist `field_map` as a dict in the spec JSON;
    the hydrator must read it back so column-rename specs
    (e.g. EODHD eod_history) keep applying the mapping after
    every dispatcher rebuild.
    """
    from dataclasses import dataclass

    from openlia_server.services.dispatcher_factory import _hydrate_spec

    @dataclass
    class _StubRow:
        department_id: str
        need_id: str
        access_mode: str
        spec: dict

    _EODHD_EOD_FIELD_MAP = {
        "date": "date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "adjusted_close": "adjusted_close",
        "volume": "volume",
    }

    row = _StubRow(
        department_id="portfolio",
        need_id="eod_history",
        access_mode="remote_mcp",
        spec={
            "need_id": "eod_history",
            "access_mode": "remote_mcp",
            "tool_name": "get_eod_data",
            "constants": {},
            "param_bindings": {},
            "shape": "list[dict]",
            "result_path": [],
            "field_map": _EODHD_EOD_FIELD_MAP,
        },
    )
    hydrated = _hydrate_spec(row)
    assert hydrated.field_map == _EODHD_EOD_FIELD_MAP


def test_build_transport_leaves_unknown_placeholder_unchanged() -> None:
    """If the secret isn't supplied, the placeholder stays literal — surfacing
    a clear failure rather than silently coercing to an empty string.
    """
    mode = {
        "kind": "remote_mcp",
        "url": "https://api.example.com/{MISSING_VAR}/mcp",
        "headers": {},
    }
    t = _build_transport("c1", mode, {})
    assert t._mode.url == "https://api.example.com/{MISSING_VAR}/mcp"  # type: ignore[attr-defined]


def test_build_transport_substitutes_placeholder_in_cli_argv() -> None:
    """A key placed as a positional CLI arg (e.g. `uvx marketdata-mcp-server {KEY}`)
    must resolve from secrets at launch, the same way remote URLs do."""
    mode = {
        "kind": "cli_mcp",
        "argv": ["uvx", "marketdata-mcp-server", "{MARKETDATA_KEY}"],
        "env_keys": [],
    }
    secrets = {"MARKETDATA_KEY": "md-secret-123"}
    t = _build_transport("c1", mode, secrets)
    assert t._mode.argv == [  # type: ignore[attr-defined]
        "uvx",
        "marketdata-mcp-server",
        "md-secret-123",
    ]


def test_build_transport_leaves_unknown_argv_placeholder_unchanged() -> None:
    """Missing secret -> placeholder stays literal so the failure is obvious."""
    mode = {
        "kind": "cli_mcp",
        "argv": ["uvx", "srv", "{MISSING}"],
        "env_keys": [],
    }
    t = _build_transport("c1", mode, {})
    assert t._mode.argv == ["uvx", "srv", "{MISSING}"]  # type: ignore[attr-defined]
