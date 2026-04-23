from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable


Tier = Literal["thinking", "everyday", "quick"]


@runtime_checkable
class Department(Protocol):
    name: str
    display_name: str
    prompt_name: str
    tier: Tier
    data_requirement_types: tuple[str, ...]
    optional_requirement_types: tuple[str, ...]
    extra_tools: tuple[dict[str, Any], ...]
