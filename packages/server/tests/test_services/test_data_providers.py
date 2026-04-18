"""Service-layer tests for data-provider CRUD.

Uses the shared `db_session` fixture from Plan 1A's conftest and the crypto
module from Plan 2. No HTTP — call service functions directly.
"""

import pytest
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode
from openlia_server.db.models.config import DataProvider
from openlia_server.services import data_providers as svc


def test_create_provider_encrypts_api_key_on_disk(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="SECRET-VALUE",
        base_url="https://eodhd.com/api",
    )
    db_session.flush()
    row = db_session.get(DataProvider, created.id)
    assert row is not None
    # Stored value is base64 ciphertext, NOT the plaintext
    assert row.api_key_encrypted is not None
    assert "SECRET-VALUE" not in row.api_key_encrypted


def test_create_provider_rejects_unknown_kind(db_session) -> None:
    with pytest.raises(svc.UnknownProviderKindError):
        svc.create_provider(
            db_session,
            kind="does-not-exist",
            label="X",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.API_KEY,
            api_key="k",
            base_url="https://x.test",
        )


def test_create_provider_with_env_var_instead_of_api_key(
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setenv("MY_EODHD_KEY", "ENV-VALUE")
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="EODHD",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key=None,
        env_var_name="MY_EODHD_KEY",
        base_url="https://eodhd.com/api",
    )
    db_session.flush()
    row = db_session.get(DataProvider, created.id)
    assert row.api_key_encrypted is None
    assert row.env_var_name == "MY_EODHD_KEY"
    # Entry resolves env var at load time
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert entry.api_key == "ENV-VALUE"


def test_list_providers_returns_enabled_and_disabled(db_session) -> None:
    svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k1",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k2",
        base_url="https://eodhd.com/api",
    )
    svc.update_provider(db_session, b.id, is_enabled=False)
    rows = svc.list_providers(db_session)
    assert {r.label for r in rows} == {"A", "B"}


def test_update_provider_can_rotate_api_key(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="OLD",
        base_url="https://eodhd.com/api",
    )
    svc.update_provider(db_session, created.id, api_key="NEW")
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert entry.api_key == "NEW"


def test_delete_provider_removes_row(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.delete_provider(db_session, created.id)
    assert db_session.get(DataProvider, created.id) is None


def test_load_provider_entry_returns_pydantic_entry(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="X",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert isinstance(entry, ProviderEntry)
    assert entry.kind == "eodhd"
    assert entry.api_key == "k"
    assert entry.priority == 100


def test_load_enabled_entries_with_priorities(db_session) -> None:
    a = svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=a.id, priority=10
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=b.id, priority=5
    )
    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    assert [e.kind for e in entries] == ["eodhd", "eodhd"]
    assert [e.id for e in entries] == [b.id, a.id]  # priority 5 < 10


def test_delete_requirement_mapping(db_session) -> None:
    p = svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_requirement_mapping(
        db_session, requirement_type="stock_quote", provider_id=p.id, priority=10
    )
    svc.delete_requirement_mapping(db_session, requirement_type="stock_quote", provider_id=p.id)
    assert svc.load_entries_for_capability(db_session, capability="stock_quote") == []


def test_auto_map_populates_mappings_for_every_basic_and_advanced_type(
    db_session,
) -> None:
    from openlia.data.manifest import load_manifest

    p = svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    summary = svc.auto_map(db_session, manifest=load_manifest())
    # EODHDAdapter declares stock_quote, historical_prices, company_profile,
    # company_news — all four should be mapped for equity_research.
    covered = {m.requirement_type for m in summary.mapped}
    assert {"stock_quote", "historical_prices", "company_profile", "company_news"} <= covered
    # Every mapping points to the sole provider we just created
    assert all(m.provider_id == p.id for m in summary.mapped)
    # stock_grade / insider_transactions / company_fundamentals not covered
    unmet_types = {u.requirement_type for u in summary.unmet}
    assert {"stock_grade", "insider_transactions"} <= unmet_types


def test_auto_map_uses_admin_set_priorities_as_tie_break(db_session) -> None:
    from openlia.data.manifest import load_manifest

    # Create two EODHD-kind providers. The one with lower priority wins.
    a = svc.create_provider(
        db_session,
        kind="eodhd",
        label="A",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    b = svc.create_provider(
        db_session,
        kind="eodhd",
        label="B",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.set_provider_default_priority(db_session, provider_id=a.id, priority=50)
    svc.set_provider_default_priority(db_session, provider_id=b.id, priority=10)
    svc.auto_map(db_session, manifest=load_manifest())

    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    # Provider B (priority 10) comes before A (priority 50)
    assert entries[0].id == b.id
    assert entries[1].id == a.id
