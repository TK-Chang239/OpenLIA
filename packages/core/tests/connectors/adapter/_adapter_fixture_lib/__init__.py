"""Test fixture python_lib for adapter introspection tests.

Exposes:
- `Client` — a regular class with two public methods + one private method.
- `Helper` — second class to verify multi-class iteration.
- `top_level_fn` — a module-level function (should be ignored: not a class method).
"""

from __future__ import annotations


class Client:
    """Fixture client used by adapter introspection tests."""

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key

    def quote(self, symbol: str) -> dict[str, str]:
        """Return a quote payload."""
        return {"symbol": symbol, "key": self.api_key}

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search results."""
        return [{"q": query, "limit": limit}]

    def _private(self) -> str:
        return "secret"


class Helper:
    """Second fixture class."""

    def ping(self) -> str:
        """Health check."""
        return "pong"


def top_level_fn(x: int) -> int:
    """Module-level function — should not appear in introspection output."""
    return x + 1
