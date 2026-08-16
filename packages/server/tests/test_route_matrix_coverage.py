"""Drift guard for the route-authorization matrix.

Enumerates the routers mounted by ``create_app()`` and asserts each router
prefix appears (as a substring) in
``planning/implementation-plans/route-authorization-matrix.md``. This keeps the
matrix from silently falling behind the live FastAPI surface: a brand-new
top-level router that no one documents fails this test.

The check is intentionally a simple substring test on router *prefixes*, not a
full per-endpoint diff — the matrix is prose, and a stricter check would be
brittle. Departments are checked at their two-segment sub-prefix because that
is where routers proliferate.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# FastAPI built-ins and app-internal endpoints that are not user-facing routers.
_IGNORED_FIRST_SEGMENTS = {"docs", "redoc", "openapi.json", "_debug"}


def _matrix_path() -> Path:
    # tests/ -> server -> packages -> repo root
    root = Path(__file__).resolve().parents[3]
    return root / "planning" / "implementation-plans" / "route-authorization-matrix.md"


def _router_prefixes(app) -> set[str]:  # type: ignore[no-untyped-def]
    prefixes: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or "{full_path" in path:
            continue
        segments = [s for s in path.split("/") if s]
        if not segments:
            continue
        first = segments[0]
        if first in _IGNORED_FIRST_SEGMENTS:
            continue
        # ``/departments`` hosts one router per department, so check the
        # two-segment sub-prefix there and require each to be documented.
        # Other trees (``/settings``, ``/admin``) mount their sub-routers under
        # one first segment, so a single-segment check is the right boundary.
        if first == "departments" and len(segments) >= 2:
            prefixes.add(f"/{first}/{segments[1]}")
        else:
            prefixes.add(f"/{first}")
    return prefixes


def test_every_router_prefix_is_documented(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_SKILLS_ROOT", str(tmp_path / "skills"))

    from openlia_server.app import create_app

    app = create_app()
    matrix_path = _matrix_path()
    assert matrix_path.is_file(), f"missing matrix: {matrix_path}"
    text = matrix_path.read_text(encoding="utf-8")

    missing = sorted(p for p in _router_prefixes(app) if p not in text)
    assert not missing, (
        "route-authorization-matrix.md is missing rows for these router "
        f"prefixes: {missing}. Add them (see the matrix merge gate)."
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
