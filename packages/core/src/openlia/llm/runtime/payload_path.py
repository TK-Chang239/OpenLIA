"""Path parser and applier for read_payload.

Five forms:
  - `key` — top-level dict access.
  - `key.subkey` — nested dict access.
  - `rows[i]` — array index. Negative indices allowed.
  - `rows[i:j]` — array slice.
  - `rows.column` — list-of-dicts column projection (returns list of values).

Composable: `rows[0:5].revenue` slices then projects; `data.rows[-1]`
navigates then indexes.

Two distinct error types:
  PathParseError — syntax is malformed.
  PathResolveError — syntax is valid but doesn't fit the payload.

Pure function module. No JSONPath, no filters, no recursive descents.
"""

from __future__ import annotations

import re
from typing import Any


class PathParseError(ValueError):
    pass


class PathResolveError(ValueError):
    pass


_TOKEN_RE = re.compile(
    r"""
    (?P<name>[A-Za-z0-9_][A-Za-z0-9_\-]*)   # bareword: alnum/_/- interior;
                                            # leading digit permits date keys
                                            # like 2026-01-31 and numeric keys
                                            # like outstandingShares.annual.0;
                                            # leading hyphen is still rejected
                                            # so it cannot shadow [-idx] syntax
    | \[ \s* " (?P<dqname>[^"]*) " \s* \]   # ["any key"] — verbatim inner
    | \[ \s* ' (?P<sqname>[^']*) ' \s* \]   # ['any key'] — verbatim inner
    | \[ \s* (?P<lo>-?\d+)? \s* : \s* (?P<hi>-?\d+)? \s* \]   # [lo:hi] slice
    | \[ \s* (?P<idx>-?\d+) \s* \]          # [i] or [-i]
    | (?P<dot>\.)
    """,
    re.VERBOSE,
)


def apply_path(payload: Any, path: str | None) -> Any:
    """Resolve `path` against `payload`.

    Returns payload as-is when path is None or empty.
    Raises PathParseError on malformed syntax.
    Raises PathResolveError when path is valid but resolution fails.
    """
    if path is None or path == "":
        return payload
    path = _normalize_path(path)
    if path == "":
        return payload
    tokens = _tokenize(path)
    result = payload
    for kind, value in tokens:
        result = _step(result, kind, value, path)
    return result


_BRACKET_STRING_RE = re.compile(r"""\[\s*['"]([A-Za-z0-9_][A-Za-z0-9_\-]*)['"]\s*\]""")


def _normalize_path(path: str) -> str:
    """Silently fix common bad forms before parsing.

    Models frequently emit JSONPath-flavored or bracket-string syntax.
    We rewrite mechanical mistakes to the canonical 5-form grammar so
    they parse instead of failing. Predicate filters are *not* rewritten
    — they change semantics and should error loudly.
    """
    s = path.strip()
    # Strip JSONPath root: "$.a" -> "a", "$a" -> "a", "$" -> "".
    if s.startswith("$"):
        s = s[1:]
        if s.startswith("."):
            s = s[1:]
    # ['key'] / ["key"] -> .key
    s = _BRACKET_STRING_RE.sub(r".\1", s)
    # [*] -> "" (wildcard reduces to column-projection via following dot)
    s = re.sub(r"\[\s*\*\s*\]", "", s)
    # Collapse runs of dots: "a..b" -> "a.b".
    s = re.sub(r"\.{2,}", ".", s)
    # A leading dot from the bracket-string rewrite is just a separator artefact.
    s = s.lstrip(".")
    # Trailing dot is meaningless.
    s = s.rstrip(".")
    return s


def _tokenize(path: str) -> list[tuple[str, Any]]:
    """Return (kind, value) step tokens; dots consumed as separators.

    Kinds: "name", "index", "slice".
    Raises PathParseError on unrecognized characters or leading dot.
    """
    if path.startswith("."):
        raise PathParseError(f"Invalid path syntax: {path!r}")

    tokens: list[tuple[str, Any]] = []
    pos = 0
    prev_kind: str | None = None

    while pos < len(path):
        m = _TOKEN_RE.match(path, pos)
        if m is None:
            raise PathParseError(f"Invalid path syntax: {path!r}")
        pos = m.end()

        if m.group("dot"):
            if prev_kind is None:
                raise PathParseError(f"Invalid path syntax: {path!r}")
            # Separator — consumed, no token emitted.
            prev_kind = "dot"
            continue

        if m.group("name"):
            tokens.append(("name", m.group("name")))
            prev_kind = "name"
        elif m.group("dqname") is not None:
            tokens.append(("name", m.group("dqname")))
            prev_kind = "name"
        elif m.group("sqname") is not None:
            tokens.append(("name", m.group("sqname")))
            prev_kind = "name"
        elif m.group("idx") is not None:
            tokens.append(("index", int(m.group("idx"))))
            prev_kind = "index"
        else:
            # slice
            lo = int(m.group("lo")) if m.group("lo") is not None else None
            hi = int(m.group("hi")) if m.group("hi") is not None else None
            tokens.append(("slice", (lo, hi)))
            prev_kind = "slice"

    if not tokens:
        raise PathParseError(f"Invalid path syntax: {path!r}")

    return tokens


def _step(value: Any, kind: str, key: Any, path: str) -> Any:
    """Apply one resolution step."""
    if kind == "name":
        if isinstance(value, dict):
            if key not in value:
                available = list(value.keys())[:10]
                raise PathResolveError(f"Key {key!r} not found; available keys: {available}")
            return value[key]
        if isinstance(value, list):
            # Column projection over list-of-dicts.
            return [row[key] for row in value if isinstance(row, dict) and key in row]
        raise PathResolveError(
            f"Cannot apply path step {kind}={key!r} to value of type {type(value).__name__}"
        )

    if kind == "index":
        if not isinstance(value, list):
            raise PathResolveError(
                f"Cannot apply path step {kind}={key!r} to value of type {type(value).__name__}"
            )
        if key >= len(value) or key < -len(value):
            raise PathResolveError(f"Index {key} out of bounds for list of length {len(value)}")
        return value[key]

    if kind == "slice":
        if not isinstance(value, list):
            raise PathResolveError(
                f"Cannot apply path step {kind}={key!r} to value of type {type(value).__name__}"
            )
        lo, hi = key
        return value[lo:hi]

    raise PathResolveError(
        f"Cannot apply path step {kind}={key!r} to value of type {type(value).__name__}"
    )
