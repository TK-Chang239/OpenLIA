"""Canned EODHD API response fixtures for unit tests.

All responses are static dicts — no live API calls.
Shaped after real EODHD API responses for MSFT.US and NESN.SW.
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Shared minimal fundamentals payload (used by multiple helpers)
# ---------------------------------------------------------------------------

MSFT_FUNDAMENTALS: dict[str, Any] = {
    "General": {
        "Code": "MSFT",
        "Type": "Common Stock",
        "Name": "Microsoft Corp",
        "Exchange": "NASDAQ",
        "CurrencyCode": "USD",
        "CurrencyName": "US Dollar",
        "CurrencySymbol": "$",
        "CountryName": "USA",
        "CountryISO": "US",
        "Sector": "Technology",
        "Industry": "Software—Infrastructure",
        "Description": "Microsoft Corporation develops and supports software...",
        "FullTimeEmployees": 221000,
        "FiscalYearEnd": "June",
        "IPODate": "1986-03-13",
    },
    "Highlights": {
        "MarketCapitalization": 3100000000000,
        "EBITDA": 110000000000,
        "PERatio": 35.5,
        "PEGRatio": 2.1,
        "EarningsShare": 11.45,
        "EPSEstimateCurrentYear": 12.10,
        "ProfitMargin": 0.358,
        "OperatingMarginTTM": 0.445,
        "ReturnOnAssetsTTM": 0.151,
        "ReturnOnEquityTTM": 0.411,
        "RevenueTTM": 245000000000,
        "RevenuePerShareTTM": 32.85,
        "QuarterlyRevenueGrowthYOY": 0.172,
        "GrossProfitTTM": 165000000000,
        "DilutedEpsTTM": 11.45,
        "QuarterlyEarningsGrowthYOY": 0.195,
    },
    "Valuation": {
        "TrailingPE": 35.5,
        "ForwardPE": 30.2,
        "PriceSalesTTM": 12.7,
        "PriceBookMRQ": 14.1,
        "EnterpriseValue": 3050000000000,
        "EnterpriseValueRevenue": 12.4,
        "EnterpriseValueEbitda": 27.7,
    },
    "Financials": {
        "Balance_Sheet": {
            "quarterly": {
                "2024-03-31": {
                    "date": "2024-03-31",
                    "totalAssets": 512163000000,
                    "totalLiabilities": 243686000000,
                    "totalStockholderEquity": 268477000000,
                    "cash": 80000000000,
                    "totalCurrentAssets": 184406000000,
                    "totalCurrentLiabilities": 125286000000,
                    "longTermDebt": 41990000000,
                },
            },
            "annual": {
                "2023-06-30": {
                    "date": "2023-06-30",
                    "totalAssets": 411976000000,
                    "totalLiabilities": 205753000000,
                    "totalStockholderEquity": 206223000000,
                },
            },
        },
        "Income_Statement": {
            "quarterly": {
                "2024-03-31": {
                    "date": "2024-03-31",
                    "totalRevenue": 61858000000,
                    "grossProfit": 42392000000,
                    "operatingIncome": 27589000000,
                    "netIncome": 21939000000,
                    "eps": 2.94,
                    "epsDiluted": 2.94,
                },
            },
            "annual": {
                "2023-06-30": {
                    "date": "2023-06-30",
                    "totalRevenue": 211915000000,
                    "grossProfit": 146052000000,
                    "operatingIncome": 88523000000,
                    "netIncome": 72361000000,
                },
            },
        },
        "Cash_Flow": {
            "quarterly": {
                "2024-03-31": {
                    "date": "2024-03-31",
                    "totalCashFromOperatingActivities": 31900000000,
                    "totalCashflowsFromInvestingActivities": -11800000000,
                    "totalCashFromFinancingActivities": -9100000000,
                    "freeCashFlow": 21500000000,
                },
            },
            "annual": {
                "2023-06-30": {
                    "date": "2023-06-30",
                    "totalCashFromOperatingActivities": 87582000000,
                    "freeCashFlow": 59475000000,
                },
            },
        },
    },
    "Earnings": {
        "History": {
            "2024-03-31": {
                "reportDate": "2024-03-31",
                "date": "2024-03-31",
                "epsActual": 2.94,
                "epsEstimate": 2.83,
                "epsDifference": 0.11,
                "surprisePercent": 3.89,
                "currency": "USD",
            },
            "2023-12-31": {
                "reportDate": "2023-12-31",
                "date": "2023-12-31",
                "epsActual": 2.93,
                "epsEstimate": 2.78,
                "epsDifference": 0.15,
                "surprisePercent": 5.40,
                "currency": "USD",
            },
        },
        "Annual": {
            "2023-06-30": {
                "date": "2023-06-30",
                "epsActual": 9.72,
                "epsEstimate": 9.55,
            },
        },
    },
    "AnalystRatings": {
        "Rating": 1.8,
        "TargetPrice": 480.0,
        "StrongBuy": 28,
        "Buy": 12,
        "Hold": 5,
        "Sell": 1,
        "StrongSell": 0,
    },
}

NESN_FUNDAMENTALS: dict[str, Any] = {
    "General": {
        "Code": "NESN",
        "Type": "Common Stock",
        "Name": "Nestle SA",
        "Exchange": "SW",
        "CurrencyCode": "CHF",
        "CurrencyName": "Swiss Franc",
        "CurrencySymbol": "CHF",
        "CountryName": "Switzerland",
        "CountryISO": "CH",
        "Sector": "Consumer Defensive",
        "Industry": "Packaged Foods",
        "Description": "Nestle S.A. manufactures and sells food and beverage products...",
        "FullTimeEmployees": 275000,
        "FiscalYearEnd": "December",
        "IPODate": "1990-01-01",
    },
    "Highlights": {
        "MarketCapitalization": 285000000000,
        "PERatio": 18.2,
        "EarningsShare": 4.85,
        "ProfitMargin": 0.112,
        "RevenueTTM": 94000000000,
    },
    "Financials": {
        "Balance_Sheet": {"quarterly": {}, "annual": {}},
        "Income_Statement": {"quarterly": {}, "annual": {}},
        "Cash_Flow": {"quarterly": {}, "annual": {}},
    },
    "Earnings": {"History": {}, "Annual": {}},
}

# ---------------------------------------------------------------------------
# EOD prices fixture
# ---------------------------------------------------------------------------

MSFT_EOD_PRICES: list[dict[str, Any]] = [
    {
        "date": "2024-01-02",
        "open": 374.02,
        "high": 376.55,
        "low": 373.01,
        "close": 374.37,
        "adjusted_close": 374.37,
        "volume": 20145600,
    },
    {
        "date": "2024-01-03",
        "open": 371.00,
        "high": 373.69,
        "low": 368.56,
        "close": 370.95,
        "adjusted_close": 370.95,
        "volume": 22890400,
    },
    {
        "date": "2024-01-04",
        "open": 369.12,
        "high": 372.10,
        "low": 366.50,
        "close": 367.79,
        "adjusted_close": 367.79,
        "volume": 18564200,
    },
]

# ---------------------------------------------------------------------------
# Intraday fixture
# ---------------------------------------------------------------------------

MSFT_INTRADAY: list[dict[str, Any]] = [
    {
        "timestamp": 1704276900,
        "gmtoffset": 0,
        "open": 374.50,
        "high": 375.20,
        "low": 374.10,
        "close": 374.80,
        "volume": 125400,
    },
    {
        "timestamp": 1704277200,
        "gmtoffset": 0,
        "open": 374.80,
        "high": 376.00,
        "low": 374.70,
        "close": 375.60,
        "volume": 98200,
    },
]

# ---------------------------------------------------------------------------
# Real-time quote fixture
# ---------------------------------------------------------------------------

MSFT_REAL_TIME_QUOTE: dict[str, Any] = {
    "code": "MSFT.US",
    "timestamp": 1716393600,
    "gmtoffset": -14400,
    "open": 419.50,
    "high": 422.90,
    "low": 418.10,
    "close": 421.44,
    "volume": 15234800,
    "previousClose": 416.78,
    "change": 4.66,
    "change_p": 1.118,
}

# ---------------------------------------------------------------------------
# Dividends fixture
# ---------------------------------------------------------------------------

MSFT_DIVIDENDS: list[dict[str, Any]] = [
    {
        "date": "2024-02-14",
        "declarationDate": "2023-11-28",
        "recordDate": "2024-02-15",
        "paymentDate": "2024-03-14",
        "value": 0.75,
        "currency": "USD",
    },
    {
        "date": "2023-11-15",
        "declarationDate": "2023-09-19",
        "recordDate": "2023-11-16",
        "paymentDate": "2023-12-14",
        "value": 0.75,
        "currency": "USD",
    },
]

# ---------------------------------------------------------------------------
# Splits fixture
# ---------------------------------------------------------------------------

MSFT_SPLITS: list[dict[str, Any]] = [
    {"date": "2003-02-18", "split": "2/1"},
    {"date": "1999-03-26", "split": "2/1"},
    {"date": "1998-02-23", "split": "2/1"},
]

# ---------------------------------------------------------------------------
# Market cap history fixture
# ---------------------------------------------------------------------------

MSFT_MARKET_CAP_HISTORY: list[dict[str, Any]] = [
    {"date": "2024-05-01", "marketCapitalization": 3050000000000},
    {"date": "2024-05-02", "marketCapitalization": 3070000000000},
    {"date": "2024-05-03", "marketCapitalization": 3100000000000},
]

# ---------------------------------------------------------------------------
# Insider transactions fixture
# ---------------------------------------------------------------------------

MSFT_INSIDER_TRANSACTIONS: list[dict[str, Any]] = [
    {
        "date": "2024-02-20",
        "ownerCik": "0001513142",
        "ownerName": "Nadella Satya",
        "transactionDate": "2024-02-16",
        "transactionCode": "S",
        "transactionAmount": 15000,
        "transactionPrice": 415.20,
        "transactionAcquiredDisposed": "D",
        "postTransactionAmount": 835000,
        "currency": "USD",
    },
]

# ---------------------------------------------------------------------------
# News fixture
# ---------------------------------------------------------------------------

MSFT_NEWS: list[dict[str, Any]] = [
    {
        "date": "2024-05-15T18:30:00+00:00",
        "title": "Microsoft Q3 Results Beat Estimates on Cloud Growth",
        "content": "Microsoft reported strong Q3 results driven by Azure cloud growth...",
        "link": "https://example.com/msft-q3-results",
        "symbols": ["MSFT.US"],
        "tags": ["earnings", "cloud"],
    },
    {
        "date": "2024-05-14T14:00:00+00:00",
        "title": "Microsoft Raises Dividend by 10%",
        "content": "Microsoft announced a 10% increase in its quarterly dividend...",
        "link": "https://example.com/msft-dividend",
        "symbols": ["MSFT.US"],
        "tags": ["dividend"],
    },
]

# ---------------------------------------------------------------------------
# Sentiment fixture
# ---------------------------------------------------------------------------

MSFT_SENTIMENT: dict[str, Any] = {
    "MSFT.US": {
        "2024-05-15": {"normalized": 0.72, "count": 45},
        "2024-05-14": {"normalized": 0.58, "count": 32},
        "2024-05-13": {"normalized": 0.41, "count": 28},
    }
}

# ---------------------------------------------------------------------------
# Upcoming earnings fixture
# ---------------------------------------------------------------------------

MSFT_UPCOMING_EARNINGS: dict[str, Any] = {
    "earnings": [
        {
            "code": "MSFT.US",
            "report_date": "2024-07-30",
            "date": "2024-07-30",
            "before_after_market": "AMC",
            "currency": "USD",
            "actual": None,
            "estimate": 3.01,
            "difference": None,
            "percent": None,
        }
    ]
}

# ---------------------------------------------------------------------------
# Technical indicators fixture
# ---------------------------------------------------------------------------

MSFT_RSI: list[dict[str, Any]] = [
    {"date": "2024-05-13", "rsi": 58.32},
    {"date": "2024-05-14", "rsi": 61.45},
    {"date": "2024-05-15", "rsi": 63.10},
]

# ---------------------------------------------------------------------------
# Macro indicator fixture
# ---------------------------------------------------------------------------

USA_GDP: list[dict[str, Any]] = [
    {"date": "2023-01-01", "value": 27360000000000.0},
    {"date": "2022-01-01", "value": 25744000000000.0},
    {"date": "2021-01-01", "value": 23315000000000.0},
]
