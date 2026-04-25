"""Tests for the cross-source reliability weight helpers."""

from __future__ import annotations

from openlia.retail_sentiment.reliability import (
    DEFAULT_SOURCE_WEIGHTS,
    _normalize_weights,
    weight_for_source,
)


def test_default_weights_sum_to_one():
    assert abs(sum(DEFAULT_SOURCE_WEIGHTS.values()) - 1.0) < 1e-9


def test_normalize_renormalizes_unbalanced_input():
    out = _normalize_weights({"a": 2.0, "b": 1.0, "c": 1.0})
    assert abs(sum(out.values()) - 1.0) < 1e-9
    assert out["a"] == 0.5
    assert out["b"] == 0.25
    assert out["c"] == 0.25


def test_normalize_with_zero_total_returns_defaults():
    out = _normalize_weights({"a": 0.0, "b": 0.0})
    assert out == DEFAULT_SOURCE_WEIGHTS


def test_normalize_with_negative_clamps_to_zero():
    out = _normalize_weights({"a": -1.0, "b": 1.0})
    assert out["a"] == 0.0
    assert out["b"] == 1.0


def test_weight_for_source_uses_default_table():
    w = weight_for_source("financial_provider")
    assert w == DEFAULT_SOURCE_WEIGHTS["financial_provider"]


def test_weight_for_source_falls_back_for_unknown():
    assert weight_for_source("unknown_src") == 0.0
    assert weight_for_source("unknown_src", default=0.123) == 0.123


def test_weight_for_source_uses_override_table():
    w = weight_for_source(
        "social_media",
        weights={"social_media": 1.0, "financial_provider": 1.0},
    )
    assert abs(w - 0.5) < 1e-9
