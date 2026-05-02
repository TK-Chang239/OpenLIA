from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from openlia.connectors.types import Category

Tier = Literal["thinking", "everyday", "quick"]


@runtime_checkable
class Department(Protocol):
    name: str
    display_name: str
    prompt_name: str
    tier: Tier
    required_categories: tuple[Category, ...]
    optional_categories: tuple[Category, ...]
    # At-least-one-of disjunctive groups. Each inner tuple is satisfied
    # when ANY of its members has a validated connector. Use this when
    # two categories serve interchangeable roles (e.g., NEWS or
    # WEB_SEARCH for headline retrieval).
    required_any_of: tuple[tuple[Category, ...], ...]
    requires_runner: bool
    disable_runtime_routing: bool
    extra_tools: tuple[dict[str, Any], ...]
