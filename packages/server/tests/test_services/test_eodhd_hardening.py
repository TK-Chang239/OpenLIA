"""The eodhd SDK issues un-timed HTTP; we inject a default timeout.

``harden_eodhd_timeout`` wraps the ``requests_get`` the SDK imported in
each of its request modules so every SDK call carries a network
timeout when the caller didn't set one. A missing timeout let a hung
EODHD endpoint block a v3 run for 54 minutes. These tests pin: the
default is injected, an explicit timeout still wins, and re-hardening
is a no-op.
"""

from __future__ import annotations

import importlib

from openlia_server.services.eodhd_hardening import (
    _EODHD_REQUEST_MODULES,
    _HARDENED_FLAG,
    harden_eodhd_timeout,
)


def _install_spy(monkeypatch, seen: dict) -> None:
    """Replace requests_get in every eodhd request module with a spy.

    monkeypatch restores the real symbols after the test, so hardening
    doesn't leak into other tests.
    """
    for module_name in _EODHD_REQUEST_MODULES:
        module = importlib.import_module(module_name)

        def spy(url, *args, _module=module_name, **kwargs):
            seen[_module] = kwargs.get("timeout", "MISSING")
            return "resp"

        monkeypatch.setattr(module, "requests_get", spy)


def test_harden_injects_default_timeout(monkeypatch):
    seen: dict = {}
    _install_spy(monkeypatch, seen)

    harden_eodhd_timeout(7.5)

    base = importlib.import_module("eodhd.APIs.BaseAPI")
    assert base.requests_get("https://eodhd.com/api/fundamentals/AVGO") == "resp"
    assert seen["eodhd.APIs.BaseAPI"] == 7.5


def test_harden_respects_explicit_timeout(monkeypatch):
    seen: dict = {}
    _install_spy(monkeypatch, seen)

    harden_eodhd_timeout(7.5)

    base = importlib.import_module("eodhd.APIs.BaseAPI")
    base.requests_get("https://x", timeout=1.0)
    assert seen["eodhd.APIs.BaseAPI"] == 1.0


def test_harden_is_idempotent(monkeypatch):
    seen: dict = {}
    _install_spy(monkeypatch, seen)

    harden_eodhd_timeout(7.5)
    base = importlib.import_module("eodhd.APIs.BaseAPI")
    wrapped_once = base.requests_get

    harden_eodhd_timeout(9.0)  # must not re-wrap

    assert base.requests_get is wrapped_once
    assert getattr(base.requests_get, _HARDENED_FLAG, False) is True
