# packages/server/src/openlia_server/routes/departments/_eu_v2_gate.py
"""Env gate for the Earnings Update v2 engine.

Mirrors the v3 ``REPORT_ENGINE_VERSION=v3`` gate. EU v2 routes return
503 when disabled so v1 stays the only live Earnings Update surface
until v2 is proven.
"""

from __future__ import annotations

import os


def eu_v2_enabled() -> bool:
    """True when ``EARNINGS_ENGINE_VERSION`` equals ``v2`` (case-insensitive)."""
    return os.environ.get("EARNINGS_ENGINE_VERSION", "").strip().lower() == "v2"
