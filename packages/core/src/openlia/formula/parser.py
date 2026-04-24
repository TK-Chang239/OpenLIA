"""Token-to-AST parser. Populated in Task 2.

Exports ``parse(source: str) -> Expression`` and the ``Expression`` base class.
"""

from __future__ import annotations


class Expression:
    """Base class for every AST node. Concrete subclasses land in Task 3."""


def parse(source: str) -> Expression:  # pragma: no cover - Task 2
    raise NotImplementedError("parse() lands in Task 2")
