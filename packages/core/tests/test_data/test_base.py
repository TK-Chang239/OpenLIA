from typing import Any

import pytest
from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode, ToolResult


class _StubAdapter(ProviderAdapter):
    kind = "stub"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote", "historical_prices"})

    async def fetch(
        self,
        capability: str,
        params: dict[str, Any],
    ) -> ToolResult:
        if capability not in self.capabilities:
            raise DataNotAvailable(
                provider_kind=self.kind,
                capability=capability,
                reason="not declared",
            )
        return ToolResult(
            provider_kind=self.kind,
            capability=capability,
            payload={"params": params},
        )

    async def health_check(self) -> bool:
        return True


def _entry() -> ProviderEntry:
    return ProviderEntry(
        id="00000000-0000-0000-0000-000000000001",
        kind="stub",
        label="Stub",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
    )


def test_adapter_is_abstract() -> None:
    with pytest.raises(TypeError):
        ProviderAdapter(_entry())  # type: ignore[abstract]


def test_stub_adapter_records_entry() -> None:
    adapter = _StubAdapter(_entry())
    assert adapter.entry.kind == "stub"
    assert adapter.kind == "stub"


def test_stub_adapter_declares_capabilities() -> None:
    adapter = _StubAdapter(_entry())
    assert "stock_quote" in adapter.capabilities
    assert "historical_prices" in adapter.capabilities
    assert "company_news" not in adapter.capabilities


async def test_stub_adapter_fetch_returns_tool_result() -> None:
    adapter = _StubAdapter(_entry())
    result = await adapter.fetch("stock_quote", {"symbol": "AAPL"})
    assert isinstance(result, ToolResult)
    assert result.capability == "stock_quote"
    assert result.payload == {"params": {"symbol": "AAPL"}}


async def test_stub_adapter_fetch_unknown_raises_data_not_available() -> None:
    adapter = _StubAdapter(_entry())
    with pytest.raises(DataNotAvailable) as exc:
        await adapter.fetch("insider_transactions", {})
    assert exc.value.provider_kind == "stub"
    assert exc.value.capability == "insider_transactions"


async def test_stub_adapter_health_check() -> None:
    adapter = _StubAdapter(_entry())
    assert await adapter.health_check() is True


def test_entry_kind_must_match_adapter_kind() -> None:
    wrong = ProviderEntry(
        id="00000000-0000-0000-0000-000000000002",
        kind="eodhd",
        label="Wrong",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
    )
    with pytest.raises(ValueError, match="kind mismatch"):
        _StubAdapter(wrong)
