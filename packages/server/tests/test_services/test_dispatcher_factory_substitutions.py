"""Tests for `{ENV_VAR_NAME}` substitution in remote_mcp launch dicts.

Built-in templates declare URLs with placeholder formatting (e.g.
`https://mcp.firecrawl.dev/{api_key}/v2/mcp` or
`https://financialmodelingprep.com/mcp?apikey={api_key}`). When
_build_transport persists a connector at install, those placeholders
must be replaced with the real secret values from `secrets`. Otherwise
the literal `{api_key}` reaches the upstream server, list_tools may
work without auth, and call_tool returns 401 — silent breakage.

The substitution is keyed by .env-style variable names: every
`{NAME}` in the URL or any header value is replaced by `secrets[NAME]`
when present.
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
