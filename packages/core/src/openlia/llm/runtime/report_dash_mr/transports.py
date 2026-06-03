"""Data transport bundle for the Morning Briefing engine.

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
class MbDataTransports:
    """Callables the Morning Briefing data tools dispatch against.

    Supplied by the server wiring layer so the core package stays free
    of the EODHD SDK. The Morning Briefing tools are market-wide rather
    than single-ticker: ``quotes`` takes a list of tickers, ``prices``
    takes a ticker and a range token, ``news`` takes an optional symbol
    (market-wide when omitted), ``economic_calendar`` takes a window
    token, and ``macro_indicators`` takes a list of indicator keys.
    """

    quotes: Callable[[list[str]], list[dict[str, Any]]]
    prices: Callable[[str, str], list[dict[str, Any]]]
    news: Callable[..., list[dict[str, Any]]]
    economic_calendar: Callable[[str], list[dict[str, Any]]]
    macro_indicators: Callable[[list[str]], dict[str, Any]]
