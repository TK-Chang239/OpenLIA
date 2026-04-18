import pytest
from openlia.data.types import (
    ProviderCategory,
    ProviderEntry,
    ProviderMode,
    ToolResult,
)
from pydantic import ValidationError


def test_provider_category_values() -> None:
    assert ProviderCategory.FINANCIAL.value == "financial"
    assert ProviderCategory.NEWS.value == "news"
    assert ProviderCategory.SOCIAL_MEDIA.value == "social_media"


def test_provider_mode_values() -> None:
    assert ProviderMode.API_KEY.value == "api_key"
    assert ProviderMode.MCP.value == "mcp"


def test_provider_entry_minimal_api_key_mode() -> None:
    entry = ProviderEntry(
        id="11111111-1111-1111-1111-111111111111",
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="secret-key",
        base_url="https://eodhd.com/api",
    )
    assert entry.kind == "eodhd"
    assert entry.api_key == "secret-key"
    assert entry.is_enabled is True
    assert entry.priority == 100


def test_provider_entry_mcp_mode_requires_mcp_url() -> None:
    with pytest.raises(ValidationError):
        ProviderEntry(
            id="2" * 36,
            kind="custom_mcp",
            label="Custom",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.MCP,
            mcp_url=None,
        )


def test_provider_entry_api_key_mode_requires_base_url() -> None:
    with pytest.raises(ValidationError):
        ProviderEntry(
            id="3" * 36,
            kind="eodhd",
            label="EODHD",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.API_KEY,
            base_url=None,
        )


def test_provider_entry_priority_and_disabled() -> None:
    entry = ProviderEntry(
        id="4" * 36,
        kind="fmp",
        label="FMP",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://financialmodelingprep.com/api/v3",
        is_enabled=False,
        priority=50,
    )
    assert entry.is_enabled is False
    assert entry.priority == 50


def test_tool_result_round_trip_dict() -> None:
    result = ToolResult(
        provider_kind="eodhd",
        capability="stock_quote",
        payload={"symbol": "AAPL", "price": 225.1},
    )
    dumped = result.model_dump()
    assert dumped["provider_kind"] == "eodhd"
    assert dumped["payload"]["symbol"] == "AAPL"


def test_tool_result_payload_can_be_list() -> None:
    result = ToolResult(
        provider_kind="eodhd",
        capability="historical_prices",
        payload=[{"date": "2026-04-10", "close": 220.0}],
    )
    assert isinstance(result.payload, list)
