# Formula Engine DSL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-23 canonical API (apply before executing this plan):**
> - Plan 17 is a standalone core library. No FastAPI, no HTTP, no database — pure Python under `packages/core/src/openlia/formula/`.
> - **Canonical import surface (Plan 18 and Plan 19 import these names verbatim — do not rename):**
>   ```python
>   from openlia.formula.engine       import FormulaEngine, FormulaError, EvaluationContext
>   from openlia.formula.parser       import parse, Expression
>   from openlia.formula.requirements import extract_requirements, RequirementRef
>   ```
> - `FormulaEngine.evaluate(expr: str | Expression, context: EvaluationContext) -> float | bool`
> - `EvaluationContext.values: dict[str, float | bool | str]`, `EvaluationContext.history: dict[str, list[float]]`
> - Supported operators: `+ - * / % ** ( )`, comparisons `< <= > >= == !=`, logical `and or not`, ternary `<a> if <cond> else <b>`.
> - Supported functions: `min, max, abs, round, mean, median, stddev, sum, last, pct_change, rolling_mean, lag`.
> - Variable syntax: `metric_name` or `metric_name[t-N]` for historical lookup.
> - Safety: no `eval` / `exec`; whitelisted operators and functions; AST depth and node count caps; per-evaluation step counter.
> - Test helper modules use unique names under the `formula` tree (`_formula_fakes.py`, never `_fakes.py`) — see "Test conventions" in `planning/implementation-plans/README.md`.

**Goal:** Ship a deterministic, safe, pure-Python expression DSL (`openlia.formula`) that Panic Thermometer (Plan 18) and Macro Research T1/T2 (Plan 19) consume to evaluate user-editable threshold rules and metric formulas against numeric time-series data. Every formula feature listed above lands with a failing test first, then the implementation, then a green run, then a commit.

**Architecture:**
- **Core-only.** The engine lives entirely in `packages/core/src/openlia/formula/`. No web imports, no database imports, no logging dependencies beyond stdlib. `from openlia.formula import FormulaEngine` must succeed with only `openlia-core` installed.
- **Two-phase:** tokenize → parse → static analysis (`extract_requirements`) → evaluate. Parse and evaluate are independent; tests cover them separately.
- **Canonical AST.** One `Expression` base class + one node type per grammar production (`Literal`, `Var`, `HistoricalVar`, `BinaryOp`, `UnaryOp`, `Call`, `IfElse`). Re-exported from `openlia.formula.parser`.
- **Safe evaluator.** `FormulaEngine` walks the AST with a bounded step counter (hard cap) and a max recursion depth. No `eval`, no `exec`, no dynamic attribute access on user input.
- **Requirement extraction is a static walk.** `extract_requirements(source)` parses the source once and returns the sorted list of `RequirementRef(name, max_lag)` so Plan 18/19 can wire data-provider tools without instantiating an engine.

**Tech Stack:**
- Python 3.12 (matches existing core package).
- Pydantic v2 only for `RequirementRef` (tiny, no evaluation-path involvement). Everything else: stdlib + dataclasses.
- Pytest for tests; no fixtures beyond standard `tmp_path` / parametrize.
- No new dependencies. Every import in the production code must already be available from `openlia-core`'s current `pyproject.toml`.

**Dependencies:**
- Plan 0: workspace scaffolding (`uv`, `ruff`, `pytest` wiring).
- Plan 3: data provider adapter system — Plan 17 is one consumer of the requirements manifest (`extract_requirements` returns a list callers feed into the manifest resolver). Plan 17 does not import Plan 3 modules; the reverse-direction coupling lives in Plans 18/19.

**Unblocks:**
- Plan 18 (Panic Thermometer) — imports `FormulaEngine`, `EvaluationContext`, `FormulaError`, `extract_requirements`, `RequirementRef`.
- Plan 19 (Macro Research T1/T2) — same imports.

---

## Design Rules

1. **Canonical API is frozen.** The three public modules (`engine`, `parser`, `requirements`) export exactly the names listed at the top of this plan. Any deviation breaks Plans 18 and 19 before they merge.
2. **No arbitrary eval, no arbitrary imports.** The evaluator dispatches on AST node type via a closed `match` statement. Function calls resolve against a hard-coded `FUNCTION_REGISTRY` dictionary. User input cannot introduce new callables.
3. **Every error class carries position when available.** `FormulaError(message, *, line=None, col=None, offset=None, source=None)`. Parse errors always fill in position; evaluation errors fill what they can (the AST node carries its source span).
4. **Historical lookup is lazy.** `Var(name)` evaluates against `context.values[name]`. `HistoricalVar(name, lag)` evaluates against `context.history[name][-1 - lag]`. A missing key raises `FormulaError("undefined variable ...")`; a too-short history raises `FormulaError("history for ... needs >= N entries")`.
5. **Short-circuit logic at the AST level.** `BinaryOp.op == "and"` and `BinaryOp.op == "or"` short-circuit. Ternary `if/else` evaluates the condition first and only the branch selected.
6. **Types are explicit.** Arithmetic requires `(int | float, int | float)`. Comparisons compare numbers. `and`/`or`/`not` operate on booleans (numbers are not truthy by default — a user who wants that writes `x != 0`). `TypeError`-class mistakes surface as `FormulaError("operator '+' requires numeric operands, got str")`.
7. **Functions are closed.** The registry is a `dict[str, _FunctionSpec]` in `engine.py`. Adding a function means: new spec entry + unit test + re-export audit. No plugin hooks.
8. **Safety caps are hard.** `MAX_AST_DEPTH = 64`, `MAX_NODE_COUNT = 1024`, `MAX_EVAL_STEPS = 10_000`. Exceeding any cap raises `FormulaError` immediately. These are constants at module top; tests exercise the thresholds.
9. **Idempotent parser.** `parse(source)` returns a new AST every call — no caching, no module-level state. The engine accepts either `str` or an already-parsed `Expression`.
10. **TDD.** Every production file lands with a failing test first, then the implementation, then the green run, then a commit. One commit per task.
11. **No placeholders.** Every step contains exact source, exact commands, exact expected output.
12. **No emojis anywhere.** Matches the project standard in `CLAUDE.md`.

---

## File Structure

### Core (`packages/core/src/openlia/formula/`)

```
formula/
├── __init__.py           # Public API re-exports (FormulaEngine, FormulaError, EvaluationContext,
│                         # parse, Expression, extract_requirements, RequirementRef)
├── tokens.py             # Token dataclass + TokenKind enum
├── lexer.py              # tokenize(source) -> list[Token]
├── parser.py             # parse(source) -> Expression; AST node classes
├── engine.py             # FormulaEngine, FormulaError, EvaluationContext, FUNCTION_REGISTRY
└── requirements.py       # extract_requirements, RequirementRef
```

### Tests (`packages/core/tests/formula/`)

```
formula/
├── __init__.py
├── _formula_fakes.py           # Shared test builders (context factories, canned histories).
│                                # Prefixed to avoid collision per README "Test conventions".
├── test_lexer.py
├── test_parser.py
├── test_ast_nodes.py
├── test_engine_arithmetic.py
├── test_engine_comparisons.py
├── test_engine_logical_ternary.py
├── test_engine_functions.py
├── test_engine_history.py
├── test_engine_safety.py
├── test_requirements.py
├── test_errors.py
└── test_integration.py
```

---

## Task Overview

| # | Task | Artifacts |
|---|---|---|
| 0 | Package scaffolding + failing smoke test | `formula/__init__.py`, `tests/formula/__init__.py`, `tests/formula/test_integration.py` (skipped stub) |
| 1 | Lexer — tokens for numbers, identifiers, operators, brackets, keywords | `tokens.py`, `lexer.py`, `test_lexer.py` |
| 2 | Parser — Pratt/recursive-descent producing AST | `parser.py`, `test_parser.py` |
| 3 | AST node classes (`Expression` base + variants) | `parser.py` (same file), `test_ast_nodes.py` |
| 4 | Evaluator — arithmetic + comparisons + logical | `engine.py`, `test_engine_arithmetic.py`, `test_engine_comparisons.py` |
| 5 | Function library (`min`, `max`, `abs`, `round`, `mean`, `median`, `stddev`, `sum`) | `engine.py` (extend registry), `test_engine_functions.py` |
| 6 | History-aware functions + `HistoricalVar` (`last`, `pct_change`, `rolling_mean`, `lag`) | `engine.py`, `parser.py`, `test_engine_history.py` |
| 7 | Safety limits (depth, node count, step counter) | `engine.py`, `parser.py`, `test_engine_safety.py` |
| 8 | Requirement extraction | `requirements.py`, `test_requirements.py` |
| 9 | Error types with position info | `engine.py` (extend), `test_errors.py` |
| 10 | Integration test: PT-style threshold rule + MR-style metric formula | `test_integration.py` (remove skip) |
| 11 | Re-exports from `packages/core/src/openlia/__init__.py`, status table update | `openlia/__init__.py`, `planning/implementation-plans/README.md` |

One commit per task. Commit messages follow the repo convention (`feat(formula): ...`, `test(formula): ...`).

---

## Task 0 — Package scaffolding + skipped smoke test

Goal: create empty modules and a skipped integration test so subsequent tasks have a stable home.

**Files:**
- Create: `packages/core/src/openlia/formula/__init__.py`
- Create: `packages/core/src/openlia/formula/tokens.py`
- Create: `packages/core/src/openlia/formula/lexer.py`
- Create: `packages/core/src/openlia/formula/parser.py`
- Create: `packages/core/src/openlia/formula/engine.py`
- Create: `packages/core/src/openlia/formula/requirements.py`
- Create: `packages/core/tests/formula/__init__.py`
- Create: `packages/core/tests/formula/_formula_fakes.py`
- Create: `packages/core/tests/formula/test_integration.py`

- [ ] **Step 1: Create the empty package files.**

Write the minimum each module needs to import cleanly.

```python
# packages/core/src/openlia/formula/__init__.py
"""OpenLIA formula engine — deterministic, safe expression DSL."""

from openlia.formula.engine import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
)
from openlia.formula.parser import Expression, parse
from openlia.formula.requirements import RequirementRef, extract_requirements

__all__ = [
    "EvaluationContext",
    "Expression",
    "FormulaEngine",
    "FormulaError",
    "RequirementRef",
    "extract_requirements",
    "parse",
]
```

```python
# packages/core/src/openlia/formula/tokens.py
"""Token types used by the lexer. Populated in Task 1."""
```

```python
# packages/core/src/openlia/formula/lexer.py
"""Source-to-token conversion. Populated in Task 1."""
```

```python
# packages/core/src/openlia/formula/parser.py
"""Token-to-AST parser. Populated in Task 2.

Exports ``parse(source: str) -> Expression`` and the ``Expression`` base class.
"""

from __future__ import annotations


class Expression:
    """Base class for every AST node. Concrete subclasses land in Task 3."""


def parse(source: str) -> Expression:  # pragma: no cover - Task 2
    raise NotImplementedError("parse() lands in Task 2")
```

```python
# packages/core/src/openlia/formula/engine.py
"""Evaluation engine. Populated in Task 4.

Exports ``FormulaEngine``, ``EvaluationContext``, ``FormulaError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class FormulaError(Exception):
    """All parse/evaluation failures raise this (or a subclass)."""


@dataclass
class EvaluationContext:
    """Inputs to a formula evaluation.

    ``values``  -- named scalars (numeric or boolean or string).
    ``history`` -- named sequences (chronological, oldest first).
    """

    values: dict[str, float | bool | str] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)


class FormulaEngine:  # pragma: no cover - Task 4
    def evaluate(self, expr, context):  # noqa: ANN001
        raise NotImplementedError("FormulaEngine lands in Task 4")
```

```python
# packages/core/src/openlia/formula/requirements.py
"""Static requirement extraction. Populated in Task 8."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequirementRef:
    """Static reference to a variable plus its maximum historical lag (if any)."""

    name: str
    max_lag: int = 0


def extract_requirements(source: str) -> list[RequirementRef]:  # pragma: no cover - Task 8
    raise NotImplementedError("extract_requirements lands in Task 8")
```

```python
# packages/core/tests/formula/__init__.py
```

```python
# packages/core/tests/formula/_formula_fakes.py
"""Test helpers for the formula engine.

Named with the ``_formula_`` prefix per README "Test conventions" to
guarantee uniqueness across the whole test tree.
"""

from __future__ import annotations

from openlia.formula import EvaluationContext


def ctx(**values: float | bool | str) -> EvaluationContext:
    return EvaluationContext(values=dict(values))


def ctx_with_history(
    *,
    values: dict[str, float | bool | str] | None = None,
    history: dict[str, list[float]] | None = None,
) -> EvaluationContext:
    return EvaluationContext(
        values=dict(values or {}),
        history={k: list(v) for k, v in (history or {}).items()},
    )
```

```python
# packages/core/tests/formula/test_integration.py
"""Cross-module integration coverage.

The real assertions land in Task 10. This stub just pins the canonical
import surface so downstream plans fail fast if a name drifts.
"""

import pytest


def test_public_api_exports():
    from openlia.formula import (  # noqa: F401
        EvaluationContext,
        Expression,
        FormulaEngine,
        FormulaError,
        RequirementRef,
        extract_requirements,
        parse,
    )


@pytest.mark.skip(reason="Integration assertions land in Task 10")
def test_threshold_rule_end_to_end():
    raise AssertionError
```

- [ ] **Step 2: Run the check and confirm the imports resolve.**

Command:
```bash
uv run pytest packages/core/tests/formula/test_integration.py -v
```

Expected output (excerpted):
```
test_integration.py::test_public_api_exports PASSED
test_integration.py::test_threshold_rule_end_to_end SKIPPED (Integration assertions land in Task 10)
```

- [ ] **Step 3: Lint.**

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
```

Expected: `All checks passed!` and `N files reformatted` (or unchanged).

- [ ] **Step 4: Commit.**

```bash
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): scaffold package with canonical API stubs"
```

---

## Task 1 — Lexer

Goal: tokenize a source string into a list of `Token` instances covering numbers, identifiers, keywords, operators, brackets, commas, and the `[t-N]` historical-index syntax.

**Files:**
- Write: `packages/core/src/openlia/formula/tokens.py`
- Write: `packages/core/src/openlia/formula/lexer.py`
- Create: `packages/core/tests/formula/test_lexer.py`

### Step 1: Write the failing test

```python
# packages/core/tests/formula/test_lexer.py
from __future__ import annotations

import pytest

from openlia.formula.lexer import tokenize
from openlia.formula.tokens import Token, TokenKind


def kinds(src: str) -> list[TokenKind]:
    return [t.kind for t in tokenize(src)]


def test_tokenize_empty_returns_only_eof():
    toks = tokenize("")
    assert len(toks) == 1
    assert toks[0].kind is TokenKind.EOF


def test_tokenize_numbers():
    toks = tokenize("1 2.5 -3 1e3 1.2e-4")
    # unary minus is handled by parser; the lexer emits MINUS, NUMBER.
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.MINUS,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
        TokenKind.NUMBER,
    ]
    assert toks[0].value == 1.0
    assert toks[1].value == 2.5
    assert toks[3].value == 3.0
    assert toks[4].value == 1000.0
    assert toks[5].value == pytest.approx(1.2e-4)


def test_tokenize_identifiers_and_keywords():
    toks = tokenize("price ma200 and or not if else true false")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.IDENT,
        TokenKind.IDENT,
        TokenKind.AND,
        TokenKind.OR,
        TokenKind.NOT,
        TokenKind.IF,
        TokenKind.ELSE,
        TokenKind.TRUE,
        TokenKind.FALSE,
    ]
    assert toks[0].value == "price"
    assert toks[1].value == "ma200"


def test_tokenize_operators_and_brackets():
    toks = tokenize("+ - * / % ** ( ) , [ ]")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.PLUS,
        TokenKind.MINUS,
        TokenKind.STAR,
        TokenKind.SLASH,
        TokenKind.PERCENT,
        TokenKind.DOUBLESTAR,
        TokenKind.LPAREN,
        TokenKind.RPAREN,
        TokenKind.COMMA,
        TokenKind.LBRACKET,
        TokenKind.RBRACKET,
    ]


def test_tokenize_comparisons():
    toks = tokenize("< <= > >= == !=")
    assert [t.kind for t in toks[:-1]] == [
        TokenKind.LT,
        TokenKind.LE,
        TokenKind.GT,
        TokenKind.GE,
        TokenKind.EQ,
        TokenKind.NE,
    ]


def test_tokenize_records_positions():
    toks = tokenize("price >= 85")
    assert toks[0].col == 1
    assert toks[1].col == 7
    assert toks[2].col == 10
    assert toks[0].line == 1


def test_tokenize_raises_on_unknown_character():
    with pytest.raises(Exception) as excinfo:
        tokenize("price @ 5")
    msg = str(excinfo.value).lower()
    assert "unexpected" in msg or "unknown" in msg
    # Position surfaced on the exception.
    assert "7" in str(excinfo.value)


def test_token_dataclass_is_hashable_and_repr_safe():
    t = Token(kind=TokenKind.IDENT, value="x", line=1, col=1)
    assert t.kind is TokenKind.IDENT
    repr(t)  # should not raise
```

### Step 2: Confirm the test fails

```bash
uv run pytest packages/core/tests/formula/test_lexer.py -v
```

Expected: every test fails with `ImportError` or `ModuleNotFoundError` because `tokens.py` and `lexer.py` are empty.

### Step 3: Implement the lexer

```python
# packages/core/src/openlia/formula/tokens.py
"""Token dataclass + kinds emitted by the lexer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class TokenKind(Enum):
    # Literals
    NUMBER = auto()
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
```

```python
# packages/core/src/openlia/formula/lexer.py
"""Convert a formula source string into a list of ``Token`` instances.

The lexer recognises numbers, identifiers, keywords, single/double-character
operators, comparison operators, brackets, commas, and the ``[t-N]`` syntax.
Whitespace is skipped. Unknown characters raise ``LexError`` with line/col.
"""

from __future__ import annotations

from openlia.formula.tokens import Token, TokenKind


class LexError(Exception):
    def __init__(self, message: str, *, line: int, col: int) -> None:
        super().__init__(f"{message} at line {line}, col {col}")
        self.line = line
        self.col = col


_KEYWORDS: dict[str, TokenKind] = {
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
}


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    i = 0
    line = 1
    line_start = 0
    n = len(source)

    while i < n:
        ch = source[i]
        col = i - line_start + 1

        if ch in " \t":
            i += 1
            continue
        if ch == "\n":
            line += 1
            i += 1
            line_start = i
            continue

        # Numbers (int, float, scientific).
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i
            has_dot = False
            has_exp = False
            while j < n:
                c = source[j]
                if c.isdigit():
                    j += 1
                elif c == "." and not has_dot and not has_exp:
                    has_dot = True
                    j += 1
                elif c in "eE" and not has_exp:
                    has_exp = True
                    j += 1
                    if j < n and source[j] in "+-":
                        j += 1
                else:
                    break
            text = source[i:j]
            try:
                value = float(text)
            except ValueError as exc:
                raise LexError(f"invalid number '{text}'", line=line, col=col) from exc
            tokens.append(
                Token(TokenKind.NUMBER, value, line=line, col=col, length=j - i)
            )
            i = j
            continue

        # Identifiers / keywords.
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            text = source[i:j]
            kind = _KEYWORDS.get(text, TokenKind.IDENT)
            value: object = text
            if kind is TokenKind.TRUE:
                value = True
            elif kind is TokenKind.FALSE:
                value = False
            tokens.append(Token(kind, value, line=line, col=col, length=j - i))
            i = j
            continue

        # Two-character operators first.
        two = source[i : i + 2]
        if two == "**":
            tokens.append(Token(TokenKind.DOUBLESTAR, "**", line=line, col=col, length=2))
            i += 2
            continue
        if two == "<=":
            tokens.append(Token(TokenKind.LE, "<=", line=line, col=col, length=2))
            i += 2
            continue
        if two == ">=":
            tokens.append(Token(TokenKind.GE, ">=", line=line, col=col, length=2))
            i += 2
            continue
        if two == "==":
            tokens.append(Token(TokenKind.EQ, "==", line=line, col=col, length=2))
            i += 2
            continue
        if two == "!=":
            tokens.append(Token(TokenKind.NE, "!=", line=line, col=col, length=2))
            i += 2
            continue

        single_map: dict[str, TokenKind] = {
            "+": TokenKind.PLUS,
            "-": TokenKind.MINUS,
            "*": TokenKind.STAR,
            "/": TokenKind.SLASH,
            "%": TokenKind.PERCENT,
            "(": TokenKind.LPAREN,
            ")": TokenKind.RPAREN,
            "[": TokenKind.LBRACKET,
            "]": TokenKind.RBRACKET,
            ",": TokenKind.COMMA,
            "<": TokenKind.LT,
            ">": TokenKind.GT,
        }
        if ch in single_map:
            tokens.append(Token(single_map[ch], ch, line=line, col=col))
            i += 1
            continue

        raise LexError(f"unexpected character {ch!r}", line=line, col=col)

    tokens.append(Token(TokenKind.EOF, None, line=line, col=i - line_start + 1))
    return tokens
```

### Step 4: Confirm the test passes

```bash
uv run pytest packages/core/tests/formula/test_lexer.py -v
```

Expected: `9 passed`.

### Step 5: Lint and commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): tokenize source into typed tokens with positions"
```

---

## Task 2 — Parser (shell) producing AST stubs

Goal: recursive-descent parser with Pratt-style precedence climbing, returning an `Expression` AST. This task does not yet implement `HistoricalVar` or call parsing — those land in Task 3 (AST) + Task 6 (history).

**Files:**
- Overwrite: `packages/core/src/openlia/formula/parser.py`
- Create: `packages/core/tests/formula/test_parser.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_parser.py
from __future__ import annotations

import pytest

from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


def test_parse_returns_expression():
    node = parse("1 + 2")
    assert isinstance(node, Expression)
    assert isinstance(node, BinaryOp)
    assert node.op == "+"
    assert isinstance(node.left, Literal) and node.left.value == 1.0
    assert isinstance(node.right, Literal) and node.right.value == 2.0


def test_parse_precedence_mul_before_add():
    node = parse("1 + 2 * 3")
    assert isinstance(node, BinaryOp) and node.op == "+"
    right = node.right
    assert isinstance(right, BinaryOp) and right.op == "*"


def test_parse_parentheses_override_precedence():
    node = parse("(1 + 2) * 3")
    assert isinstance(node, BinaryOp) and node.op == "*"
    assert isinstance(node.left, BinaryOp) and node.left.op == "+"


def test_parse_unary_minus_and_not():
    node = parse("-price")
    assert isinstance(node, UnaryOp) and node.op == "-"
    assert isinstance(node.operand, Var) and node.operand.name == "price"

    node2 = parse("not ready")
    assert isinstance(node2, UnaryOp) and node2.op == "not"


def test_parse_comparison_chain_is_flat_not_chained():
    # We do not support Python-style chained comparisons; `a < b < c` must
    # parse as `(a < b) < c` per the operator precedence table, and fail
    # type-checking at evaluation time rather than silently merging.
    node = parse("a < b < c")
    assert isinstance(node, BinaryOp) and node.op == "<"
    assert isinstance(node.left, BinaryOp) and node.left.op == "<"


def test_parse_logical_and_or_precedence():
    # `not` binds tighter than `and`, which binds tighter than `or`.
    node = parse("a or b and not c")
    assert isinstance(node, BinaryOp) and node.op == "or"
    assert isinstance(node.right, BinaryOp) and node.right.op == "and"
    assert isinstance(node.right.right, UnaryOp) and node.right.right.op == "not"


def test_parse_ternary_if_else():
    node = parse("1 if cond else 2")
    assert isinstance(node, IfElse)
    assert isinstance(node.then_branch, Literal) and node.then_branch.value == 1.0
    assert isinstance(node.condition, Var) and node.condition.name == "cond"
    assert isinstance(node.else_branch, Literal) and node.else_branch.value == 2.0


def test_parse_function_call_zero_and_many_args():
    node = parse("mean(price, 5)")
    assert isinstance(node, Call)
    assert node.callee == "mean"
    assert len(node.args) == 2


def test_parse_exponent_is_right_associative():
    node = parse("2 ** 3 ** 2")
    assert isinstance(node, BinaryOp) and node.op == "**"
    right = node.right
    assert isinstance(right, BinaryOp) and right.op == "**"
    assert isinstance(right.left, Literal) and right.left.value == 3.0


def test_parse_boolean_and_numeric_literals():
    assert isinstance(parse("true"), Literal)
    assert parse("true").value is True
    assert parse("false").value is False
    assert parse("3.14").value == pytest.approx(3.14)


def test_parse_reports_position_on_syntax_error():
    from openlia.formula.engine import FormulaError

    with pytest.raises(FormulaError) as exc:
        parse("1 +")
    msg = str(exc.value)
    assert "expected" in msg.lower()


def test_parse_rejects_trailing_garbage():
    from openlia.formula.engine import FormulaError

    with pytest.raises(FormulaError):
        parse("1 + 2 )")
```

### Step 2: Confirm the test fails

```bash
uv run pytest packages/core/tests/formula/test_parser.py -v
```

Expected: `ImportError: cannot import name 'BinaryOp' from 'openlia.formula.parser'`.

### Step 3: Implement parser + initial AST nodes

```python
# packages/core/src/openlia/formula/parser.py
"""Pratt-style parser producing a typed AST.

The grammar (in pseudo-EBNF, loosest precedence first):

    expr        := ternary
    ternary     := or_expr ("if" or_expr "else" expr)?
    or_expr     := and_expr ("or" and_expr)*
    and_expr    := not_expr ("and" not_expr)*
    not_expr    := "not" not_expr | comparison
    comparison  := additive ( ("<"|"<="|">"|">="|"=="|"!=") additive )*
    additive    := multiplicative ( ("+"|"-") multiplicative )*
    multiplicative := unary ( ("*"|"/"|"%") unary )*
    unary       := "-" unary | power
    power       := primary ( "**" unary )?
    primary     := NUMBER | TRUE | FALSE | IDENT ( "[" history "]" )? | call | "(" expr ")"
    call        := IDENT "(" [ expr ("," expr)* ] ")"
    history     := "t" "-" NUMBER            # populated in Task 6
"""

from __future__ import annotations

from dataclasses import dataclass, field

from openlia.formula.engine import FormulaError
from openlia.formula.lexer import LexError, tokenize
from openlia.formula.tokens import Token, TokenKind


class Expression:
    """Base class for every AST node."""

    # Source span (set by parser where available). Evaluator reads these for
    # richer error messages.
    line: int = 0
    col: int = 0


@dataclass
class Literal(Expression):
    value: float | bool
    line: int = 0
    col: int = 0


@dataclass
class Var(Expression):
    name: str
    line: int = 0
    col: int = 0


@dataclass
class HistoricalVar(Expression):
    """Placeholder; body lands in Task 6."""

    name: str
    lag: int
    line: int = 0
    col: int = 0


@dataclass
class BinaryOp(Expression):
    op: str
    left: Expression
    right: Expression
    line: int = 0
    col: int = 0


@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression
    line: int = 0
    col: int = 0


@dataclass
class Call(Expression):
    callee: str
    args: list[Expression] = field(default_factory=list)
    line: int = 0
    col: int = 0


@dataclass
class IfElse(Expression):
    condition: Expression
    then_branch: Expression
    else_branch: Expression
    line: int = 0
    col: int = 0


_COMPARISON_KINDS: dict[TokenKind, str] = {
    TokenKind.LT: "<",
    TokenKind.LE: "<=",
    TokenKind.GT: ">",
    TokenKind.GE: ">=",
    TokenKind.EQ: "==",
    TokenKind.NE: "!=",
}


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # ---- navigation ----
    @property
    def peek(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def accept(self, kind: TokenKind) -> Token | None:
        if self.peek.kind is kind:
            return self.advance()
        return None

    def expect(self, kind: TokenKind, what: str) -> Token:
        if self.peek.kind is not kind:
            t = self.peek
            raise FormulaError(
                f"expected {what} but found {t.kind.name}",
                line=t.line,
                col=t.col,
            )
        return self.advance()

    # ---- grammar ----
    def parse(self) -> Expression:
        node = self.ternary()
        if self.peek.kind is not TokenKind.EOF:
            t = self.peek
            raise FormulaError(
                f"unexpected token {t.kind.name} after expression",
                line=t.line,
                col=t.col,
            )
        return node

    def ternary(self) -> Expression:
        left = self.or_expr()
        if self.accept(TokenKind.IF):
            cond = self.or_expr()
            self.expect(TokenKind.ELSE, "'else'")
            other = self.ternary()
            return IfElse(
                condition=cond, then_branch=left, else_branch=other,
                line=left.line, col=left.col,
            )
        return left

    def or_expr(self) -> Expression:
        node = self.and_expr()
        while self.accept(TokenKind.OR):
            right = self.and_expr()
            node = BinaryOp("or", node, right, line=node.line, col=node.col)
        return node

    def and_expr(self) -> Expression:
        node = self.not_expr()
        while self.accept(TokenKind.AND):
            right = self.not_expr()
            node = BinaryOp("and", node, right, line=node.line, col=node.col)
        return node

    def not_expr(self) -> Expression:
        if self.accept(TokenKind.NOT):
            operand = self.not_expr()
            return UnaryOp("not", operand, line=operand.line, col=operand.col)
        return self.comparison()

    def comparison(self) -> Expression:
        node = self.additive()
        while self.peek.kind in _COMPARISON_KINDS:
            op_tok = self.advance()
            right = self.additive()
            node = BinaryOp(
                _COMPARISON_KINDS[op_tok.kind], node, right,
                line=node.line, col=node.col,
            )
        return node

    def additive(self) -> Expression:
        node = self.multiplicative()
        while True:
            if self.accept(TokenKind.PLUS):
                right = self.multiplicative()
                node = BinaryOp("+", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.MINUS):
                right = self.multiplicative()
                node = BinaryOp("-", node, right, line=node.line, col=node.col)
            else:
                return node

    def multiplicative(self) -> Expression:
        node = self.unary()
        while True:
            if self.accept(TokenKind.STAR):
                right = self.unary()
                node = BinaryOp("*", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.SLASH):
                right = self.unary()
                node = BinaryOp("/", node, right, line=node.line, col=node.col)
            elif self.accept(TokenKind.PERCENT):
                right = self.unary()
                node = BinaryOp("%", node, right, line=node.line, col=node.col)
            else:
                return node

    def unary(self) -> Expression:
        if self.accept(TokenKind.MINUS):
            operand = self.unary()
            return UnaryOp("-", operand, line=operand.line, col=operand.col)
        return self.power()

    def power(self) -> Expression:
        base = self.primary()
        if self.accept(TokenKind.DOUBLESTAR):
            exponent = self.unary()  # right-associative
            return BinaryOp("**", base, exponent, line=base.line, col=base.col)
        return base

    def primary(self) -> Expression:
        t = self.peek
        if t.kind is TokenKind.NUMBER:
            self.advance()
            return Literal(value=t.value, line=t.line, col=t.col)
        if t.kind is TokenKind.TRUE:
            self.advance()
            return Literal(value=True, line=t.line, col=t.col)
        if t.kind is TokenKind.FALSE:
            self.advance()
            return Literal(value=False, line=t.line, col=t.col)
        if t.kind is TokenKind.LPAREN:
            self.advance()
            node = self.ternary()
            self.expect(TokenKind.RPAREN, "')'")
            return node
        if t.kind is TokenKind.IDENT:
            self.advance()
            # Function call?
            if self.accept(TokenKind.LPAREN):
                args: list[Expression] = []
                if self.peek.kind is not TokenKind.RPAREN:
                    args.append(self.ternary())
                    while self.accept(TokenKind.COMMA):
                        args.append(self.ternary())
                self.expect(TokenKind.RPAREN, "')'")
                return Call(callee=t.value, args=args, line=t.line, col=t.col)
            # Historical indexing lands in Task 6.
            if self.accept(TokenKind.LBRACKET):
                return self._parse_history_index(t)
            return Var(name=t.value, line=t.line, col=t.col)

        raise FormulaError(
            f"expected expression but found {t.kind.name}", line=t.line, col=t.col,
        )

    # Placeholder; Task 6 replaces the body with full `[t-N]` parsing.
    def _parse_history_index(self, ident: Token) -> Expression:  # pragma: no cover
        raise FormulaError(
            "historical indexing '[t-N]' lands in Task 6",
            line=ident.line,
            col=ident.col,
        )


def parse(source: str) -> Expression:
    try:
        tokens = tokenize(source)
    except LexError as exc:
        raise FormulaError(str(exc), line=exc.line, col=exc.col) from exc
    return _Parser(tokens).parse()
```

Also extend `engine.py`'s `FormulaError` so parse-time position info survives:

```python
# packages/core/src/openlia/formula/engine.py  (replace the stub class)
class FormulaError(Exception):
    """Parse/evaluation failure with optional source position."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        if line is not None and col is not None:
            super().__init__(f"{message} (line {line}, col {col})")
        else:
            super().__init__(message)
        self.line = line
        self.col = col
```

Leave `EvaluationContext` and the `FormulaEngine` stub in place.

### Step 4: Confirm the test passes

```bash
uv run pytest packages/core/tests/formula/test_parser.py -v
```

Expected: `12 passed`.

### Step 5: Lint + commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): recursive-descent parser with Pratt precedence"
```

---

## Task 3 — AST round-trip tests

Goal: pin the `Expression` subclass contract (equality semantics, `__repr__`, attribute names) so downstream code depending on specific field names cannot silently break.

**Files:**
- Create: `packages/core/tests/formula/test_ast_nodes.py`
- (No new production code — this task hardens the models that landed in Task 2.)

### Step 1: Failing test

```python
# packages/core/tests/formula/test_ast_nodes.py
from __future__ import annotations

from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    HistoricalVar,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


def test_every_node_class_inherits_expression():
    classes = [BinaryOp, Call, HistoricalVar, IfElse, Literal, UnaryOp, Var]
    for cls in classes:
        assert issubclass(cls, Expression), cls.__name__


def test_literal_attribute_shape():
    node = parse("3.14")
    assert isinstance(node, Literal)
    assert node.value == 3.14
    assert hasattr(node, "line") and hasattr(node, "col")


def test_var_carries_name_and_position():
    node = parse("ma200")
    assert isinstance(node, Var)
    assert node.name == "ma200"
    assert node.col == 1


def test_binary_op_has_op_left_right():
    node = parse("a + b")
    assert isinstance(node, BinaryOp)
    for attr in ("op", "left", "right", "line", "col"):
        assert hasattr(node, attr)


def test_unary_op_has_op_and_operand():
    node = parse("-x")
    assert isinstance(node, UnaryOp)
    assert node.op == "-"
    assert hasattr(node, "operand")


def test_call_has_callee_and_args():
    node = parse("max(a, b, 3)")
    assert isinstance(node, Call)
    assert node.callee == "max"
    assert len(node.args) == 3


def test_if_else_has_condition_then_else():
    node = parse("1 if cond else 2")
    assert isinstance(node, IfElse)
    assert hasattr(node, "condition")
    assert hasattr(node, "then_branch")
    assert hasattr(node, "else_branch")


def test_nodes_are_dataclass_equal():
    assert parse("1 + 2") == parse("1 + 2")
    assert parse("1 + 2") != parse("2 + 1")


def test_nodes_repr_is_useful():
    text = repr(parse("1 + 2"))
    assert "BinaryOp" in text
    assert "Literal" in text
```

### Step 2: Confirm / implement

```bash
uv run pytest packages/core/tests/formula/test_ast_nodes.py -v
```

Every test should pass without further changes because Task 2 landed the dataclasses. If any assertion fails, tighten Task 2's dataclass definitions (e.g., missing `line=0` default) rather than introducing new types.

### Step 3: Commit

```bash
git add packages/core/tests/formula/test_ast_nodes.py
git commit -m "test(formula): pin AST node attribute contract"
```

---

## Task 4 — Evaluator for arithmetic, comparison, logical

Goal: walk the AST and compute numbers / booleans. Implements `FormulaEngine.evaluate(...)` for everything except function calls and historical lookup.

**Files:**
- Overwrite: `packages/core/src/openlia/formula/engine.py`
- Create: `packages/core/tests/formula/test_engine_arithmetic.py`
- Create: `packages/core/tests/formula/test_engine_comparisons.py`
- Create: `packages/core/tests/formula/test_engine_logical_ternary.py`

### Step 1: Failing tests

```python
# packages/core/tests/formula/test_engine_arithmetic.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


@pytest.mark.parametrize(
    "src,expected",
    [
        ("1 + 2", 3.0),
        ("10 - 4", 6.0),
        ("3 * 4", 12.0),
        ("10 / 4", 2.5),
        ("10 % 3", 1.0),
        ("2 ** 3", 8.0),
        ("2 ** 3 ** 2", 512.0),
        ("-5 + 3", -2.0),
        ("(1 + 2) * 3", 9.0),
        ("1 + 2 * 3", 7.0),
    ],
)
def test_numeric_expressions(engine: FormulaEngine, src: str, expected: float):
    assert engine.evaluate(src, EvaluationContext()) == expected


def test_variable_lookup(engine: FormulaEngine):
    assert engine.evaluate("price * 2", ctx(price=10.0)) == 20.0


def test_division_by_zero_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("1 / 0", EvaluationContext())
    assert "division" in str(exc.value).lower()


def test_modulo_by_zero_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("5 % 0", EvaluationContext())


def test_undefined_variable_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("ghost + 1", EvaluationContext())
    assert "ghost" in str(exc.value)


def test_string_operand_is_type_error(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("name + 1", ctx(name="alice"))
    assert "numeric" in str(exc.value).lower()


def test_accepts_prebuilt_ast(engine: FormulaEngine):
    from openlia.formula import parse

    tree = parse("price + 1")
    assert engine.evaluate(tree, ctx(price=4.0)) == 5.0
```

```python
# packages/core/tests/formula/test_engine_comparisons.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


@pytest.mark.parametrize(
    "src,expected",
    [
        ("1 < 2", True),
        ("2 < 1", False),
        ("3 <= 3", True),
        ("4 > 2", True),
        ("4 >= 5", False),
        ("1 == 1", True),
        ("1 != 2", True),
    ],
)
def test_numeric_comparisons(engine: FormulaEngine, src: str, expected: bool):
    assert engine.evaluate(src, EvaluationContext()) is expected


def test_string_equality_works(engine: FormulaEngine):
    # Strings may only compare with == / !=.
    assert engine.evaluate("status == status", ctx(status="red")) is True


def test_string_ordering_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("status < status", ctx(status="red"))
    assert "order" in str(exc.value).lower() or "numeric" in str(exc.value).lower()
```

```python
# packages/core/tests/formula/test_engine_logical_ternary.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_and_or_not_evaluation(engine: FormulaEngine):
    assert engine.evaluate("true and false", EvaluationContext()) is False
    assert engine.evaluate("true or false", EvaluationContext()) is True
    assert engine.evaluate("not true", EvaluationContext()) is False


def test_short_circuit_and_skips_rhs(engine: FormulaEngine):
    # `ghost` is undefined; if we short-circuit we must not look it up.
    result = engine.evaluate("false and ghost", EvaluationContext())
    assert result is False


def test_short_circuit_or_skips_rhs(engine: FormulaEngine):
    result = engine.evaluate("true or ghost", EvaluationContext())
    assert result is True


def test_ternary_selects_then_branch(engine: FormulaEngine):
    assert engine.evaluate("1 if true else 2", EvaluationContext()) == 1.0


def test_ternary_selects_else_branch(engine: FormulaEngine):
    assert engine.evaluate("1 if false else 2", EvaluationContext()) == 2.0


def test_ternary_short_circuits_unused_branch(engine: FormulaEngine):
    # Division by zero in the unused branch must not explode.
    assert engine.evaluate("1 if true else 1/0", EvaluationContext()) == 1.0


def test_logical_requires_boolean_operands(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("1 and 2", EvaluationContext())
```

### Step 2: Confirm failures

```bash
uv run pytest packages/core/tests/formula/test_engine_arithmetic.py \
  packages/core/tests/formula/test_engine_comparisons.py \
  packages/core/tests/formula/test_engine_logical_ternary.py -v
```

Expected: every test errors with `NotImplementedError: FormulaEngine lands in Task 4`.

### Step 3: Implement the evaluator core

```python
# packages/core/src/openlia/formula/engine.py
"""Safe, deterministic evaluator for the formula DSL.

This module owns three public names:

    FormulaEngine       -- entry point; stateless across calls
    EvaluationContext   -- dict wrappers for values + history
    FormulaError        -- every error surfaces as this or a subclass
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    HistoricalVar,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


class FormulaError(Exception):
    """Parse/evaluation failure with optional source position."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        if line is not None and col is not None:
            super().__init__(f"{message} (line {line}, col {col})")
        else:
            super().__init__(message)
        self.line = line
        self.col = col


@dataclass
class EvaluationContext:
    values: dict[str, float | bool | str] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)


# Safety caps -- public constants so tests can import them.
MAX_AST_DEPTH = 64
MAX_NODE_COUNT = 1024
MAX_EVAL_STEPS = 10_000


# Function registry landed here; full population in Tasks 5 & 6.
@dataclass(frozen=True, slots=True)
class _FunctionSpec:
    name: str
    min_args: int
    max_args: int
    needs_history: bool
    impl: Any  # Callable — annotated loosely to avoid heavy typing imports.


FUNCTION_REGISTRY: dict[str, _FunctionSpec] = {}


class FormulaEngine:
    """Evaluate an expression (source string or pre-parsed AST) against a context."""

    def evaluate(
        self, expr: str | Expression, context: EvaluationContext
    ) -> float | bool:
        if isinstance(expr, str):
            tree = parse(expr)
        else:
            tree = expr
        state = _EvalState()
        result = _eval_node(tree, context, state)
        return _coerce_final(result)


@dataclass
class _EvalState:
    steps: int = 0


def _step(state: _EvalState) -> None:
    state.steps += 1
    if state.steps > MAX_EVAL_STEPS:
        raise FormulaError(
            f"evaluation exceeded {MAX_EVAL_STEPS} steps; aborting"
        )


def _coerce_final(value: Any) -> float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    raise FormulaError(
        f"formula produced non-numeric/non-boolean result: {type(value).__name__}"
    )


def _require_number(value: Any, *, op: str, node: Expression) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormulaError(
            f"operator {op!r} requires numeric operands, got "
            f"{type(value).__name__}",
            line=node.line,
            col=node.col,
        )
    return float(value)


def _require_bool(value: Any, *, op: str, node: Expression) -> bool:
    if not isinstance(value, bool):
        raise FormulaError(
            f"operator {op!r} requires boolean operands, got "
            f"{type(value).__name__}",
            line=node.line,
            col=node.col,
        )
    return value


def _eval_node(node: Expression, ctx: EvaluationContext, state: _EvalState) -> Any:
    _step(state)

    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Var):
        if node.name not in ctx.values:
            raise FormulaError(
                f"undefined variable {node.name!r}",
                line=node.line,
                col=node.col,
            )
        return ctx.values[node.name]

    if isinstance(node, HistoricalVar):
        # Body lands in Task 6; for now raise to keep behaviour explicit.
        raise FormulaError(
            "historical variables land in Task 6",
            line=node.line, col=node.col,
        )

    if isinstance(node, UnaryOp):
        operand = _eval_node(node.operand, ctx, state)
        if node.op == "-":
            return -_require_number(operand, op="-", node=node)
        if node.op == "not":
            return not _require_bool(operand, op="not", node=node)
        raise FormulaError(
            f"unknown unary operator {node.op!r}",
            line=node.line, col=node.col,
        )

    if isinstance(node, BinaryOp):
        return _eval_binary(node, ctx, state)

    if isinstance(node, IfElse):
        cond = _eval_node(node.condition, ctx, state)
        cond_b = _require_bool(cond, op="if", node=node)
        branch = node.then_branch if cond_b else node.else_branch
        return _eval_node(branch, ctx, state)

    if isinstance(node, Call):
        return _eval_call(node, ctx, state)

    raise FormulaError(
        f"unsupported AST node {type(node).__name__}",
        line=node.line, col=node.col,
    )


def _eval_binary(
    node: BinaryOp, ctx: EvaluationContext, state: _EvalState
) -> Any:
    op = node.op

    # Short-circuit logical operators.
    if op == "and":
        left = _require_bool(
            _eval_node(node.left, ctx, state), op="and", node=node,
        )
        if not left:
            return False
        return _require_bool(
            _eval_node(node.right, ctx, state), op="and", node=node,
        )
    if op == "or":
        left = _require_bool(
            _eval_node(node.left, ctx, state), op="or", node=node,
        )
        if left:
            return True
        return _require_bool(
            _eval_node(node.right, ctx, state), op="or", node=node,
        )

    left = _eval_node(node.left, ctx, state)
    right = _eval_node(node.right, ctx, state)

    if op in {"==", "!="}:
        # Strict equality — types must match.
        if type(left) is not type(right):
            # Allow int/float interop (both ultimately floats after coercion).
            if not (
                isinstance(left, (int, float))
                and isinstance(right, (int, float))
                and not isinstance(left, bool)
                and not isinstance(right, bool)
            ):
                raise FormulaError(
                    f"comparison {op!r} requires matching types, got "
                    f"{type(left).__name__} and {type(right).__name__}",
                    line=node.line, col=node.col,
                )
        return (left == right) if op == "==" else (left != right)

    if op in {"<", "<=", ">", ">="}:
        ln = _require_number(left, op=op, node=node)
        rn = _require_number(right, op=op, node=node)
        return {
            "<": ln < rn,
            "<=": ln <= rn,
            ">": ln > rn,
            ">=": ln >= rn,
        }[op]

    # Arithmetic.
    ln = _require_number(left, op=op, node=node)
    rn = _require_number(right, op=op, node=node)
    if op == "+":
        return ln + rn
    if op == "-":
        return ln - rn
    if op == "*":
        return ln * rn
    if op == "/":
        if rn == 0.0:
            raise FormulaError(
                "division by zero", line=node.line, col=node.col,
            )
        return ln / rn
    if op == "%":
        if rn == 0.0:
            raise FormulaError(
                "modulo by zero", line=node.line, col=node.col,
            )
        return ln % rn
    if op == "**":
        return ln ** rn

    raise FormulaError(
        f"unknown binary operator {op!r}",
        line=node.line, col=node.col,
    )


def _eval_call(node: Call, ctx: EvaluationContext, state: _EvalState) -> Any:
    spec = FUNCTION_REGISTRY.get(node.callee)
    if spec is None:
        raise FormulaError(
            f"unknown function {node.callee!r}",
            line=node.line, col=node.col,
        )
    if not (spec.min_args <= len(node.args) <= spec.max_args):
        raise FormulaError(
            f"function {node.callee!r} expects {spec.min_args}..{spec.max_args} "
            f"args, got {len(node.args)}",
            line=node.line, col=node.col,
        )
    return spec.impl(node, ctx, state)
```

### Step 4: Confirm the new tests pass

```bash
uv run pytest packages/core/tests/formula/test_engine_arithmetic.py \
  packages/core/tests/formula/test_engine_comparisons.py \
  packages/core/tests/formula/test_engine_logical_ternary.py -v
```

Expected: everything passes.

### Step 5: Lint + commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): evaluator for arithmetic, comparison, logical, ternary"
```

---

## Task 5 — Function library (stateless math)

Goal: wire up `min`, `max`, `abs`, `round`, `mean`, `median`, `stddev`, `sum` into `FUNCTION_REGISTRY`. Each accepts a variadic list of numeric expressions.

**Files:**
- Extend: `packages/core/src/openlia/formula/engine.py`
- Create: `packages/core/tests/formula/test_engine_functions.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_engine_functions.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


@pytest.mark.parametrize(
    "src,expected",
    [
        ("min(1, 2, 3)", 1.0),
        ("max(1, 2, 3)", 3.0),
        ("abs(-5)", 5.0),
        ("abs(5)", 5.0),
        ("round(2.6)", 3.0),
        ("round(2.45, 1)", 2.5),
        ("mean(1, 2, 3, 4)", 2.5),
        ("median(1, 2, 3)", 2.0),
        ("median(1, 2, 3, 4)", 2.5),
        ("sum(1, 2, 3)", 6.0),
    ],
)
def test_math_functions(engine: FormulaEngine, src: str, expected: float):
    assert engine.evaluate(src, EvaluationContext()) == pytest.approx(expected)


def test_stddev_matches_sample_formula(engine: FormulaEngine):
    # Sample stddev of [2,4,4,4,5,5,7,9] == 2.138089935...
    value = engine.evaluate("stddev(2, 4, 4, 4, 5, 5, 7, 9)", EvaluationContext())
    assert value == pytest.approx(2.138089935, rel=1e-6)


def test_stddev_requires_at_least_two_values(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("stddev(1)", EvaluationContext())
    assert "at least two" in str(exc.value).lower() or "two" in str(exc.value).lower()


def test_unknown_function_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("fibonacci(5)", EvaluationContext())
    assert "fibonacci" in str(exc.value)


def test_wrong_arity_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("abs(1, 2)", EvaluationContext())
    assert "args" in str(exc.value)


def test_nonnumeric_argument_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate(
            "min(a, 1)", EvaluationContext(values={"a": "hi"})
        )
```

### Step 2: Fail

```bash
uv run pytest packages/core/tests/formula/test_engine_functions.py -v
```

Expected: every test fails with `unknown function ...`.

### Step 3: Implement the registry entries

Append to `engine.py`:

```python
# packages/core/src/openlia/formula/engine.py (append at bottom)
import statistics as _stats


def _eval_args_as_numbers(
    node: Call, ctx: EvaluationContext, state: _EvalState
) -> list[float]:
    out: list[float] = []
    for arg in node.args:
        val = _eval_node(arg, ctx, state)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise FormulaError(
                f"function {node.callee!r} requires numeric args, got "
                f"{type(val).__name__}",
                line=node.line,
                col=node.col,
            )
        out.append(float(val))
    return out


def _impl_min(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    return min(_eval_args_as_numbers(node, ctx, state))


def _impl_max(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    return max(_eval_args_as_numbers(node, ctx, state))


def _impl_abs(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return abs(args[0])


def _impl_round(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    if len(args) == 1:
        return float(round(args[0]))
    # Python's round accepts a negative ndigits; clamp to int.
    return float(round(args[0], int(args[1])))


def _impl_mean(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return sum(args) / len(args)


def _impl_median(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return float(_stats.median(args))


def _impl_stddev(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    if len(args) < 2:
        raise FormulaError(
            "stddev requires at least two values",
            line=node.line, col=node.col,
        )
    return float(_stats.stdev(args))


def _impl_sum(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return float(sum(args))


FUNCTION_REGISTRY.update(
    {
        "min": _FunctionSpec("min", 1, 64, False, _impl_min),
        "max": _FunctionSpec("max", 1, 64, False, _impl_max),
        "abs": _FunctionSpec("abs", 1, 1, False, _impl_abs),
        "round": _FunctionSpec("round", 1, 2, False, _impl_round),
        "mean": _FunctionSpec("mean", 1, 64, False, _impl_mean),
        "median": _FunctionSpec("median", 1, 64, False, _impl_median),
        "stddev": _FunctionSpec("stddev", 2, 64, False, _impl_stddev),
        "sum": _FunctionSpec("sum", 1, 64, False, _impl_sum),
    }
)
```

### Step 4: Confirm pass

```bash
uv run pytest packages/core/tests/formula/test_engine_functions.py -v
```

Expected: `16 passed` (10 parametrized + 6 direct).

### Step 5: Commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): add stateless math functions to registry"
```

---

## Task 6 — Historical variables + rolling / lag / pct_change / last

Goal: implement `metric[t-N]` syntax in the parser and the four history-aware functions (`last`, `pct_change`, `rolling_mean`, `lag`).

**Files:**
- Extend: `packages/core/src/openlia/formula/parser.py` (`_parse_history_index`)
- Extend: `packages/core/src/openlia/formula/engine.py` (`HistoricalVar` body + four new registry entries)
- Create: `packages/core/tests/formula/test_engine_history.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_engine_history.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx_with_history


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_historical_var_current_tick_is_zero_lag(engine: FormulaEngine):
    # `price[t-0]` is the last entry.
    history = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0]})
    assert engine.evaluate("price[t-0]", history) == 4.0


def test_historical_var_nonzero_lag(engine: FormulaEngine):
    history = ctx_with_history(history={"price": [10.0, 11.0, 12.0, 13.0]})
    assert engine.evaluate("price[t-1]", history) == 12.0
    assert engine.evaluate("price[t-3]", history) == 10.0


def test_historical_var_negative_lag_raises(engine: FormulaEngine):
    history = ctx_with_history(history={"price": [1.0]})
    with pytest.raises(FormulaError):
        engine.evaluate("price[t+1]", history)  # parser should not accept +
    with pytest.raises(FormulaError):
        engine.evaluate("price[t-10]", history)  # out of range


def test_historical_var_missing_series_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("ghost[t-0]", EvaluationContext())
    assert "ghost" in str(exc.value)


def test_last_returns_final_value(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0]})
    assert engine.evaluate("last(price)", h) == 3.0


def test_pct_change_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [100.0, 110.0, 121.0]})
    # pct_change(series, 1) -> (121-110)/110 * 100 = 10.0
    assert engine.evaluate("pct_change(price, 1)", h) == pytest.approx(10.0)
    # pct_change(series, 2) -> (121-100)/100 * 100 = 21.0
    assert engine.evaluate("pct_change(price, 2)", h) == pytest.approx(21.0)


def test_rolling_mean_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0, 5.0]})
    assert engine.evaluate("rolling_mean(price, 3)", h) == pytest.approx(4.0)


def test_rolling_mean_requires_enough_history(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0]})
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("rolling_mean(price, 5)", h)
    assert "history" in str(exc.value).lower()


def test_lag_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0]})
    # lag(price, 0) -> 4.0, lag(price, 1) -> 3.0, lag(price, 3) -> 1.0.
    assert engine.evaluate("lag(price, 0)", h) == 4.0
    assert engine.evaluate("lag(price, 1)", h) == 3.0
    assert engine.evaluate("lag(price, 3)", h) == 1.0


def test_pct_change_requires_positive_prior(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [0.0, 10.0]})
    with pytest.raises(FormulaError):
        engine.evaluate("pct_change(price, 1)", h)


def test_history_func_first_arg_must_be_variable(engine: FormulaEngine):
    # The parser enforces this so requirement extraction is straightforward.
    h = ctx_with_history(history={"price": [1.0, 2.0]})
    with pytest.raises(FormulaError):
        engine.evaluate("rolling_mean(1 + 2, 3)", h)
```

### Step 2: Fail

```bash
uv run pytest packages/core/tests/formula/test_engine_history.py -v
```

Expected: each test raises "historical variables land in Task 6" or unknown function.

### Step 3: Implement parser `[t-N]`

Replace `_Parser._parse_history_index` with the real body:

```python
# packages/core/src/openlia/formula/parser.py  (replace the placeholder)
    def _parse_history_index(self, ident: Token) -> Expression:
        # Already consumed the opening '['. Expect ``t - NUMBER`` then ']'.
        t_tok = self.peek
        if t_tok.kind is not TokenKind.IDENT or t_tok.value != "t":
            raise FormulaError(
                "history index must start with 't'",
                line=t_tok.line, col=t_tok.col,
            )
        self.advance()
        minus = self.peek
        if minus.kind is not TokenKind.MINUS:
            raise FormulaError(
                "history index must use '-' (e.g. 'price[t-3]')",
                line=minus.line, col=minus.col,
            )
        self.advance()
        number = self.peek
        if number.kind is not TokenKind.NUMBER:
            raise FormulaError(
                "history index requires an integer lag",
                line=number.line, col=number.col,
            )
        self.advance()
        lag_val = number.value
        if float(lag_val).is_integer() is False or lag_val < 0:
            raise FormulaError(
                "history lag must be a non-negative integer",
                line=number.line, col=number.col,
            )
        self.expect(TokenKind.RBRACKET, "']'")
        return HistoricalVar(
            name=ident.value, lag=int(lag_val), line=ident.line, col=ident.col,
        )
```

### Step 4: Implement `HistoricalVar` evaluation + history-aware functions

Replace the `HistoricalVar` branch in `_eval_node`:

```python
    if isinstance(node, HistoricalVar):
        series = ctx.history.get(node.name)
        if series is None:
            raise FormulaError(
                f"undefined historical series {node.name!r}",
                line=node.line, col=node.col,
            )
        if node.lag >= len(series):
            raise FormulaError(
                f"history for {node.name!r} needs >= {node.lag + 1} entries, "
                f"got {len(series)}",
                line=node.line, col=node.col,
            )
        return float(series[-1 - node.lag])
```

And append four new implementations:

```python
# packages/core/src/openlia/formula/engine.py (append)

def _history_arg(
    node: Call, ctx: EvaluationContext, index: int = 0
) -> tuple[str, list[float]]:
    if not node.args or not isinstance(node.args[index], Var):
        raise FormulaError(
            f"function {node.callee!r} requires a bare variable as "
            f"argument {index + 1}",
            line=node.line, col=node.col,
        )
    name = node.args[index].name  # type: ignore[attr-defined]
    series = ctx.history.get(name)
    if series is None:
        raise FormulaError(
            f"undefined historical series {name!r}",
            line=node.line, col=node.col,
        )
    return name, list(series)


def _int_arg(
    node: Call, ctx: EvaluationContext, state: _EvalState, index: int
) -> int:
    val = _eval_node(node.args[index], ctx, state)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise FormulaError(
            f"function {node.callee!r} requires an integer argument",
            line=node.line, col=node.col,
        )
    if float(val).is_integer() is False or val < 0:
        raise FormulaError(
            f"function {node.callee!r} requires a non-negative integer",
            line=node.line, col=node.col,
        )
    return int(val)


def _impl_last(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    if len(node.args) == 1:
        _, series = _history_arg(node, ctx)
        if not series:
            raise FormulaError(
                f"last({node.args[0]}) requires non-empty history",
                line=node.line, col=node.col,
            )
        return float(series[-1])
    # last(series, n) returns the mean of the last n values (handy shorthand).
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        raise FormulaError(
            f"last({name}, {n}) requires history of at least {n} entries",
            line=node.line, col=node.col,
        )
    return float(series[-n])


def _impl_pct_change(
    node: Call, ctx: EvaluationContext, state: _EvalState
) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n <= 0 or n >= len(series):
        raise FormulaError(
            f"pct_change({name}, {n}) requires history of at least {n + 1} entries",
            line=node.line, col=node.col,
        )
    previous = series[-1 - n]
    current = series[-1]
    if previous == 0:
        raise FormulaError(
            f"pct_change({name}, {n}): prior value is zero",
            line=node.line, col=node.col,
        )
    return (current - previous) / previous * 100.0


def _impl_rolling_mean(
    node: Call, ctx: EvaluationContext, state: _EvalState
) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        raise FormulaError(
            f"rolling_mean({name}, {n}): history has only {len(series)} entries",
            line=node.line, col=node.col,
        )
    window = series[-n:]
    return sum(window) / float(n)


def _impl_lag(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n >= len(series):
        raise FormulaError(
            f"lag({name}, {n}): history has only {len(series)} entries",
            line=node.line, col=node.col,
        )
    return float(series[-1 - n])


FUNCTION_REGISTRY.update(
    {
        "last": _FunctionSpec("last", 1, 2, True, _impl_last),
        "pct_change": _FunctionSpec("pct_change", 2, 2, True, _impl_pct_change),
        "rolling_mean": _FunctionSpec("rolling_mean", 2, 2, True, _impl_rolling_mean),
        "lag": _FunctionSpec("lag", 2, 2, True, _impl_lag),
    }
)
```

### Step 5: Run and confirm

```bash
uv run pytest packages/core/tests/formula/test_engine_history.py -v
```

Expected: every test passes.

Also re-run the earlier suites to confirm no regressions:

```bash
uv run pytest packages/core/tests/formula -v
```

### Step 6: Commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): history lookup, rolling/lag/pct_change/last"
```

---

## Task 7 — Safety limits (depth, node count, step counter)

Goal: enforce `MAX_AST_DEPTH`, `MAX_NODE_COUNT`, `MAX_EVAL_STEPS` and prove each one fires.

**Files:**
- Extend: `packages/core/src/openlia/formula/parser.py` (count nodes, check depth)
- Extend: `packages/core/src/openlia/formula/engine.py` (already has step counter)
- Create: `packages/core/tests/formula/test_engine_safety.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_engine_safety.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.formula.engine import MAX_AST_DEPTH, MAX_EVAL_STEPS, MAX_NODE_COUNT
from openlia.formula.parser import parse


def test_max_ast_depth_is_enforced_at_parse_time():
    # Build a deeply-nested expression that exceeds the depth cap.
    depth = MAX_AST_DEPTH + 2
    source = "(" * depth + "1" + ")" * depth
    with pytest.raises(FormulaError) as exc:
        parse(source)
    assert "depth" in str(exc.value).lower()


def test_max_node_count_is_enforced_at_parse_time():
    # A long chain of + operations easily exceeds the node cap.
    terms = ["1"] * (MAX_NODE_COUNT + 5)
    source = " + ".join(terms)
    with pytest.raises(FormulaError) as exc:
        parse(source)
    assert "node" in str(exc.value).lower() or "complex" in str(exc.value).lower()


def test_max_eval_steps_is_enforced_at_runtime():
    # Construct a tiny AST but evaluate it inside a manually-invoked loop.
    # The step counter fires if a single call recurses past the cap.
    engine = FormulaEngine()
    # Chain many ternaries to exceed the step count. Each ternary adds ~3 steps.
    terms = "0"
    for _ in range(MAX_EVAL_STEPS // 2 + 10):
        terms = f"(1 if true else {terms}) + 0"
    with pytest.raises(FormulaError) as exc:
        engine.evaluate(terms, EvaluationContext())
    assert "step" in str(exc.value).lower()


def test_safety_limits_are_public_constants():
    assert isinstance(MAX_AST_DEPTH, int) and MAX_AST_DEPTH > 0
    assert isinstance(MAX_NODE_COUNT, int) and MAX_NODE_COUNT > 0
    assert isinstance(MAX_EVAL_STEPS, int) and MAX_EVAL_STEPS > 0
```

### Step 2: Fail

```bash
uv run pytest packages/core/tests/formula/test_engine_safety.py -v
```

Expected: depth/node-count tests fail because the parser does not yet enforce them.

### Step 3: Implement caps in the parser

Add a counter + depth tracker to `_Parser`:

```python
# packages/core/src/openlia/formula/parser.py  (modifications)

# Import at top:
from openlia.formula.engine import FormulaError, MAX_AST_DEPTH, MAX_NODE_COUNT


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.node_count = 0
        self.depth = 0

    def _enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_AST_DEPTH:
            t = self.peek
            raise FormulaError(
                f"expression exceeds max depth of {MAX_AST_DEPTH}",
                line=t.line, col=t.col,
            )

    def _exit(self) -> None:
        self.depth -= 1

    def _count(self) -> None:
        self.node_count += 1
        if self.node_count > MAX_NODE_COUNT:
            t = self.peek
            raise FormulaError(
                f"expression exceeds max node count of {MAX_NODE_COUNT}",
                line=t.line, col=t.col,
            )
```

Wrap every production with `_enter()` / `_exit()`. Increment `_count()` in every node constructor path:

```python
    def ternary(self) -> Expression:
        self._enter()
        try:
            left = self.or_expr()
            if self.accept(TokenKind.IF):
                cond = self.or_expr()
                self.expect(TokenKind.ELSE, "'else'")
                other = self.ternary()
                self._count()
                return IfElse(
                    condition=cond, then_branch=left, else_branch=other,
                    line=left.line, col=left.col,
                )
            return left
        finally:
            self._exit()

    def or_expr(self) -> Expression:
        self._enter()
        try:
            node = self.and_expr()
            while self.accept(TokenKind.OR):
                right = self.and_expr()
                self._count()
                node = BinaryOp("or", node, right, line=node.line, col=node.col)
            return node
        finally:
            self._exit()

    def and_expr(self) -> Expression:
        self._enter()
        try:
            node = self.not_expr()
            while self.accept(TokenKind.AND):
                right = self.not_expr()
                self._count()
                node = BinaryOp("and", node, right, line=node.line, col=node.col)
            return node
        finally:
            self._exit()

    def not_expr(self) -> Expression:
        self._enter()
        try:
            if self.accept(TokenKind.NOT):
                operand = self.not_expr()
                self._count()
                return UnaryOp("not", operand, line=operand.line, col=operand.col)
            return self.comparison()
        finally:
            self._exit()

    def comparison(self) -> Expression:
        self._enter()
        try:
            node = self.additive()
            while self.peek.kind in _COMPARISON_KINDS:
                op_tok = self.advance()
                right = self.additive()
                self._count()
                node = BinaryOp(
                    _COMPARISON_KINDS[op_tok.kind], node, right,
                    line=node.line, col=node.col,
                )
            return node
        finally:
            self._exit()

    def additive(self) -> Expression:
        self._enter()
        try:
            node = self.multiplicative()
            while True:
                if self.accept(TokenKind.PLUS):
                    right = self.multiplicative()
                    self._count()
                    node = BinaryOp("+", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.MINUS):
                    right = self.multiplicative()
                    self._count()
                    node = BinaryOp("-", node, right, line=node.line, col=node.col)
                else:
                    return node
        finally:
            self._exit()

    def multiplicative(self) -> Expression:
        self._enter()
        try:
            node = self.unary()
            while True:
                if self.accept(TokenKind.STAR):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("*", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.SLASH):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("/", node, right, line=node.line, col=node.col)
                elif self.accept(TokenKind.PERCENT):
                    right = self.unary()
                    self._count()
                    node = BinaryOp("%", node, right, line=node.line, col=node.col)
                else:
                    return node
        finally:
            self._exit()

    def unary(self) -> Expression:
        self._enter()
        try:
            if self.accept(TokenKind.MINUS):
                operand = self.unary()
                self._count()
                return UnaryOp("-", operand, line=operand.line, col=operand.col)
            return self.power()
        finally:
            self._exit()

    def power(self) -> Expression:
        self._enter()
        try:
            base = self.primary()
            if self.accept(TokenKind.DOUBLESTAR):
                exponent = self.unary()
                self._count()
                return BinaryOp("**", base, exponent, line=base.line, col=base.col)
            return base
        finally:
            self._exit()

    def primary(self) -> Expression:
        self._enter()
        try:
            t = self.peek
            if t.kind is TokenKind.NUMBER:
                self.advance()
                self._count()
                return Literal(value=t.value, line=t.line, col=t.col)
            if t.kind is TokenKind.TRUE:
                self.advance()
                self._count()
                return Literal(value=True, line=t.line, col=t.col)
            if t.kind is TokenKind.FALSE:
                self.advance()
                self._count()
                return Literal(value=False, line=t.line, col=t.col)
            if t.kind is TokenKind.LPAREN:
                self.advance()
                node = self.ternary()
                self.expect(TokenKind.RPAREN, "')'")
                return node
            if t.kind is TokenKind.IDENT:
                self.advance()
                if self.accept(TokenKind.LPAREN):
                    args: list[Expression] = []
                    if self.peek.kind is not TokenKind.RPAREN:
                        args.append(self.ternary())
                        while self.accept(TokenKind.COMMA):
                            args.append(self.ternary())
                    self.expect(TokenKind.RPAREN, "')'")
                    self._count()
                    return Call(callee=t.value, args=args, line=t.line, col=t.col)
                if self.accept(TokenKind.LBRACKET):
                    self._count()
                    return self._parse_history_index(t)
                self._count()
                return Var(name=t.value, line=t.line, col=t.col)

            raise FormulaError(
                f"expected expression but found {t.kind.name}",
                line=t.line, col=t.col,
            )
        finally:
            self._exit()
```

### Step 4: Pass

```bash
uv run pytest packages/core/tests/formula/test_engine_safety.py -v
uv run pytest packages/core/tests/formula -v
```

Expected: safety tests pass; earlier tests continue to pass.

### Step 5: Commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): enforce depth, node-count, and step caps"
```

---

## Task 8 — Requirement extraction

Goal: walk a parsed AST and return a sorted list of `RequirementRef(name, max_lag)` so scheduler / wiring code (Plans 18 and 19) knows which data tools to invoke, and how many historical bars to provide.

**Files:**
- Overwrite: `packages/core/src/openlia/formula/requirements.py`
- Create: `packages/core/tests/formula/test_requirements.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_requirements.py
from __future__ import annotations

import pytest

from openlia.formula import RequirementRef, extract_requirements


def test_scalar_only_returns_single_ref_with_zero_lag():
    refs = extract_requirements("price > 85")
    assert refs == [RequirementRef(name="price", max_lag=0)]


def test_multiple_scalars_are_sorted_unique():
    refs = extract_requirements("ma50 > ma200 and ma200 > 0")
    assert refs == [
        RequirementRef(name="ma200", max_lag=0),
        RequirementRef(name="ma50", max_lag=0),
    ]


def test_historical_var_records_max_lag():
    refs = extract_requirements("price[t-5] + price[t-1]")
    assert refs == [RequirementRef(name="price", max_lag=5)]


def test_rolling_mean_records_lookback_minus_one():
    # rolling_mean(price, 20) needs the last 20 values -> max_lag == 19.
    refs = extract_requirements("rolling_mean(price, 20)")
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_pct_change_records_lookback():
    # pct_change(price, 5) needs entries at lag 0 and lag 5 -> max_lag == 5.
    refs = extract_requirements("pct_change(price, 5)")
    assert refs == [RequirementRef(name="price", max_lag=5)]


def test_lag_records_lookback():
    refs = extract_requirements("lag(cpi, 12)")
    assert refs == [RequirementRef(name="cpi", max_lag=12)]


def test_last_single_arg_zero_lag():
    refs = extract_requirements("last(price)")
    assert refs == [RequirementRef(name="price", max_lag=0)]


def test_last_n_arg_records_lookback_minus_one():
    refs = extract_requirements("last(price, 12)")
    assert refs == [RequirementRef(name="price", max_lag=11)]


def test_maximum_lag_wins_across_references():
    refs = extract_requirements("price[t-3] + rolling_mean(price, 20)")
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_function_only_references_are_counted():
    refs = extract_requirements("mean(1, 2, 3)")
    assert refs == []


def test_parse_error_propagates():
    from openlia.formula import FormulaError

    with pytest.raises(FormulaError):
        extract_requirements("1 + ")
```

### Step 2: Fail

```bash
uv run pytest packages/core/tests/formula/test_requirements.py -v
```

Expected: every test errors with `NotImplementedError: extract_requirements lands in Task 8`.

### Step 3: Implement

```python
# packages/core/src/openlia/formula/requirements.py
"""Static requirement extraction — parse once, walk the AST, return refs.

Consumers (Plan 18 / Plan 19) feed the returned refs into the data-provider
manifest resolver so scheduled jobs fetch exactly the series and history
depth the formulas need.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    HistoricalVar,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


@dataclass(frozen=True, slots=True)
class RequirementRef:
    name: str
    max_lag: int = 0


# How each history-aware function maps its lookback to max_lag.
# Keys match FUNCTION_REGISTRY names exactly.
_HISTORY_FUNCTIONS: dict[str, int] = {
    # "last": handled separately (1-arg vs 2-arg).
    "pct_change": 0,
    "rolling_mean": -1,  # max_lag = n - 1 (needs n trailing values).
    "lag": 0,
}


def extract_requirements(source: str | Expression) -> list[RequirementRef]:
    tree = parse(source) if isinstance(source, str) else source
    acc: dict[str, int] = {}
    _walk(tree, acc)
    return [RequirementRef(name=name, max_lag=lag) for name, lag in sorted(acc.items())]


def _record(acc: dict[str, int], name: str, lag: int) -> None:
    prior = acc.get(name, -1)
    if lag > prior:
        acc[name] = lag


def _literal_int(node: Expression) -> int | None:
    if isinstance(node, Literal) and isinstance(node.value, (int, float)):
        val = float(node.value)
        if val.is_integer() and val >= 0:
            return int(val)
    return None


def _walk(node: Expression, acc: dict[str, int]) -> None:
    if isinstance(node, Literal):
        return

    if isinstance(node, Var):
        _record(acc, node.name, 0)
        return

    if isinstance(node, HistoricalVar):
        _record(acc, node.name, node.lag)
        return

    if isinstance(node, UnaryOp):
        _walk(node.operand, acc)
        return

    if isinstance(node, BinaryOp):
        _walk(node.left, acc)
        _walk(node.right, acc)
        return

    if isinstance(node, IfElse):
        _walk(node.condition, acc)
        _walk(node.then_branch, acc)
        _walk(node.else_branch, acc)
        return

    if isinstance(node, Call):
        _walk_call(node, acc)
        return

    # Unknown node type — ignore defensively.
    return


def _walk_call(node: Call, acc: dict[str, int]) -> None:
    # If the first argument is a bare Var and the function has a declared
    # lookback, credit the max_lag to that series. Otherwise, walk each arg.
    if node.callee == "last" and len(node.args) >= 1 and isinstance(node.args[0], Var):
        name = node.args[0].name
        if len(node.args) == 2:
            n = _literal_int(node.args[1])
            if n is not None and n > 0:
                _record(acc, name, n - 1)
                return
        _record(acc, name, 0)
        return

    if (
        node.callee in _HISTORY_FUNCTIONS
        and len(node.args) >= 2
        and isinstance(node.args[0], Var)
    ):
        name = node.args[0].name
        n = _literal_int(node.args[1])
        if n is None:
            _record(acc, name, 0)
            for arg in node.args:
                _walk(arg, acc)
            return
        offset = _HISTORY_FUNCTIONS[node.callee]
        max_lag = max(0, n + offset)
        _record(acc, name, max_lag)
        return

    # Fall-through: stateless functions (min/max/abs/...), or calls whose first
    # arg isn't a bare Var. Walk every argument to collect any nested refs.
    for arg in node.args:
        _walk(arg, acc)
```

### Step 4: Pass

```bash
uv run pytest packages/core/tests/formula/test_requirements.py -v
```

Expected: all tests pass.

### Step 5: Commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "feat(formula): extract_requirements static AST walk"
```

---

## Task 9 — Error types with position info

Goal: explicit assertions that every error class carries `line` / `col`, that parse errors surface with positions, and that evaluation errors carry the offending node's position.

**Files:**
- Create: `packages/core/tests/formula/test_errors.py`
- (No production changes; Tasks 2 and 4 already emit positions. This task locks the contract.)

### Step 1: Failing test

```python
# packages/core/tests/formula/test_errors.py
from __future__ import annotations

import pytest

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError, parse

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_parse_error_has_line_and_col():
    with pytest.raises(FormulaError) as exc:
        parse("1 + ")
    assert exc.value.line is not None
    assert exc.value.col is not None
    assert f"line {exc.value.line}" in str(exc.value)
    assert f"col {exc.value.col}" in str(exc.value)


def test_lex_error_surfaces_as_formula_error():
    with pytest.raises(FormulaError) as exc:
        parse("1 @ 2")
    assert exc.value.col == 3


def test_undefined_variable_error_carries_position(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("5 + missing_var", EvaluationContext())
    assert "missing_var" in str(exc.value)
    # Var position was populated in the parser.
    assert exc.value.line == 1


def test_type_error_carries_op_and_position(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("1 + name", ctx(name="x"))
    msg = str(exc.value)
    assert "numeric" in msg
    assert "+" in msg


def test_division_by_zero_carries_position(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("5 / 0", EvaluationContext())
    assert "division" in str(exc.value).lower()
    assert exc.value.line == 1


def test_history_error_mentions_series_name_and_size(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate(
            "price[t-10]",
            EvaluationContext(history={"price": [1.0, 2.0]}),
        )
    assert "price" in str(exc.value)
    assert "11" in str(exc.value)  # needs >= 11 entries
```

### Step 2: Run

```bash
uv run pytest packages/core/tests/formula/test_errors.py -v
```

If any assertion fails, patch the corresponding producer (`parse`, `_eval_node`, `_eval_binary`) to fill in `line=node.line, col=node.col` on the `FormulaError` it raises. The expected outcome after patches: all six tests pass.

### Step 3: Commit

```bash
uv run ruff check packages/core/src/openlia/formula packages/core/tests/formula
uv run ruff format packages/core/src/openlia/formula packages/core/tests/formula
git add packages/core/src/openlia/formula packages/core/tests/formula
git commit -m "test(formula): lock error position contract"
```

---

## Task 10 — Integration test (PT threshold + MR metric)

Goal: replace the skipped stub from Task 0 with two end-to-end assertions — one modelled on a Panic Thermometer threshold rule, one on a Macro Research metric formula.

**Files:**
- Overwrite: `packages/core/tests/formula/test_integration.py`

### Step 1: Overwrite the stub

```python
# packages/core/tests/formula/test_integration.py
"""End-to-end smoke tests for Plan 17 against shapes Plans 18 and 19 will use."""

from __future__ import annotations

import pytest

from openlia.formula import (
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    RequirementRef,
    extract_requirements,
    parse,
)


def test_public_api_exports():
    # Names that Plans 18 and 19 depend on — locked.
    from openlia.formula import (  # noqa: F401
        EvaluationContext,
        Expression,
        FormulaEngine,
        FormulaError,
        RequirementRef,
        extract_requirements,
        parse,
    )


def test_panic_thermometer_like_threshold_rule():
    """Mirrors a PT red-status rule: oil streak above MA200 times a buffer."""
    engine = FormulaEngine()
    # A simplified form (the real spec injects `streak_days`; here we test
    # the building blocks).
    source = (
        "price > rolling_mean(price, 20) * 1.15 and pct_change(price, 5) > 3.0"
    )

    # Canned 25-bar series ending with an upward break-out.
    history = {
        "price": [
            70.0, 70.5, 70.3, 70.8, 71.0,
            71.5, 72.0, 72.5, 73.0, 73.2,
            73.4, 73.8, 74.0, 74.5, 75.0,
            75.2, 75.5, 76.0, 76.4, 76.8,
            77.0, 82.0, 86.0, 88.0, 91.0,
        ]
    }
    ctx = EvaluationContext(
        values={"price": history["price"][-1]}, history=history,
    )

    assert engine.evaluate(source, ctx) is True

    # Requirement extraction yields a single series with the larger lookback.
    refs = extract_requirements(source)
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_macro_research_like_metric_formula():
    """Mirrors an MR T2 metric: weighted combination of sub-indicators."""
    engine = FormulaEngine()
    # Weighted mean with a guard for missing data.
    source = (
        "(debt_to_gdp * 0.5 + credit_growth * 0.3 + short_rate * 0.2) "
        "if debt_to_gdp > 0 else 0"
    )
    ctx = EvaluationContext(
        values={
            "debt_to_gdp": 120.0,
            "credit_growth": 4.5,
            "short_rate": 1.75,
        }
    )
    value = engine.evaluate(source, ctx)
    assert value == pytest.approx(61.7, rel=1e-3)

    refs = extract_requirements(source)
    assert refs == [
        RequirementRef(name="credit_growth", max_lag=0),
        RequirementRef(name="debt_to_gdp", max_lag=0),
        RequirementRef(name="short_rate", max_lag=0),
    ]


def test_accepts_prebuilt_ast_for_hot_path():
    engine = FormulaEngine()
    tree = parse("price > 100 and not recession")
    ctx = EvaluationContext(values={"price": 125.0, "recession": False})
    assert engine.evaluate(tree, ctx) is True


def test_error_propagation_across_parse_and_eval():
    engine = FormulaEngine()
    # Unknown identifier surfaces as FormulaError at eval time, with position.
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("price > threshold", EvaluationContext(values={"price": 1.0}))
    assert "threshold" in str(exc.value)
    assert exc.value.line == 1
```

### Step 2: Run

```bash
uv run pytest packages/core/tests/formula/test_integration.py -v
```

Expected: `4 passed`.

### Step 3: Commit

```bash
git add packages/core/tests/formula/test_integration.py
git commit -m "test(formula): PT-like threshold + MR-like metric integration"
```

---

## Task 11 — Re-exports and README status update

Goal: surface the formula engine through `openlia.__init__` so casual callers can write `from openlia import FormulaEngine`, and flip the status row in `planning/implementation-plans/README.md` from "Not started" to "Draft"/"Done" when executed.

**Files:**
- Edit: `packages/core/src/openlia/__init__.py`
- Edit: `planning/implementation-plans/README.md`
- Create: `packages/core/tests/formula/test_package_exports.py`

### Step 1: Failing test

```python
# packages/core/tests/formula/test_package_exports.py
from __future__ import annotations


def test_openlia_top_level_exports_formula_symbols():
    import openlia

    names = {
        "FormulaEngine",
        "EvaluationContext",
        "FormulaError",
        "RequirementRef",
        "extract_requirements",
        "parse",
        "Expression",
    }
    for name in names:
        assert hasattr(openlia, name), name
```

### Step 2: Fail

```bash
uv run pytest packages/core/tests/formula/test_package_exports.py -v
```

Expected: AssertionError for each name.

### Step 3: Update `openlia/__init__.py`

```python
# packages/core/src/openlia/__init__.py
"""OpenLIA core library — pure Python, zero web dependencies."""

from openlia.formula import (
    EvaluationContext,
    Expression,
    FormulaEngine,
    FormulaError,
    RequirementRef,
    extract_requirements,
    parse,
)

__version__ = "0.1.0"

__all__ = [
    "EvaluationContext",
    "Expression",
    "FormulaEngine",
    "FormulaError",
    "RequirementRef",
    "__version__",
    "extract_requirements",
    "parse",
]
```

### Step 4: Flip status row

In `planning/implementation-plans/README.md`, change:

```
| 17 | 6 | Formula engine DSL | Not started | — |
```

to:

```
| 17 | 6 | Formula engine DSL | Draft | `2026-04-23-phase-17-formula-engine.md` |
```

(Update to `Done (YYYY-MM-DD)` only after the PR merges — do not flip to Done in this task.)

### Step 5: Run the full formula suite

```bash
uv run pytest packages/core/tests/formula -v
```

Expected: every test in every file passes.

### Step 6: Aggregate suite + lint

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Expected: `All checks passed!` + the aggregate test run green. If anything outside the formula tree broke, stop and investigate before committing.

### Step 7: Commit

```bash
git add packages/core/src/openlia/__init__.py packages/core/tests/formula planning/implementation-plans/README.md
git commit -m "feat(formula): re-export from openlia + flip status to Draft"
```

---

## Acceptance Criteria

Before opening the PR:

1. **Canonical imports work exactly as specified.**
   ```python
   from openlia.formula.engine       import FormulaEngine, FormulaError, EvaluationContext
   from openlia.formula.parser       import parse, Expression
   from openlia.formula.requirements import extract_requirements, RequirementRef
   ```
   Any rename breaks Plans 18 and 19 — do not merge until all three succeed.

2. **Aggregate suite green.** `uv run pytest -q` at the repo root passes with no new failures outside the `formula` tree.

3. **Lint + format clean.** `uv run ruff check .` and `uv run ruff format --check .` both pass.

4. **No new runtime dependencies.** `packages/core/pyproject.toml` is unchanged. The engine uses only stdlib + Pydantic (already shipped) + dataclasses.

5. **Safety caps fire.** The three tests in `test_engine_safety.py` prove that depth, node count, and evaluation steps each raise `FormulaError` with a helpful message when exceeded.

6. **Requirement extraction is deterministic.** `extract_requirements(...)` returns alphabetically sorted refs with the maximum observed lag per series.

7. **Integration test pins the downstream contract.** `test_integration.py` exercises a PT-like threshold rule and an MR-like metric formula end-to-end; both depend on the engine's documented behaviour.

8. **README row flipped to `Draft`**, with the plan filename recorded. A follow-up PR flips to `Done` when the implementation PR merges.

9. **One commit per task** with the messages above. Commits remain in order so bisect works cleanly.

---

## Out-of-scope Notes (for downstream plans)

The following features belong to Plan 18 / Plan 19 and must not leak into Plan 17:

- **String / event side-channels.** Plan 18's "Fed Language Tracker" and "Diplomatic Progress" panels inject pre-computed booleans into `EvaluationContext.values`. The engine treats them as scalars; it does not do text matching.
- **Derived scalars (`ma200`, `atr_14`, `streak_days`).** Those are caller-side conveniences per the design spec — Plan 18 computes them once per fetch and injects them into `values`. The engine does not know about "price" as a distinguished series.
- **Null semantics.** The design spec allows `null` to propagate through comparisons as `false`. v1 of the engine (this plan) does not support `null` — callers that need null-safe rules must guard at the call site (`price > 0 and ...`). Adding `null` is a deliberate future extension with its own spec review.
- **`evaluate_ruleset` / `PanelResult`.** These higher-level constructs belong to Plan 18's panel wiring. Plan 17 stops at single-formula evaluation.
- **HTTP endpoints (`/formula/parse`, `/formula/test`, `/ruleset/preview`).** Plans 18 and 19 own the server-side endpoints. Plan 17 is core-only.

If Plan 18 or Plan 19 needs additional primitives (e.g., `cross_above`, `percentile`, `slope`, `consecutive`, `days_since`), add them as a targeted Plan 17 follow-up with new tests — do not smuggle them into the department plans.
