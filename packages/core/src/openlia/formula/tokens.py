"""Token dataclass + kinds emitted by the lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenKind(Enum):
    # Literals
    NUMBER = auto()
    STRING = auto()
    NULL = auto()
    IDENT = auto()
    # Arithmetic
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    DOUBLESTAR = auto()
    # Comparison
    LT = auto()
    LE = auto()
    GT = auto()
    GE = auto()
    EQ = auto()
    NE = auto()
    # Brackets / punctuation
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    # Keywords
    AND = auto()
    OR = auto()
    NOT = auto()
    IF = auto()
    ELSE = auto()
    TRUE = auto()
    FALSE = auto()
    # End of input
    EOF = auto()


@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    value: Any
    line: int
    col: int
    length: int = 1
