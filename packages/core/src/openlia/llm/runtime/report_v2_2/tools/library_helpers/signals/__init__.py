"""Signals helpers bundle (PR 2.8).

3 helpers:
  insider_signal_panel        — Form 4 insider trading signal, code-filtered, role-weighted
  moving_average_panel        — MA trend regime, crossovers, mean-reversion stretch
  historical_multiple_trends  — Historical P/E, EV/EBITDA, P/B, P/S vs own history

All self-register via register_helper() on import.
"""

from . import (  # noqa: F401
    historical_multiple_trends,
    insider_signal_panel,
    moving_average_panel,
)
