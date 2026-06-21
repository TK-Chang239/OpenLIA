# packages/server/src/openlia_server/routes/departments/_eu_v2_gate.py
"""Engine gate for Earnings Update v2.

v2 is now the sole live Earnings Update engine and is always enabled
(mirrors the retired v3 ``REPORT_ENGINE_VERSION`` gate). The
``EARNINGS_ENGINE_VERSION`` flag is retained only for backward
compatibility: any value, including unset, keeps v2 on.
"""

from __future__ import annotations


def eu_v2_enabled() -> bool:
    """True always. The ``EARNINGS_ENGINE_VERSION`` flag is retired."""
    return True
