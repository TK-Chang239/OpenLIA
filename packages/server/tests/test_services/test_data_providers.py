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
    # company_news, financial_statements (P0-3-04).
    covered = {m.requirement_type for m in summary.mapped}
    assert {
        "stock_quote",
        "historical_prices",
        "company_profile",
        "company_news",
        "financial_statements",
    } <= covered
    assert all(m.provider_id == p.id for m in summary.mapped)
    # stock_grade still unmet (EODHD declares insider_transactions now).
    unmet_types = {u.requirement_type for u in summary.unmet}
    assert "stock_grade" in unmet_types
    assert "financial_statements" not in unmet_types


def test_auto_map_first_match_wins(db_session) -> None:
    """Per P0-3-03, only the highest-priority capable provider is mapped per
    requirement. Runners-up are NOT recorded as mapping rows."""
    from openlia.data.manifest import load_manifest

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
    summary = svc.auto_map(db_session, manifest=load_manifest())

    # Provider B (priority 10) wins; A is NOT mapped.
    assert all(m.provider_id == b.id for m in summary.mapped)
    # Each (requirement_type, provider_id) pair appears at most once.
    pairs = {(m.requirement_type, m.provider_id) for m in summary.mapped}
    assert len(pairs) == len(summary.mapped)

    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    assert len(entries) == 1
    assert entries[0].id == b.id


def test_auto_map_is_idempotent(db_session) -> None:
    from openlia.data.manifest import load_manifest

    svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    s1 = svc.auto_map(db_session, manifest=load_manifest())
    s2 = svc.auto_map(db_session, manifest=load_manifest())
    pairs1 = {(m.requirement_type, m.provider_id) for m in s1.mapped}
    pairs2 = {(m.requirement_type, m.provider_id) for m in s2.mapped}
    assert pairs1 == pairs2


# ---------- P0-3-01 / P0-3-02 / P1-3-09 ----------


def test_create_provider_persists_category(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="newsapi_org",
        label="N",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://newsapi.org/v2",
    )
    row = db_session.get(DataProvider, created.id)
    assert row.category == "news"
    assert row.mode == "api_key"


def test_row_to_entry_uses_db_category_for_unknown_kinds(db_session) -> None:
    """If row.kind has no adapter, the category MUST come from the DB column,
    not from a fallback to FINANCIAL."""
    created = svc.create_provider(
        db_session,
        kind="newsapi_ai",
        label="N",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://newsapi.ai",
    )
    # Force kind to a value with no adapter.
    row = db_session.get(DataProvider, created.id)
    row.kind = "no-such-adapter"
    db_session.flush()
    entry = svc.load_provider_entry(db_session, created.id, priority=100)
    assert entry.category is ProviderCategory.NEWS


def test_create_mcp_provider_roundtrips(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="EODHD-MCP",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.MCP,
        mcp_url="https://mcp.eodhd.test/sse",
        mcp_auth_header="Bearer token",
    )
    row = db_session.get(DataProvider, created.id)
    assert row.mode == "mcp"
    assert row.mcp_url == "https://mcp.eodhd.test/sse"
    assert row.mcp_auth_header == "Bearer token"
    entry = svc.load_provider_entry(db_session, created.id, priority=10)
    assert entry.mode is ProviderMode.MCP
    assert entry.mcp_url == "https://mcp.eodhd.test/sse"


def test_create_mcp_provider_without_mcp_url_raises(db_session) -> None:
    with pytest.raises(ValueError, match="mcp_url"):
        svc.create_provider(
            db_session,
            kind="eodhd",
            label="bad",
            category=ProviderCategory.FINANCIAL,
            mode=ProviderMode.MCP,
        )


# ---------- P1-3-05 ----------


def test_create_provider_accepts_fmp_newsapi_search_kinds(db_session) -> None:
    for kind, category in (
        ("fmp", ProviderCategory.FINANCIAL),
        ("finnhub", ProviderCategory.FINANCIAL),
        ("yfinance", ProviderCategory.FINANCIAL),
        ("newsapi_ai", ProviderCategory.NEWS),
        ("newsapi_org", ProviderCategory.NEWS),
        ("mediastack", ProviderCategory.NEWS),
    ):
        created = svc.create_provider(
            db_session,
            kind=kind,
            label=kind.upper(),
            category=category,
            mode=ProviderMode.API_KEY,
            api_key="k",
            base_url=f"https://{kind}.test",
        )
        row = db_session.get(DataProvider, created.id)
        assert row.kind == kind
        assert row.category == category.value


def test_provider_category_enum_includes_search() -> None:
    assert ProviderCategory.SEARCH.value == "search"


# ---------- P1-3-10 ----------


def test_load_entries_for_capability_skips_disabled_provider(db_session) -> None:
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
        db_session, requirement_type="stock_quote", provider_id=b.id, priority=20
    )
    svc.update_provider(db_session, a.id, is_enabled=False)
    entries = svc.load_entries_for_capability(db_session, capability="stock_quote")
    assert [e.id for e in entries] == [b.id]


# ---------- P1-3-11 ----------


def test_set_provider_default_priority_rejects_negative(db_session) -> None:
    created = svc.create_provider(
        db_session,
        kind="eodhd",
        label="x",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    with pytest.raises(ValueError):
        svc.set_provider_default_priority(db_session, provider_id=created.id, priority=-1)


# ---------- list_providers_by_category ----------


def test_list_providers_by_category(db_session) -> None:
    svc.create_provider(
        db_session,
        kind="eodhd",
        label="E",
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://eodhd.com/api",
    )
    svc.create_provider(
        db_session,
        kind="newsapi_org",
        label="N",
        category=ProviderCategory.NEWS,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://newsapi.org/v2",
    )
    fin = svc.list_providers_by_category(db_session, category=ProviderCategory.FINANCIAL)
    news = svc.list_providers_by_category(db_session, category=ProviderCategory.NEWS)
    assert {r.kind for r in fin} == {"eodhd"}
    assert {r.kind for r in news} == {"newsapi_org"}
