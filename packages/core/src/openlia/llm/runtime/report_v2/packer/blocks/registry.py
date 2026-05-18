from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BlockEntry:
    tag: str
    assembler: Callable[..., Any]
    schema: dict[str, Any] | None = None


class BlockRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, BlockEntry] = {}

    def register(
        self,
        tag: str,
        *,
        assembler: Callable[..., Any],
        schema: dict[str, Any] | None = None,
    ) -> None:
        if tag in self._entries:
            raise ValueError(f"block tag {tag!r} already registered")
        self._entries[tag] = BlockEntry(tag=tag, assembler=assembler, schema=schema)

    def get(self, tag: str) -> BlockEntry | None:
        return self._entries.get(tag)

    def tags(self) -> list[str]:
        return list(self._entries.keys())


default_block_registry = BlockRegistry()


def register_block(
    tag: str,
    *,
    assembler: Callable[..., Any],
    schema: dict[str, Any] | None = None,
) -> None:
    default_block_registry.register(tag, assembler=assembler, schema=schema)
