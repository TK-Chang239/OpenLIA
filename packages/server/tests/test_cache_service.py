"""Tests for SQLAlchemyCacheStore (F5 cache service)."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.connectors.base import ToolResult
from openlia_server.db.base import Base
from openlia_server.db.models import register_all  # noqa: F401 — register all ORM models
from openlia_server.services.cache_service import SQLAlchemyCacheStore
from sqlalchemy import create_engine


@pytest.fixture()
def mem_engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def store(mem_engine):
    """Return a SQLAlchemyCacheStore wired to the in-memory engine."""
    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=mem_engine, autoflush=False, autocommit=False)

    def _session():
        return factory()

    return SQLAlchemyCacheStore(session_factory=_session)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_miss_returns_none(store):
    assert store.get("nonexistent:key:_:abc123456789") is None


def test_upsert_then_get_returns_row(store):
    result = ToolResult(content="financials payload", metadata={"source": "eodhd"})
    key = "eodhd:get_financials:AAPL:2024Q1"

    store.upsert(key, result, adapter_name="eodhd", tool="get_financials")
    doc = store.get(key)

    assert doc is not None
    assert doc.content_text == "financials payload"
    assert doc.raw_metadata == {"source": "eodhd"}
    assert doc.ticker == "AAPL"
    assert doc.fiscal_period == "2024Q1"
    assert doc.source == "eodhd"
    assert doc.bytes_size == len(b"financials payload")


def test_upsert_non_string_content_converts(store):
    result = ToolResult(content={"key": "value"}, metadata={})
    key = "sdk:get_data:MSFT:2023Q4"
    store.upsert(key, result, adapter_name="sdk", tool="get_data")
    doc = store.get(key)
    assert isinstance(doc.content_text, str)
    assert "key" in doc.content_text


def test_upsert_overwrites_existing(store):
    key = "eodhd:get_financials:TSLA:2024Q2"
    result1 = ToolResult(content="old data", metadata={})
    store.upsert(key, result1, adapter_name="eodhd", tool="get_financials")

    result2 = ToolResult(content="new data", metadata={"updated": True})
    store.upsert(key, result2, adapter_name="eodhd", tool="get_financials")

    doc = store.get(key)
    assert doc.content_text == "new data"
    assert doc.raw_metadata == {"updated": True}


def test_ticker_none_when_underscore(store):
    """Cache key with underscore ticker -> ticker column is NULL."""
    key = "web:search:_:abc123456789"
    result = ToolResult(content="search results", metadata={})
    store.upsert(key, result, adapter_name="web", tool="search")
    doc = store.get(key)
    assert doc.ticker is None


def test_bytes_size_matches_utf8_encoding(store):
    content = "hello world"
    key = "eodhd:get_news:NVDA:xyz123456789"
    store.upsert(
        key, ToolResult(content=content, metadata={}), adapter_name="eodhd", tool="get_news"
    )
    doc = store.get(key)
    assert doc.bytes_size == len(content.encode())
