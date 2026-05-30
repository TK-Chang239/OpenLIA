# Earnings Update v2 — Dynamic Data Sources (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Earnings Update v2 settings "Data sources" section reflect what the engine can actually use (env keys + installed EODHD connector + model-native web search) instead of three hardcoded toggles.

**Architecture:** Keep the three capability booleans. Add (1) an EODHD secret bridge so an installed EODHD connector's key works, (2) a pure `compute_data_sources` service + GET endpoint reporting per-slot availability, (3) run-time AND-gating so an unavailable source can't reach the engine, (4) a dynamic settings-modal section that fetches availability, disables unavailable slots with a reason, shows an empty state, and a muted footnote for not-yet-routable connectors.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / pytest (backend); React + TypeScript / Radix / react-i18next / Vitest (frontend).

**Design doc:** `planning/2026-05-30-earnings-update-v2-dynamic-data-sources-design.md`.

**Branch:** `feat/eu-v2-dynamic-data-sources` (already created off `feat/earnings-update-v2-frontend`).

**Conventions (must follow):**
- Use `uv run` for Python; `npm` (in `frontend/`) for JS.
- Scope `ruff`/lint to changed paths only — never `ruff --fix .` across the repo.
- No emojis. Strict modern type hints. Fail loudly.
- Localize ALL user-facing strings (en + zh-TW). `unavailable_reason` is a stable CODE from the backend; the frontend maps codes → localized text. `provider_label` is the raw provider/model identity ("EODHD" or the model id); the frontend composes the displayed string.

---

## Shared contracts (defined once, referenced by later tasks)

**Backend service dataclasses** (Task 2, `eu_v2_data_sources.py`):

```python
@dataclass(frozen=True)
class DataSourceSlot:
    available: bool
    provider_label: str | None        # "EODHD" or the model id; None when unavailable
    unavailable_reason: str | None     # code: "eodhd_unconfigured" | "model_no_web_search" | None

@dataclass(frozen=True)
class OtherConnector:
    display_name: str
    category: str                      # financial | news | social | web_search

@dataclass(frozen=True)
class EuDataSources:
    financial: DataSourceSlot
    earnings_calendar: DataSourceSlot
    web_search: DataSourceSlot
    other_connectors: list[OtherConnector]
```

**Reason codes (module constants):** `_REASON_EODHD = "eodhd_unconfigured"`, `_REASON_WS = "model_no_web_search"`.

**Frontend types** (Task 5, `api/earnings-update.ts`) mirror the JSON shape:

```ts
export interface DataSourceSlot {
  available: boolean;
  provider_label: string | null;
  unavailable_reason: string | null;
}
export interface OtherConnector { display_name: string; category: string }
export interface DataSourcesInfo {
  financial: DataSourceSlot;
  earnings_calendar: DataSourceSlot;
  web_search: DataSourceSlot;
  other_connectors: OtherConnector[];
}
```

---

## Task 1: EODHD secret bridge in the wiring service

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_wiring.py`
- Test: `packages/server/tests/test_services/test_eu_v2_wiring.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/server/tests/test_services/test_eu_v2_wiring.py`:

```python
def test_resolve_eodhd_api_key_prefers_env(monkeypatch, db_session):
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.setenv("EODHD_API_KEY", "env-key")
    assert resolve_eodhd_api_key(db_session) == "env-key"


def test_resolve_eodhd_api_key_falls_back_to_validated_connector(monkeypatch, db_session):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db-key"},
            status="validated",
        )
    )
    db_session.commit()
    assert resolve_eodhd_api_key(db_session) == "db-key"


def test_resolve_eodhd_api_key_ignores_unvalidated_connector(monkeypatch, db_session):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd-pending",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={},
            secrets={"EODHD_API_KEY": "db-key"},
            status="pending",
        )
    )
    db_session.commit()
    assert resolve_eodhd_api_key(db_session) is None


def test_resolve_eodhd_api_key_none_when_nothing(monkeypatch, db_session):
    from openlia_server.services.eu_v2_wiring import resolve_eodhd_api_key

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    assert resolve_eodhd_api_key(db_session) is None


def test_build_transports_uses_explicit_api_key(monkeypatch):
    from openlia_server.services.eu_v2_wiring import build_eu_v2_transports

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    # With no env key but an explicit key, transports build (non-None).
    assert build_eu_v2_transports(api_key="explicit") is not None
```

If `test_eu_v2_wiring.py` lacks a `db_session` fixture, mirror the session fixture used in `packages/server/tests/test_services/test_eu_v2_settings.py` (a `SessionLocal()`-backed fixture over a temp SQLite DB with `Base.metadata.create_all`). Reuse that exact fixture code.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_wiring.py -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_eodhd_api_key'` and `build_eu_v2_transports() got an unexpected keyword argument 'api_key'`.

- [ ] **Step 3: Implement**

In `eu_v2_wiring.py`, change the `build_eu_v2_transports` signature and key resolution, and add `resolve_eodhd_api_key`.

Replace the opening of `build_eu_v2_transports`:

```python
def build_eu_v2_transports(api_key: str | None = None) -> EuDataTransports | None:
    """Build EODHD-backed transports for the EU v2 runner.

    Uses ``api_key`` when provided (e.g. resolved from an installed
    connector), else falls back to ``EODHD_API_KEY``. Returns ``None``
    when neither yields a key so the runner uses its loud null fallback.
    """
    key = api_key or os.getenv("EODHD_API_KEY")
    if not key:
        log.info("EODHD_API_KEY unset; EU v2 data tools will return a not-configured error.")
        return None

    from eodhd import APIClient

    client = APIClient(api_key=key)
```

(The rest of the function body — `fundamentals` / `prices` / `news` / `earnings_calendar` / the `return EuDataTransports(...)` — is unchanged.)

Add, near the top-level (after `build_eu_v2_transports`), a new helper and export it:

```python
def resolve_eodhd_api_key(db: "Session") -> str | None:
    """Resolve the EODHD key from env first, then an installed connector.

    Falls back to the ``secrets["EODHD_API_KEY"]`` of the first
    ``validated`` connector with ``provider_id == "eodhd"`` so an
    EODHD connector installed through the Connectors UI is usable by
    the report engine (whose transports otherwise read env only).
    """
    env = os.getenv("EODHD_API_KEY")
    if env:
        return env
    from openlia_server.services import connectors_service

    for connector in connectors_service.list_connectors(db):
        if connector.provider_id == "eodhd" and connector.status == "validated":
            key = (connector.secrets or {}).get("EODHD_API_KEY")
            if key:
                return key
    return None
```

Add the import for the type-only annotation at the top of the file:

```python
from sqlalchemy.orm import Session
```

and update `__all__`:

```python
__all__ = ["build_eu_v2_transports", "resolve_eodhd_api_key"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_wiring.py -v`
Expected: PASS (all tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/server/src/openlia_server/services/eu_v2_wiring.py packages/server/tests/test_services/test_eu_v2_wiring.py
git add packages/server/src/openlia_server/services/eu_v2_wiring.py packages/server/tests/test_services/test_eu_v2_wiring.py
git commit -m "feat(eu-v2): EODHD secret bridge (env or installed connector)"
```

---

## Task 2: `compute_data_sources` service

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_v2_data_sources.py`
- Test: `packages/server/tests/test_services/test_eu_v2_data_sources.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/server/tests/test_services/test_eu_v2_data_sources.py`. Mirror the `db_session` fixture from `test_eu_v2_settings.py` (copy it). Tests:

```python
from openlia_server.db.models.connectors import Connector
from openlia_server.services import eu_v2_data_sources, eu_v2_settings


def _set_model(db, *, provider_kind, model):
    eu_v2_settings.update_settings(
        db,
        user_id="local",
        provider_kind=provider_kind,
        model=model,
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        financial_enabled=True,
        calendar_enabled=True,
        web_search_enabled=True,
    )


def test_financial_available_with_env(monkeypatch, db_session):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is True
    assert ds.financial.provider_label == "EODHD"
    assert ds.earnings_calendar.available is True
    assert ds.financial.unavailable_reason is None


def test_financial_unavailable_without_eodhd(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is False
    assert ds.financial.provider_label is None
    assert ds.financial.unavailable_reason == "eodhd_unconfigured"
    assert ds.earnings_calendar.unavailable_reason == "eodhd_unconfigured"


def test_financial_available_via_connector(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add(
        Connector(
            id="c-eodhd", provider_id="eodhd", source="built_in",
            category="financial", launch={}, secrets={"EODHD_API_KEY": "db"},
            status="validated",
        )
    )
    db_session.commit()
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    assert ds.financial.available is True


def test_web_search_follows_model_capability(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    yes = eu_v2_data_sources.compute_data_sources(
        db_session, user_id="local",
        provider_kind="anthropic", model="claude-sonnet-4-6",
    )
    assert yes.web_search.available is True
    assert yes.web_search.provider_label == "claude-sonnet-4-6"
    no = eu_v2_data_sources.compute_data_sources(
        db_session, user_id="local",
        provider_kind="anthropic", model="claude-haiku-4-5-20251001",
    )
    assert no.web_search.available is False
    assert no.web_search.unavailable_reason == "model_no_web_search"


def test_other_connectors_excludes_eodhd_lists_rest(monkeypatch, db_session):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    db_session.add_all([
        Connector(id="c-eodhd", provider_id="eodhd", source="built_in",
                  category="financial", launch={}, secrets={}, status="validated"),
        Connector(id="c-fmp", provider_id="fmp", source="built_in",
                  category="financial", launch={}, secrets={}, status="validated",
                  display_name="FMP"),
        Connector(id="c-news", provider_id="newsapi_ai", source="built_in",
                  category="news", launch={}, secrets={}, status="pending",
                  display_name="News"),
    ])
    db_session.commit()
    ds = eu_v2_data_sources.compute_data_sources(db_session, user_id="local")
    names = {c.display_name for c in ds.other_connectors}
    assert names == {"FMP"}  # eodhd excluded; pending news excluded
```

Confirm the `eu_v2_settings.update_settings` keyword signature matches the helper above by reading `packages/server/src/openlia_server/services/eu_v2_settings.py` first; adjust the `_set_model` call to the real signature if it differs (do not change behavior, only the call shape). The `db_session` fixture must seed the `local` user row if `update_settings`/`get_settings` requires it — copy the seeding from `test_eu_v2_settings.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_data_sources.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'openlia_server.services.eu_v2_data_sources'`.

- [ ] **Step 3: Implement**

Create `packages/server/src/openlia_server/services/eu_v2_data_sources.py`:

```python
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
        if c.status == "validated" and c.provider_id != _EODHD_PROVIDER_ID
    ]

    return EuDataSources(
        financial=financial,
        earnings_calendar=earnings_calendar,
        web_search=web_search,
        other_connectors=other,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_data_sources.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/server/src/openlia_server/services/eu_v2_data_sources.py packages/server/tests/test_services/test_eu_v2_data_sources.py
git add packages/server/src/openlia_server/services/eu_v2_data_sources.py packages/server/tests/test_services/test_eu_v2_data_sources.py
git commit -m "feat(eu-v2): compute_data_sources availability service"
```

---

## Task 3: `GET /data-sources` route

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py`
- Test: `packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py`:

```python
def test_data_sources_503_when_disabled(client_eu_v2_disabled):
    r = client_eu_v2_disabled.get(f"{_BASE}/data-sources")
    assert r.status_code == 503


def test_data_sources_financial_unavailable_without_eodhd(client_eu_v2, monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    r = client_eu_v2.get(f"{_BASE}/data-sources")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["financial"]["available"] is False
    assert body["financial"]["unavailable_reason"] == "eodhd_unconfigured"
    assert body["earnings_calendar"]["available"] is False
    assert body["other_connectors"] == []


def test_data_sources_financial_available_with_env(client_eu_v2, monkeypatch):
    monkeypatch.setenv("EODHD_API_KEY", "k")
    r = client_eu_v2.get(f"{_BASE}/data-sources")
    body = r.json()
    assert body["financial"]["available"] is True
    assert body["financial"]["provider_label"] == "EODHD"


def test_data_sources_web_search_query_override(client_eu_v2, monkeypatch):
    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    r = client_eu_v2.get(
        f"{_BASE}/data-sources",
        params={"provider_kind": "anthropic", "model": "claude-sonnet-4-6"},
    )
    body = r.json()
    assert body["web_search"]["available"] is True
    assert body["web_search"]["provider_label"] == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -k data_sources -v`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Implement**

In `earnings_update_v2.py`:

(a) Add the import near the other service imports (top of file, with `from openlia_server.services import ...`):

```python
from openlia_server.services import eu_v2_data_sources
```

(b) Add the response DTOs next to the other `class ...Out(BaseModel)` definitions (after `SettingsOut`):

```python
class DataSourceSlotOut(BaseModel):
    available: bool
    provider_label: str | None
    unavailable_reason: str | None


class OtherConnectorOut(BaseModel):
    display_name: str
    category: str


class DataSourcesOut(BaseModel):
    financial: DataSourceSlotOut
    earnings_calendar: DataSourceSlotOut
    web_search: DataSourceSlotOut
    other_connectors: list[OtherConnectorOut]
```

(c) Add a module-level slot mapper (next to `_summary` and the other helpers):

```python
def _slot_out(slot: eu_v2_data_sources.DataSourceSlot) -> DataSourceSlotOut:
    return DataSourceSlotOut(
        available=slot.available,
        provider_label=slot.provider_label,
        unavailable_reason=slot.unavailable_reason,
    )
```

(d) Inside `build_earnings_update_v2_router`, register the handler immediately after the `get_settings` handler:

```python
    @router.get("/data-sources", response_model=DataSourcesOut)
    def get_data_sources(
        provider_kind: str | None = Query(default=None),
        model: str | None = Query(default=None),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> DataSourcesOut:
        if not eu_v2_enabled():
            raise _engine_disabled()
        ds = eu_v2_data_sources.compute_data_sources(
            db, user_id=user.id, provider_kind=provider_kind, model=model
        )
        return DataSourcesOut(
            financial=_slot_out(ds.financial),
            earnings_calendar=_slot_out(ds.earnings_calendar),
            web_search=_slot_out(ds.web_search),
            other_connectors=[
                OtherConnectorOut(display_name=c.display_name, category=c.category)
                for c in ds.other_connectors
            ],
        )
```

(`Query` is already imported at the top of the file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -k data_sources -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py
git add packages/server/src/openlia_server/routes/departments/earnings_update_v2.py packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py
git commit -m "feat(eu-v2): GET /data-sources availability endpoint"
```

---

## Task 4: Run-time AND-gating + transport key bridge

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Test: `packages/server/tests/test_services/test_eu_v2_run_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/server/tests/test_services/test_eu_v2_run_service.py` (mirror its existing `db_session` fixture and any user/settings seeding it already uses):

```python
def test_build_run_request_gates_financial_off_without_eodhd(monkeypatch, db_session):
    from openlia_server.services import eu_v2_run_service, eu_v2_settings

    monkeypatch.delenv("EODHD_API_KEY", raising=False)
    eu_v2_settings.update_settings(
        db_session, user_id="local",
        provider_kind="anthropic", model="claude-sonnet-4-6",
        template_id="eu_default", language="en", length="normal",
        reasoning_effort=None,
        financial_enabled=True, calendar_enabled=True, web_search_enabled=True,
    )
    req = eu_v2_run_service.build_run_request(
        db_session, user_id="local", ticker="AAPL.US", trigger_kind="on_demand",
        fiscal_period=None, report_date=None, release_timing=None,
        eps_estimate=None, revenue_estimate=None,
    )
    # No EODHD -> financial + calendar gated off; web search stays on
    # (sonnet supports native web search).
    assert req.enabled_connectors.financial is False
    assert req.enabled_connectors.earnings_calendar is False
    assert req.enabled_connectors.web_search is True


def test_build_run_request_gates_web_search_off_for_incapable_model(monkeypatch, db_session):
    from openlia_server.services import eu_v2_run_service, eu_v2_settings

    monkeypatch.setenv("EODHD_API_KEY", "k")
    eu_v2_settings.update_settings(
        db_session, user_id="local",
        provider_kind="anthropic", model="claude-haiku-4-5-20251001",
        template_id="eu_default", language="en", length="normal",
        reasoning_effort=None,
        financial_enabled=True, calendar_enabled=True, web_search_enabled=True,
    )
    req = eu_v2_run_service.build_run_request(
        db_session, user_id="local", ticker="AAPL.US", trigger_kind="on_demand",
        fiscal_period=None, report_date=None, release_timing=None,
        eps_estimate=None, revenue_estimate=None,
    )
    assert req.enabled_connectors.financial is True
    assert req.enabled_connectors.web_search is False  # haiku has no native web search
```

Verify the `eu_v2_settings.update_settings` keyword signature against the source and adjust if needed. Seed the `local` user the same way the existing tests in this file do.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_run_service.py -k gates -v`
Expected: FAIL — both assert the gated value but current code passes the raw boolean (financial stays True without EODHD; web_search stays True for haiku).

- [ ] **Step 3: Implement**

In `eu_v2_run_service.py`:

(a) Extend the wiring import (currently `from openlia_server.services.eu_v2_wiring import build_eu_v2_transports`):

```python
from openlia_server.services.eu_v2_wiring import (
    build_eu_v2_transports,
    resolve_eodhd_api_key,
)
```

(b) Add the capabilities import next to the other `from openlia...` imports:

```python
from openlia.llm.capabilities import capabilities_for
```

(c) In `build_run_request`, replace the `connectors = EnabledConnectors(...)` block with availability-gated values:

```python
    eodhd_available = resolve_eodhd_api_key(db) is not None
    caps = capabilities_for(provider_kind=settings.provider_kind, model=settings.model)
    connectors = EnabledConnectors(
        financial=settings.financial_enabled and eodhd_available,
        earnings_calendar=settings.calendar_enabled and eodhd_available,
        web_search=settings.web_search_enabled and caps.web_search_native,
    )
```

(d) In `start_run_async`, resolve the bridged transports when the caller did not inject them. Add this immediately before the `cancel_token = CancelToken()` line (while `db` is still open):

```python
    if transports is None:
        transports = build_eu_v2_transports(api_key=resolve_eodhd_api_key(db))
```

(`_resolve_transports` stays as the final null-fallback for the background task.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_run_service.py -v`
Expected: PASS (new gating tests + existing tests still green).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/server/src/openlia_server/services/eu_v2_run_service.py packages/server/tests/test_services/test_eu_v2_run_service.py
git add packages/server/src/openlia_server/services/eu_v2_run_service.py packages/server/tests/test_services/test_eu_v2_run_service.py
git commit -m "feat(eu-v2): gate engine connectors by live availability + bridge transport key"
```

---

## Task 5: Frontend API client

**Files:**
- Modify: `frontend/src/api/earnings-update.ts`
- Test: `frontend/src/api/earnings-update.test.ts` (only if it already exercises endpoints; otherwise skip the test file and rely on Task 6's hook test)

- [ ] **Step 1: Implement the types + fetcher**

Add to `frontend/src/api/earnings-update.ts` (after the `EuSettings` interface):

```ts
export interface DataSourceSlot {
  available: boolean;
  provider_label: string | null;
  unavailable_reason: string | null;
}
export interface OtherConnector {
  display_name: string;
  category: string;
}
export interface DataSourcesInfo {
  financial: DataSourceSlot;
  earnings_calendar: DataSourceSlot;
  web_search: DataSourceSlot;
  other_connectors: OtherConnector[];
}

export const getEuDataSources = (
  params?: { provider_kind?: string; model?: string },
): Promise<DataSourcesInfo> => {
  const q = new URLSearchParams();
  if (params?.provider_kind) q.set("provider_kind", params.provider_kind);
  if (params?.model) q.set("model", params.model);
  const qs = q.toString();
  return fetchJson<DataSourcesInfo>(`${BASE}/data-sources${qs ? `?${qs}` : ""}`);
};
```

- [ ] **Step 2: Typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: no new errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/earnings-update.ts
git commit -m "feat(eu-v2-fe): data-sources API client"
```

---

## Task 6: `useEuDataSources` hook

**Files:**
- Create: `frontend/src/hooks/useEuDataSources.ts`
- Test: `frontend/src/hooks/__tests__/useEuDataSources.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/hooks/__tests__/useEuDataSources.test.tsx`:

```tsx
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useEuDataSources } from "../useEuDataSources";
import * as api from "../../api/earnings-update";

const SLOT = { available: true, provider_label: "EODHD", unavailable_reason: null };

describe("useEuDataSources", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("fetches on mount and refetches when the model changes", async () => {
    const spy = vi
      .spyOn(api, "getEuDataSources")
      .mockResolvedValue({
        financial: SLOT,
        earnings_calendar: SLOT,
        web_search: { available: false, provider_label: null, unavailable_reason: "model_no_web_search" },
        other_connectors: [],
      });

    const { result, rerender } = renderHook(
      ({ pk, m }) => useEuDataSources(pk, m),
      { initialProps: { pk: "anthropic", m: "claude-sonnet-4-6" } },
    );

    await waitFor(() => expect(result.current.dataSources).not.toBeNull());
    expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-sonnet-4-6" });

    rerender({ pk: "anthropic", m: "claude-haiku-4-5-20251001" });
    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith({ provider_kind: "anthropic", model: "claude-haiku-4-5-20251001" }),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuDataSources.test.tsx`
Expected: FAIL — cannot resolve `../useEuDataSources`.

- [ ] **Step 3: Implement**

Create `frontend/src/hooks/useEuDataSources.ts`:

```ts
import { useCallback, useEffect, useState } from "react";

import { getEuDataSources, type DataSourcesInfo } from "../api/earnings-update";

export function useEuDataSources(providerKind: string, model: string) {
  const [dataSources, setDataSources] = useState<DataSourcesInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const info = await getEuDataSources({ provider_kind: providerKind, model });
      setDataSources(info);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [providerKind, model]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { dataSources, loading, error, refresh };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuDataSources.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useEuDataSources.ts frontend/src/hooks/__tests__/useEuDataSources.test.tsx
git commit -m "feat(eu-v2-fe): useEuDataSources hook"
```

---

## Task 7: i18n keys (en + zh-TW)

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Add the keys**

In `en.json`, under `earnings.settings_modal` (next to the existing `connectors_*` keys at ~line 763), add:

```json
"ds_via": "via {{provider}}",
"ds_reason_eodhd_unconfigured": "Set EODHD_API_KEY or install the EODHD connector in Settings → Connectors.",
"ds_reason_model_no_web_search": "The selected model does not support web search.",
"ds_empty": "No data sources available. Configure a data provider in Settings → Connectors, or pick a model with web search.",
"ds_other_configured": "Also configured: {{names}} — routing for these arrives in a later update."
```

In `zh-TW.json`, under the same `earnings.settings_modal` object, add:

```json
"ds_via": "透過 {{provider}}",
"ds_reason_eodhd_unconfigured": "請設定 EODHD_API_KEY，或在「設定 → 連接器」中安裝 EODHD 連接器。",
"ds_reason_model_no_web_search": "所選模型不支援網路搜尋。",
"ds_empty": "沒有可用的資料來源。請在「設定 → 連接器」設定資料供應商，或選擇支援網路搜尋的模型。",
"ds_other_configured": "另已設定：{{names}} — 這些連接器的串接將於後續更新提供。"
```

- [ ] **Step 2: Verify JSON validity**

Run: `cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/i18n/locales/en.json','utf8')); JSON.parse(require('fs').readFileSync('src/i18n/locales/zh-TW.json','utf8')); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n(eu-v2-fe): dynamic data-source strings (en + zh-TW)"
```

---

## Task 8: Dynamic "Data sources" section in the settings modal

**Files:**
- Modify: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`

- [ ] **Step 1: Write the failing tests**

Add to `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`. Mock both hooks the modal uses. Mirror the existing render-helper / `useEuTemplates` mock already in that file, then add a `useEuDataSources` mock:

```tsx
vi.mock("../../../hooks/useEuDataSources", () => ({
  useEuDataSources: vi.fn(),
}));
import { useEuDataSources } from "../../../hooks/useEuDataSources";

const AVAILABLE = { available: true, provider_label: "EODHD", unavailable_reason: null };
const WS_OK = { available: true, provider_label: "claude-sonnet-4-6", unavailable_reason: null };
const WS_OFF = { available: false, provider_label: null, unavailable_reason: "model_no_web_search" };
const FIN_OFF = { available: false, provider_label: null, unavailable_reason: "eodhd_unconfigured" };

function mockDataSources(over = {}) {
  (useEuDataSources as unknown as vi.Mock).mockReturnValue({
    dataSources: {
      financial: AVAILABLE,
      earnings_calendar: AVAILABLE,
      web_search: WS_OK,
      other_connectors: [],
      ...over,
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  });
}

it("renders available financial slot with provider label and an enabled toggle", () => {
  mockDataSources();
  renderModal(); // use the file's existing render helper
  const tog = screen.getByTestId("eu-v2-connector-financial");
  expect(tog).not.toBeDisabled();
  expect(screen.getByText(/EODHD/)).toBeInTheDocument();
});

it("disables an unavailable web-search slot and shows its reason", () => {
  mockDataSources({ web_search: WS_OFF });
  renderModal();
  expect(screen.getByTestId("eu-v2-connector-web_search")).toBeDisabled();
  expect(screen.getByText(/does not support web search/i)).toBeInTheDocument();
});

it("shows the empty state when all slots are unavailable", () => {
  mockDataSources({ financial: FIN_OFF, earnings_calendar: FIN_OFF, web_search: WS_OFF });
  renderModal();
  expect(screen.getByTestId("eu-v2-data-sources-empty")).toBeInTheDocument();
});

it("shows the muted footnote listing other configured connectors", () => {
  mockDataSources({ other_connectors: [{ display_name: "FMP", category: "financial" }] });
  renderModal();
  expect(screen.getByTestId("eu-v2-data-sources-other")).toHaveTextContent("FMP");
});
```

If the test file has no shared `renderModal` helper, add one that renders `<ReportSettingsModal settings={defaultSettings} onSave={vi.fn().mockResolvedValue(undefined)} onClose={vi.fn()} />` wrapped in the i18n provider used by the file's other tests. Ensure every test calls `mockDataSources(...)` (or sets the mock) before rendering.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`
Expected: FAIL — the modal does not yet call `useEuDataSources`; new test ids absent.

- [ ] **Step 3: Implement**

In `ReportSettingsModal.tsx`:

(a) Extend `Toggle` to support a disabled state. Replace the `<button ...>` inside `Toggle` so it accepts `disabled` and reflects it (add `disabled?: boolean` to the `Toggle` props and pass `disabled={disabled}` plus `aria-disabled`):

```tsx
function Toggle({
  on,
  onClick,
  testId,
  label,
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label className={[
      "flex items-center justify-between gap-4 px-4 py-3.5 transition-colors",
      disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer hover:bg-[--color-surface-hover]",
    ].join(" ")}>
      <span className="text-[13.5px] font-medium text-[--color-text-primary]">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        data-testid={testId}
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on && !disabled ? "bg-[--color-accent-primary]" : "bg-[--color-border-subtle]",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
            on && !disabled ? "left-5" : "left-1",
          ].join(" ")}
        />
      </button>
    </label>
  );
}
```

(b) Add the hook + helper inside the component (after the existing `useEuTemplates()` line):

```tsx
  const { dataSources } = useEuDataSources(draft.provider_kind, draft.model);
```

and the import at the top:

```tsx
import { useEuDataSources } from "../../hooks/useEuDataSources";
import type { DataSourceSlot } from "../../api/earnings-update";
```

(c) Add a render helper for one slot, above the `return (`:

```tsx
  function slotLabel(base: string, slot: DataSourceSlot | undefined, isWebSearch: boolean): string {
    if (!slot?.available || !slot.provider_label) return base;
    const provider = isWebSearch
      ? t("earnings.settings_modal.ds_via", { provider: slot.provider_label })
      : slot.provider_label;
    return `${base} · ${provider}`;
  }

  function reasonText(slot: DataSourceSlot | undefined): string | null {
    if (!slot || slot.available || !slot.unavailable_reason) return null;
    return t(`earnings.settings_modal.ds_reason_${slot.unavailable_reason}`);
  }

  function renderSlot(
    base: string,
    slot: DataSourceSlot | undefined,
    enabled: boolean,
    onToggle: () => void,
    testId: string,
    isWebSearch = false,
  ) {
    const reason = reasonText(slot);
    return (
      <div key={testId}>
        <Toggle
          on={enabled && !!slot?.available}
          onClick={onToggle}
          testId={testId}
          label={slotLabel(base, slot, isWebSearch)}
          disabled={!slot?.available}
        />
        {reason ? (
          <p className="px-4 pb-3 -mt-1 text-[12px] text-[--color-text-tertiary] leading-[1.4]">
            {reason}
          </p>
        ) : null}
      </div>
    );
  }
```

(d) Replace the entire Connectors `<section>` body (the `<div className="border ...">` containing the three `Toggle`s) with the dynamic version:

```tsx
            <section className="mb-7">
              {sectionTitle(t("earnings.settings_modal.connectors_title"))}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.connectors_hint")}
              </p>
              {dataSources &&
              !dataSources.financial.available &&
              !dataSources.earnings_calendar.available &&
              !dataSources.web_search.available ? (
                <p
                  data-testid="eu-v2-data-sources-empty"
                  className="text-[13px] text-[--color-text-tertiary] leading-[1.5] border border-[--color-border-subtle] rounded-lg px-4 py-3"
                >
                  {t("earnings.settings_modal.ds_empty")}
                </p>
              ) : (
                <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
                  {renderSlot(
                    t("earnings.settings_modal.connector_financial"),
                    dataSources?.financial,
                    draft.financial_enabled,
                    () => setDraft((d) => ({ ...d, financial_enabled: !d.financial_enabled })),
                    "eu-v2-connector-financial",
                  )}
                  {renderSlot(
                    t("earnings.settings_modal.connector_calendar"),
                    dataSources?.earnings_calendar,
                    draft.calendar_enabled,
                    () => setDraft((d) => ({ ...d, calendar_enabled: !d.calendar_enabled })),
                    "eu-v2-connector-calendar",
                  )}
                  {renderSlot(
                    t("earnings.settings_modal.connector_web_search"),
                    dataSources?.web_search,
                    draft.web_search_enabled,
                    () => setDraft((d) => ({ ...d, web_search_enabled: !d.web_search_enabled })),
                    "eu-v2-connector-web_search",
                    true,
                  )}
                </div>
              )}
              {dataSources && dataSources.other_connectors.length > 0 ? (
                <p
                  data-testid="eu-v2-data-sources-other"
                  className="mt-3 text-[12px] text-[--color-text-tertiary] leading-[1.5]"
                >
                  {t("earnings.settings_modal.ds_other_configured", {
                    names: dataSources.other_connectors.map((c) => c.display_name).join(", "),
                  })}
                </p>
              ) : null}
            </section>
```

(e) Sanitize unavailable slots on save. In `handleSave`, build a sanitized payload before `onSave`:

```tsx
  async function handleSave() {
    setSaving(true);
    try {
      const sanitized: EuSettings = {
        ...draft,
        financial_enabled: draft.financial_enabled && !!dataSources?.financial.available,
        calendar_enabled: draft.calendar_enabled && !!dataSources?.earnings_calendar.available,
        web_search_enabled: draft.web_search_enabled && !!dataSources?.web_search.available,
      };
      await onSave(sanitized);
      onClose();
    } finally {
      setSaving(false);
    }
  }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`
Expected: PASS.

- [ ] **Step 5: Typecheck + commit**

```bash
cd frontend && npx tsc --noEmit
git add frontend/src/components/earnings-update/ReportSettingsModal.tsx frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx
git commit -m "feat(eu-v2-fe): dynamic Data Sources section (availability + reasons + footnote)"
```

---

## Task 9: Full-suite sanity + design-doc sync

**Files:**
- Modify: `planning/2026-05-30-earnings-update-v2-dynamic-data-sources-design.md` (note the reason-code refinement)

- [ ] **Step 1: Run the backend EU suite**

Run: `uv run pytest packages/server/tests/test_services/test_eu_v2_wiring.py packages/server/tests/test_services/test_eu_v2_data_sources.py packages/server/tests/test_services/test_eu_v2_run_service.py packages/server/tests/test_routes/departments/test_earnings_update_v2_routes.py -v`
Expected: all PASS.

- [ ] **Step 2: Run the frontend EU suite**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuDataSources.test.tsx src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx && npx tsc --noEmit`
Expected: all PASS, no type errors.

- [ ] **Step 3: Sync the design doc**

In the design doc, add a short note under §3/§4 that `unavailable_reason` is delivered as a stable code (`eodhd_unconfigured` / `model_no_web_search`) and `provider_label` is the raw provider/model identity, with the displayed label and reason text composed client-side for i18n.

- [ ] **Step 4: Commit**

```bash
git add planning/2026-05-30-earnings-update-v2-dynamic-data-sources-design.md
git commit -m "docs(eu-v2): note reason-code/label i18n refinement in design"
```

---

## Self-review against the spec

- **Effective-availability list (registry + env/native):** Tasks 1 (bridge), 2 (compute), 3 (endpoint) — covered.
- **No regression for env-only users:** financial available via env in Task 2/3 tests — covered.
- **Secret bridge:** Task 1 + Task 4(d) — covered.
- **Availability rules (financial/calendar EODHD; web search model-native):** Task 2 — covered.
- **Endpoint with model query override:** Task 3 — covered.
- **Keep 3 booleans / no migration:** persistence untouched; Task 4 gates at run time — covered.
- **Muted footnote of other connectors:** Task 2 (`other_connectors`) + Task 8(d) — covered.
- **Empty state + disabled-with-reason UI:** Task 8 — covered.
- **Run-time enforcement (AND-gate):** Task 4(c) — covered.
- **Bilingual strings:** Task 7 — covered.
- **Phase 2 not built:** no dispatcher wiring anywhere — correct.

Type consistency: `DataSourceSlot` / `OtherConnector` / `DataSourcesInfo` field names identical across backend dataclasses (Task 2), route DTOs (Task 3), and frontend types (Task 5). `resolve_eodhd_api_key` / `build_eu_v2_transports(api_key=...)` signatures consistent between Tasks 1 and 4. Reason codes `eodhd_unconfigured` / `model_no_web_search` consistent between Task 2 and the Task 7 i18n keys (`ds_reason_<code>`).
