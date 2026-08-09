"""Tests for the shared news-scanning helpers."""

from __future__ import annotations

from openlia.panic_thermometer.panels._scanning import (
    article_text,
    keyword_hit,
    matching_articles,
)


def test_keyword_hit_matches_whole_words_only() -> None:
    assert keyword_hit("The Fed stays patient", ["patient"]) == "patient"
    # word-boundary: "patient" must not match inside "impatient"
    assert keyword_hit("Markets grow impatient", ["patient"]) is None


def test_keyword_hit_matches_multiword_phrase_case_insensitively() -> None:
    assert keyword_hit("Officials cite Persistent Inflation", ["persistent inflation"]) == (
        "persistent inflation"
    )


def test_keyword_hit_scans_headline_and_summary() -> None:
    text = article_text({"headline": "Jobs report", "summary": "talk of a ceasefire"})
    assert keyword_hit(text, ["ceasefire"]) == "ceasefire"


def test_matching_articles_returns_every_match() -> None:
    articles = [
        {"headline": "Ceasefire reached", "summary": ""},
        {"headline": "Markets rally", "summary": "no news"},
        {"headline": "Second ceasefire holds", "summary": ""},
    ]
    matched = matching_articles(articles, ["ceasefire"])
    assert len(matched) == 2
    assert all(kw == "ceasefire" for kw, _ in matched)
