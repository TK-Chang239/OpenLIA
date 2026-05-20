"""Working-capital cycle helpers (WS7)."""

from __future__ import annotations


def cycle_days(
    receivables: float,
    inventory: float,
    payables: float,
    revenue: float,
    cogs: float,
) -> dict:
    """DSO, DIO, DPO, and CCC. Inputs in raw dollars, revenue/cogs are TTM."""
    if revenue <= 0:
        raise ValueError("revenue must be positive")
    if cogs <= 0:
        raise ValueError("cogs must be positive")
    dso = (receivables / revenue) * 365.0
    dio = (inventory / cogs) * 365.0
    dpo = (payables / cogs) * 365.0
    return {
        "dso": dso,
        "dio": dio,
        "dpo": dpo,
        "ccc": dso + dio - dpo,
    }
