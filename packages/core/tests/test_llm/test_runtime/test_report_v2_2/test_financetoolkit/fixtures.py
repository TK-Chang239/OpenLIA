"""Canned MSFT-like financial statement fixtures for FinanceToolkit helper tests.

All values are static — no live API calls.
Derived from MSFT Q1 FY2024 (period ending 2024-03-31) approximate figures.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Income Statement
# ---------------------------------------------------------------------------

INCOME: dict = {
    "revenue": 61_858_000_000.0,
    "gross_profit": 42_392_000_000.0,
    "operating_income": 27_589_000_000.0,
    "net_income": 21_939_000_000.0,
    "ebit": 27_589_000_000.0,
    "interest_expense": 300_000_000.0,
    "depreciation_and_amortization": 3_500_000_000.0,
    "income_before_tax": 28_000_000_000.0,
    "income_tax_expense": 6_061_000_000.0,
    "cost_of_goods_sold": 19_466_000_000.0,
}

# Prior period (Q1 FY2023 approximate)
INCOME_PRIOR: dict = {
    "revenue": 52_748_000_000.0,
    "gross_profit": 34_670_000_000.0,
    "operating_income": 22_352_000_000.0,
    "net_income": 18_299_000_000.0,
    "eps": 2.45,
}

# ---------------------------------------------------------------------------
# Balance Sheet
# ---------------------------------------------------------------------------

BALANCE: dict = {
    "current_assets": 184_406_000_000.0,
    "current_liabilities": 125_286_000_000.0,
    "cash_and_equivalents": 80_000_000_000.0,
    "accounts_receivable": 48_500_000_000.0,
    "inventory": 2_500_000_000.0,
    "accounts_payable": 18_000_000_000.0,
    "total_assets": 512_163_000_000.0,
    "total_equity": 268_477_000_000.0,
    "total_liabilities": 243_686_000_000.0,
    "total_debt": 79_300_000_000.0,
    "long_term_debt": 41_990_000_000.0,
    "short_term_debt": 37_310_000_000.0,
    "retained_earnings": 200_000_000_000.0,
    "fixed_assets": 95_000_000_000.0,
    "marketable_securities": 5_000_000_000.0,
}

# Prior period (Q1 FY2023 approximate)
BALANCE_PRIOR: dict = {
    "current_assets": 175_000_000_000.0,
    "current_liabilities": 118_000_000_000.0,
    "total_assets": 411_976_000_000.0,
    "total_equity": 206_223_000_000.0,
    "total_debt": 81_000_000_000.0,
    "total_liabilities": 205_753_000_000.0,
    "retained_earnings": 180_000_000_000.0,
    "gross_profit": 34_670_000_000.0,
    "revenue": 52_748_000_000.0,
}

# ---------------------------------------------------------------------------
# Cash Flow
# ---------------------------------------------------------------------------

CASH_FLOW: dict = {
    "operating_cash_flow": 31_900_000_000.0,
    "free_cash_flow": 21_500_000_000.0,
    "capital_expenditure": 10_400_000_000.0,
    "net_debt_repayment": 5_000_000_000.0,
}

CASH_FLOW_PRIOR: dict = {
    "operating_cash_flow": 26_000_000_000.0,
    "free_cash_flow": 17_000_000_000.0,
}

# ---------------------------------------------------------------------------
# Market Data
# ---------------------------------------------------------------------------

MARKET: dict = {
    "share_price": 421.44,
    "shares_outstanding": 7_440_000_000.0,
    "market_cap": 3_100_000_000_000.0,
    "eps": 2.94,
    "dividends_per_share": 3.00,
    "dividends_paid": 22_320_000_000.0,
    "beta": 0.90,
}

MARKET_PRIOR: dict = {
    "shares_outstanding": 7_444_000_000.0,
    "dividends_paid": 20_000_000_000.0,
}

# ---------------------------------------------------------------------------
# Canned FRED CSV response (for credit spreads test)
# ---------------------------------------------------------------------------

FRED_HY_CSV = """\
DATE,BAMLH0A0HYM2
2024-05-10,3.21
2024-05-13,3.18
2024-05-14,3.15
"""

FRED_IG_CSV = """\
DATE,BAMLC0A0CM
2024-05-10,0.95
2024-05-13,0.93
2024-05-14,0.91
"""

FRED_TSY_CSV = """\
DATE,DGS10
2024-05-10,4.46
2024-05-13,4.48
2024-05-14,4.50
"""
