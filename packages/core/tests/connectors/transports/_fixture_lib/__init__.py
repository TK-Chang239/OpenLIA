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
