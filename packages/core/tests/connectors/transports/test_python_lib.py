"""Tests for `PythonLibTransport`.

Covers:
- sync method dispatch
- async method dispatch (awaitable result)
- `$ENV_VAR_NAME` placeholder substitution from `secrets`
- `list_tools` introspection skips private methods
- `CallableTransport` Protocol membership at runtime
- `aclose` clears the cached instance
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the fixture package importable as a top-level module.
sys.path.insert(0, str(Path(__file__).parent))

from openlia.connectors.transports import CallableTransport
from openlia.connectors.transports.python_lib import PythonLibTransport
from openlia.connectors.types import InstanceFactory


def _make_transport(secrets: dict[str, str] | None = None) -> PythonLibTransport:
    return PythonLibTransport(
        module="_fixture_lib",
        instance_factory=InstanceFactory(
            cls="Client",
            args={"api_key": "$FIXTURE_KEY", "region": "eu"},
        ),
        secrets=secrets or {"FIXTURE_KEY": "k-123"},
    )


def test_implements_callable_transport_protocol() -> None:
    t = _make_transport()
    assert isinstance(t, CallableTransport)


@pytest.mark.asyncio
async def test_call_tool_sync_method_with_placeholder_secret() -> None:
    t = _make_transport()
    result = await t.call_tool("quote", {"symbol": "AAPL"})
    assert result == {"symbol": "AAPL", "key": "k-123", "region": "eu"}


@pytest.mark.asyncio
async def test_call_tool_async_method() -> None:
    t = _make_transport()
    result = await t.call_tool("aquote", {"symbol": "MSFT"})
    assert result == {"symbol": "MSFT", "key": "k-123", "async": "yes"}


@pytest.mark.asyncio
async def test_placeholder_substitution_pulls_from_secrets_dict() -> None:
    t = _make_transport(secrets={"FIXTURE_KEY": "rotated-key"})
    result = await t.call_tool("quote", {"symbol": "GOOG"})
    assert result["key"] == "rotated-key"


@pytest.mark.asyncio
async def test_braced_placeholder_form_also_resolves() -> None:
    t = PythonLibTransport(
        module="_fixture_lib",
        instance_factory=InstanceFactory(
            cls="Client",
            args={"api_key": "${FIXTURE_KEY}", "region": "us"},
        ),
        secrets={"FIXTURE_KEY": "braced-key"},
    )
    result = await t.call_tool("quote", {"symbol": "AAPL"})
    assert result["key"] == "braced-key"


@pytest.mark.asyncio
async def test_non_placeholder_args_pass_through_untouched() -> None:
    t = PythonLibTransport(
        module="_fixture_lib",
        instance_factory=InstanceFactory(
            cls="Client",
            args={"api_key": "literal", "region": "apac"},
        ),
        secrets={},
    )
    result = await t.call_tool("quote", {"symbol": "TSM"})
    assert result == {"symbol": "TSM", "key": "literal", "region": "apac"}


@pytest.mark.asyncio
async def test_list_tools_returns_public_methods_only() -> None:
    t = _make_transport()
    listed = await t.list_tools()
    names = {entry["name"] for entry in listed}
    assert "quote" in names
    assert "aquote" in names
    assert "_private" not in names
    quote_entry = next(e for e in listed if e["name"] == "quote")
    assert "sync quote" in quote_entry["description"]
    assert quote_entry["input_schema"] == {}


@pytest.mark.asyncio
async def test_aclose_clears_cached_instance() -> None:
    t = _make_transport()
    await t.call_tool("quote", {"symbol": "AAPL"})
    assert t._instance is not None
    await t.aclose()
    assert t._instance is None
