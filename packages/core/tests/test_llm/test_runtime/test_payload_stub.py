from __future__ import annotations

import json

from openlia.llm.runtime.payload_stub import (
    RECORD_STRING_VALUE_MAX_CHARS,
    TABULAR_STRING_VALUE_MAX_CHARS,
    generate_stub,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REF = "run-abc/tool-xyz"
TOOL = "financial_statements"


def stub(payload, *, ref=REF, tool_name=TOOL):
    return generate_stub(payload, ref=ref, tool_name=tool_name)


def common_fields(s, shape):
    """Assert the six mandatory fields are present and correct."""
    assert s["ref"] == REF
    assert s["tool"] == TOOL
    assert s["shape"] == shape
    assert isinstance(s["size_chars"], int)
    assert s["truncated"] is True


# ---------------------------------------------------------------------------
# Test 1: Empty list → tabular n_rows=0
# ---------------------------------------------------------------------------


def test_empty_list_is_tabular_zero_rows():
    s = stub([])
    common_fields(s, "tabular")
    assert s["n_rows"] == 0
    assert s["columns"] == []
    assert s["sample"] == []


# ---------------------------------------------------------------------------
# Test 2: Single-row tabular
# ---------------------------------------------------------------------------


def test_single_row_tabular():
    s = stub([{"a": 1, "b": 2}])
    common_fields(s, "tabular")
    assert s["n_rows"] == 1
    assert set(s["columns"]) == {"a", "b"}


# ---------------------------------------------------------------------------
# Test 3: Standard tabular — 10 rows {a, b, c}, no time column
# ---------------------------------------------------------------------------


def test_standard_tabular_10_rows():
    rows = [{"a": i, "b": i * 2, "c": f"val{i}"} for i in range(10)]
    s = stub(rows)
    common_fields(s, "tabular")
    assert s["n_rows"] == 10
    assert sorted(s["columns"]) == ["a", "b", "c"]
    assert len(s["sample"]) == 3


# ---------------------------------------------------------------------------
# Test 4: Time-series with ISO dates, ascending
# ---------------------------------------------------------------------------


def test_time_series_iso_dates_ascending():
    rows = [{"date": f"20{20 + i:02d}-01-01", "value": i * 100} for i in range(10)]
    s = stub(rows)
    common_fields(s, "time_series")
    assert s["ordering"] == "asc"
    assert s["period_range"] == ["2020-01-01", "2029-01-01"]
    assert "head" in s["sample"]
    assert "tail" in s["sample"]


# ---------------------------------------------------------------------------
# Test 5: Time-series with quarter strings
# ---------------------------------------------------------------------------


def test_time_series_quarter_strings():
    rows = [
        {"period": "2024Q1", "revenue": 100},
        {"period": "2024Q2", "revenue": 110},
    ]
    s = stub(rows)
    common_fields(s, "time_series")
    assert s["ordering"] == "asc"


# ---------------------------------------------------------------------------
# Test 6: Time-series descending
# ---------------------------------------------------------------------------


def test_time_series_descending():
    rows = [{"date": f"202{9 - i}-01-01", "value": i} for i in range(5)]
    s = stub(rows)
    common_fields(s, "time_series")
    assert s["ordering"] == "desc"


# ---------------------------------------------------------------------------
# Test 7: Heterogeneous list → unknown_list
# ---------------------------------------------------------------------------


def test_heterogeneous_list_is_unknown_list():
    payload = [1, "two", {"three": 3}, [4, 5]]
    s = stub(payload)
    common_fields(s, "unknown_list")
    assert s["n_items"] == 4
    assert len(s["sample"]) == 2


# ---------------------------------------------------------------------------
# Test 8: Single dict, primitives → record
# ---------------------------------------------------------------------------


def test_single_dict_primitives_is_record():
    payload = {"name": "Apple", "ticker": "AAPL", "price": 190.5}
    s = stub(payload)
    common_fields(s, "record")
    assert "name" in s["top_keys"]
    assert "name" in s["sample"]


# ---------------------------------------------------------------------------
# Test 9: Long description in record value → truncated at 200 chars in sample
# ---------------------------------------------------------------------------


def test_record_long_string_value_truncated():
    long_val = "x" * 400
    payload = {"description": long_val, "ticker": "AAPL"}
    s = stub(payload)
    common_fields(s, "record")
    assert len(s["sample"]["description"]) == RECORD_STRING_VALUE_MAX_CHARS


# ---------------------------------------------------------------------------
# Test 10: Nested: dict-of-dicts → nested with subshapes
# ---------------------------------------------------------------------------


def test_nested_dict_of_dicts():
    payload = {
        "income_statement": [
            {"year": 2020, "revenue": 100},
            {"year": 2021, "revenue": 110},
            {"year": 2022, "revenue": 120},
            {"year": 2023, "revenue": 130},
            {"year": 2024, "revenue": 140},
            {"year": 2025, "revenue": 150},
            {"year": 2026, "revenue": 160},
            {"year": 2027, "revenue": 170},
            {"year": 2028, "revenue": 180},
            {"year": 2029, "revenue": 190},
            {"year": 2030, "revenue": 200},
            {"year": 2031, "revenue": 210},
        ],
        "balance_sheet": {"assets": 500, "liabilities": 300},
    }
    s = stub(payload)
    common_fields(s, "nested")
    assert "income_statement" in s["subshapes"]
    assert "balance_sheet" in s["subshapes"]
    # income_statement is a list-of-dicts with year integers → check it's detected
    assert "income_statement" in s["top_keys"]


# ---------------------------------------------------------------------------
# Test 11: Wide table (50 columns) → columns capped at 20
# ---------------------------------------------------------------------------


def test_wide_table_columns_capped():
    rows = [{f"col{i}": i for i in range(50)} for _ in range(5)]
    s = stub(rows)
    common_fields(s, "tabular")
    assert len(s["columns"]) == 20
    assert s["n_columns"] == 50
    assert s["columns_truncated"] is True


# ---------------------------------------------------------------------------
# Test 12: Sample row string values capped at 100 chars
# ---------------------------------------------------------------------------


def test_tabular_sample_string_values_capped():
    long_str = "a" * 300
    rows = [{"name": long_str, "value": i} for i in range(5)]
    s = stub(rows)
    common_fields(s, "tabular")
    for row in s["sample"]:
        assert len(row["name"]) == TABULAR_STRING_VALUE_MAX_CHARS


# ---------------------------------------------------------------------------
# Test 13: unknown_dict for weird dict structure
# ---------------------------------------------------------------------------


def test_unknown_dict_weird_structure():
    # A dict where values are all non-dict, non-list-of-dict primitives
    # and structures that don't trigger nested
    payload = {"a": 1, "b": "hello"}
    s = stub(payload)
    # This is a simple record (all primitives)
    common_fields(s, "record")

    # For a genuinely weird dict: mixed complex values that don't fit nested
    payload2 = {"x": 42, "y": [1, 2, 3], "z": "text"}
    s2 = stub(payload2)
    # y is a list but not list-of-dicts, so not nested → record or unknown_dict
    assert s2["shape"] in ("record", "unknown_dict")
    assert s2["truncated"] is True


# ---------------------------------------------------------------------------
# Test 14: Non-list, non-dict → unknown_dict with sample_repr
# ---------------------------------------------------------------------------


def test_non_collection_becomes_unknown_dict():
    for payload in [42, "some string", 3.14, True, None]:
        s = stub(payload)
        common_fields(s, "unknown_dict")
        assert "sample_repr" in s
        assert isinstance(s["sample_repr"], str)


# ---------------------------------------------------------------------------
# Test 15: size_chars matches json.dumps len
# ---------------------------------------------------------------------------


def test_size_chars_matches_json_dumps():
    payload = [{"a": i, "b": f"val{i}"} for i in range(20)]
    s = stub(payload)
    expected = len(json.dumps(payload, default=str))
    assert s["size_chars"] == expected


# ---------------------------------------------------------------------------
# Test 16: All stubs include ref, tool, shape, size_chars, truncated
# ---------------------------------------------------------------------------


def test_all_shapes_have_mandatory_fields():
    payloads = [
        [],  # tabular
        [{"date": "2020-01-01", "v": 1}, {"date": "2021-01-01", "v": 2}],  # time_series
        {"k": "v"},  # record
        {"a": {"x": 1, "y": 2}, "b": {"x": 3, "y": 4}},  # nested
        [1, "two", 3.0],  # unknown_list
        42,  # unknown_dict
    ]
    for payload in payloads:
        s = generate_stub(payload, ref=REF, tool_name=TOOL)
        assert "ref" in s, f"missing ref for {type(payload)}"
        assert "tool" in s, f"missing tool for {type(payload)}"
        assert "shape" in s, f"missing shape for {type(payload)}"
        assert "size_chars" in s, f"missing size_chars for {type(payload)}"
        assert s["truncated"] is True, f"truncated not True for {type(payload)}"


# ---------------------------------------------------------------------------
# Test 17: Tabular with date column but unsorted → tabular NOT time_series
# ---------------------------------------------------------------------------


def test_unsorted_date_column_stays_tabular():
    rows = [
        {"date": "2020-01-01", "v": 1},
        {"date": "2025-01-01", "v": 5},
        {"date": "2022-01-01", "v": 3},
    ]
    s = stub(rows)
    common_fields(s, "tabular")


# ---------------------------------------------------------------------------
# Test 18: Single-element list of dict → tabular with n_rows=1
# ---------------------------------------------------------------------------


def test_single_element_list_of_dict_is_tabular():
    s = stub([{"ticker": "AAPL", "price": 190}])
    common_fields(s, "tabular")
    assert s["n_rows"] == 1
