"""Data transport bundle for the Earnings Update v2 engine.

Lives in its own module (rather than ``__init__.py``) so ``runner.py``
can import the type for its ``transports`` annotation without a forward
reference — ``typing.get_type_hints(Runner)`` / ``dataclasses.fields``
resolve cleanly. The public surface re-exports it from the package
``__init__``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EuDataTransports:
    """Callables the EU v2 data tools dispatch against.

    Supplied by the server wiring layer so the core package stays free
    of the EODHD SDK. ``earnings_calendar`` returns the upcoming-events
    list for a ticker.
    """

    fundamentals: Callable[[str], dict[str, Any]]
    prices: Callable[[str, str, str], list[dict[str, Any]]]
    news: Callable[[str, int], list[dict[str, Any]]]
    earnings_calendar: Callable[[str], list[dict[str, Any]]]
