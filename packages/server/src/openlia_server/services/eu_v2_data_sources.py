"""Compute the effective Earnings Update v2 data-source list.

The list is dynamic and registry-driven: it changes as connectors are
added or removed. Three kinds of source surface:

- The curated EODHD slot (key ``eodhd``, ``routing="curated"``), available
  when an EODHD key resolves from env or an installed connector.
- One dispatcher-routed entry per *other* validated connector
  (``routing="dispatcher"``), keyed by the connector's ``provider_id``.
- The model-native web-search slot (key ``model_web_search``,
  ``routing="model_native"``), available per the selected model's
  capability.

``available`` reflects whether the engine can use the source today;
``enabled`` reflects the user's per-source toggle in settings.
"""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.types import ConnectorStatus
from openlia.llm.capabilities import capabilities_for
from sqlalchemy.orm import Session

from openlia_server.services import connectors_service, eu_v2_settings
from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key
from openlia_server.services.llm_providers import get_capability_override

_REASON_EODHD = "eodhd_unconfigured"
_REASON_WS = "model_no_web_search"
_EODHD_PROVIDER_ID = "eodhd"
_WEB_SEARCH_KEY = "model_web_search"


@dataclass(frozen=True)
class DataSource:
    key: str  # provider_id, or "model_web_search"
    display_name: str
    category: str  # financial | news | social | web_search
    routing: str  # "curated" | "dispatcher" | "model_native"
    available: bool
    enabled: bool
    unavailable_reason: str | None  # reason code or None


@dataclass(frozen=True)
class EuDataSources:
    sources: list[DataSource]


def compute_data_sources(
    db: Session,
    *,
    user_id: str,
    provider_kind: str | None = None,
    model: str | None = None,
) -> EuDataSources:
    """Return the engine's effective data-source list.

    ``provider_kind`` / ``model`` override the persisted settings so the
    settings modal can preview web-search availability for an unsaved
    model selection.
    """
    settings = eu_v2_settings.get_settings(db, user_id=user_id)
    effective_kind = provider_kind or settings.provider_kind
    effective_model = model or settings.model
    enabled_ids = settings.enabled_provider_ids
    ws_enabled = settings.web_search_enabled

    sources: list[DataSource] = []

    # 1. Curated EODHD slot.
    eodhd_available = resolve_eodhd_api_key(db) is not None
    sources.append(
        DataSource(
            key=_EODHD_PROVIDER_ID,
            display_name="EODHD",
            category="financial",
            routing="curated",
            available=eodhd_available,
            enabled=_EODHD_PROVIDER_ID in enabled_ids,
            unavailable_reason=None if eodhd_available else _REASON_EODHD,
        )
    )

    # 2. One dispatcher-routed entry per other validated connector.
    others = [
        c
        for c in connectors_service.list_connectors(db)
        if c.status == ConnectorStatus.VALIDATED.value and c.provider_id != _EODHD_PROVIDER_ID
    ]
    for c in sorted(others, key=lambda row: row.display_name):
        sources.append(
            DataSource(
                key=c.provider_id,
                display_name=c.display_name,
                category=c.category,
                routing="dispatcher",
                available=True,
                enabled=c.provider_id in enabled_ids,
                unavailable_reason=None,
            )
        )

    # 3. Model-native web-search slot. Resolve the SAME capability override the
    # run/session path applies, so the preview and the actual run agree — a
    # user who enables web_search_native in Settings -> Models sees the slot
    # available here too.
    ws_override = get_capability_override(db, provider_kind=effective_kind, model=effective_model)
    ws_available = capabilities_for(
        provider_kind=effective_kind, model=effective_model, override=ws_override
    ).web_search_native
    sources.append(
        DataSource(
            key=_WEB_SEARCH_KEY,
            display_name="Web search",
            category="web_search",
            routing="model_native",
            available=ws_available,
            enabled=ws_enabled,
            unavailable_reason=None if ws_available else _REASON_WS,
        )
    )

    return EuDataSources(sources=sources)
