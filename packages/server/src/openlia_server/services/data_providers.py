"""Service layer for data_providers CRUD + requirement mapping.

Bridges the pure-Python adapter system in `openlia-core` with the database.
Call sites (routes, setup wizard, resolver consumers) touch this module only
— they do not construct DataProvider rows directly.

Encryption: `api_key` (when provided) is AES-256-GCM encrypted via
`openlia_server.db.crypto.encrypt_for_row` with the provider row's `id` as
AAD. On read, `decrypt_for_row` is called with the same AAD. Providers can
also reference an environment variable via `env_var_name` (takes precedence
over the encrypted column during `load_provider_entry`).
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass

from openlia.data.adapters import ADAPTERS
from openlia.data.manifest.types import RequirementsManifest
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.crypto import decrypt_for_row, encrypt_for_row
from openlia_server.db.models.config import (
    DataProvider,
    DataProviderRequirementMapping,
)


class UnknownProviderKindError(ValueError):
    """Raised when a provider is created with a kind that has no adapter."""


class ProviderNotFoundError(LookupError):
    """Raised when a lookup by id yields no row."""


@dataclass(slots=True)
class ProviderCreated:
    id: str


def _require_known_kind(kind: str) -> None:
    if kind not in ADAPTERS:
        raise UnknownProviderKindError(f"unknown provider kind {kind!r}; known: {sorted(ADAPTERS)}")


def create_provider(
    session: Session,
    *,
    kind: str,
    label: str,
    category: ProviderCategory,
    mode: ProviderMode,
    api_key: str | None = None,
    env_var_name: str | None = None,
    base_url: str | None = None,
    mcp_url: str | None = None,
    mcp_auth_header: str | None = None,
    extra_config: dict | None = None,
    created_by_user_id: str | None = None,
) -> ProviderCreated:
    _require_known_kind(kind)
    if mode is ProviderMode.API_KEY and not base_url:
        raise ValueError("api_key mode requires base_url")
    if mode is ProviderMode.API_KEY and not (api_key or env_var_name):
        raise ValueError("api_key mode requires api_key or env_var_name")
    if mode is ProviderMode.MCP and not mcp_url:
        raise ValueError("mcp mode requires mcp_url")

    new_id = str(uuid.uuid4())
    row = DataProvider(
        id=new_id,
        kind=kind,
        label=label,
        category=category.value,
        mode=mode.value,
        api_key_encrypted=(
            encrypt_for_row(row_id=new_id, plaintext=api_key) if api_key is not None else None
        ),
        env_var_name=env_var_name,
        base_url=base_url,
        mcp_url=mcp_url,
        mcp_auth_header=mcp_auth_header,
        extra_config=(extra_config or None),
        is_enabled=True,
        created_by_user_id=created_by_user_id,
    )
    session.add(row)
    session.flush()
    return ProviderCreated(id=new_id)


def list_providers(session: Session) -> list[DataProvider]:
    return list(session.scalars(select(DataProvider)).all())


def list_providers_by_category(
    session: Session, *, category: ProviderCategory
) -> list[DataProvider]:
    stmt = select(DataProvider).where(DataProvider.category == category.value)
    return list(session.scalars(stmt).all())


def get_provider(session: Session, provider_id: str) -> DataProvider:
    row = session.get(DataProvider, provider_id)
    if row is None:
        raise ProviderNotFoundError(provider_id)
    return row


def update_provider(
    session: Session,
    provider_id: str,
    *,
    label: str | None = None,
    api_key: str | None = None,
    env_var_name: str | None = None,
    base_url: str | None = None,
    mcp_url: str | None = None,
    mcp_auth_header: str | None = None,
    extra_config: dict | None = None,
    is_enabled: bool | None = None,
) -> None:
    row = get_provider(session, provider_id)
    if label is not None:
        row.label = label
    if api_key is not None:
        row.api_key_encrypted = encrypt_for_row(row_id=provider_id, plaintext=api_key)
    if env_var_name is not None:
        row.env_var_name = env_var_name
    if base_url is not None:
        row.base_url = base_url
    if mcp_url is not None:
        row.mcp_url = mcp_url
    if mcp_auth_header is not None:
        row.mcp_auth_header = mcp_auth_header
    if extra_config is not None:
        row.extra_config = extra_config
    if is_enabled is not None:
        row.is_enabled = is_enabled
    session.flush()


def delete_provider(session: Session, provider_id: str) -> None:
    row = get_provider(session, provider_id)
    session.delete(row)
    session.flush()


def load_provider_entry(
    session: Session,
    provider_id: str,
    *,
    priority: int = 100,
) -> ProviderEntry:
    row = get_provider(session, provider_id)
    return _row_to_entry(row, priority=priority)


def _row_to_entry(row: DataProvider, *, priority: int) -> ProviderEntry:
    api_key: str | None = None
    if row.env_var_name:
        api_key = os.environ.get(row.env_var_name)
    elif row.api_key_encrypted:
        api_key = decrypt_for_row(row_id=row.id, token=row.api_key_encrypted)

    try:
        category = ProviderCategory(row.category)
    except ValueError:
        category = ProviderCategory.FINANCIAL
    try:
        mode = ProviderMode(row.mode)
    except ValueError:
        mode = ProviderMode.API_KEY
    return ProviderEntry(
        id=row.id,
        kind=row.kind,
        label=row.label,
        category=category,
        mode=mode,
        api_key=api_key,
        base_url=row.base_url,
        mcp_url=row.mcp_url,
        mcp_auth_header=row.mcp_auth_header,
        extra_config=row.extra_config or {},
        is_enabled=row.is_enabled,
        priority=priority,
    )


def set_requirement_mapping(
    session: Session,
    *,
    requirement_type: str,
    provider_id: str,
    priority: int,
) -> None:
    row = session.get(DataProviderRequirementMapping, (requirement_type, provider_id))
    if row is None:
        row = DataProviderRequirementMapping(
            requirement_type=requirement_type,
            provider_id=provider_id,
            priority=priority,
        )
        session.add(row)
    else:
        row.priority = priority
    session.flush()


def load_entries_for_capability(
    session: Session,
    *,
    capability: str,
) -> list[ProviderEntry]:
    stmt = (
        select(DataProviderRequirementMapping, DataProvider)
        .join(
            DataProvider,
            DataProvider.id == DataProviderRequirementMapping.provider_id,
        )
        .where(DataProviderRequirementMapping.requirement_type == capability)
        .where(DataProvider.is_enabled.is_(True))
        .order_by(DataProviderRequirementMapping.priority.asc())
    )
    result = session.execute(stmt).all()
    return [_row_to_entry(prov, priority=m.priority) for m, prov in result]


_DEFAULT_PRIORITY_KEY = "default_priority"


def set_provider_default_priority(
    session: Session,
    *,
    provider_id: str,
    priority: int,
) -> None:
    if not isinstance(priority, int) or priority < 0:
        raise ValueError("priority must be a non-negative integer")
    row = get_provider(session, provider_id)
    cfg = dict(row.extra_config or {})
    cfg[_DEFAULT_PRIORITY_KEY] = priority
    row.extra_config = cfg
    session.flush()


def delete_requirement_mapping(
    session: Session,
    *,
    requirement_type: str,
    provider_id: str,
) -> None:
    row = session.get(DataProviderRequirementMapping, (requirement_type, provider_id))
    if row is not None:
        session.delete(row)
        session.flush()


@dataclass(slots=True)
class _AutoMapEntry:
    requirement_type: str
    provider_id: str


@dataclass(slots=True)
class _AutoMapUnmet:
    requirement_type: str
    department: str


@dataclass(slots=True)
class AutoMapSummary:
    mapped: list[_AutoMapEntry]
    unmet: list[_AutoMapUnmet]


def auto_map(
    session: Session,
    *,
    manifest: RequirementsManifest,
) -> AutoMapSummary:
    """Heuristic provider-to-requirement mapper — NOT the spec's AI review.

    First-match-wins: for each requirement_type, the highest-priority enabled
    provider whose adapter declares the capability is selected; runners-up
    are NOT recorded as mapping rows. Each (requirement_type, provider_id)
    pair is also de-duped across departments so a requirement common to two
    departments produces one mapping row, not two.

    The spec's AI review (data-provider-design.md §"AI Review") is deferred;
    `openlia.data.review` is a marker-only package today.
    """
    providers: list[DataProvider] = list(session.scalars(select(DataProvider)).all())

    def _priority(row: DataProvider) -> int:
        cfg = row.extra_config or {}
        value = cfg.get(_DEFAULT_PRIORITY_KEY, 100)
        try:
            return int(value)
        except (TypeError, ValueError):
            return 100

    providers.sort(key=_priority)

    mapped: list[_AutoMapEntry] = []
    unmet: list[_AutoMapUnmet] = []

    seen_req_types: set[str] = set()
    mapped_req_types: set[str] = set()

    for dep in manifest.departments:
        for req in dep.requirements:
            if req.type in mapped_req_types or req.type in seen_req_types:
                # Already handled (mapped or recorded as unmet); skip dup.
                continue
            seen_req_types.add(req.type)
            winner: DataProvider | None = None
            for prov in providers:
                if not prov.is_enabled:
                    continue
                adapter_cls = ADAPTERS.get(prov.kind)
                if adapter_cls is None:
                    continue
                if req.type in adapter_cls.capabilities:
                    winner = prov
                    break
            if winner is None:
                unmet.append(_AutoMapUnmet(requirement_type=req.type, department=dep.department))
                continue
            set_requirement_mapping(
                session,
                requirement_type=req.type,
                provider_id=winner.id,
                priority=_priority(winner),
            )
            mapped.append(
                _AutoMapEntry(
                    requirement_type=req.type,
                    provider_id=winner.id,
                )
            )
            mapped_req_types.add(req.type)

    return AutoMapSummary(mapped=mapped, unmet=unmet)
