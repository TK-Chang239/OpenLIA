from __future__ import annotations

from openlia.llm.runtime.web_search import WebSearchResolution, WebSearchResult


def test_web_search_resolution_native_variant() -> None:
    r = WebSearchResolution(available=True, variant="native")
    assert r.available is True
    assert r.variant == "native"


def test_web_search_resolution_unavailable() -> None:
    r = WebSearchResolution(available=False, variant=None)
    assert r.available is False
    assert r.variant is None


def test_web_search_result_shape() -> None:
    r = WebSearchResult(title="T", url="https://u", snippet="S")
    assert r.title == "T"
    assert r.url == "https://u"
    assert r.snippet == "S"
