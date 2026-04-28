"""Tests for `introspect_python_lib`."""

from __future__ import annotations

import sys
from pathlib import Path

# Make the local fixture package importable as a top-level module.
sys.path.insert(0, str(Path(__file__).parent))

from openlia.connectors.adapter import introspect_python_lib  # noqa: E402


def _qualnames(defs) -> set[str]:
    return {d.qualname for d in defs}


def test_introspect_returns_public_class_methods() -> None:
    defs = introspect_python_lib("_adapter_fixture_lib")
    qns = _qualnames(defs)
    # Public methods on both classes are surfaced.
    assert "Client.quote" in qns
    assert "Client.search" in qns
    assert "Helper.ping" in qns


def test_introspect_excludes_private_methods() -> None:
    defs = introspect_python_lib("_adapter_fixture_lib")
    qns = _qualnames(defs)
    assert "Client._private" not in qns


def test_introspect_excludes_module_level_functions() -> None:
    defs = introspect_python_lib("_adapter_fixture_lib")
    qns = _qualnames(defs)
    # `top_level_fn` is not bound to any class, so it must not appear.
    assert not any(qn.endswith(".top_level_fn") for qn in qns)
    assert "top_level_fn" not in qns


def test_introspect_captures_signature_and_doc() -> None:
    defs = introspect_python_lib("_adapter_fixture_lib")
    by_qn = {d.qualname: d for d in defs}
    quote = by_qn["Client.quote"]
    assert "symbol" in quote.signature
    assert "quote payload" in quote.doc.lower()


def test_introspect_skips_signature_failures(monkeypatch) -> None:
    """Members whose `inspect.signature` raises must be silently skipped."""
    import inspect as _inspect

    real_signature = _inspect.signature

    def maybe_raise(obj, *args, **kwargs):
        if getattr(obj, "__name__", "") == "search":
            raise ValueError("synthetic introspection failure")
        return real_signature(obj, *args, **kwargs)

    monkeypatch.setattr(
        "openlia.connectors.adapter.introspect.inspect.signature", maybe_raise
    )
    defs = introspect_python_lib("_adapter_fixture_lib")
    qns = _qualnames(defs)
    assert "Client.quote" in qns
    assert "Client.search" not in qns
