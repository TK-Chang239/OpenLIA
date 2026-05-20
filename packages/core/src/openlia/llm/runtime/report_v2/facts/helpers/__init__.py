"""Deterministic financial helpers (WS7).

Importing this package triggers registration of every helper-derived fact
with the default registry. Pure-Python helpers live alongside the registered
fact wrappers; the helpers themselves are independently importable for
testing and reuse.
"""

from __future__ import annotations

# Force registration of every helper-derived fact.
from openlia.llm.runtime.report_v2.facts.helpers import (  # noqa: F401
    distressed,
    forecast,
    liquidity,
    returns,
    saas,
    sbc_dilution,
    valuation,
    working_capital,
)
