from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest


def _entry(provider: str, identifier: str, payload=None) -> dict:
    return {
        "kind": "fetch",
        "provider": provider,
        "identifier": identifier,
        "raw_payload": payload or {},
        "retrieved_at": "2026-05-17T20:00:00Z",
    }


def test_append_assigns_monotonic_ids() -> None:
    m = Manifest()
    a = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    b = m.append(**_entry("eodhd", "get_holders/NET.US"))
    assert a.id == 1
    assert b.id == 2


def test_append_dedupes_by_identifier_returns_existing() -> None:
    m = Manifest()
    a = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    b = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    assert a.id == b.id == 1
    assert len(m.entries) == 1


def test_resolve_known_marker() -> None:
    m = Manifest()
    e = m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    assert m.resolve(e.id) is e


def test_resolve_unknown_marker_raises() -> None:
    m = Manifest()
    with pytest.raises(KeyError):
        m.resolve(99)


def test_as_prompt_list_renders_compact_form() -> None:
    m = Manifest()
    m.append(**_entry("eodhd", "get_fundamentals_data/NET.US"))
    m.append(**_entry("websearch", "edge platform market TAM 2025"))
    rendered = m.as_prompt_list()
    assert "[1] eodhd/get_fundamentals_data/NET.US" in rendered
    assert "[2] websearch/edge platform market TAM 2025" in rendered
