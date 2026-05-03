"""Tests for the Phase 7 smoke pipeline.

The smoke pipeline runs every save-time `CallableSpec` through the
selected transport with canonical args, classifies the result into one
of {success, auth, schema_miss, empty, bad_params, transient}, and (for
list[dict] shapes) pipes the first item through the dept's `from_dict`
adapter to ensure canonical keys are present.

Tests use a stub transport so no real network calls are made.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from openlia.connectors.types import CallableSpec, ParamBinding
from openlia_server.services.smoke_service import (
    CANONICAL_ARGS,
    SmokeResult,
    classify_exception,
    run_smoke,
)


class _StubTransport:
    """Minimal transport stub. Raises a queue of exceptions / returns values."""

    def __init__(
        self,
        *,
        responses: list[Any] | None = None,
        exceptions: list[BaseException] | None = None,
    ) -> None:
        self._responses = list(responses or [])
        self._exceptions = list(exceptions or [])
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        if self._exceptions:
            exc = self._exceptions.pop(0)
            raise exc
        return self._responses.pop(0)

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


def _quote_spec() -> CallableSpec:
    return CallableSpec(
        need_id="stock_quote",
        access_mode="remote_mcp",
        tool_name="quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol")},
        constants={"endpoint": "quote"},
        shape="float",
    )


def _http_status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError(f"{code}", request=request, response=response)


# --------------------------- canonical args ----------------------------------


@pytest.mark.asyncio
async def test_smoke_uses_canonical_args() -> None:
    """The dispatched call carries the canonical AAPL ticker for stock_quote."""
    transport = _StubTransport(responses=[123.45])
    spec = _quote_spec()
    result = await run_smoke(spec=spec, transport=transport)
    assert result.status == "success"
    assert transport.calls == [("quote", {"symbol": "AAPL", "endpoint": "quote"})]


def test_canonical_args_covers_known_needs() -> None:
    assert CANONICAL_ARGS["stock_quote"] == {"ticker": "AAPL"}
    assert "social_posts" in CANONICAL_ARGS
    assert "geopolitical_news" in CANONICAL_ARGS


# --------------------------- classification ----------------------------------


@pytest.mark.asyncio
async def test_smoke_classifies_auth_failure() -> None:
    transport = _StubTransport(exceptions=[_http_status_error(401)])
    result = await run_smoke(spec=_quote_spec(), transport=transport)
    assert result.status == "auth"
    assert "401" in (result.error_message or "")


@pytest.mark.asyncio
async def test_smoke_classifies_bad_params() -> None:
    transport = _StubTransport(exceptions=[_http_status_error(400)])
    result = await run_smoke(spec=_quote_spec(), transport=transport)
    assert result.status == "bad_params"


@pytest.mark.asyncio
async def test_smoke_classifies_transient_5xx() -> None:
    transport = _StubTransport(
        exceptions=[
            _http_status_error(503),
            _http_status_error(503),
        ],
        responses=[123.45],
    )
    result = await run_smoke(spec=_quote_spec(), transport=transport)
    assert result.status == "success"
    assert result.attempts == 3
    assert len(transport.calls) == 3


@pytest.mark.asyncio
async def test_smoke_classifies_transient_exhausted() -> None:
    transport = _StubTransport(
        exceptions=[_http_status_error(503), _http_status_error(503), _http_status_error(503)],
    )
    result = await run_smoke(spec=_quote_spec(), transport=transport)
    assert result.status == "transient"
    assert result.attempts == 3


@pytest.mark.asyncio
async def test_smoke_classifies_schema_miss() -> None:
    """result_path doesn't resolve → schema_miss."""
    spec = CallableSpec(
        need_id="stock_quote",
        access_mode="remote_mcp",
        tool_name="quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol")},
        shape="float",
        result_path=("data", "price"),
    )
    transport = _StubTransport(responses=[{"data": {"close": 100.0}}])
    result = await run_smoke(spec=spec, transport=transport)
    assert result.status == "schema_miss"
    assert "price" in (result.error_message or "")


@pytest.mark.asyncio
async def test_smoke_classifies_empty_result() -> None:
    spec = CallableSpec(
        need_id="geopolitical_news",
        access_mode="python_lib",
        method="X.headlines",
        shape="list[dict]",
        field_map={
            "title": "title",
            "url": "url",
            "source": "source",
            "published_at": "date",
            "summary": "summary",
        },
    )
    transport = _StubTransport(responses=[[]])
    result = await run_smoke(spec=spec, transport=transport)
    assert result.status == "empty"


# --------------------------- list[dict] from_dict pipe ------------------------


@pytest.mark.asyncio
async def test_smoke_pipes_first_item_through_from_dict_for_list_dict_shape() -> None:
    """First item is fed to dept's from_dict; KeyError → schema_miss with offending key."""
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="python_lib",
        method="X.posts",
        shape="list[dict]",
        field_map={
            "id": "id",
            "ticker": "ticker",
            "source": "source",
            "text": "text",
            "created_at": "ts",
            "engagement": "engagement",
        },
    )
    # Endpoint returns items missing 'ts' (so created_at can't be filled).
    transport = _StubTransport(
        responses=[
            [
                {
                    "id": "p1",
                    "ticker": "AAPL",
                    "source": "twitter",
                    "text": "hello",
                    "engagement": {},
                }
            ]
        ]
    )
    result = await run_smoke(spec=spec, transport=transport)
    assert result.status == "schema_miss"
    assert "ts" in (result.error_message or "") or "created_at" in (result.error_message or "")


@pytest.mark.asyncio
async def test_smoke_passes_for_well_formed_list_dict() -> None:
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="python_lib",
        method="X.posts",
        shape="list[dict]",
        field_map={
            "id": "id",
            "ticker": "ticker",
            "source": "source",
            "text": "text",
            "created_at": "ts",
            "engagement": "engagement",
        },
    )
    transport = _StubTransport(
        responses=[
            [
                {
                    "id": "p1",
                    "ticker": "AAPL",
                    "source": "twitter",
                    "text": "hello",
                    "ts": "2026-05-02T12:00:00Z",
                    "engagement": {"likes": 1},
                }
            ]
        ]
    )
    result = await run_smoke(spec=spec, transport=transport)
    assert result.status == "success"


# --------------------------- classify_exception unit ------------------------


def test_classify_exception_buckets() -> None:
    assert classify_exception(_http_status_error(401))[0] == "auth"
    assert classify_exception(_http_status_error(403))[0] == "auth"
    assert classify_exception(_http_status_error(400))[0] == "bad_params"
    assert classify_exception(_http_status_error(500))[0] == "transient"
    assert classify_exception(_http_status_error(503))[0] == "transient"
    assert classify_exception(httpx.TimeoutException("slow"))[0] == "transient"
    assert classify_exception(httpx.ConnectError("net down"))[0] == "transient"


def test_smoke_result_dataclass_has_required_fields() -> None:
    r = SmokeResult(
        status="success",
        attempts=1,
        error_class=None,
        error_message=None,
        response_excerpt=None,
    )
    assert r.status == "success"
