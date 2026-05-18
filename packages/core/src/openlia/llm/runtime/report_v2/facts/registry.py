from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openlia.llm.runtime.report_v2.types import ExtractorTier, Fact

ExtractorFn = Callable[[Any, Any], Fact]


@dataclass(frozen=True)
class RegistryEntry:
    name: str
    tier: ExtractorTier
    depends_on: list[str]
    fn: ExtractorFn


class FactRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, RegistryEntry] = {}

    def register(
        self,
        name: str,
        *,
        tier: ExtractorTier,
        depends_on: list[str],
    ) -> Callable[[ExtractorFn], ExtractorFn]:
        if name in self._entries:
            raise ValueError(f"fact {name!r} already registered")

        def deco(fn: ExtractorFn) -> ExtractorFn:
            self._entries[name] = RegistryEntry(
                name=name, tier=tier, depends_on=list(depends_on), fn=fn
            )
            return fn

        return deco

    def get(self, name: str) -> RegistryEntry:
        return self._entries[name]

    def names(self) -> list[str]:
        return list(self._entries.keys())

    def resolution_order(self, requested: list[str]) -> list[str]:
        """Topological sort with dedup. Raises on unknown deps or cycles."""
        order: list[str] = []
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(n: str) -> None:
            if n in visited:
                return
            if n in visiting:
                raise ValueError(f"cycle detected at {n!r}")
            if n not in self._entries:
                raise ValueError(f"unknown dependency: {n!r}")
            visiting.add(n)
            for d in self._entries[n].depends_on:
                visit(d)
            visiting.remove(n)
            visited.add(n)
            order.append(n)

        for n in requested:
            visit(n)
        return order


default_registry = FactRegistry()


def register_fact(
    name: str,
    *,
    tier: ExtractorTier,
    depends_on: list[str],
) -> Callable[[ExtractorFn], ExtractorFn]:
    """Module-level decorator for the default registry."""
    return default_registry.register(name, tier=tier, depends_on=depends_on)
