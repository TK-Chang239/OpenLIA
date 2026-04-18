"""Core data types for the provider adapter system.

ProviderEntry is the in-memory shape every adapter receives at construction
time. Server code builds this from a data_providers DB row (decrypting the
api_key column) before handing it to the adapter. Adapters never touch the
database themselves.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderCategory(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL_MEDIA = "social_media"


class ProviderMode(StrEnum):
    API_KEY = "api_key"
    MCP = "mcp"


class ProviderEntry(BaseModel):
    """In-memory representation of a configured data provider.

    Populated by the server service layer from a `data_providers` row with the
    encrypted `api_key_encrypted` column already decrypted into `api_key`.
    The adapter uses `base_url` (api_key mode) or `mcp_url` (mcp mode) to
    construct requests. `priority` comes from data_provider_requirement_mapping
    when iterating providers for a specific requirement, or defaults to 100.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    label: str
    category: ProviderCategory
    mode: ProviderMode

    api_key: str | None = None
    base_url: str | None = None

    mcp_url: str | None = None
    mcp_auth_header: str | None = None

    extra_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True
    priority: int = 100

    @model_validator(mode="after")
    def _transport_requirements(self) -> "ProviderEntry":
        if self.mode is ProviderMode.API_KEY and not self.base_url:
            raise ValueError("api_key mode requires base_url")
        if self.mode is ProviderMode.MCP and not self.mcp_url:
            raise ValueError("mcp mode requires mcp_url")
        return self


class ToolResult(BaseModel):
    """The uniform shape every adapter.fetch(...) coroutine resolves to.

    The runtime dispatch layer (Plan 5) consumes this and serializes it into
    the SSE `chat.tool_result` / `report.tool_result` payload for the LLM.
    """

    model_config = ConfigDict(frozen=True)

    provider_kind: str
    capability: str
    payload: dict[str, Any] | list[Any]
