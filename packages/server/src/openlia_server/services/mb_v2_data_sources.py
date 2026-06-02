"""Compute the effective Morning Briefing v2 data-source list.

Forked from ``eu_v2_data_sources.py``. The available/enabled/routing
computation is engine-agnostic: three kinds of source surface from the
connector registry plus the caller's enabled-connectors set.

- The curated EODHD slot (key ``eodhd``, ``routing="curated"``), available
  when an EODHD key resolves from env or an installed connector.
- One dispatcher-routed entry per *other* validated connector
  (``routing="dispatcher"``), keyed by the connector's ``provider_id``.
- The model-native web-search slot (key ``model_web_search``,
  ``routing="model_native"``), available per the selected model's
  capability.

The one structural delta from EU: Morning Briefing has no per-user EU-style
settings row. A schedule binds its own connectors / model
(``mb_schedules.enabled_connectors`` + ``provider_kind`` / ``model``), so
this service is a leaf that takes the enabled set, web-search flag,
provider kind, and model as explicit arguments rather than reading a
settings service.

``available`` reflects whether the engine can use the source today;
``enabled`` reflects the schedule's per-source toggle.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from openlia.connectors.types import ConnectorStatus
from openlia.llm.capabilities import capabilities_for
from sqlalchemy.orm import Session

from openlia_server.services import connectors_service
from openlia_server.services.mb_v2_wiring import resolve_eodhd_api_key

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
class MbDataSources:
    sources: list[DataSource]


def compute_data_sources(
    db: Session,
    *,
    provider_kind: str,
    model: str,
    enabled_provider_ids: Iterable[str],
    web_search_enabled: bool,
) -> MbDataSources:
    """Return the engine's effective data-source list.

    ``enabled_provider_ids`` / ``web_search_enabled`` come from the firing
    schedule's connector binding; ``provider_kind`` / ``model`` from the
    same binding so web-search availability tracks the schedule's model.
    """
    enabled_ids = set(enabled_provider_ids)

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

    # 3. Model-native web-search slot.
    ws_available = capabilities_for(provider_kind=provider_kind, model=model).web_search_native
    sources.append(
        DataSource(
            key=_WEB_SEARCH_KEY,
            display_name="Web search",
            category="web_search",
            routing="model_native",
            available=ws_available,
            enabled=web_search_enabled,
            unavailable_reason=None if ws_available else _REASON_WS,
        )
    )

    return MbDataSources(sources=sources)
