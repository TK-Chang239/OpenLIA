from __future__ import annotations

import pytest
from openlia.llm.runtime.payload_path import (
    PathParseError,
    PathResolveError,
    apply_path,
)

# --- None / empty path ---


def test_none_path_returns_payload() -> None:
    payload = {"a": 1}
    assert apply_path(payload, None) is payload


def test_empty_path_returns_payload() -> None:
    payload = {"a": 1}
    assert apply_path(payload, "") is payload


# --- Single key ---


def test_single_key_access() -> None:
    assert apply_path({"a": 1}, "a") == 1


# --- Nested key ---


def test_nested_key_access() -> None:
    assert apply_path({"a": {"b": 2}}, "a.b") == 2


# --- Array index ---


def test_array_index_positive() -> None:
    assert apply_path({"rows": [10, 20, 30]}, "rows[1]") == 20


def test_array_index_negative() -> None:
    assert apply_path({"rows": [10, 20, 30]}, "rows[-1]") == 30


# --- Slice ---


def test_slice_both_bounds() -> None:
    assert apply_path({"rows": [10, 20, 30, 40]}, "rows[1:3]") == [20, 30]


def test_slice_omit_lo() -> None:
    assert apply_path({"rows": [10, 20, 30]}, "rows[:3]") == [10, 20, 30]


def test_slice_omit_hi() -> None:
    assert apply_path({"rows": [10, 20, 30, 40]}, "rows[2:]") == [30, 40]


# --- Column projection ---


def test_column_projection() -> None:
    rows = [{"x": 1}, {"x": 2}, {"x": 3}]
    assert apply_path({"rows": rows}, "rows.x") == [1, 2, 3]


# --- Composition ---


def test_slice_then_project() -> None:
    rows = [{"x": 1}, {"x": 2}, {"x": 3}]
    assert apply_path({"rows": rows}, "rows[0:2].x") == [1, 2]


def test_nav_then_index_then_key() -> None:
    payload = {"data": {"rows": [{"x": 1}]}}
    assert apply_path(payload, "data.rows[-1].x") == 1


# --- Parse errors ---


def test_parse_error_bad_syntax() -> None:
    with pytest.raises(PathParseError):
        apply_path({}, "rows[abc]")


def test_parse_error_unbalanced_bracket() -> None:
    with pytest.raises(PathParseError):
        apply_path({}, "rows[1")


def test_leading_dot_is_normalized() -> None:
    # Leading dot is a mechanical typo — normalized away rather than rejected.
    assert apply_path({"rows": 1}, ".rows") == 1


# --- Resolve errors ---


def test_resolve_missing_key_mentions_available() -> None:
    with pytest.raises(PathResolveError, match="available keys"):
        apply_path({"a": 1}, "b")


def test_resolve_index_out_of_bounds() -> None:
    with pytest.raises(PathResolveError, match="out of bounds"):
        apply_path({"r": [1, 2]}, "r[5]")


def test_resolve_wrong_type_for_index() -> None:
    with pytest.raises(PathResolveError):
        apply_path({"r": 5}, "r[0]")


# --- Edge case: dict access (not list) for dot-access ---


def test_dot_access_on_dict_returns_value_not_list() -> None:
    # "r.x" where r is a plain dict — should return dict["x"], not a list.
    assert apply_path({"r": {"x": 1}}, "r.x") == 1


# --- Normalization of common bad forms (silently fixed before parsing) ---


def test_normalize_strips_leading_dollar() -> None:
    assert apply_path({"a": 1}, "$.a") == 1


def test_normalize_strips_bare_leading_dollar() -> None:
    assert apply_path({"a": 1}, "$a") == 1


def test_normalize_bracket_string_single_quote() -> None:
    assert apply_path({"rows": [{"date": "x"}]}, "rows['date']") == ["x"]


def test_normalize_bracket_string_double_quote() -> None:
    assert apply_path({"rows": [{"date": "x"}]}, 'rows["date"]') == ["x"]


def test_normalize_leading_bracket_string() -> None:
    assert apply_path({"rows": [1, 2, 3]}, "['rows'][0]") == 1


def test_normalize_collapses_double_dots() -> None:
    assert apply_path({"a": {"b": 2}}, "a..b") == 2


def test_normalize_strips_trailing_dot() -> None:
    assert apply_path({"a": 1}, "a.") == 1


def test_normalize_strips_whitespace() -> None:
    assert apply_path({"a": {"b": 2}}, "  a.b  ") == 2


def test_normalize_wildcard_becomes_projection() -> None:
    rows = [{"x": 1}, {"x": 2}]
    assert apply_path({"rows": rows}, "rows[*].x") == [1, 2]


def test_normalize_preserves_valid_path() -> None:
    rows = [{"x": 1}, {"x": 2}]
    assert apply_path({"rows": rows}, "rows[0:2].x") == [1, 2]


def test_filter_expression_still_errors() -> None:
    # We don't try to silently fix predicate filters — they change semantics.
    with pytest.raises(PathParseError):
        apply_path({"rows": []}, "rows[?(@.x>0)]")


# --- Provider-payload key shapes (date keys, numeric keys) ---


def test_dotted_date_key_resolves() -> None:
    # Provider fundamentals nest by ISO date; the LLM drills via dotted form.
    payload = {
        "Financials": {
            "Income_Statement": {
                "yearly": {"2026-01-31": {"totalRevenue": 281700}},
            },
        },
    }
    assert apply_path(payload, "Financials.Income_Statement.yearly.2026-01-31") == {
        "totalRevenue": 281700
    }


def test_dotted_date_key_then_field_resolves() -> None:
    payload = {"yearly": {"2026-01-31": {"totalRevenue": 281700}}}
    assert apply_path(payload, "yearly.2026-01-31.totalRevenue") == 281700


def test_bracket_string_date_key_resolves() -> None:
    payload = {"yearly": {"2026-01-31": {"totalRevenue": 281700}}}
    assert apply_path(payload, 'yearly["2026-01-31"]') == {"totalRevenue": 281700}


def test_numeric_leading_key_resolves() -> None:
    # EODHD outstandingShares.annual uses string-integer keys like "0", "1".
    payload = {"annual": {"0": {"shares": 7_400_000_000}}}
    assert apply_path(payload, "annual.0.shares") == 7_400_000_000


def test_leading_hyphen_still_rejected() -> None:
    # A bareword cannot start with a hyphen; that would collide with -idx.
    with pytest.raises(PathParseError):
        apply_path({"-x": 1}, "-x")


# --- Bracket-quoted keys with arbitrary characters ---
# Real provider payloads contain keys with spaces, dots, %, /, &, etc.
# Bareword syntax cannot express these — bracket-string is the canonical
# fallback. Inner content of a quoted bracket key is taken verbatim.


def test_bracket_string_key_with_space() -> None:
    # FMP segment data: keys like "Intelligent Cloud", "More Personal Computing".
    payload = {"segments": {"Intelligent Cloud": {"revenue": 105_360}}}
    assert apply_path(payload, 'segments["Intelligent Cloud"]') == {"revenue": 105_360}


def test_bracket_string_key_with_dot() -> None:
    # EODHD ETF holdings: keys are tickers like "AAPL.US", "BRK-B.US".
    payload = {"Holdings": {"AAPL.US": {"Code": "AAPL", "Pct": 7.2}}}
    assert apply_path(payload, 'Holdings["AAPL.US"]') == {"Code": "AAPL", "Pct": 7.2}


def test_bracket_string_key_with_percent_sign() -> None:
    # EODHD fund composition: keys like "Long_%", "Equity_%", "Assets_%".
    payload = {"AssetAllocation": {"Long_%": "99.6"}}
    assert apply_path(payload, 'AssetAllocation["Long_%"]') == "99.6"


def test_bracket_string_key_with_slash() -> None:
    # EODHD geographic regions: "Africa/Middle East".
    payload = {"World": {"Africa/Middle East": {"Equity_%": "0"}}}
    assert apply_path(payload, 'World["Africa/Middle East"]') == {"Equity_%": "0"}


def test_bracket_string_key_with_ampersand_and_spaces() -> None:
    # MSFT segment key: "Productivity & Business Processes".
    payload = {
        "Segments": {"Productivity & Business Processes": {"mix": 31.8}},
    }
    assert apply_path(payload, 'Segments["Productivity & Business Processes"]') == {"mix": 31.8}


def test_bracket_string_key_at_path_start() -> None:
    # Bracket-quoted key can also be the very first token of the path.
    payload = {"Basic Materials": {"Equity_%": "1.75"}}
    assert apply_path(payload, '["Basic Materials"]') == {"Equity_%": "1.75"}


def test_bracket_string_key_then_dotted_subkey() -> None:
    # Composition: bracket key followed by a dotted sub-access.
    payload = {"Holdings": {"BRK-B.US": {"Code": "BRK-B"}}}
    assert apply_path(payload, 'Holdings["BRK-B.US"].Code') == "BRK-B"


def test_bracket_string_key_single_quoted() -> None:
    # Single-quote form is supported alongside double-quote.
    payload = {"Sectors": {"Health Care": 11.2}}
    assert apply_path(payload, "Sectors['Health Care']") == 11.2


def test_bracket_string_unclosed_quote_errors() -> None:
    with pytest.raises(PathParseError):
        apply_path({"a": 1}, '["a')
