from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# A validator inspects raw block YAML and returns a list of error strings.
# Empty list means the block shape is valid.
BlockShapeValidator = Callable[[dict[str, Any]], list[str]]


@dataclass(frozen=True)
class BlockEntry:
    tag: str
    assembler: Callable[..., Any]
    schema: dict[str, Any] | None = None
    validate_shape: BlockShapeValidator | None = None


class BlockShapeError(Exception):
    """Raised when one or more block shape gates reject blocks in a section.

    The dispatcher aggregates per-block defects into a single error so the
    section retry prompt receives every defect at once instead of having to
    fail repeatedly.
    """

    def __init__(self, defects: list[str]) -> None:
        self.defects = list(defects)
        super().__init__("; ".join(self.defects))


class BlockRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, BlockEntry] = {}

    def register(
        self,
        tag: str,
        *,
        assembler: Callable[..., Any],
        schema: dict[str, Any] | None = None,
        validate_shape: BlockShapeValidator | None = None,
    ) -> None:
        if tag in self._entries:
            raise ValueError(f"block tag {tag!r} already registered")
        self._entries[tag] = BlockEntry(
            tag=tag,
            assembler=assembler,
            schema=schema,
            validate_shape=validate_shape,
        )

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
    validate_shape: BlockShapeValidator | None = None,
) -> None:
    default_block_registry.register(
        tag,
        assembler=assembler,
        schema=schema,
        validate_shape=validate_shape,
    )
