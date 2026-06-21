"""Inject a network timeout into the eodhd SDK.

The eodhd SDK issues ``requests.get(url)`` with no timeout (in both
``eodhd.APIs.BaseAPI`` and ``eodhd.apiclient``) and its ``APIClient``
constructor exposes no timeout argument, so a slow or unresponsive
EODHD endpoint blocks the caller forever. A hung call once took down a
v3 equity-research run for 54 minutes: the synchronous request sat past
the engine's wall-time guard (which only checks between turns) until a
deploy restarted the process.

``harden_eodhd_timeout`` wraps the module-level ``requests_get`` the SDK
imported so every SDK request carries a default timeout when the caller
didn't pass one. Called once at app startup; the patch is process-wide,
so every ``APIClient`` instance (v3, Earnings Update, Morning Briefing)
benefits. Idempotent, and best-effort: if the SDK's module shape ever
changes we log and leave it alone rather than crash report generation —
the engine's per-tool cap is the hard backstop.
"""

from __future__ import annotations

import functools
import importlib
import logging
from typing import Any

log = logging.getLogger(__name__)

# Default network timeout (seconds) for every eodhd request. A single
# EODHD GET normally returns in a few seconds; beyond this it is hung.
DEFAULT_EODHD_TIMEOUT_SECONDS = 30.0

# Sentinel marking an already-wrapped ``requests_get`` so re-hardening
# is a no-op rather than nesting wrappers.
_HARDENED_FLAG = "_openlia_timeout_hardened"

# eodhd modules that do ``from requests import get as requests_get`` and
# call it without a timeout.
_EODHD_REQUEST_MODULES = ("eodhd.APIs.BaseAPI", "eodhd.apiclient")


def _wrap_with_timeout(original: Any, timeout_seconds: float) -> Any:
    @functools.wraps(original)
    def _get_with_timeout(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", timeout_seconds)
        return original(*args, **kwargs)

    setattr(_get_with_timeout, _HARDENED_FLAG, True)
    return _get_with_timeout


def harden_eodhd_timeout(timeout_seconds: float = DEFAULT_EODHD_TIMEOUT_SECONDS) -> None:
    """Wrap the eodhd SDK's ``requests_get`` to carry a default timeout."""
    for module_name in _EODHD_REQUEST_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            log.warning("eodhd module %s not importable; skipping timeout hardening", module_name)
            continue
        current = getattr(module, "requests_get", None)
        if current is None:
            log.warning(
                "eodhd module %s has no requests_get; skipping timeout hardening", module_name
            )
            continue
        if getattr(current, _HARDENED_FLAG, False):
            continue  # already hardened
        module.requests_get = _wrap_with_timeout(current, timeout_seconds)


__all__ = ["DEFAULT_EODHD_TIMEOUT_SECONDS", "harden_eodhd_timeout"]
