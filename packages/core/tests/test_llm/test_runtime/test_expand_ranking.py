"""Tests for expand_ranking.rank_candidates — TDD vertical slices."""

from __future__ import annotations

from typing import Any

import pytest
from openlia.llm.runtime.expand_ranking import (
    DEFAULT_TOP_K,
    _idf_for_corpus,
    _strip_name_noise,
    _tokenize,
    rank_candidates,
)

# ---------------------------------------------------------------------------
# Fixture corpus — plausible OpenLIA tool inventory
# ---------------------------------------------------------------------------

GOLDEN_CORPUS: list[dict[str, Any]] = [
    {
        "name": "fmp__statements",
        "description": (
            "income statement, balance sheet, cash flow for any ticker, annual or quarterly"
        ),
        "category": "financial",
    },
    {
        "name": "fmp__quote",
        "description": "real-time and recent quote data for any ticker",
        "category": "financial",
    },
    {
        "name": "fmp__company",
        "description": "company profile: sector, industry, description, CEO, market cap",
        "category": "financial",
    },
    {
        "name": "fmp__news",
        "description": "company news articles by ticker and date range",
        "category": "news",
    },
    {
        "name": "fmp__insider_trades",
        "description": "Form 4 insider transactions for any ticker",
        "category": "financial",
    },
    {
        "name": "fmp__earnings_transcript",
        "description": "earnings call transcripts for any company",
        "category": "financial",
    },
    {
        "name": "fmp__analyst_estimates",
        "description": "Wall Street analyst estimates and price targets",
        "category": "financial",
    },
    {
        "name": "fmp__discounted_cash_flow",
        "description": "DCF valuation models for any ticker",
        "category": "financial",
    },
    {
        "name": "fmp__market_index",
        "description": "real-time and historical index levels: S&P 500, NASDAQ, Dow",
        "category": "financial",
    },
    {
        "name": "eodhd__macro_indicator",
        "description": "macro indicators: GDP, CPI, PPI, unemployment, treasury yield by country",
        "category": "financial",
    },
    {
        "name": "eodhd__historical_prices",
        "description": "historical OHLC stock prices by ticker",
        "category": "financial",
    },
    {
        "name": "fmp__commitment_of_traders",
        "description": "CFTC commitments of traders report by futures contract, COT data",
        "category": "financial",
    },
    {
        "name": "fmp__economic_calendar",
        "description": (
            "upcoming earnings dates, economic data releases,"
            " and scheduled calendar events this week"
        ),
        "category": "financial",
    },
    {
        "name": "x__user_timeline",
        "description": "X (Twitter) user timeline posts by username",
        "category": "social",
    },
    {
        "name": "newsapi__articles",
        "description": "world news articles by topic or query",
        "category": "news",
    },
]

GOLDEN_QUERIES: list[tuple[str, str]] = [
    ("NVDA quarterly income statement", "fmp__statements"),
    ("AAPL insider trades last 90 days", "fmp__insider_trades"),
    ("upcoming earnings this week", "fmp__economic_calendar"),
    ("US 10-year treasury yield", "eodhd__macro_indicator"),
    ("CPI prints for the eurozone", "eodhd__macro_indicator"),
    ("NVDA earnings call transcript", "fmp__earnings_transcript"),
    ("Tesla DCF valuation", "fmp__discounted_cash_flow"),
    ("MSFT analyst price target", "fmp__analyst_estimates"),
    ("S&P 500 closing levels last year", "fmp__market_index"),
    ("CFTC oil COT report", "fmp__commitment_of_traders"),
]


# ---------------------------------------------------------------------------
# 1. Empty corpus
# ---------------------------------------------------------------------------


def test_empty_corpus_returns_empty() -> None:
    result = rank_candidates([], reason="anything", category_hint=None)
    assert result == []


# ---------------------------------------------------------------------------
# 2. Empty reason
# ---------------------------------------------------------------------------


def test_empty_reason_returns_empty() -> None:
    corpus = [{"name": "fmp__quote", "description": "stock quote", "category": "financial"}]
    assert rank_candidates(corpus, reason="", category_hint=None) == []


def test_whitespace_reason_returns_empty() -> None:
    corpus = [{"name": "fmp__quote", "description": "stock quote", "category": "financial"}]
    assert rank_candidates(corpus, reason="   ", category_hint=None) == []


# ---------------------------------------------------------------------------
# 3. Tokenize basics
# ---------------------------------------------------------------------------


def test_tokenize_lowercases() -> None:
    tokens = _tokenize("AAPL NVDA")
    assert tokens == ["aapl", "nvda"]


def test_tokenize_splits_on_non_alphanum() -> None:
    tokens = _tokenize("income-statement, balance.sheet")
    assert "income" in tokens
    assert "statement" in tokens
    assert "balance" in tokens
    assert "sheet" in tokens


def test_tokenize_drops_stopwords() -> None:
    tokens = _tokenize("i need the company news")
    assert "i" not in tokens
    assert "need" not in tokens
    assert "the" not in tokens
    assert "company" in tokens
    assert "news" in tokens


def test_tokenize_drops_short_tokens() -> None:
    # Single-char tokens dropped; "a" is also a stopword but len check fires first
    tokens = _tokenize("a x stock")
    assert "a" not in tokens
    assert "x" not in tokens
    assert "stock" in tokens


def test_tokenize_empty_string_returns_empty() -> None:
    assert _tokenize("") == []


# ---------------------------------------------------------------------------
# 4. Name noise strip
# ---------------------------------------------------------------------------


def test_strip_name_noise_removes_get_prefix() -> None:
    # Internal underscores preserved; only leading prefix stripped
    assert _strip_name_noise("get_company_news") == "company_news"


def test_strip_name_noise_removes_fetch_prefix() -> None:
    assert _strip_name_noise("fetch_statements") == "statements"


def test_strip_name_noise_removes_list_prefix() -> None:
    assert _strip_name_noise("list_reports") == "reports"


def test_strip_name_noise_removes_data_suffix() -> None:
    assert _strip_name_noise("quote_data") == "quote"


def test_strip_name_noise_removes_history_suffix() -> None:
    assert _strip_name_noise("price_history") == "price"


def test_strip_name_noise_no_noise() -> None:
    # No known prefix/suffix: unchanged (lowercased)
    assert _strip_name_noise("fmp__statements") == "fmp__statements"


def test_strip_name_noise_does_not_strip_internal() -> None:
    # Only leading prefix and trailing suffix stripped
    result = _strip_name_noise("get_company_news")
    assert "company_news" in result


# ---------------------------------------------------------------------------
# 5. Single-result happy path
# ---------------------------------------------------------------------------


def test_single_result_happy_path() -> None:
    corpus = [
        {
            "name": "fmp__statements",
            "description": "income, balance, cash flow statements",
            "category": "financial",
        },
        {
            "name": "fmp__quote",
            "description": "real-time stock price quote",
            "category": "financial",
        },
        {
            "name": "x__user_timeline",
            "description": "X Twitter user posts",
            "category": "social",
        },
    ]
    results = rank_candidates(corpus, reason="quarterly income statement", category_hint=None)
    assert len(results) >= 1
    assert results[0]["name"] == "fmp__statements"


# ---------------------------------------------------------------------------
# 6. Category boost lifts a tie
# ---------------------------------------------------------------------------


def test_category_boost_lifts_tied_candidate() -> None:
    """Two candidates tied on token overlap; category match should rank first."""
    corpus = [
        {
            "name": "tool_alpha",
            "description": "earnings report for companies",
            "category": "financial",
        },
        {
            "name": "tool_beta",
            "description": "earnings report for companies",
            "category": "news",
        },
    ]
    # Both have identical description; financial category_hint should lift tool_alpha
    results = rank_candidates(corpus, reason="quarterly earnings report", category_hint="financial")
    assert len(results) >= 1
    assert results[0]["name"] == "tool_alpha"


# ---------------------------------------------------------------------------
# 7. Strong keyword match beats category match with no keyword overlap
# ---------------------------------------------------------------------------


def test_strong_keyword_beats_category_match_no_overlap() -> None:
    corpus = [
        {
            "name": "fmp__statements",
            "description": "income statement balance sheet cash flow quarterly annual",
            "category": "financial",
        },
        {
            "name": "x__user_timeline",
            "description": "social media posts tweets",
            "category": "news",  # matches category_hint but no token overlap
        },
    ]
    results = rank_candidates(
        corpus,
        reason="quarterly income statement",
        category_hint="news",  # x__user_timeline matches category but has no keyword overlap
    )
    assert len(results) >= 1
    assert results[0]["name"] == "fmp__statements"


# ---------------------------------------------------------------------------
# 8. Score floor drops noise
# ---------------------------------------------------------------------------


def test_score_floor_drops_unrelated_tools() -> None:
    corpus = [
        {"name": "tool_a", "description": "pizza delivery service", "category": "food"},
        {"name": "tool_b", "description": "weather forecast rain umbrella", "category": "weather"},
        {"name": "tool_c", "description": "music playlist songs audio", "category": "media"},
        {
            "name": "tool_d",
            "description": "restaurant booking reservation table",
            "category": "food",
        },
        {
            "name": "tool_e",
            "description": "hotel rooms check-in checkout travel",
            "category": "travel",
        },
        {"name": "tool_f", "description": "ride sharing taxi uber lyft", "category": "transport"},
        {"name": "tool_g", "description": "grocery shopping cart checkout", "category": "retail"},
        {
            "name": "tool_h",
            "description": "gaming leaderboard scores points",
            "category": "gaming",
        },
        {
            "name": "tool_i",
            "description": "fitness workout calories exercise gym",
            "category": "health",
        },
        {
            "name": "tool_j",
            "description": "recipe cooking ingredients meal prep",
            "category": "food",
        },
    ]
    # "quarterly income" has zero overlap with any of these tools
    result = rank_candidates(corpus, reason="quarterly income", category_hint=None)
    assert result == []


# ---------------------------------------------------------------------------
# 9. Only 1-2 candidates above floor: return them (not gated by MIN_RESULTS)
# ---------------------------------------------------------------------------


def test_few_above_floor_returns_what_we_have() -> None:
    """With 1 candidate above floor, returns it rather than empty list."""
    corpus = [
        {
            "name": "fmp__statements",
            "description": "income statement balance sheet cash flow",
            "category": "financial",
        },
        {"name": "tool_b", "description": "pizza delivery service", "category": "food"},
        {"name": "tool_c", "description": "weather forecast rain", "category": "weather"},
    ]
    result = rank_candidates(corpus, reason="income statement", category_hint=None)
    # At least 1 result above floor
    assert len(result) >= 1
    assert result[0]["name"] == "fmp__statements"


def test_zero_above_floor_returns_empty() -> None:
    corpus = [
        {"name": "tool_a", "description": "pizza delivery service", "category": "food"},
    ]
    result = rank_candidates(corpus, reason="quarterly income", category_hint=None)
    assert result == []


# ---------------------------------------------------------------------------
# 10. Deterministic tiebreaker: alphabetical by name
# ---------------------------------------------------------------------------


def test_deterministic_tiebreaker_alphabetical() -> None:
    """Identical scores -> alphabetical by name -> same order on repeated calls."""
    corpus = [
        {
            "name": "zzz_tool",
            "description": "income statement balance sheet",
            "category": "financial",
        },
        {
            "name": "aaa_tool",
            "description": "income statement balance sheet",
            "category": "financial",
        },
    ]
    result1 = rank_candidates(corpus, reason="income statement", category_hint=None)
    result2 = rank_candidates(corpus, reason="income statement", category_hint=None)
    assert result1 == result2
    assert result1[0]["name"] == "aaa_tool"
    assert result1[1]["name"] == "zzz_tool"


# ---------------------------------------------------------------------------
# 11. Top-K cap
# ---------------------------------------------------------------------------


def test_top_k_cap() -> None:
    """20 candidates above floor -> returns exactly DEFAULT_TOP_K."""
    # Build 20 candidates all containing "earnings" so they all score
    corpus = [
        {
            "name": f"tool_{i:02d}",
            "description": f"earnings report quarterly statement {i}",
            "category": "financial",
        }
        for i in range(20)
    ]
    result = rank_candidates(corpus, reason="quarterly earnings statement", category_hint=None)
    assert len(result) == DEFAULT_TOP_K


def test_top_k_custom() -> None:
    corpus = [
        {
            "name": f"tool_{i:02d}",
            "description": f"earnings quarterly statement {i}",
            "category": "financial",
        }
        for i in range(20)
    ]
    result = rank_candidates(corpus, reason="quarterly earnings", category_hint=None, top_k=3)
    assert len(result) == 3


def test_top_k_zero_returns_empty() -> None:
    corpus = [{"name": "fmp__quote", "description": "stock price quote", "category": "financial"}]
    result = rank_candidates(corpus, reason="stock quote", category_hint=None, top_k=0)
    assert result == []


# ---------------------------------------------------------------------------
# 12. Name boost: name match ranks above description-only match
# ---------------------------------------------------------------------------


def test_name_boost_ranks_name_match_higher() -> None:
    """A tool whose name contains query tokens ranks above one where only
    the description matches, all else equal."""
    corpus = [
        {
            # "insider" only in description
            "name": "fmp__transactions",
            "description": "insider trading data, Form 4 filings by company",
            "category": "financial",
        },
        {
            # "insider" in name AND description
            "name": "fmp__insider_trades",
            "description": "insider transactions for any ticker",
            "category": "financial",
        },
    ]
    results = rank_candidates(corpus, reason="insider trades", category_hint=None)
    assert len(results) >= 1
    assert results[0]["name"] == "fmp__insider_trades"


# ---------------------------------------------------------------------------
# 13. Stopword behavior in query
# ---------------------------------------------------------------------------


def test_stopwords_stripped_from_query() -> None:
    tokens = _tokenize("i need the company news data")
    assert "i" not in tokens
    assert "need" not in tokens
    assert "the" not in tokens
    # "data" is not a stopword (it's a name suffix only)
    assert "data" in tokens
    assert "company" in tokens
    assert "news" in tokens


def test_only_stopwords_query_returns_empty() -> None:
    """Query with only stopwords -> no tokens -> returns []."""
    corpus = [{"name": "fmp__quote", "description": "stock price", "category": "financial"}]
    # "i", "the", "or" are all stopwords; "be" is too
    result = rank_candidates(corpus, reason="i or the be", category_hint=None)
    assert result == []


# ---------------------------------------------------------------------------
# 14. Golden test set (parametrized)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("query,expected_top", GOLDEN_QUERIES)
def test_golden_queries(query: str, expected_top: str) -> None:
    result = rank_candidates(GOLDEN_CORPUS, reason=query, category_hint=None, top_k=1)
    assert len(result) == 1, f"No result for query={query!r}"
    actual = result[0]["name"]
    assert actual == expected_top, f"Query {query!r}: expected {expected_top!r}, got {actual!r}"


# ---------------------------------------------------------------------------
# 15. Long reason does not crash or hang
# ---------------------------------------------------------------------------


def test_very_long_reason_does_not_crash() -> None:
    corpus = [
        {
            "name": "fmp__statements",
            "description": "income statement balance sheet cash flow",
            "category": "financial",
        }
    ]
    long_reason = "quarterly income statement " * 200  # ~5400 chars
    result = rank_candidates(corpus, reason=long_reason, category_hint=None)
    # Must not raise; result is list (possibly empty or not)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# IDF helper sanity checks
# ---------------------------------------------------------------------------


def test_idf_empty_corpus_returns_empty_dict() -> None:
    assert _idf_for_corpus([]) == {}


def test_idf_rare_token_scores_higher_than_common() -> None:
    corpus = [
        {"name": "tool_a", "description": "income statement quarterly report"},
        {"name": "tool_b", "description": "quarterly earnings report"},
        {"name": "tool_c", "description": "quarterly filings"},
        # "income" appears only in tool_a; "quarterly" appears in all three
    ]
    idf = _idf_for_corpus(corpus)
    assert idf["income"] > idf["quarterly"]
