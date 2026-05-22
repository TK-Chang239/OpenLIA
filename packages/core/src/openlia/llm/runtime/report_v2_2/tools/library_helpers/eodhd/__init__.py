"""EODHD adapter helpers for report_v2_2.

All 18 helpers self-register at import via register_helper().
Import this package to load all EODHD adapters into the helper registry.
"""

from . import (  # noqa: F401
    eodhd_balance_sheet,
    eodhd_cash_flow,
    eodhd_company_info,
    eodhd_dividends,
    eodhd_earnings_history,
    eodhd_eod_prices,
    eodhd_fundamentals,
    eodhd_income_statement,
    eodhd_insider_transactions,
    eodhd_intraday,
    eodhd_macro_indicator,
    eodhd_market_cap_history,
    eodhd_news,
    eodhd_real_time_quote,
    eodhd_sentiment,
    eodhd_splits,
    eodhd_technical_indicators,
    eodhd_upcoming_earnings,
)
