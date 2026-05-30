"""Compute the effective Earnings Update v2 data-source availability.

Phase 1: the engine has three capability slots (financial, earnings
calendar, web search). A slot is "available" only when the engine can
actually use it today — EODHD env-or-connector key for the financial
slots, model-native capability for web search. Connectors that exist
but cannot yet be routed are surfaced separately as ``other_connectors``
(routing arrives in Phase 2).
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.types import ConnectorStatus
from openlia.llm.capabilities import capabilities_for
from sqlalchemy.orm import Session

from openlia_server.services import connectors_service, eu_v2_settings
from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

_REASON_EODHD = "eodhd_unconfigured"
_REASON_WS = "model_no_web_search"
_EODHD_PROVIDER_ID = "eodhd"


@dataclass(frozen=True)
class DataSourceSlot:
    available: bool
    provider_label: str | None
    unavailable_reason: str | None


@dataclass(frozen=True)
class OtherConnector:
    display_name: str
    category: str


@dataclass(frozen=True)
class EuDataSources:
    financial: DataSourceSlot
    earnings_calendar: DataSourceSlot
    web_search: DataSourceSlot
    other_connectors: list[OtherConnector]


def _eodhd_slot(available: bool) -> DataSourceSlot:
    return DataSourceSlot(
        available=available,
        provider_label="EODHD" if available else None,
        unavailable_reason=None if available else _REASON_EODHD,
    )


def compute_data_sources(
    db: Session,
    *,
    user_id: str,
    provider_kind: str | None = None,
    model: str | None = None,
) -> EuDataSources:
    """Return the engine's effective data-source availability.

    ``provider_kind`` / ``model`` override the persisted settings so the
    settings modal can preview web-search availability for an unsaved
    model selection.
    """
    settings = eu_v2_settings.get_settings(db, user_id=user_id)
    effective_kind = provider_kind or settings.provider_kind
    effective_model = model or settings.model

    eodhd_available = resolve_eodhd_api_key(db) is not None
    financial = _eodhd_slot(eodhd_available)
    earnings_calendar = _eodhd_slot(eodhd_available)

    caps = capabilities_for(provider_kind=effective_kind, model=effective_model)
    ws_available = caps.web_search_native
    web_search = DataSourceSlot(
        available=ws_available,
        provider_label=effective_model if ws_available else None,
        unavailable_reason=None if ws_available else _REASON_WS,
    )

    other = [
        OtherConnector(display_name=c.display_name, category=c.category)
        for c in connectors_service.list_connectors(db)
        if c.status == ConnectorStatus.VALIDATED.value and c.provider_id != _EODHD_PROVIDER_ID
    ]

    return EuDataSources(
        financial=financial,
        earnings_calendar=earnings_calendar,
        web_search=web_search,
        other_connectors=other,
    )
