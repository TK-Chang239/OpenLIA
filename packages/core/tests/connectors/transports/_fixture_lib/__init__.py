"""Test fixture python_lib for transport tests.

Exposes a `Client` class with one sync method, one async method, and a
private method that should be excluded from `list_tools`.
"""

from __future__ import annotations


class Client:
    """Fixture client used by PythonLibTransport tests."""

    def __init__(self, *, api_key: str, region: str = "us") -> None:
        self.api_key = api_key
        self.region = region

    def quote(self, symbol: str) -> dict[str, str]:
        """Return a sync quote payload."""
        return {"symbol": symbol, "key": self.api_key, "region": self.region}

    async def aquote(self, symbol: str) -> dict[str, str]:
        """Return an async quote payload."""
        return {"symbol": symbol, "key": self.api_key, "async": "yes"}

    def _private(self) -> str:
        return "secret"

    def fixed_signature(self, s: str | None = None, t: str | None = None) -> dict:
        """Mimics EODHD's `financial_news(s, t, from_date, to_date, ...)`
        — a method whose signature does NOT accept arbitrary kwargs and
        will raise TypeError if the caller passes one not in the
        signature (e.g. `from`, which is also a Python reserved word)."""
        return {"s": s, "t": t}

    def varkw(self, **kwargs) -> dict:
        """Method that accepts **kwargs — the transport must pass
        unknown keys straight through here."""
        return dict(kwargs)

    def sys_exit_caller(self) -> None:
        """Mimics misbehaving SDKs (e.g. eodhd) that call `sys.exit(1)`
        on API errors instead of raising. Without a transport-level
        guard the SystemExit propagates through the async stack and
        kills the SSE response handler, surfacing as 'Connection
        lost' in the browser."""
        import sys

        sys.exit(1)
