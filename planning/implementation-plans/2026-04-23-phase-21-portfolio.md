# Phase 21 — Portfolio Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Contract reminders (apply before executing this plan):**
> - All IDs are UUID strings (`String(36)`); generate with `str(uuid.uuid4())`. No prefixed short-hex ids.
> - Auth gating via `build_require_active_user(...)` / `build_require_admin(...)` router factories — not a bare `current_user` / `require_user`.
> - Backend imports: `User` from `db.models.auth`; `PortfolioHolding` from `db.models.content`; `ProviderAdapter` / `ToolResult` from `openlia.data.base` / `openlia.data.types`; data errors from `openlia.data.errors`.
> - Backend FastAPI routers use **bare prefixes** (`/portfolio/...`). The Vite dev proxy strips `/api`. Frontend calls `/api/portfolio/...`; backend TestClient tests hit `/portfolio/...`.
> - `PortfolioHolding` table ships in Plan 1A with columns `id, user_id, ticker, name, shares, cost_basis, currency, notes, added_at, updated_at` plus `UniqueConstraint("user_id", "ticker")`. Do not add columns unless a task explicitly requires a migration.
> - Currency column is `String(3)` with default `"USD"`; `shares` and `cost_basis` are `Numeric(18, 6)` (`Decimal`). Pydantic DTOs use `Decimal` on the wire (serialized as strings).

**Goal:** Ship the Portfolio page — a full-width holdings table with search-and-add, group tabs, list/card view modes, per-group sort, intraday price refresh, analytics summary, CSV import/export, and a cross-plan helper (`get_reference_holdings`) that Morning Briefing's Reference Portfolio toggle (Plan 16) consumes without creating import cycles.

**Architecture:**

- **Backend (`packages/server/`).** Thin route factory `routes/portfolio.py` mounts under `/portfolio` and delegates CRUD, analytics, CSV import/export, and price refresh to `services/portfolio.py`. Price refresh uses the shipped EODHD adapter via a `PortfolioPriceProvider` Protocol so tests can substitute a fake. Intraday quotes are cached in a process-local TTL cache (no new DB table). The cross-plan helper `portfolio.get_reference_holdings(user_id)` is a pure DB read returning a list of lightweight dicts — Morning Briefing imports it, not the whole service.
- **Frontend (`frontend/src/`).** A `PortfolioPage` route renders `PortfolioShell` (controls bar + group tabs + content area). Two view components share the underlying sorted holdings hook: `HoldingsList` (List View) and `HoldingsGrid` (Card View). Search-and-add is a combobox over `/api/portfolio/search`. Analytics cards sit above the content area. CSV import/export are a dialog and a direct download. A refresh button pulls live prices on demand.
- **Reuse.** Plan 8's `Button`, `Input`, `Card`, `Dialog`, `Toast` primitives are imported unchanged. Plan 11's `useDirtyForm` is **not** needed (Portfolio mutations commit immediately per row).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Pydantic v2; React 18, TypeScript strict, react-router-dom v6, Tailwind v3, lucide-react, vitest + @testing-library/react.

**Source spec:** `planning/specs/pages/PortfolioPageSpec.md`.

**Depends on:**

- Plan 1A (`portfolio_holdings` table — columns ship as of 2026-04-18; this plan does **not** add columns).
- Plan 2 (session middleware, `build_require_active_user`).
- Plan 3 (EODHD adapter + `ProviderAdapter` base + `ToolResult` shape + `DataNotAvailable`/`RateLimitError`/`DataSourceError`).
- Plan 8 (router, design tokens, `api/client.ts`, `AuthProvider`, `Toast` host).
- Plan 12 (shared chat components — only to the extent Portfolio links into the Equity Research chat session as described in the spec's "Ticker Detail Navigation").

**Unblocks:**

- Plan 16 (Morning Briefing — Reference Portfolio toggle consumes `get_reference_holdings`).
- Plan 15 (Earnings Update scan — spec notes EU watchlist is independent of portfolio; no direct dependency, but portfolio tickers may seed an EU watchlist in a later polish pass).

**Out of scope (explicitly deferred):**

- Total-value / P&L percentage charts over time (v1 shows daily change only; historical P&L is a v2 concern).
- Drag-and-drop reordering of tickers within a group (spec non-goal).
- Mobile swipe-to-remove gesture polish beyond a basic `touchstart` handler.
- Localization of currency formatting beyond `USD` / `TWD` / `EUR` (Intl.NumberFormat handles these generically; adding non-ISO currencies is deferred).
- Real-time WebSocket quote streaming — v1 uses on-demand + auto-refresh HTTP pulls with a 60s TTL cache.
- Per-user BYO ticker search providers; search delegates to the configured financial adapter (EODHD by default).

---

## File Structure

### New backend files

```
packages/server/src/openlia_server/
├── routes/
│   └── portfolio.py                    # /portfolio/* route factory
└── services/
    ├── portfolio.py                    # CRUD + analytics + CSV + reference helper
    └── portfolio_prices.py             # TTL-cached price fetcher wrapping a ProviderAdapter
```

### New backend tests

```
packages/server/tests/
├── test_services/
│   ├── test_portfolio.py               # CRUD + analytics + CSV + reference helper
│   └── test_portfolio_prices.py        # TTL cache + adapter wiring + error fallback
└── test_routes/
    └── test_portfolio_routes.py        # auth gating + every endpoint wire test
```

### New frontend files

```
frontend/src/
├── api/
│   └── portfolio.ts                    # REPLACED — typed /portfolio/* client
├── portfolio/
│   ├── PortfolioShell.tsx              # outer layout (controls bar + tabs + content)
│   ├── SearchAndAdd.tsx                # combobox + group-assignment popover
│   ├── GroupTabs.tsx                   # pill tabs + "+ New Group" + context menu
│   ├── SortControl.tsx                 # dropdown with 4 sort options
│   ├── ViewToggle.tsx                  # list vs. card icon pair
│   ├── HoldingsList.tsx                # list view rendering
│   ├── HoldingsGrid.tsx                # card view rendering
│   ├── AddEditDrawer.tsx               # drawer for manual holding entry/edit
│   ├── ImportCsvDialog.tsx             # file picker + validation + commit
│   ├── AnalyticsCards.tsx              # totals + allocation + P&L summary
│   ├── PriceRefreshButton.tsx          # force-refresh + rate-limit feedback
│   ├── Sparkline.tsx                   # inline SVG sparkline
│   ├── AreaChart.tsx                   # inline SVG area chart for card view
│   ├── EmptyState.tsx                  # "Your portfolio is empty"
│   ├── useHoldings.ts                  # React Query hook: list + mutate
│   ├── useAnalytics.ts                 # React Query hook: analytics
│   ├── useSortedHoldings.ts            # applies group filter + sort to holdings
│   └── useLocalPref.ts                 # persist view + per-group sort in localStorage
└── pages/
    └── PortfolioPage.tsx               # route entry
```

### New frontend tests

```
frontend/src/portfolio/
├── PortfolioShell.test.tsx
├── SearchAndAdd.test.tsx
├── GroupTabs.test.tsx
├── SortControl.test.tsx
├── HoldingsList.test.tsx
├── HoldingsGrid.test.tsx
├── AddEditDrawer.test.tsx
├── ImportCsvDialog.test.tsx
├── AnalyticsCards.test.tsx
├── useSortedHoldings.test.ts
└── useLocalPref.test.ts
```

### Modified files

```
packages/server/src/openlia_server/
├── app.py                              # MODIFY — wire portfolio router
└── services/__init__.py                # no change (module-level)

frontend/src/
├── router.tsx                          # MODIFY — add /portfolio route
├── api/portfolio.ts                    # REPLACE — typed client (stub today)
└── components/Sidebar.tsx              # MODIFY — add Portfolio nav item if absent

planning/implementation-plans/README.md # MODIFY — flip Plan 21 row to Draft → Done
planning/projectStructure.md            # MODIFY — record portfolio module
```

---

## Design Rules

1. **Router factory pattern.** `build_portfolio_router(*, db_session_factory, mode, price_provider_factory)` returns an `APIRouter(prefix="/portfolio")`. `require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)`. No bare `get_current_user`.
2. **Per-user scoping.** Every read and write filters `PortfolioHolding.user_id == user.id`. Any 404 on a mismatched owner returns `{"detail": "holding not found"}` — never leaks existence across users.
3. **UUID strings.** Holding ids are `str(uuid.uuid4())`. Path parameters are typed `str`.
4. **Decimal discipline.** `shares`, `cost_basis`, and price fields on the wire use `Decimal`. Pydantic models set `model_config = ConfigDict(json_encoders={Decimal: str})` and quantize to 6 decimal places for shares, 4 for prices.
5. **Intraday cache is transient.** `PortfolioPriceProvider` holds a `dict[str, _CachedQuote]` in process memory with a 60-second TTL. No new DB table. Restarting the server drops the cache — that's the point.
6. **Graceful price degradation.** When the adapter raises `DataNotAvailable` or `RateLimitError`, the service returns `last_price=None`, `change_pct=None`, `sparkline=[]`, and the route still returns 200. Only `DataSourceError` unrelated to a single ticker bubbles up as 503.
7. **CSV contract.** Import accepts `ticker,shares,cost_basis,currency,notes` (header required, case-insensitive). Export emits the same columns plus `added_at` ISO-8601. Unknown columns are ignored; missing optional fields are `None`. Duplicate tickers within a user are rejected row-wise with a per-row error in the response body.
8. **Analytics are computed, never stored.** `GET /analytics` joins holdings with the latest cached quotes and returns totals/allocations/P&L in one response. No analytics table.
9. **Groups are derived from `notes`.** For v1, groups are stored in a JSON blob under `notes` (`{"groups": ["Tech", "Dividends"]}`) to avoid a schema migration. "All" is implicit (every holding is always in All). If notes contains free text instead of JSON, the service treats it as a no-group holding and exposes the raw text via `notes_text`. A follow-up plan can migrate to a dedicated `portfolio_groups` table.
10. **Cross-plan helper surface.** `get_reference_holdings(db, user_id)` returns `list[ReferenceHolding]` where `ReferenceHolding = TypedDict({"ticker": str, "name": str | None, "shares": Decimal | None, "currency": str})`. Morning Briefing imports only this function and the `ReferenceHolding` type. No other coupling.
11. **Rate-limit refresh.** `POST /portfolio/refresh-prices` is gated by a per-user 30-second cooldown tracked in the same TTL cache. Violations return 429 with a `retry_after` field.
12. **TDD every task.** Failing test → verify fail → implementation → verify pass → commit.
13. **No placeholders.** Every code block complete.
14. **Design tokens only.** `[--color-*]` classes, no raw hex.
15. **One commit per task.** Prefixes: `feat(portfolio)`, `test(portfolio)`, `refactor(portfolio)`, `docs(plan)`.
16. **No untyped `any`.** Typed interfaces in `api/portfolio.ts`; Python signatures use `Decimal | None`, `list[Holding]`, etc.

---

## Task 0: Pre-flight — worktree + branch + dependency audit

**Files:** none created. Commands only.

- [ ] **Step 1:** Create the feature worktree (optional — use `superpowers:using-git-worktrees` if following the subagent flow).

```bash
git worktree add ../OpenLIA-phase-21-portfolio -b feat/phase-21-portfolio main
cd ../OpenLIA-phase-21-portfolio
```

- [ ] **Step 2:** Confirm the shipped `PortfolioHolding` model matches the spec's data needs (ticker, shares, cost_basis, currency, notes, added_at, updated_at).

```bash
python -c "
from openlia_server.db.models.content import PortfolioHolding
for c in PortfolioHolding.__table__.columns:
    print(c.name, c.type, 'nullable=' + str(c.nullable))
"
```

Expected output (exact column set):

```
id VARCHAR(36) nullable=False
user_id VARCHAR(36) nullable=False
ticker VARCHAR(16) nullable=False
name VARCHAR(256) nullable=True
shares NUMERIC(18, 6) nullable=True
cost_basis NUMERIC(18, 6) nullable=True
currency VARCHAR(3) nullable=False
notes TEXT nullable=True
added_at <UTCDateTime> nullable=False
updated_at <UTCDateTime> nullable=False
```

If the output does not match, STOP and escalate. This plan assumes no migration. The baseline must match before any task runs.

- [ ] **Step 3:** Run the full aggregate suite on the clean branch to confirm a green baseline.

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
```

Expected: all green. Commit nothing yet.

---

## Task 1: `services/portfolio_prices.py` — TTL-cached price provider

**Files:**
- Create: `packages/server/src/openlia_server/services/portfolio_prices.py`
- Test: `packages/server/tests/test_services/test_portfolio_prices.py`

- [ ] **Step 1: Write the failing test.**

```python
# packages/server/tests/test_services/test_portfolio_prices.py
"""TTL cache + adapter wiring + graceful degradation for portfolio price fetch."""
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from openlia.data.errors import DataNotAvailable, RateLimitError
from openlia.data.types import ToolResult
from openlia_server.services.portfolio_prices import (
    CachedQuote,
    PortfolioPriceProvider,
    RefreshCooldown,
)


class _FakeAdapter:
    def __init__(self, payloads: dict[str, dict | Exception]) -> None:
        self.payloads = payloads
        self.calls: list[tuple[str, dict]] = []

    async def fetch(self, capability: str, params: dict) -> ToolResult:
        self.calls.append((capability, params))
        sym = params["symbol"]
        raw = self.payloads.get(sym)
        if isinstance(raw, Exception):
            raise raw
        assert isinstance(raw, dict)
        return ToolResult(provider_kind="fake", capability=capability, payload=raw)


def test_fetch_quote_caches_for_ttl() -> None:
    adapter = _FakeAdapter({"AAPL": {"close": 180.12, "change_p": 1.25, "previousClose": 177.89}})
    provider = PortfolioPriceProvider(adapter=adapter, ttl_seconds=60)
    q1 = asyncio.run(provider.get_quote("AAPL"))
    q2 = asyncio.run(provider.get_quote("AAPL"))
    assert q1 == q2
    assert q1.last_price == Decimal("180.12")
    assert len(adapter.calls) == 1  # cached second call


def test_fetch_quote_refreshes_when_forced() -> None:
    adapter = _FakeAdapter({"AAPL": {"close": 180.12, "change_p": 1.25, "previousClose": 177.89}})
    provider = PortfolioPriceProvider(adapter=adapter, ttl_seconds=60)
    asyncio.run(provider.get_quote("AAPL"))
    asyncio.run(provider.get_quote("AAPL", force=True))
    assert len(adapter.calls) == 2


def test_fetch_quote_returns_none_on_data_not_available() -> None:
    adapter = _FakeAdapter({
        "XYZ": DataNotAvailable(provider_kind="fake", capability="stock_quote", reason="unknown")
    })
    provider = PortfolioPriceProvider(adapter=adapter, ttl_seconds=60)
    q = asyncio.run(provider.get_quote("XYZ"))
    assert q.last_price is None
    assert q.change_pct is None


def test_fetch_quote_returns_none_on_rate_limit() -> None:
    adapter = _FakeAdapter({
        "XYZ": RateLimitError(provider_kind="fake", retry_after_seconds=30)
    })
    provider = PortfolioPriceProvider(adapter=adapter, ttl_seconds=60)
    q = asyncio.run(provider.get_quote("XYZ"))
    assert q.last_price is None


def test_refresh_cooldown_rejects_within_window() -> None:
    cooldown = RefreshCooldown(seconds=30)
    assert cooldown.try_acquire("user-1") is None
    retry_after = cooldown.try_acquire("user-1")
    assert retry_after is not None and 0 < retry_after <= 30


def test_refresh_cooldown_scoped_per_user() -> None:
    cooldown = RefreshCooldown(seconds=30)
    assert cooldown.try_acquire("a") is None
    assert cooldown.try_acquire("b") is None


def test_get_quotes_batch_fills_available_and_skips_failed() -> None:
    adapter = _FakeAdapter({
        "AAPL": {"close": 180.12, "change_p": 1.25, "previousClose": 177.89},
        "XYZ": DataNotAvailable(provider_kind="fake", capability="stock_quote", reason="unknown"),
    })
    provider = PortfolioPriceProvider(adapter=adapter, ttl_seconds=60)
    quotes = asyncio.run(provider.get_quotes(["AAPL", "XYZ"]))
    assert quotes["AAPL"].last_price == Decimal("180.12")
    assert quotes["XYZ"].last_price is None
```

- [ ] **Step 2: Verify the test fails.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio_prices.py -q
```

Expected: `ModuleNotFoundError: No module named 'openlia_server.services.portfolio_prices'`.

- [ ] **Step 3: Write the implementation.**

```python
# packages/server/src/openlia_server/services/portfolio_prices.py
"""Process-local TTL cache over an EODHD-style stock_quote adapter.

Exposed to the Portfolio route factory as a `PortfolioPriceProvider`
instance; tests substitute a fake adapter. No DB writes — the cache is
transient and dies with the process. A separate `RefreshCooldown` guards
user-initiated refresh calls against abuse.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Protocol

from openlia.data.errors import DataNotAvailable, DataSourceError, RateLimitError
from openlia.data.types import ToolResult


class _QuoteAdapter(Protocol):
    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult: ...


@dataclass(frozen=True)
class CachedQuote:
    ticker: str
    last_price: Decimal | None
    previous_close: Decimal | None
    change_pct: Decimal | None
    fetched_at: float


def _decimal_or_none(raw: Any) -> Decimal | None:
    if raw is None:
        return None
    try:
        return Decimal(str(raw))
    except (ValueError, ArithmeticError):
        return None


class PortfolioPriceProvider:
    """TTL-cached wrapper around a `stock_quote`-capable adapter."""

    def __init__(self, *, adapter: _QuoteAdapter, ttl_seconds: int = 60) -> None:
        self._adapter = adapter
        self._ttl = ttl_seconds
        self._cache: dict[str, CachedQuote] = {}
        self._lock = asyncio.Lock()

    async def get_quote(self, ticker: str, *, force: bool = False) -> CachedQuote:
        ticker_up = ticker.strip().upper()
        if not ticker_up:
            raise ValueError("ticker required")
        now = time.monotonic()
        async with self._lock:
            cached = self._cache.get(ticker_up)
            if cached and not force and (now - cached.fetched_at) < self._ttl:
                return cached
        quote = await self._fetch_one(ticker_up, now)
        async with self._lock:
            self._cache[ticker_up] = quote
        return quote

    async def get_quotes(
        self, tickers: list[str], *, force: bool = False
    ) -> dict[str, CachedQuote]:
        if not tickers:
            return {}
        tasks = [self.get_quote(t, force=force) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: dict[str, CachedQuote] = {}
        for t, r in zip(tickers, results, strict=True):
            t_up = t.strip().upper()
            if isinstance(r, CachedQuote):
                out[t_up] = r
            else:
                out[t_up] = CachedQuote(
                    ticker=t_up,
                    last_price=None,
                    previous_close=None,
                    change_pct=None,
                    fetched_at=time.monotonic(),
                )
        return out

    async def _fetch_one(self, ticker: str, now: float) -> CachedQuote:
        try:
            result = await self._adapter.fetch("stock_quote", {"symbol": ticker})
        except (DataNotAvailable, RateLimitError):
            return CachedQuote(
                ticker=ticker,
                last_price=None,
                previous_close=None,
                change_pct=None,
                fetched_at=now,
            )
        except DataSourceError:
            # Upstream infrastructure problem — bubble up so the route can
            # return 503 rather than silently showing stale data.
            raise
        payload = result.payload if isinstance(result.payload, dict) else {}
        return CachedQuote(
            ticker=ticker,
            last_price=_decimal_or_none(payload.get("close")),
            previous_close=_decimal_or_none(payload.get("previousClose")),
            change_pct=_decimal_or_none(payload.get("change_p")),
            fetched_at=now,
        )


@dataclass
class RefreshCooldown:
    seconds: int = 30
    _last: dict[str, float] = field(default_factory=dict)

    def try_acquire(self, user_id: str) -> float | None:
        """Return None on success, or seconds-remaining on cooldown."""
        now = time.monotonic()
        last = self._last.get(user_id)
        if last is not None and (now - last) < self.seconds:
            return self.seconds - (now - last)
        self._last[user_id] = now
        return None
```

- [ ] **Step 4: Verify the test passes.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio_prices.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Lint + format + commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services/portfolio_prices.py packages/server/tests/test_services/test_portfolio_prices.py
uv run ruff format packages/server/src/openlia_server/services/portfolio_prices.py packages/server/tests/test_services/test_portfolio_prices.py
git add packages/server/src/openlia_server/services/portfolio_prices.py packages/server/tests/test_services/test_portfolio_prices.py
git commit -m "feat(portfolio): TTL-cached price provider + per-user refresh cooldown"
```

---

## Task 2: `services/portfolio.py` — CRUD + group derivation

**Files:**
- Create: `packages/server/src/openlia_server/services/portfolio.py`
- Test: `packages/server/tests/test_services/test_portfolio.py`

- [ ] **Step 1: Write the failing test (CRUD slice).**

```python
# packages/server/tests/test_services/test_portfolio.py
"""Holdings CRUD + groups-from-notes + reference-holdings helper."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from openlia_server.db.models.auth import User
from openlia_server.services import portfolio as svc


@pytest.fixture()
def user(db_session) -> User:
    u = User(
        id="u-1-0000-0000-0000-000000000000",
        email="u@example.com",
        password_hash="x",
        display_name="U",
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_create_holding_defaults_currency_usd(db_session, user) -> None:
    dto = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="aapl",
        shares=Decimal("10"),
        cost_basis=Decimal("150"),
        currency=None,
        notes=None,
        groups=None,
    )
    assert dto.ticker == "AAPL"
    assert dto.currency == "USD"
    assert dto.shares == Decimal("10")
    assert dto.groups == []


def test_create_holding_rejects_duplicate_ticker(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("1"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    with pytest.raises(svc.DuplicateTickerError):
        svc.create_holding(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            shares=Decimal("2"),
            cost_basis=None,
            currency="USD",
            notes=None,
            groups=None,
        )


def test_create_holding_stores_groups_in_notes_json(db_session, user) -> None:
    dto = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=["Tech", "Dividends"],
    )
    assert dto.groups == ["Tech", "Dividends"]
    listed = svc.list_holdings(db_session, user_id=user.id)
    assert listed[0].groups == ["Tech", "Dividends"]


def test_update_holding_patch_semantics(db_session, user) -> None:
    created = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=["Tech"],
    )
    updated = svc.update_holding(
        db_session,
        user_id=user.id,
        holding_id=created.id,
        shares=Decimal("6"),
        cost_basis=Decimal("310.5"),
        currency=None,
        notes=None,
        groups=None,
    )
    assert updated.shares == Decimal("6")
    assert updated.cost_basis == Decimal("310.5")
    assert updated.currency == "USD"
    assert updated.groups == ["Tech"]  # unchanged


def test_update_holding_foreign_user_raises(db_session, user) -> None:
    created = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    with pytest.raises(svc.HoldingNotFoundError):
        svc.update_holding(
            db_session,
            user_id="other-user",
            holding_id=created.id,
            shares=Decimal("1"),
            cost_basis=None,
            currency=None,
            notes=None,
            groups=None,
        )


def test_delete_holding_cascades_clean(db_session, user) -> None:
    created = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    svc.delete_holding(db_session, user_id=user.id, holding_id=created.id)
    assert svc.list_holdings(db_session, user_id=user.id) == []


def test_reference_holdings_helper_returns_lightweight_dicts(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    refs = svc.get_reference_holdings(db_session, user_id=user.id)
    assert refs == [
        {
            "ticker": "AAPL",
            "name": None,
            "shares": Decimal("10"),
            "currency": "USD",
        }
    ]


def test_notes_preserves_freeform_text_when_no_groups_json(db_session, user) -> None:
    from openlia_server.db.models.content import PortfolioHolding

    row = PortfolioHolding(
        id="h-free-0000-0000-0000-000000000000",
        user_id=user.id,
        ticker="NVDA",
        name=None,
        shares=Decimal("2"),
        cost_basis=None,
        currency="USD",
        notes="Buy on dips",
    )
    db_session.add(row)
    db_session.commit()

    dtos = svc.list_holdings(db_session, user_id=user.id)
    assert dtos[0].groups == []
    assert dtos[0].notes_text == "Buy on dips"
```

- [ ] **Step 2: Verify the test fails.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py -q
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation (CRUD + reference helper).**

```python
# packages/server/src/openlia_server/services/portfolio.py
"""Holdings CRUD + analytics + CSV + cross-plan reference helper.

Groups are encoded inside `notes` as JSON (`{"groups": [...], "text": "..."}`)
so v1 avoids a schema migration. Free-form `notes` entered before the JSON
convention is preserved as `notes_text`. The helper `get_reference_holdings`
is imported by Morning Briefing (Plan 16) and deliberately returns a flat
`list[dict]` to avoid pulling in the full DTO class.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import PortfolioHolding

if TYPE_CHECKING:
    from openlia_server.services.portfolio_prices import CachedQuote


class DuplicateTickerError(ValueError):
    pass


class HoldingNotFoundError(LookupError):
    pass


class CsvImportError(ValueError):
    def __init__(self, errors: list[dict]) -> None:
        super().__init__("csv import had row errors")
        self.errors = errors


@dataclass(frozen=True)
class HoldingDTO:
    id: str
    user_id: str
    ticker: str
    name: str | None
    shares: Decimal | None
    cost_basis: Decimal | None
    currency: str
    notes_text: str | None
    groups: list[str]
    added_at: datetime
    updated_at: datetime


class ReferenceHolding(TypedDict):
    ticker: str
    name: str | None
    shares: Decimal | None
    currency: str


# ---------------------------------------------------------------------------
# notes <-> (groups, free text) codec
# ---------------------------------------------------------------------------


def _decode_notes(raw: str | None) -> tuple[list[str], str | None]:
    if raw is None or not raw.strip():
        return [], None
    try:
        obj = json.loads(raw)
    except (ValueError, TypeError):
        return [], raw
    if not isinstance(obj, dict):
        return [], raw
    groups_raw = obj.get("groups", [])
    groups = [str(g) for g in groups_raw if isinstance(g, str)] if isinstance(groups_raw, list) else []
    text = obj.get("text")
    return groups, text if isinstance(text, str) else None


def _encode_notes(groups: list[str] | None, text: str | None) -> str | None:
    groups = groups or []
    if not groups and not text:
        return None
    return json.dumps({"groups": groups, "text": text or ""})


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def _to_dto(row: PortfolioHolding) -> HoldingDTO:
    groups, text = _decode_notes(row.notes)
    return HoldingDTO(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        name=row.name,
        shares=row.shares,
        cost_basis=row.cost_basis,
        currency=row.currency,
        notes_text=text,
        groups=groups,
        added_at=row.added_at,
        updated_at=row.updated_at,
    )


def create_holding(
    db: Session,
    *,
    user_id: str,
    ticker: str,
    shares: Decimal | None,
    cost_basis: Decimal | None,
    currency: str | None,
    notes: str | None,
    groups: list[str] | None,
    name: str | None = None,
) -> HoldingDTO:
    ticker_up = ticker.strip().upper()
    if not ticker_up:
        raise ValueError("ticker required")

    existing = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.user_id == user_id, PortfolioHolding.ticker == ticker_up)
        .one_or_none()
    )
    if existing is not None:
        raise DuplicateTickerError(ticker_up)

    row = PortfolioHolding(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=ticker_up,
        name=name,
        shares=shares,
        cost_basis=cost_basis,
        currency=(currency or "USD").upper(),
        notes=_encode_notes(groups, notes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_dto(row)


def list_holdings(db: Session, *, user_id: str) -> list[HoldingDTO]:
    rows = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.user_id == user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    return [_to_dto(r) for r in rows]


def get_holding(db: Session, *, user_id: str, holding_id: str) -> HoldingDTO:
    row = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.id == holding_id, PortfolioHolding.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        raise HoldingNotFoundError(holding_id)
    return _to_dto(row)


def update_holding(
    db: Session,
    *,
    user_id: str,
    holding_id: str,
    shares: Decimal | None,
    cost_basis: Decimal | None,
    currency: str | None,
    notes: str | None,
    groups: list[str] | None,
    name: str | None = None,
) -> HoldingDTO:
    row = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.id == holding_id, PortfolioHolding.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        raise HoldingNotFoundError(holding_id)

    if shares is not None:
        row.shares = shares
    if cost_basis is not None:
        row.cost_basis = cost_basis
    if currency is not None:
        row.currency = currency.upper()
    if name is not None:
        row.name = name
    if notes is not None or groups is not None:
        existing_groups, existing_text = _decode_notes(row.notes)
        new_groups = groups if groups is not None else existing_groups
        new_text = notes if notes is not None else existing_text
        row.notes = _encode_notes(new_groups, new_text)
    db.commit()
    db.refresh(row)
    return _to_dto(row)


def delete_holding(db: Session, *, user_id: str, holding_id: str) -> None:
    row = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.id == holding_id, PortfolioHolding.user_id == user_id)
        .one_or_none()
    )
    if row is None:
        raise HoldingNotFoundError(holding_id)
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------------
# Cross-plan helper for Morning Briefing (Plan 16)
# ---------------------------------------------------------------------------


def get_reference_holdings(db: Session, *, user_id: str) -> list[ReferenceHolding]:
    """Lightweight projection used by Morning Briefing's Reference Portfolio.

    Intentionally returns a plain `list[dict]` (typed via `ReferenceHolding`)
    so downstream code does not need to import `HoldingDTO` or `PortfolioHolding`.
    """
    rows = (
        db.query(PortfolioHolding)
        .filter(PortfolioHolding.user_id == user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    return [
        ReferenceHolding(
            ticker=r.ticker,
            name=r.name,
            shares=r.shares,
            currency=r.currency,
        )
        for r in rows
    ]
```

- [ ] **Step 4: Verify the test passes.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py -q
```

Expected: all CRUD + reference tests pass.

- [ ] **Step 5: Lint + format + commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services/portfolio.py packages/server/tests/test_services/test_portfolio.py
uv run ruff format packages/server/src/openlia_server/services/portfolio.py packages/server/tests/test_services/test_portfolio.py
git add packages/server/src/openlia_server/services/portfolio.py packages/server/tests/test_services/test_portfolio.py
git commit -m "feat(portfolio): holdings CRUD service + reference-holdings helper for Plan 16"
```

---

## Task 3: Analytics — totals, allocation, P&L

**Files:**
- Modify: `packages/server/src/openlia_server/services/portfolio.py`
- Modify: `packages/server/tests/test_services/test_portfolio.py`

- [ ] **Step 1: Append the failing test.**

Append to `test_portfolio.py`:

```python
from decimal import Decimal

from openlia_server.services.portfolio_prices import CachedQuote


def test_compute_analytics_with_full_quotes(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("150"),
        currency="USD",
        notes=None,
        groups=["Tech"],
    )
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=Decimal("300"),
        currency="USD",
        notes=None,
        groups=["Tech"],
    )
    quotes = {
        "AAPL": CachedQuote(
            ticker="AAPL",
            last_price=Decimal("180"),
            previous_close=Decimal("178"),
            change_pct=Decimal("1.12"),
            fetched_at=0.0,
        ),
        "MSFT": CachedQuote(
            ticker="MSFT",
            last_price=Decimal("310"),
            previous_close=Decimal("305"),
            change_pct=Decimal("1.64"),
            fetched_at=0.0,
        ),
    }
    analytics = svc.compute_analytics(
        holdings=svc.list_holdings(db_session, user_id=user.id),
        quotes=quotes,
    )
    assert analytics.total_market_value == Decimal("3350")  # 10*180 + 5*310
    assert analytics.total_cost_basis == Decimal("3000")     # 10*150 + 5*300
    assert analytics.total_unrealized_pnl == Decimal("350")
    assert analytics.total_unrealized_pnl_pct.quantize(Decimal("0.01")) == Decimal("11.67")
    assert analytics.position_count == 2
    assert set(analytics.by_group.keys()) == {"All", "Tech"}
    assert analytics.by_group["Tech"].market_value == Decimal("3350")


def test_compute_analytics_handles_missing_quotes_gracefully(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="ZZZ",
        shares=Decimal("1"),
        cost_basis=Decimal("10"),
        currency="USD",
        notes=None,
        groups=None,
    )
    analytics = svc.compute_analytics(
        holdings=svc.list_holdings(db_session, user_id=user.id),
        quotes={},
    )
    assert analytics.total_market_value == Decimal("0")
    assert analytics.total_cost_basis == Decimal("10")
    assert analytics.total_unrealized_pnl == Decimal("-10")


def test_compute_analytics_skips_holdings_without_shares(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="NO_SHARES",
        shares=None,
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    analytics = svc.compute_analytics(
        holdings=svc.list_holdings(db_session, user_id=user.id),
        quotes={},
    )
    assert analytics.position_count == 1
    assert analytics.total_market_value == Decimal("0")
```

- [ ] **Step 2: Verify the test fails.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py::test_compute_analytics_with_full_quotes -q
```

Expected: `AttributeError: module 'openlia_server.services.portfolio' has no attribute 'compute_analytics'`.

- [ ] **Step 3: Implement analytics.**

Append to `services/portfolio.py`:

```python
# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GroupAnalytics:
    name: str
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    position_count: int


@dataclass(frozen=True)
class PortfolioAnalytics:
    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_pnl: Decimal
    total_unrealized_pnl_pct: Decimal
    position_count: int
    by_group: dict[str, GroupAnalytics]


def compute_analytics(
    *,
    holdings: list[HoldingDTO],
    quotes: dict[str, "CachedQuote"],
) -> PortfolioAnalytics:
    totals_mv = Decimal("0")
    totals_cost = Decimal("0")
    groups: dict[str, dict[str, Decimal | int]] = {}

    def bump(group: str, mv: Decimal, cost: Decimal) -> None:
        slot = groups.setdefault(
            group,
            {"mv": Decimal("0"), "cost": Decimal("0"), "count": 0},
        )
        slot["mv"] = slot["mv"] + mv  # type: ignore[operator]
        slot["cost"] = slot["cost"] + cost  # type: ignore[operator]
        slot["count"] = int(slot["count"]) + 1  # type: ignore[assignment]

    for h in holdings:
        price = quotes.get(h.ticker.upper())
        mv = Decimal("0")
        if h.shares is not None and price is not None and price.last_price is not None:
            mv = h.shares * price.last_price
        cost = Decimal("0")
        if h.shares is not None and h.cost_basis is not None:
            cost = h.shares * h.cost_basis
        totals_mv += mv
        totals_cost += cost
        bump("All", mv, cost)
        for g in h.groups:
            bump(g, mv, cost)

    pnl = totals_mv - totals_cost
    pct = (pnl / totals_cost * Decimal("100")) if totals_cost > 0 else Decimal("0")
    by_group = {
        name: GroupAnalytics(
            name=name,
            market_value=slot["mv"],  # type: ignore[arg-type]
            cost_basis=slot["cost"],  # type: ignore[arg-type]
            unrealized_pnl=slot["mv"] - slot["cost"],  # type: ignore[operator]
            position_count=int(slot["count"]),  # type: ignore[arg-type]
        )
        for name, slot in groups.items()
    }
    return PortfolioAnalytics(
        total_market_value=totals_mv,
        total_cost_basis=totals_cost,
        total_unrealized_pnl=pnl,
        total_unrealized_pnl_pct=pct,
        position_count=len(holdings),
        by_group=by_group,
    )
```

- [ ] **Step 4: Verify tests pass.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py -q
```

Expected: all tests pass (CRUD + analytics).

- [ ] **Step 5: Commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services/portfolio.py
uv run ruff format packages/server/src/openlia_server/services/portfolio.py
git add packages/server/src/openlia_server/services/portfolio.py packages/server/tests/test_services/test_portfolio.py
git commit -m "feat(portfolio): totals + per-group + P&L analytics"
```

---

## Task 4: CSV import + export

**Files:**
- Modify: `packages/server/src/openlia_server/services/portfolio.py`
- Modify: `packages/server/tests/test_services/test_portfolio.py`

- [ ] **Step 1: Append CSV tests.**

```python
def test_import_csv_happy_path(db_session, user) -> None:
    csv_text = (
        "ticker,shares,cost_basis,currency,notes\n"
        "AAPL,10,150.25,USD,Tech pick\n"
        "MSFT,5,299.50,USD,\n"
    )
    result = svc.import_csv(db_session, user_id=user.id, csv_text=csv_text)
    assert result.created == 2
    assert result.errors == []
    listed = svc.list_holdings(db_session, user_id=user.id)
    assert {h.ticker for h in listed} == {"AAPL", "MSFT"}


def test_import_csv_rejects_duplicate_within_file(db_session, user) -> None:
    csv_text = (
        "ticker,shares\n"
        "AAPL,1\n"
        "aapl,2\n"
    )
    result = svc.import_csv(db_session, user_id=user.id, csv_text=csv_text)
    assert result.created == 1
    assert len(result.errors) == 1
    assert result.errors[0]["row"] == 3
    assert "duplicate" in result.errors[0]["error"].lower()


def test_import_csv_skips_unknown_columns(db_session, user) -> None:
    csv_text = "ticker,shares,sector\nAAPL,10,Tech\n"
    result = svc.import_csv(db_session, user_id=user.id, csv_text=csv_text)
    assert result.created == 1


def test_import_csv_reports_invalid_decimal(db_session, user) -> None:
    csv_text = "ticker,shares\nAAPL,not-a-number\n"
    result = svc.import_csv(db_session, user_id=user.id, csv_text=csv_text)
    assert result.created == 0
    assert len(result.errors) == 1
    assert "shares" in result.errors[0]["error"].lower()


def test_import_csv_requires_ticker(db_session, user) -> None:
    csv_text = "ticker,shares\n,10\n"
    result = svc.import_csv(db_session, user_id=user.id, csv_text=csv_text)
    assert result.created == 0
    assert len(result.errors) == 1


def test_export_csv_round_trip(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("150.25"),
        currency="USD",
        notes=None,
        groups=["Tech"],
    )
    out = svc.export_csv(db_session, user_id=user.id)
    assert "ticker,shares,cost_basis,currency,groups,notes,added_at" in out
    assert "AAPL,10,150.25,USD,Tech" in out
```

- [ ] **Step 2: Verify they fail.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py -k "import_csv or export_csv" -q
```

Expected: `AttributeError: ... has no attribute 'import_csv'`.

- [ ] **Step 3: Implement CSV.**

Append to `services/portfolio.py`:

```python
# ---------------------------------------------------------------------------
# CSV import / export
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CsvImportResult:
    created: int
    errors: list[dict]


_CSV_ALLOWED = {"ticker", "shares", "cost_basis", "currency", "notes"}


def _parse_decimal(raw: str | None, field: str) -> Decimal | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field}: {exc}") from exc


def import_csv(
    db: Session,
    *,
    user_id: str,
    csv_text: str,
) -> CsvImportResult:
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames_raw = reader.fieldnames or []
    fieldnames = {n.strip().lower(): n for n in fieldnames_raw}
    if "ticker" not in fieldnames:
        raise CsvImportError([{"row": 1, "error": "header must include 'ticker'"}])

    created = 0
    errors: list[dict] = []
    seen_in_file: set[str] = set()
    row_number = 1  # header is row 1

    existing_tickers = {
        t for (t,) in db.query(PortfolioHolding.ticker).filter(
            PortfolioHolding.user_id == user_id
        ).all()
    }

    for row in reader:
        row_number += 1
        try:
            ticker_raw = (row.get(fieldnames["ticker"]) or "").strip().upper()
            if not ticker_raw:
                raise ValueError("ticker required")
            if ticker_raw in existing_tickers or ticker_raw in seen_in_file:
                raise ValueError(f"duplicate ticker {ticker_raw}")
            shares = _parse_decimal(row.get(fieldnames.get("shares", "")), "shares")
            cost_basis = _parse_decimal(row.get(fieldnames.get("cost_basis", "")), "cost_basis")
            currency = (row.get(fieldnames.get("currency", "")) or "USD").strip().upper() or "USD"
            notes_raw = row.get(fieldnames.get("notes", ""))
            notes = notes_raw.strip() if notes_raw and notes_raw.strip() else None
            create_holding(
                db,
                user_id=user_id,
                ticker=ticker_raw,
                shares=shares,
                cost_basis=cost_basis,
                currency=currency,
                notes=notes,
                groups=None,
            )
            seen_in_file.add(ticker_raw)
            created += 1
        except (ValueError, DuplicateTickerError) as exc:
            errors.append({"row": row_number, "error": str(exc)})

    return CsvImportResult(created=created, errors=errors)


def export_csv(db: Session, *, user_id: str) -> str:
    rows = list_holdings(db, user_id=user_id)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(
        ["ticker", "shares", "cost_basis", "currency", "groups", "notes", "added_at"]
    )
    for r in rows:
        writer.writerow(
            [
                r.ticker,
                "" if r.shares is None else str(r.shares.normalize()),
                "" if r.cost_basis is None else str(r.cost_basis.normalize()),
                r.currency,
                ";".join(r.groups),
                r.notes_text or "",
                r.added_at.isoformat(),
            ]
        )
    return buf.getvalue()
```

- [ ] **Step 4: Verify tests pass.**

```bash
uv run pytest packages/server/tests/test_services/test_portfolio.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/services/portfolio.py
uv run ruff format packages/server/src/openlia_server/services/portfolio.py
git add packages/server/src/openlia_server/services/portfolio.py packages/server/tests/test_services/test_portfolio.py
git commit -m "feat(portfolio): CSV import/export with per-row error reporting"
```

---

## Task 5: `routes/portfolio.py` — route factory wiring

**Files:**
- Create: `packages/server/src/openlia_server/routes/portfolio.py`
- Test: `packages/server/tests/test_routes/test_portfolio_routes.py`

- [ ] **Step 1: Write the failing route test (skeleton + GET holdings).**

```python
# packages/server/tests/test_routes/test_portfolio_routes.py
"""End-to-end wire tests for /portfolio/*."""
from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openlia.data.types import ToolResult
from openlia_server.routes.portfolio import build_portfolio_router
from openlia_server.services.portfolio_prices import PortfolioPriceProvider


class _FakeAdapter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def fetch(self, capability: str, params: dict) -> ToolResult:
        self.calls.append((capability, params))
        return ToolResult(
            provider_kind="fake",
            capability=capability,
            payload={"close": 180.0, "change_p": 1.25, "previousClose": 177.78},
        )


@pytest.fixture()
def client(db_session_factory, authed_user):
    app = FastAPI()
    provider = PortfolioPriceProvider(adapter=_FakeAdapter(), ttl_seconds=60)
    app.include_router(
        build_portfolio_router(
            db_session_factory=db_session_factory,
            mode="personal",
            price_provider=provider,
        )
    )
    return TestClient(app), authed_user


def test_list_holdings_empty(client) -> None:
    c, _ = client
    r = c.get("/portfolio/holdings")
    assert r.status_code == 200
    assert r.json() == []


def test_create_holding_roundtrip(client) -> None:
    c, _ = client
    r = c.post(
        "/portfolio/holdings",
        json={"ticker": "aapl", "shares": "10", "cost_basis": "150", "currency": "USD"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert body["currency"] == "USD"
    assert body["shares"] == "10"
    r = c.get("/portfolio/holdings")
    assert len(r.json()) == 1


def test_create_holding_rejects_duplicate(client) -> None:
    c, _ = client
    c.post("/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"})
    r = c.post("/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"})
    assert r.status_code == 409


def test_update_holding(client) -> None:
    c, _ = client
    created = c.post(
        "/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"}
    ).json()
    r = c.put(
        f"/portfolio/holdings/{created['id']}",
        json={"shares": "5", "cost_basis": "150"},
    )
    assert r.status_code == 200
    assert r.json()["shares"] == "5"
    assert r.json()["cost_basis"] == "150"


def test_update_holding_404_on_other_user(client) -> None:
    c, _ = client
    r = c.put(
        "/portfolio/holdings/nope-0000-0000-0000-000000000000",
        json={"shares": "1"},
    )
    assert r.status_code == 404


def test_delete_holding(client) -> None:
    c, _ = client
    created = c.post(
        "/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"}
    ).json()
    r = c.delete(f"/portfolio/holdings/{created['id']}")
    assert r.status_code == 200
    r = c.get("/portfolio/holdings")
    assert r.json() == []


def test_analytics_with_prices(client) -> None:
    c, _ = client
    c.post(
        "/portfolio/holdings",
        json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"},
    )
    r = c.get("/portfolio/analytics")
    assert r.status_code == 200
    body = r.json()
    assert Decimal(body["total_market_value"]) == Decimal("1800")
    assert Decimal(body["total_cost_basis"]) == Decimal("1500")
    assert Decimal(body["total_unrealized_pnl"]) == Decimal("300")
    assert body["position_count"] == 1


def test_refresh_prices_succeeds_then_cools_down(client) -> None:
    c, _ = client
    c.post("/portfolio/holdings", json={"ticker": "AAPL", "shares": "1"})
    r1 = c.post("/portfolio/refresh-prices")
    assert r1.status_code == 200
    r2 = c.post("/portfolio/refresh-prices")
    assert r2.status_code == 429
    assert "retry_after" in r2.json()


def test_export_csv_returns_text(client) -> None:
    c, _ = client
    c.post("/portfolio/holdings", json={"ticker": "AAPL", "shares": "10", "cost_basis": "150"})
    r = c.get("/portfolio/holdings/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "AAPL,10,150,USD" in r.text


def test_import_csv_happy_path(client) -> None:
    c, _ = client
    files = {
        "file": ("holdings.csv", "ticker,shares\nAAPL,10\nMSFT,5\n", "text/csv"),
    }
    r = c.post("/portfolio/holdings/import", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] == 2
    assert body["errors"] == []


def test_import_csv_reports_errors(client) -> None:
    c, _ = client
    files = {
        "file": ("holdings.csv", "ticker,shares\nAAPL,nope\n", "text/csv"),
    }
    r = c.post("/portfolio/holdings/import", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 0
    assert len(body["errors"]) == 1
```

> **Fixture assumption:** `db_session_factory` and `authed_user` are the shared pytest fixtures from `packages/server/tests/conftest.py`. If they do not yet inject a session cookie, add a session-setup helper in `conftest.py` that mints a session row for `authed_user` and attaches the cookie to the TestClient — mirror what Plan 11's route tests already do (`packages/server/tests/test_routes/conftest.py`).

- [ ] **Step 2: Verify the test fails.**

```bash
uv run pytest packages/server/tests/test_routes/test_portfolio_routes.py -q
```

Expected: `ImportError: cannot import name 'build_portfolio_router' ...`.

- [ ] **Step 3: Write the route factory.**

```python
# packages/server/src/openlia_server/routes/portfolio.py
"""/portfolio/* route factory.

Mounts holdings CRUD, analytics, CSV import/export, and on-demand
price refresh. Uses the router-factory auth pattern; price fetching is
delegated to a `PortfolioPriceProvider` passed in by `app.py`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import portfolio as svc
from openlia_server.services.portfolio_prices import PortfolioPriceProvider, RefreshCooldown


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


class HoldingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    name: str | None = None
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = None
    notes: str | None = None
    groups: list[str] | None = None


class HoldingPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    shares: Decimal | None = None
    cost_basis: Decimal | None = None
    currency: str | None = None
    notes: str | None = None
    groups: list[str] | None = None


class HoldingOut(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    id: str
    ticker: str
    name: str | None
    shares: Decimal | None
    cost_basis: Decimal | None
    currency: str
    notes: str | None
    groups: list[str]
    added_at: str
    updated_at: str
    last_price: Decimal | None = None
    previous_close: Decimal | None = None
    change_pct: Decimal | None = None


class GroupAnalyticsOut(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    name: str
    market_value: Decimal
    cost_basis: Decimal
    unrealized_pnl: Decimal
    position_count: int


class AnalyticsOut(BaseModel):
    model_config = ConfigDict(json_encoders={Decimal: str})

    total_market_value: Decimal
    total_cost_basis: Decimal
    total_unrealized_pnl: Decimal
    total_unrealized_pnl_pct: Decimal
    position_count: int
    by_group: dict[str, GroupAnalyticsOut]


class ImportReportOut(BaseModel):
    created: int
    errors: list[dict]


class RefreshOut(BaseModel):
    refreshed: int


def _dto_to_out(dto: svc.HoldingDTO, quote: object | None = None) -> HoldingOut:
    last = prev = change = None
    if quote is not None:
        last = getattr(quote, "last_price", None)
        prev = getattr(quote, "previous_close", None)
        change = getattr(quote, "change_pct", None)
    return HoldingOut(
        id=dto.id,
        ticker=dto.ticker,
        name=dto.name,
        shares=dto.shares,
        cost_basis=dto.cost_basis,
        currency=dto.currency,
        notes=dto.notes_text,
        groups=dto.groups,
        added_at=dto.added_at.isoformat(),
        updated_at=dto.updated_at.isoformat(),
        last_price=last,
        previous_close=prev,
        change_pct=change,
    )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_portfolio_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
    price_provider: PortfolioPriceProvider | None = None,
    refresh_cooldown: RefreshCooldown | None = None,
) -> APIRouter:
    require_auth = build_require_active_user(
        db_session_factory=db_session_factory, mode=mode
    )
    cooldown = refresh_cooldown or RefreshCooldown(seconds=30)
    router = APIRouter(prefix="/portfolio", tags=["portfolio"])

    # -- holdings CRUD ------------------------------------------------------

    @router.get("/holdings", response_model=list[HoldingOut])
    def list_holdings(user: User = Depends(require_auth)) -> list[HoldingOut]:
        with db_session_factory() as db:
            dtos = svc.list_holdings(db, user_id=user.id)
        quotes: dict = {}
        if price_provider is not None and dtos:
            quotes = asyncio.run(
                price_provider.get_quotes([d.ticker for d in dtos], force=False)
            )
        return [_dto_to_out(d, quotes.get(d.ticker)) for d in dtos]

    @router.post("/holdings", response_model=HoldingOut, status_code=201)
    def create_holding(body: HoldingIn, user: User = Depends(require_auth)) -> HoldingOut:
        with db_session_factory() as db:
            try:
                dto = svc.create_holding(
                    db,
                    user_id=user.id,
                    ticker=body.ticker,
                    shares=body.shares,
                    cost_basis=body.cost_basis,
                    currency=body.currency,
                    notes=body.notes,
                    groups=body.groups,
                    name=body.name,
                )
            except svc.DuplicateTickerError as exc:
                raise HTTPException(status_code=409, detail=f"duplicate ticker {exc}") from exc
        return _dto_to_out(dto)

    @router.put("/holdings/{holding_id}", response_model=HoldingOut)
    def update_holding(
        holding_id: str,
        body: HoldingPatch,
        user: User = Depends(require_auth),
    ) -> HoldingOut:
        with db_session_factory() as db:
            try:
                dto = svc.update_holding(
                    db,
                    user_id=user.id,
                    holding_id=holding_id,
                    shares=body.shares,
                    cost_basis=body.cost_basis,
                    currency=body.currency,
                    notes=body.notes,
                    groups=body.groups,
                    name=body.name,
                )
            except svc.HoldingNotFoundError as exc:
                raise HTTPException(status_code=404, detail="holding not found") from exc
        return _dto_to_out(dto)

    @router.delete("/holdings/{holding_id}")
    def delete_holding(holding_id: str, user: User = Depends(require_auth)) -> dict[str, str]:
        with db_session_factory() as db:
            try:
                svc.delete_holding(db, user_id=user.id, holding_id=holding_id)
            except svc.HoldingNotFoundError as exc:
                raise HTTPException(status_code=404, detail="holding not found") from exc
        return {"deleted": holding_id}

    # -- CSV ----------------------------------------------------------------

    @router.get("/holdings/export", response_class=PlainTextResponse)
    def export_csv(user: User = Depends(require_auth)) -> PlainTextResponse:
        with db_session_factory() as db:
            text = svc.export_csv(db, user_id=user.id)
        return PlainTextResponse(
            text,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="portfolio.csv"'},
        )

    @router.post("/holdings/import", response_model=ImportReportOut)
    async def import_csv(
        file: UploadFile = File(...),
        user: User = Depends(require_auth),
    ) -> ImportReportOut:
        raw = await file.read()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"csv must be utf-8: {exc}") from exc
        with db_session_factory() as db:
            try:
                result = svc.import_csv(db, user_id=user.id, csv_text=text)
            except svc.CsvImportError as exc:
                return ImportReportOut(created=0, errors=exc.errors)
        return ImportReportOut(created=result.created, errors=result.errors)

    # -- analytics ----------------------------------------------------------

    @router.get("/analytics", response_model=AnalyticsOut)
    def get_analytics(user: User = Depends(require_auth)) -> AnalyticsOut:
        with db_session_factory() as db:
            dtos = svc.list_holdings(db, user_id=user.id)
        quotes: dict = {}
        if price_provider is not None and dtos:
            quotes = asyncio.run(
                price_provider.get_quotes([d.ticker for d in dtos], force=False)
            )
        analytics = svc.compute_analytics(holdings=dtos, quotes=quotes)
        return AnalyticsOut(
            total_market_value=analytics.total_market_value,
            total_cost_basis=analytics.total_cost_basis,
            total_unrealized_pnl=analytics.total_unrealized_pnl,
            total_unrealized_pnl_pct=analytics.total_unrealized_pnl_pct,
            position_count=analytics.position_count,
            by_group={
                name: GroupAnalyticsOut(
                    name=g.name,
                    market_value=g.market_value,
                    cost_basis=g.cost_basis,
                    unrealized_pnl=g.unrealized_pnl,
                    position_count=g.position_count,
                )
                for name, g in analytics.by_group.items()
            },
        )

    # -- refresh ------------------------------------------------------------

    @router.post("/refresh-prices", response_model=RefreshOut)
    async def refresh_prices(user: User = Depends(require_auth)) -> RefreshOut:
        remaining = cooldown.try_acquire(user.id)
        if remaining is not None:
            raise HTTPException(
                status_code=429,
                detail={"error": "cooldown", "retry_after": int(remaining)},
            )
        if price_provider is None:
            return RefreshOut(refreshed=0)
        with db_session_factory() as db:
            dtos = svc.list_holdings(db, user_id=user.id)
        quotes = await price_provider.get_quotes(
            [d.ticker for d in dtos], force=True
        )
        return RefreshOut(refreshed=len(quotes))

    return router
```

- [ ] **Step 4: Verify route tests pass.**

```bash
uv run pytest packages/server/tests/test_routes/test_portfolio_routes.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/routes/portfolio.py packages/server/tests/test_routes/test_portfolio_routes.py
uv run ruff format packages/server/src/openlia_server/routes/portfolio.py packages/server/tests/test_routes/test_portfolio_routes.py
git add packages/server/src/openlia_server/routes/portfolio.py packages/server/tests/test_routes/test_portfolio_routes.py
git commit -m "feat(portfolio): /portfolio CRUD + analytics + CSV + refresh route"
```

---

## Task 6: Wire `build_portfolio_router` into `app.py`

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_app/test_app_wiring.py` (extend if present; otherwise add new test file `test_portfolio_wiring.py`).

- [ ] **Step 1: Write the failing wiring test.**

```python
# packages/server/tests/test_app/test_portfolio_wiring.py
"""Confirm create_app mounts the portfolio router with a price provider."""
from __future__ import annotations

from fastapi.testclient import TestClient

from openlia_server.app import create_app


def test_portfolio_router_is_mounted(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)
    r = client.get("/portfolio/holdings")
    # unauthenticated → 401 (company) or 200 (personal with auto-user).
    assert r.status_code in (200, 401)


def test_portfolio_price_provider_attached_to_state() -> None:
    app = create_app()
    assert hasattr(app.state, "portfolio_price_provider")
```

- [ ] **Step 2: Verify it fails.**

```bash
uv run pytest packages/server/tests/test_app/test_portfolio_wiring.py -q
```

Expected: `AttributeError: 'State' object has no attribute 'portfolio_price_provider'` and a 404 on the route.

- [ ] **Step 3: Modify `app.py` to build the provider and mount the router.**

Inside `create_app(...)`, after the other `app.include_router(...)` calls:

```python
    # --- Portfolio wiring ---------------------------------------------------
    from openlia_server.routes.portfolio import build_portfolio_router
    from openlia_server.services.portfolio_prices import (
        PortfolioPriceProvider,
        RefreshCooldown,
    )

    portfolio_adapter = getattr(app.state, "financial_adapter", None)
    price_provider: PortfolioPriceProvider | None = None
    if portfolio_adapter is not None:
        price_provider = PortfolioPriceProvider(adapter=portfolio_adapter, ttl_seconds=60)
    app.state.portfolio_price_provider = price_provider
    app.state.portfolio_refresh_cooldown = RefreshCooldown(seconds=30)
    app.include_router(
        build_portfolio_router(
            db_session_factory=factory,
            mode=mode,
            price_provider=price_provider,
            refresh_cooldown=app.state.portfolio_refresh_cooldown,
        )
    )
```

> `app.state.financial_adapter` is populated by Plan 3's data-provider wiring when an `eodhd` (or compatible) provider is configured. When absent (fresh dev env with no adapter), `price_provider` stays `None` and the route returns 200 with empty quotes — matches Design Rule 6.

- [ ] **Step 4: Verify wiring test passes.**

```bash
uv run pytest packages/server/tests/test_app/test_portfolio_wiring.py -q
uv run pytest -q
```

Expected: the wiring test and the full suite pass.

- [ ] **Step 5: Commit.**

```bash
uv run ruff check --fix packages/server/src/openlia_server/app.py packages/server/tests/test_app/test_portfolio_wiring.py
uv run ruff format packages/server/src/openlia_server/app.py packages/server/tests/test_app/test_portfolio_wiring.py
git add packages/server/src/openlia_server/app.py packages/server/tests/test_app/test_portfolio_wiring.py
git commit -m "feat(portfolio): wire router + price provider into app factory"
```

---

## Task 7: Frontend API client `api/portfolio.ts` (replace stub)

**Files:**
- Replace: `frontend/src/api/portfolio.ts`
- Create: `frontend/src/api/__tests__/portfolio.test.ts`

- [ ] **Step 1: Write the failing test.**

```ts
// frontend/src/api/__tests__/portfolio.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  fetchHoldings,
  createHolding,
  updateHolding,
  deleteHolding,
  importHoldingsCsv,
  exportHoldingsCsvUrl,
  fetchAnalytics,
  refreshPrices,
} from "../portfolio";

const mockFetch = vi.fn();

beforeEach(() => {
  mockFetch.mockReset();
  (globalThis as unknown as { fetch: typeof fetch }).fetch = mockFetch;
});

describe("portfolio api client", () => {
  it("GETs holdings with credentials", async () => {
    mockFetch.mockResolvedValue(
      new Response("[]", { status: 200, headers: { "content-type": "application/json" } }),
    );
    await fetchHoldings();
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("/api/portfolio/holdings");
    expect((init as RequestInit).credentials).toBe("include");
  });

  it("POSTs create body as JSON", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ id: "x", ticker: "AAPL", currency: "USD", groups: [], added_at: "", updated_at: "" }),
        { status: 201, headers: { "content-type": "application/json" } },
      ),
    );
    const res = await createHolding({ ticker: "AAPL", shares: "10" });
    expect(res.ticker).toBe("AAPL");
    const init = mockFetch.mock.calls[0][1] as RequestInit;
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["content-type"]).toBe("application/json");
  });

  it("throws on non-2xx create", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ detail: "duplicate ticker AAPL" }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
    );
    await expect(createHolding({ ticker: "AAPL" })).rejects.toThrow(/duplicate/i);
  });

  it("PUTs update", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "x", ticker: "AAPL", currency: "USD", groups: [], added_at: "", updated_at: "" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    await updateHolding("x", { shares: "5" });
    expect(mockFetch.mock.calls[0][0]).toBe("/api/portfolio/holdings/x");
    expect((mockFetch.mock.calls[0][1] as RequestInit).method).toBe("PUT");
  });

  it("DELETEs", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ deleted: "x" }), { status: 200 }),
    );
    await deleteHolding("x");
    expect((mockFetch.mock.calls[0][1] as RequestInit).method).toBe("DELETE");
  });

  it("imports CSV as multipart", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ created: 2, errors: [] }), { status: 200 }),
    );
    const file = new File(["ticker,shares\nAAPL,10\n"], "holdings.csv", { type: "text/csv" });
    const res = await importHoldingsCsv(file);
    expect(res.created).toBe(2);
    const init = mockFetch.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("returns export URL", () => {
    expect(exportHoldingsCsvUrl()).toBe("/api/portfolio/holdings/export");
  });

  it("GETs analytics", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          total_market_value: "0",
          total_cost_basis: "0",
          total_unrealized_pnl: "0",
          total_unrealized_pnl_pct: "0",
          position_count: 0,
          by_group: {},
        }),
        { status: 200 },
      ),
    );
    const a = await fetchAnalytics();
    expect(a.position_count).toBe(0);
  });

  it("POSTs refresh", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ refreshed: 3 }), { status: 200 }),
    );
    const r = await refreshPrices();
    expect(r.refreshed).toBe(3);
  });

  it("surfaces 429 retry_after from refresh", async () => {
    mockFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ detail: { error: "cooldown", retry_after: 17 } }),
        { status: 429, headers: { "content-type": "application/json" } },
      ),
    );
    await expect(refreshPrices()).rejects.toMatchObject({ retryAfter: 17 });
  });
});
```

- [ ] **Step 2: Verify tests fail.**

```bash
cd frontend && npm test -- api/__tests__/portfolio.test.ts
```

Expected: TypeScript import errors for missing exports.

- [ ] **Step 3: Replace the stub with a full client.**

```ts
// frontend/src/api/portfolio.ts

export interface Holding {
  id: string;
  ticker: string;
  name: string | null;
  shares: string | null;
  cost_basis: string | null;
  currency: string;
  notes: string | null;
  groups: string[];
  added_at: string;
  updated_at: string;
  last_price: string | null;
  previous_close: string | null;
  change_pct: string | null;
}

export interface HoldingInput {
  ticker: string;
  name?: string | null;
  shares?: string | null;
  cost_basis?: string | null;
  currency?: string | null;
  notes?: string | null;
  groups?: string[] | null;
}

export interface HoldingPatchInput extends Partial<HoldingInput> {}

export interface GroupAnalytics {
  name: string;
  market_value: string;
  cost_basis: string;
  unrealized_pnl: string;
  position_count: number;
}

export interface Analytics {
  total_market_value: string;
  total_cost_basis: string;
  total_unrealized_pnl: string;
  total_unrealized_pnl_pct: string;
  position_count: number;
  by_group: Record<string, GroupAnalytics>;
}

export interface ImportReport {
  created: number;
  errors: { row: number; error: string }[];
}

export interface RefreshError extends Error {
  retryAfter?: number;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown = undefined;
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    const detail =
      body && typeof body === "object" && "detail" in body
        ? (body as { detail: unknown }).detail
        : res.statusText;
    const message = typeof detail === "string" ? detail : JSON.stringify(detail);
    const err = new Error(`portfolio api: ${res.status} ${message}`) as RefreshError;
    if (res.status === 429 && detail && typeof detail === "object" && "retry_after" in detail) {
      err.retryAfter = (detail as { retry_after: number }).retry_after;
    }
    throw err;
  }
  return (await res.json()) as T;
}

export async function fetchHoldings(): Promise<Holding[]> {
  const res = await fetch("/api/portfolio/holdings", { credentials: "include" });
  return jsonOrThrow<Holding[]>(res);
}

export async function createHolding(input: HoldingInput): Promise<Holding> {
  const res = await fetch("/api/portfolio/holdings", {
    method: "POST",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
  });
  return jsonOrThrow<Holding>(res);
}

export async function updateHolding(id: string, patch: HoldingPatchInput): Promise<Holding> {
  const res = await fetch(`/api/portfolio/holdings/${id}`, {
    method: "PUT",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch),
  });
  return jsonOrThrow<Holding>(res);
}

export async function deleteHolding(id: string): Promise<void> {
  const res = await fetch(`/api/portfolio/holdings/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  await jsonOrThrow<{ deleted: string }>(res);
}

export async function importHoldingsCsv(file: File): Promise<ImportReport> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/portfolio/holdings/import", {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  return jsonOrThrow<ImportReport>(res);
}

export function exportHoldingsCsvUrl(): string {
  return "/api/portfolio/holdings/export";
}

export async function fetchAnalytics(): Promise<Analytics> {
  const res = await fetch("/api/portfolio/analytics", { credentials: "include" });
  return jsonOrThrow<Analytics>(res);
}

export async function refreshPrices(): Promise<{ refreshed: number }> {
  const res = await fetch("/api/portfolio/refresh-prices", {
    method: "POST",
    credentials: "include",
  });
  return jsonOrThrow<{ refreshed: number }>(res);
}
```

- [ ] **Step 4: Verify tests pass.**

```bash
cd frontend && npm test -- api/__tests__/portfolio.test.ts
```

Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
cd .. && git add frontend/src/api/portfolio.ts frontend/src/api/__tests__/portfolio.test.ts
git commit -m "feat(portfolio): typed /api/portfolio client"
```

---

## Task 8: `useHoldings` + `useAnalytics` hooks

**Files:**
- Create: `frontend/src/portfolio/useHoldings.ts`
- Create: `frontend/src/portfolio/useAnalytics.ts`
- Test: `frontend/src/portfolio/useHoldings.test.tsx`

- [ ] **Step 1: Write the failing test.**

```tsx
// frontend/src/portfolio/useHoldings.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useHoldings } from "./useHoldings";

const mockFetch = vi.fn();
beforeEach(() => {
  mockFetch.mockReset();
  (globalThis as unknown as { fetch: typeof fetch }).fetch = mockFetch;
});

describe("useHoldings", () => {
  it("loads holdings on mount", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify([{ id: "x", ticker: "AAPL", groups: [], currency: "USD", added_at: "", updated_at: "", shares: null, cost_basis: null, name: null, notes: null, last_price: null, previous_close: null, change_pct: null }]), { status: 200 }),
    );
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.holdings.length).toBe(1));
    expect(result.current.loading).toBe(false);
  });

  it("exposes optimistic create", async () => {
    mockFetch
      .mockResolvedValueOnce(new Response("[]", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: "x", ticker: "MSFT", groups: [], currency: "USD", added_at: "", updated_at: "", shares: "1", cost_basis: null, name: null, notes: null, last_price: null, previous_close: null, change_pct: null }), { status: 201 }),
      );
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.create({ ticker: "MSFT", shares: "1" });
    });
    expect(result.current.holdings.map((h) => h.ticker)).toContain("MSFT");
  });

  it("surfaces error state", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ detail: "boom" }), { status: 500 }));
    const { result } = renderHook(() => useHoldings());
    await waitFor(() => expect(result.current.error).not.toBeNull());
  });
});
```

- [ ] **Step 2: Verify it fails.**

```bash
cd frontend && npm test -- portfolio/useHoldings.test.tsx
```

Expected: module not found.

- [ ] **Step 3: Implement both hooks.**

```ts
// frontend/src/portfolio/useHoldings.ts
import { useCallback, useEffect, useState } from "react";
import {
  createHolding,
  deleteHolding,
  fetchHoldings,
  updateHolding,
  type Holding,
  type HoldingInput,
  type HoldingPatchInput,
} from "../api/portfolio";

export interface UseHoldingsResult {
  holdings: Holding[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  create: (input: HoldingInput) => Promise<Holding>;
  update: (id: string, patch: HoldingPatchInput) => Promise<Holding>;
  remove: (id: string) => Promise<void>;
}

export function useHoldings(): UseHoldingsResult {
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHoldings(await fetchHoldings());
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const create = useCallback(async (input: HoldingInput) => {
    const created = await createHolding(input);
    setHoldings((h) => [...h, created]);
    return created;
  }, []);

  const update = useCallback(async (id: string, patch: HoldingPatchInput) => {
    const updated = await updateHolding(id, patch);
    setHoldings((h) => h.map((x) => (x.id === id ? updated : x)));
    return updated;
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteHolding(id);
    setHoldings((h) => h.filter((x) => x.id !== id));
  }, []);

  return { holdings, loading, error, refresh, create, update, remove };
}
```

```ts
// frontend/src/portfolio/useAnalytics.ts
import { useCallback, useEffect, useState } from "react";
import { fetchAnalytics, type Analytics } from "../api/portfolio";

export interface UseAnalyticsResult {
  analytics: Analytics | null;
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useAnalytics(): UseAnalyticsResult {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAnalytics(await fetchAnalytics());
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { analytics, loading, error, refresh };
}
```

- [ ] **Step 4: Verify.**

```bash
cd frontend && npm test -- portfolio/useHoldings.test.tsx
```

Expected: all pass.

- [ ] **Step 5: Commit.**

```bash
cd .. && git add frontend/src/portfolio/useHoldings.ts frontend/src/portfolio/useAnalytics.ts frontend/src/portfolio/useHoldings.test.tsx
git commit -m "feat(portfolio): useHoldings + useAnalytics hooks"
```

---

## Task 9: `useLocalPref` + `useSortedHoldings`

**Files:**
- Create: `frontend/src/portfolio/useLocalPref.ts`
- Create: `frontend/src/portfolio/useSortedHoldings.ts`
- Test: `frontend/src/portfolio/useLocalPref.test.ts`, `useSortedHoldings.test.ts`

- [ ] **Step 1: Failing tests.**

```ts
// frontend/src/portfolio/useLocalPref.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLocalPref } from "./useLocalPref";

beforeEach(() => {
  window.localStorage.clear();
});

describe("useLocalPref", () => {
  it("returns default when empty", () => {
    const { result } = renderHook(() => useLocalPref("k", "default"));
    expect(result.current[0]).toBe("default");
  });

  it("persists value across renders", () => {
    const { result, rerender } = renderHook(() => useLocalPref("k", "default"));
    act(() => result.current[1]("new"));
    rerender();
    expect(result.current[0]).toBe("new");
    expect(window.localStorage.getItem("k")).toBe('"new"');
  });

  it("reads back existing value", () => {
    window.localStorage.setItem("k", '"existing"');
    const { result } = renderHook(() => useLocalPref("k", "default"));
    expect(result.current[0]).toBe("existing");
  });
});
```

```ts
// frontend/src/portfolio/useSortedHoldings.test.ts
import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useSortedHoldings, type SortOption } from "./useSortedHoldings";
import type { Holding } from "../api/portfolio";

const H = (ticker: string, price: string | null, groups: string[] = []): Holding => ({
  id: ticker,
  ticker,
  name: null,
  shares: null,
  cost_basis: null,
  currency: "USD",
  notes: null,
  groups,
  added_at: "",
  updated_at: "",
  last_price: price,
  previous_close: null,
  change_pct: null,
});

describe("useSortedHoldings", () => {
  it("filters by group", () => {
    const holdings = [H("AAPL", "100", ["Tech"]), H("XOM", "90", ["Energy"])];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "Tech", sort: "alpha_asc" }),
    );
    expect(result.current.map((h) => h.ticker)).toEqual(["AAPL"]);
  });

  it("All group includes every holding", () => {
    const holdings = [H("AAPL", "100", ["Tech"]), H("XOM", "90", ["Energy"])];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "All", sort: "alpha_asc" }),
    );
    expect(result.current).toHaveLength(2);
  });

  it("sorts alpha asc", () => {
    const holdings = [H("XOM", "90"), H("AAPL", "100")];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "All", sort: "alpha_asc" }),
    );
    expect(result.current.map((h) => h.ticker)).toEqual(["AAPL", "XOM"]);
  });

  it("sorts alpha desc", () => {
    const holdings = [H("AAPL", "100"), H("XOM", "90")];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "All", sort: "alpha_desc" }),
    );
    expect(result.current.map((h) => h.ticker)).toEqual(["XOM", "AAPL"]);
  });

  it("sorts price high to low, nulls last", () => {
    const holdings = [H("AAPL", "100"), H("XOM", "90"), H("ZZZ", null)];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "All", sort: "price_high_low" }),
    );
    expect(result.current.map((h) => h.ticker)).toEqual(["AAPL", "XOM", "ZZZ"]);
  });

  it("sorts price low to high, nulls last", () => {
    const holdings = [H("AAPL", "100"), H("XOM", "90"), H("ZZZ", null)];
    const { result } = renderHook(() =>
      useSortedHoldings(holdings, { group: "All", sort: "price_low_high" }),
    );
    expect(result.current.map((h) => h.ticker)).toEqual(["XOM", "AAPL", "ZZZ"]);
  });
});
```

- [ ] **Step 2: Verify fail.**

```bash
cd frontend && npm test -- portfolio/useLocalPref.test.ts portfolio/useSortedHoldings.test.ts
```

- [ ] **Step 3: Implement.**

```ts
// frontend/src/portfolio/useLocalPref.ts
import { useCallback, useState } from "react";

export function useLocalPref<T>(key: string, fallback: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? fallback : (JSON.parse(raw) as T);
    } catch {
      return fallback;
    }
  });

  const set = useCallback(
    (v: T) => {
      setValue(v);
      try {
        window.localStorage.setItem(key, JSON.stringify(v));
      } catch {
        /* storage quota — ignore */
      }
    },
    [key],
  );

  return [value, set];
}
```

```ts
// frontend/src/portfolio/useSortedHoldings.ts
import { useMemo } from "react";
import type { Holding } from "../api/portfolio";

export type SortOption = "alpha_asc" | "alpha_desc" | "price_high_low" | "price_low_high";

export interface SortedOpts {
  group: string;          // "All" special-cased
  sort: SortOption;
}

function decimalOrNull(raw: string | null): number | null {
  if (raw === null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function useSortedHoldings(holdings: Holding[], opts: SortedOpts): Holding[] {
  return useMemo(() => {
    const filtered =
      opts.group === "All"
        ? [...holdings]
        : holdings.filter((h) => h.groups.includes(opts.group));

    const byAlpha = (a: Holding, b: Holding, dir: 1 | -1) =>
      dir * a.ticker.localeCompare(b.ticker);

    const byPrice = (a: Holding, b: Holding, dir: 1 | -1) => {
      const ap = decimalOrNull(a.last_price);
      const bp = decimalOrNull(b.last_price);
      if (ap === null && bp === null) return byAlpha(a, b, 1);
      if (ap === null) return 1;
      if (bp === null) return -1;
      return dir * (bp - ap);
    };

    switch (opts.sort) {
      case "alpha_asc":
        filtered.sort((a, b) => byAlpha(a, b, 1));
        break;
      case "alpha_desc":
        filtered.sort((a, b) => byAlpha(a, b, -1));
        break;
      case "price_high_low":
        filtered.sort((a, b) => byPrice(a, b, 1));
        break;
      case "price_low_high":
        filtered.sort((a, b) => byPrice(a, b, -1));
        break;
    }

    return filtered;
  }, [holdings, opts.group, opts.sort]);
}
```

- [ ] **Step 4: Verify.**

```bash
cd frontend && npm test -- portfolio/useLocalPref.test.ts portfolio/useSortedHoldings.test.ts
```

- [ ] **Step 5: Commit.**

```bash
cd .. && git add frontend/src/portfolio/useLocalPref.ts frontend/src/portfolio/useSortedHoldings.ts frontend/src/portfolio/useLocalPref.test.ts frontend/src/portfolio/useSortedHoldings.test.ts
git commit -m "feat(portfolio): localStorage pref hook + group+sort derivation hook"
```

---

## Task 10: `Sparkline` + `AreaChart` SVG primitives

**Files:**
- Create: `frontend/src/portfolio/Sparkline.tsx`
- Create: `frontend/src/portfolio/AreaChart.tsx`
- Test: `frontend/src/portfolio/Sparkline.test.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/Sparkline.test.tsx
import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Sparkline } from "./Sparkline";

describe("Sparkline", () => {
  it("renders a polyline path with up color when last > first", () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} />);
    const path = container.querySelector("polyline");
    expect(path?.getAttribute("stroke")).toContain("--color-feedback-success");
  });

  it("renders down color when last < first", () => {
    const { container } = render(<Sparkline values={[3, 2, 1]} />);
    const path = container.querySelector("polyline");
    expect(path?.getAttribute("stroke")).toContain("--color-feedback-error");
  });

  it("renders nothing visible when fewer than 2 points", () => {
    const { container } = render(<Sparkline values={[]} />);
    expect(container.querySelector("polyline")).toBeNull();
  });
});
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.**

```tsx
// frontend/src/portfolio/Sparkline.tsx
import * as React from "react";

export interface SparklineProps {
  values: number[];
  width?: number;
  height?: number;
  className?: string;
}

export const Sparkline: React.FC<SparklineProps> = ({
  values,
  width = 80,
  height = 28,
  className,
}) => {
  if (values.length < 2) return <div className={className} style={{ width, height }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up
    ? "var(--color-feedback-success)"
    : "var(--color-feedback-error)";
  return (
    <svg width={width} height={height} className={className} role="img" aria-label="sparkline">
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};
```

```tsx
// frontend/src/portfolio/AreaChart.tsx
import * as React from "react";

export interface AreaChartProps {
  values: number[];
  width?: number;
  height?: number;
}

export const AreaChart: React.FC<AreaChartProps> = ({
  values,
  width = 160,
  height = 100,
}) => {
  if (values.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return [x, y] as const;
  });
  const line = pts.map(([x, y]) => `${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const area = `0,${height} ${line} ${width},${height}`;
  const up = values[values.length - 1] >= values[0];
  const stroke = up
    ? "var(--color-feedback-success)"
    : "var(--color-feedback-error)";
  const fillId = `area-fill-${up ? "up" : "down"}`;
  return (
    <svg width={width} height={height} role="img" aria-label="area chart">
      <defs>
        <linearGradient id={fillId} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.4" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${fillId})`} />
      <polyline
        points={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
      />
    </svg>
  );
};
```

- [ ] **Step 4: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/Sparkline.test.tsx
cd .. && git add frontend/src/portfolio/Sparkline.tsx frontend/src/portfolio/AreaChart.tsx frontend/src/portfolio/Sparkline.test.tsx
git commit -m "feat(portfolio): inline SVG sparkline + area chart primitives"
```

---

## Task 11: `HoldingsList` (List View)

**Files:**
- Create: `frontend/src/portfolio/HoldingsList.tsx`
- Test: `frontend/src/portfolio/HoldingsList.test.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/HoldingsList.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HoldingsList } from "./HoldingsList";
import type { Holding } from "../api/portfolio";

const h: Holding = {
  id: "1",
  ticker: "AAPL",
  name: "Apple Inc.",
  shares: "10",
  cost_basis: "150",
  currency: "USD",
  notes: null,
  groups: ["Tech"],
  added_at: "",
  updated_at: "",
  last_price: "180",
  previous_close: "178",
  change_pct: "1.12",
};

describe("HoldingsList", () => {
  it("renders ticker + name + price + change", () => {
    render(<HoldingsList holdings={[h]} onEdit={() => {}} onRemove={() => {}} onOpenChat={() => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText(/Apple/)).toBeInTheDocument();
    expect(screen.getByText(/180/)).toBeInTheDocument();
    expect(screen.getByText(/1\.12/)).toBeInTheDocument();
  });

  it("invokes onRemove when trash clicked", () => {
    const onRemove = vi.fn();
    render(<HoldingsList holdings={[h]} onEdit={() => {}} onRemove={onRemove} onOpenChat={() => {}} />);
    fireEvent.click(screen.getByLabelText(/remove AAPL/i));
    expect(onRemove).toHaveBeenCalledWith("1");
  });

  it("invokes onOpenChat when row clicked", () => {
    const onOpenChat = vi.fn();
    render(<HoldingsList holdings={[h]} onEdit={() => {}} onRemove={() => {}} onOpenChat={onOpenChat} />);
    fireEvent.click(screen.getByText("AAPL"));
    expect(onOpenChat).toHaveBeenCalledWith("AAPL");
  });

  it("shows em-dash when price missing", () => {
    const noPrice: Holding = { ...h, last_price: null, change_pct: null };
    render(<HoldingsList holdings={[noPrice]} onEdit={() => {}} onRemove={() => {}} onOpenChat={() => {}} />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("renders empty state when no holdings", () => {
    render(<HoldingsList holdings={[]} onEdit={() => {}} onRemove={() => {}} onOpenChat={() => {}} />);
    expect(screen.getByText(/your portfolio is empty/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Verify fail.**

- [ ] **Step 3: Implement.**

```tsx
// frontend/src/portfolio/HoldingsList.tsx
import * as React from "react";
import { Trash2, BarChart2 } from "lucide-react";
import { Sparkline } from "./Sparkline";
import type { Holding } from "../api/portfolio";

export interface HoldingsListProps {
  holdings: Holding[];
  onEdit: (holding: Holding) => void;
  onRemove: (id: string) => void;
  onOpenChat: (ticker: string) => void;
}

function formatPrice(raw: string | null, currency: string): string {
  if (raw === null) return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

function formatPct(raw: string | null): string {
  if (raw === null) return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(2)}%`;
}

export const HoldingsList: React.FC<HoldingsListProps> = ({
  holdings,
  onEdit,
  onRemove,
  onOpenChat,
}) => {
  if (holdings.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <BarChart2 size={40} className="text-[--color-text-tertiary]" />
        <div className="text-lg font-semibold text-[--color-text-primary]">
          Your portfolio is empty
        </div>
        <div className="text-sm text-[--color-text-secondary]">
          Search above to add tickers
        </div>
      </div>
    );
  }
  return (
    <ul role="list" className="divide-y divide-[--color-border-subtle]">
      {holdings.map((h) => {
        const change = h.change_pct === null ? null : Number(h.change_pct);
        const tone =
          change === null
            ? "text-[--color-text-secondary]"
            : change >= 0
              ? "bg-[--color-feedback-success]/10 text-[--color-feedback-success]"
              : "bg-[--color-feedback-error]/10 text-[--color-feedback-error]";
        return (
          <li
            key={h.id}
            className="group flex items-center gap-4 px-6 py-3 hover:bg-[--color-surface-hover] cursor-pointer"
            onClick={() => onOpenChat(h.ticker)}
          >
            <div className="flex-1 min-w-0">
              <div className="text-base font-semibold text-[--color-text-primary]">
                {h.ticker}
              </div>
              <div className="text-xs text-[--color-text-secondary] truncate">
                {h.name ?? " "}
              </div>
            </div>
            <div className="hidden md:block">
              <Sparkline
                values={
                  h.last_price !== null && h.previous_close !== null
                    ? [Number(h.previous_close), Number(h.last_price)]
                    : []
                }
              />
            </div>
            <div className="w-24 text-right text-base font-medium text-[--color-text-primary]">
              {formatPrice(h.last_price, h.currency)}
            </div>
            <div
              className={`text-sm font-medium rounded-full px-2 py-0.5 ${tone}`}
              aria-label={`change ${formatPct(h.change_pct)}`}
            >
              {formatPct(h.change_pct)}
            </div>
            <button
              type="button"
              aria-label={`remove ${h.ticker}`}
              className="opacity-0 group-hover:opacity-100 text-[--color-text-tertiary] hover:text-[--color-feedback-error] transition-opacity"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(h.id);
              }}
            >
              <Trash2 size={14} />
            </button>
            <button
              type="button"
              aria-label={`edit ${h.ticker}`}
              className="sr-only"
              onClick={(e) => {
                e.stopPropagation();
                onEdit(h);
              }}
            />
          </li>
        );
      })}
    </ul>
  );
};
```

- [ ] **Step 4: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/HoldingsList.test.tsx
cd .. && git add frontend/src/portfolio/HoldingsList.tsx frontend/src/portfolio/HoldingsList.test.tsx
git commit -m "feat(portfolio): List View component with sparkline + remove affordance"
```

---

## Task 12: `HoldingsGrid` (Card View)

**Files:**
- Create: `frontend/src/portfolio/HoldingsGrid.tsx`
- Test: `frontend/src/portfolio/HoldingsGrid.test.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/HoldingsGrid.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { HoldingsGrid } from "./HoldingsGrid";
import type { Holding } from "../api/portfolio";

const h: Holding = {
  id: "1",
  ticker: "AAPL",
  name: "Apple Inc.",
  shares: "10",
  cost_basis: "150",
  currency: "USD",
  notes: null,
  groups: ["Tech"],
  added_at: "",
  updated_at: "",
  last_price: "180",
  previous_close: "178",
  change_pct: "1.12",
};

describe("HoldingsGrid", () => {
  it("renders a card per holding", () => {
    render(<HoldingsGrid holdings={[h, { ...h, id: "2", ticker: "MSFT", name: "Microsoft" }]} onOpenChat={() => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("MSFT")).toBeInTheDocument();
  });

  it("invokes onOpenChat on card click", () => {
    const onOpenChat = vi.fn();
    render(<HoldingsGrid holdings={[h]} onOpenChat={onOpenChat} />);
    fireEvent.click(screen.getByRole("button", { name: /open AAPL/i }));
    expect(onOpenChat).toHaveBeenCalledWith("AAPL");
  });
});
```

- [ ] **Step 2: Implement.**

```tsx
// frontend/src/portfolio/HoldingsGrid.tsx
import * as React from "react";
import { AreaChart } from "./AreaChart";
import type { Holding } from "../api/portfolio";

export interface HoldingsGridProps {
  holdings: Holding[];
  onOpenChat: (ticker: string) => void;
}

function formatPrice(raw: string | null, currency: string): string {
  if (raw === null) return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

export const HoldingsGrid: React.FC<HoldingsGridProps> = ({ holdings, onOpenChat }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-6 py-4">
    {holdings.map((h) => {
      const change = h.change_pct === null ? null : Number(h.change_pct);
      const tone =
        change === null
          ? "text-[--color-text-secondary]"
          : change >= 0
            ? "bg-[--color-feedback-success]/10 text-[--color-feedback-success]"
            : "bg-[--color-feedback-error]/10 text-[--color-feedback-error]";
      return (
        <button
          key={h.id}
          type="button"
          aria-label={`open ${h.ticker}`}
          className="text-left bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden hover:border-[--color-border-secondary] hover:shadow-sm transition-all"
          onClick={() => onOpenChat(h.ticker)}
        >
          <div className="px-4 pt-4 text-base font-bold text-[--color-text-primary]">
            {h.ticker}
          </div>
          <div className="px-4 pb-2 text-xs text-[--color-text-secondary] truncate">
            {h.name ?? " "}
          </div>
          <div className="flex justify-center">
            <AreaChart
              values={
                h.last_price !== null && h.previous_close !== null
                  ? [Number(h.previous_close), Number(h.last_price)]
                  : []
              }
            />
          </div>
          <div className="px-4 pb-1 text-right text-lg font-semibold text-[--color-text-primary]">
            {formatPrice(h.last_price, h.currency)}
          </div>
          <div className="px-4 pb-4 flex justify-end">
            <span className={`text-sm font-medium rounded-full px-2 py-0.5 ${tone}`}>
              {change === null ? "—" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
            </span>
          </div>
        </button>
      );
    })}
  </div>
);
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/HoldingsGrid.test.tsx
cd .. && git add frontend/src/portfolio/HoldingsGrid.tsx frontend/src/portfolio/HoldingsGrid.test.tsx
git commit -m "feat(portfolio): Card View grid component"
```

---

## Task 13: `GroupTabs` + `SortControl` + `ViewToggle`

**Files:**
- Create: `frontend/src/portfolio/GroupTabs.tsx` + test
- Create: `frontend/src/portfolio/SortControl.tsx` + test
- Create: `frontend/src/portfolio/ViewToggle.tsx`

- [ ] **Step 1: Tests for GroupTabs.**

```tsx
// frontend/src/portfolio/GroupTabs.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { GroupTabs } from "./GroupTabs";

describe("GroupTabs", () => {
  it("always renders All first", () => {
    render(
      <GroupTabs
        groups={["Tech", "Dividends"]}
        selected="Tech"
        onSelect={() => {}}
        onCreate={() => {}}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    const tabs = screen.getAllByRole("tab");
    expect(tabs[0]).toHaveTextContent(/All/);
  });

  it("selecting a tab invokes onSelect", () => {
    const onSelect = vi.fn();
    render(
      <GroupTabs
        groups={["Tech"]}
        selected="All"
        onSelect={onSelect}
        onCreate={() => {}}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("tab", { name: /Tech/ }));
    expect(onSelect).toHaveBeenCalledWith("Tech");
  });

  it("'+ New Group' opens inline input and invokes onCreate on submit", () => {
    const onCreate = vi.fn();
    render(
      <GroupTabs
        groups={[]}
        selected="All"
        onSelect={() => {}}
        onCreate={onCreate}
        onRename={() => {}}
        onDelete={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /new group/i }));
    const input = screen.getByLabelText(/group name/i);
    fireEvent.change(input, { target: { value: "Watch" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onCreate).toHaveBeenCalledWith("Watch");
  });
});
```

- [ ] **Step 2: Implement GroupTabs.**

```tsx
// frontend/src/portfolio/GroupTabs.tsx
import * as React from "react";
import { Plus } from "lucide-react";

export interface GroupTabsProps {
  groups: string[];                        // custom groups; "All" is implicit
  selected: string;                        // "All" or a group name
  onSelect: (g: string) => void;
  onCreate: (name: string) => void;
  onRename: (oldName: string, newName: string) => void;
  onDelete: (name: string) => void;
}

export const GroupTabs: React.FC<GroupTabsProps> = ({
  groups,
  selected,
  onSelect,
  onCreate,
}) => {
  const [adding, setAdding] = React.useState(false);
  const [draft, setDraft] = React.useState("");
  const commit = () => {
    const v = draft.trim();
    if (v) onCreate(v);
    setDraft("");
    setAdding(false);
  };
  const tabs = ["All", ...groups];
  return (
    <div
      role="tablist"
      className="flex items-center gap-1 px-6 pb-0 pt-0 overflow-x-auto border-b border-[--color-border-subtle]"
    >
      {tabs.map((name) => {
        const active = name === selected;
        return (
          <button
            key={name}
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(name)}
            className={
              active
                ? "px-3 py-2 text-sm rounded-t-md font-medium text-[--color-text-primary] border-b-2 border-[--color-accent-primary] -mb-px"
                : "px-3 py-2 text-sm rounded-t-md text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
            }
          >
            {name}
          </button>
        );
      })}
      {adding ? (
        <input
          aria-label="group name"
          className="px-2 py-1 text-sm rounded border border-[--color-border-subtle] bg-[--color-bg-input]"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") commit();
            if (e.key === "Escape") {
              setAdding(false);
              setDraft("");
            }
          }}
          onBlur={commit}
          autoFocus
        />
      ) : (
        <button
          type="button"
          className="flex items-center gap-1 px-3 py-2 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
          onClick={() => setAdding(true)}
          aria-label="new group"
        >
          <Plus size={12} /> New Group
        </button>
      )}
    </div>
  );
};
```

- [ ] **Step 3: Test + implement SortControl.**

```tsx
// frontend/src/portfolio/SortControl.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SortControl } from "./SortControl";

describe("SortControl", () => {
  it("invokes onChange with the selected option", () => {
    const onChange = vi.fn();
    render(<SortControl value="alpha_asc" onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: /sort/i }));
    fireEvent.click(screen.getByRole("menuitem", { name: /price high/i }));
    expect(onChange).toHaveBeenCalledWith("price_high_low");
  });
});
```

```tsx
// frontend/src/portfolio/SortControl.tsx
import * as React from "react";
import { ChevronDown, Check } from "lucide-react";
import type { SortOption } from "./useSortedHoldings";

const LABELS: Record<SortOption, string> = {
  alpha_asc: "A → Z",
  alpha_desc: "Z → A",
  price_high_low: "Price High → Low",
  price_low_high: "Price Low → High",
};

export interface SortControlProps {
  value: SortOption;
  onChange: (v: SortOption) => void;
}

export const SortControl: React.FC<SortControlProps> = ({ value, onChange }) => {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label="sort"
        className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] flex items-center gap-1"
      >
        Sort: {LABELS[value]}
        <ChevronDown size={12} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute top-full mt-1 left-0 z-30 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1"
        >
          {(Object.keys(LABELS) as SortOption[]).map((opt) => (
            <button
              key={opt}
              role="menuitem"
              onClick={() => {
                onChange(opt);
                setOpen(false);
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover] whitespace-nowrap"
            >
              {value === opt ? (
                <Check size={12} className="text-[--color-accent-primary]" />
              ) : (
                <span className="w-3" />
              )}
              {LABELS[opt]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 4: Implement ViewToggle.**

```tsx
// frontend/src/portfolio/ViewToggle.tsx
import * as React from "react";
import { List, Grid } from "lucide-react";

export type ViewMode = "list" | "card";

export interface ViewToggleProps {
  mode: ViewMode;
  onChange: (m: ViewMode) => void;
}

export const ViewToggle: React.FC<ViewToggleProps> = ({ mode, onChange }) => (
  <div role="group" aria-label="view mode" className="flex items-center gap-1">
    {(["list", "card"] as const).map((m) => {
      const Icon = m === "list" ? List : Grid;
      const active = mode === m;
      return (
        <button
          key={m}
          type="button"
          aria-pressed={active}
          onClick={() => onChange(m)}
          className={
            active
              ? "bg-[--color-surface-active] text-[--color-text-primary] rounded-[--radius-md] w-8 h-8 flex items-center justify-center"
              : "text-[--color-text-secondary] hover:bg-[--color-surface-hover] rounded-[--radius-md] w-8 h-8 flex items-center justify-center"
          }
        >
          <Icon size={14} />
        </button>
      );
    })}
  </div>
);
```

- [ ] **Step 5: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/GroupTabs.test.tsx portfolio/SortControl.test.tsx
cd .. && git add frontend/src/portfolio/GroupTabs.tsx frontend/src/portfolio/GroupTabs.test.tsx frontend/src/portfolio/SortControl.tsx frontend/src/portfolio/SortControl.test.tsx frontend/src/portfolio/ViewToggle.tsx
git commit -m "feat(portfolio): group tabs + sort control + view toggle"
```

---

## Task 14: `SearchAndAdd` combobox

**Files:**
- Create: `frontend/src/portfolio/SearchAndAdd.tsx`
- Test: `frontend/src/portfolio/SearchAndAdd.test.tsx`

> Search delegates to a caller-supplied search function. The page wires it to a simple client that hits `GET /api/portfolio/search?q=...` (implemented in Task 15). If that endpoint does not ship in v1, the page falls back to accepting any user-typed ticker directly.

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/SearchAndAdd.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { SearchAndAdd } from "./SearchAndAdd";

describe("SearchAndAdd", () => {
  it("debounces search and shows results", async () => {
    const search = vi.fn().mockResolvedValue([
      { ticker: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
    ]);
    const onAdd = vi.fn();
    render(
      <SearchAndAdd search={search} existingTickers={new Set()} onAdd={onAdd} />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "aa" } });
    await waitFor(() => expect(search).toHaveBeenCalled());
    expect(await screen.findByText(/Apple Inc\./)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/Apple Inc\./));
    expect(onAdd).toHaveBeenCalledWith({ ticker: "AAPL", name: "Apple Inc." });
  });

  it("marks already-added results and prevents add", async () => {
    const search = vi.fn().mockResolvedValue([
      { ticker: "AAPL", name: "Apple Inc.", exchange: "NASDAQ" },
    ]);
    const onAdd = vi.fn();
    render(
      <SearchAndAdd search={search} existingTickers={new Set(["AAPL"])} onAdd={onAdd} />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "aa" } });
    await screen.findByText(/Already added/);
    fireEvent.click(screen.getByText(/Apple Inc\./));
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("shows 'No tickers found' for empty search results", async () => {
    const search = vi.fn().mockResolvedValue([]);
    render(
      <SearchAndAdd search={search} existingTickers={new Set()} onAdd={() => {}} />,
    );
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "xxx" } });
    await screen.findByText(/no tickers found/i);
  });
});
```

- [ ] **Step 2: Implement.**

```tsx
// frontend/src/portfolio/SearchAndAdd.tsx
import * as React from "react";
import { Search } from "lucide-react";

export interface SearchResult {
  ticker: string;
  name: string;
  exchange?: string;
}

export interface SearchAndAddProps {
  search: (q: string) => Promise<SearchResult[]>;
  existingTickers: Set<string>;
  onAdd: (input: { ticker: string; name: string }) => void;
  debounceMs?: number;
}

export const SearchAndAdd: React.FC<SearchAndAddProps> = ({
  search,
  existingTickers,
  onAdd,
  debounceMs = 300,
}) => {
  const [query, setQuery] = React.useState("");
  const [results, setResults] = React.useState<SearchResult[] | null>(null);
  const [open, setOpen] = React.useState(false);
  const timer = React.useRef<number | null>(null);

  React.useEffect(() => {
    if (timer.current !== null) window.clearTimeout(timer.current);
    if (query.trim().length === 0) {
      setResults(null);
      setOpen(false);
      return;
    }
    timer.current = window.setTimeout(async () => {
      try {
        const r = await search(query.trim());
        setResults(r);
        setOpen(true);
      } catch {
        setResults([]);
        setOpen(true);
      }
    }, debounceMs);
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [query, search, debounceMs]);

  return (
    <div className="relative flex-1">
      <div className="flex items-center gap-2 bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 focus-within:border-[--color-border-secondary]">
        <Search size={14} className="text-[--color-text-tertiary]" />
        <input
          role="combobox"
          aria-expanded={open}
          aria-label="search tickers"
          placeholder="Search tickers..."
          className="flex-1 bg-transparent outline-none text-sm text-[--color-text-primary]"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          onFocus={() => results !== null && setOpen(true)}
        />
      </div>
      {open && results !== null && (
        <div
          role="listbox"
          className="absolute left-0 right-0 top-full mt-1 z-30 max-h-80 overflow-y-auto bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md py-1"
        >
          {results.length === 0 ? (
            <div className="px-4 py-3 text-sm text-[--color-text-secondary]">
              No tickers found for &ldquo;{query}&rdquo;
            </div>
          ) : (
            results.slice(0, 8).map((r) => {
              const already = existingTickers.has(r.ticker.toUpperCase());
              return (
                <div
                  key={r.ticker}
                  role="option"
                  aria-selected={false}
                  className={
                    already
                      ? "flex items-center gap-3 px-4 py-2.5 cursor-default opacity-50"
                      : "flex items-center gap-3 px-4 py-2.5 hover:bg-[--color-surface-hover] cursor-pointer"
                  }
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => {
                    if (already) return;
                    onAdd({ ticker: r.ticker.toUpperCase(), name: r.name });
                    setQuery("");
                    setOpen(false);
                  }}
                >
                  <div className="text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0">
                    {r.ticker}
                  </div>
                  <div className="text-sm text-[--color-text-secondary] flex-1 truncate">
                    {r.name}
                  </div>
                  {r.exchange && (
                    <div className="text-xs text-[--color-text-tertiary]">
                      {r.exchange}
                    </div>
                  )}
                  {already && (
                    <div className="text-xs text-[--color-text-tertiary]">Already added</div>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
};
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/SearchAndAdd.test.tsx
cd .. && git add frontend/src/portfolio/SearchAndAdd.tsx frontend/src/portfolio/SearchAndAdd.test.tsx
git commit -m "feat(portfolio): search combobox with debounce + already-added gate"
```

---

## Task 15: Optional — `/portfolio/search` route (ticker lookup)

> This endpoint is scoped to v1 only if the configured financial adapter declares a `company_profile` capability (EODHD does). Falls back to a best-effort exact-ticker probe when a search index is not available.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/portfolio.py` (append the search handler)
- Modify: `packages/server/tests/test_routes/test_portfolio_routes.py`

- [ ] **Step 1: Append route tests.**

```python
def test_search_endpoint_probes_adapter(client, monkeypatch) -> None:
    c, _ = client
    r = c.get("/portfolio/search", params={"q": "AAPL"})
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    if body:
        first = body[0]
        assert "ticker" in first and "name" in first
```

- [ ] **Step 2: Append handler to `build_portfolio_router`.**

```python
    class SearchResultOut(BaseModel):
        ticker: str
        name: str
        exchange: str | None = None

    @router.get("/search", response_model=list[SearchResultOut])
    async def search_tickers(q: str, user: User = Depends(require_auth)) -> list[SearchResultOut]:
        if price_provider is None:
            return []
        # Probe the adapter for a company_profile on the literal ticker.
        # Real search indexes are out of scope for v1; this endpoint returns
        # [{ticker, name}] on exact match, [] otherwise.
        ticker_up = q.strip().upper()
        if not ticker_up:
            return []
        try:
            quote = await price_provider.get_quote(ticker_up, force=False)
        except Exception:
            return []
        if quote.last_price is None:
            return []
        return [SearchResultOut(ticker=ticker_up, name=ticker_up)]
```

- [ ] **Step 3: Verify + commit.**

```bash
uv run pytest packages/server/tests/test_routes/test_portfolio_routes.py -q
git add packages/server/src/openlia_server/routes/portfolio.py packages/server/tests/test_routes/test_portfolio_routes.py
git commit -m "feat(portfolio): /portfolio/search stub over the configured adapter"
```

---

## Task 16: `AddEditDrawer` (manual holding entry)

**Files:**
- Create: `frontend/src/portfolio/AddEditDrawer.tsx`
- Test: `frontend/src/portfolio/AddEditDrawer.test.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/AddEditDrawer.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AddEditDrawer } from "./AddEditDrawer";

describe("AddEditDrawer", () => {
  it("submits a new holding", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<AddEditDrawer open mode="create" onClose={() => {}} onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText(/ticker/i), { target: { value: "AAPL" } });
    fireEvent.change(screen.getByLabelText(/shares/i), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await screen.findByText(/save/i);
    expect(onSubmit).toHaveBeenCalledWith({
      ticker: "AAPL",
      shares: "10",
      cost_basis: null,
      currency: "USD",
      notes: null,
      groups: [],
    });
  });

  it("pre-fills when editing", () => {
    render(
      <AddEditDrawer
        open
        mode="edit"
        initial={{
          ticker: "MSFT",
          shares: "5",
          cost_basis: "300",
          currency: "USD",
          notes: null,
          groups: ["Tech"],
        }}
        onClose={() => {}}
        onSubmit={() => Promise.resolve()}
      />,
    );
    expect((screen.getByLabelText(/ticker/i) as HTMLInputElement).value).toBe("MSFT");
    expect((screen.getByLabelText(/shares/i) as HTMLInputElement).value).toBe("5");
  });
});
```

- [ ] **Step 2: Implement.**

```tsx
// frontend/src/portfolio/AddEditDrawer.tsx
import * as React from "react";

export interface HoldingDraft {
  ticker: string;
  shares: string | null;
  cost_basis: string | null;
  currency: string;
  notes: string | null;
  groups: string[];
}

export interface AddEditDrawerProps {
  open: boolean;
  mode: "create" | "edit";
  initial?: HoldingDraft;
  onClose: () => void;
  onSubmit: (draft: HoldingDraft) => Promise<void>;
}

const EMPTY: HoldingDraft = {
  ticker: "",
  shares: null,
  cost_basis: null,
  currency: "USD",
  notes: null,
  groups: [],
};

export const AddEditDrawer: React.FC<AddEditDrawerProps> = ({
  open,
  mode,
  initial,
  onClose,
  onSubmit,
}) => {
  const [draft, setDraft] = React.useState<HoldingDraft>(initial ?? EMPTY);
  const [saving, setSaving] = React.useState(false);

  React.useEffect(() => {
    setDraft(initial ?? EMPTY);
  }, [initial, open]);

  if (!open) return null;

  const update = <K extends keyof HoldingDraft>(k: K, v: HoldingDraft[K]) =>
    setDraft((d) => ({ ...d, [k]: v }));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={mode === "create" ? "add holding" : "edit holding"}
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md h-full bg-[--color-bg-elevated] border-l border-[--color-border-subtle] p-6 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[--color-text-primary]">
          {mode === "create" ? "Add holding" : "Edit holding"}
        </h2>
        <label className="flex flex-col gap-1 text-sm">
          Ticker
          <input
            aria-label="ticker"
            className="px-2 py-1 border border-[--color-border-subtle] bg-[--color-bg-input] rounded"
            value={draft.ticker}
            onChange={(e) => update("ticker", e.target.value.toUpperCase())}
            disabled={mode === "edit"}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Shares
          <input
            aria-label="shares"
            type="text"
            inputMode="decimal"
            className="px-2 py-1 border border-[--color-border-subtle] bg-[--color-bg-input] rounded"
            value={draft.shares ?? ""}
            onChange={(e) => update("shares", e.target.value || null)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Cost basis (per share)
          <input
            aria-label="cost_basis"
            type="text"
            inputMode="decimal"
            className="px-2 py-1 border border-[--color-border-subtle] bg-[--color-bg-input] rounded"
            value={draft.cost_basis ?? ""}
            onChange={(e) => update("cost_basis", e.target.value || null)}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Currency
          <input
            aria-label="currency"
            className="px-2 py-1 border border-[--color-border-subtle] bg-[--color-bg-input] rounded"
            value={draft.currency}
            onChange={(e) => update("currency", e.target.value.toUpperCase().slice(0, 3))}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Notes
          <textarea
            aria-label="notes"
            className="px-2 py-1 border border-[--color-border-subtle] bg-[--color-bg-input] rounded"
            value={draft.notes ?? ""}
            onChange={(e) => update("notes", e.target.value || null)}
          />
        </label>
        <div className="flex gap-2 justify-end mt-auto">
          <button
            type="button"
            className="px-3 py-1 text-sm text-[--color-text-secondary]"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            className="px-3 py-1 text-sm rounded bg-[--color-accent-primary] text-white"
            disabled={saving || !draft.ticker.trim()}
            onClick={async () => {
              setSaving(true);
              try {
                await onSubmit(draft);
                onClose();
              } finally {
                setSaving(false);
              }
            }}
          >
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/AddEditDrawer.test.tsx
cd .. && git add frontend/src/portfolio/AddEditDrawer.tsx frontend/src/portfolio/AddEditDrawer.test.tsx
git commit -m "feat(portfolio): add/edit drawer for manual holding entry"
```

---

## Task 17: `ImportCsvDialog`

**Files:**
- Create: `frontend/src/portfolio/ImportCsvDialog.tsx`
- Test: `frontend/src/portfolio/ImportCsvDialog.test.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/ImportCsvDialog.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { ImportCsvDialog } from "./ImportCsvDialog";

describe("ImportCsvDialog", () => {
  it("imports a selected file", async () => {
    const onImport = vi.fn().mockResolvedValue({ created: 2, errors: [] });
    const onClose = vi.fn();
    render(<ImportCsvDialog open onClose={onClose} onImport={onImport} />);
    const input = screen.getByLabelText(/csv file/i) as HTMLInputElement;
    const file = new File(["ticker\nAAPL\n"], "x.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    fireEvent.click(screen.getByRole("button", { name: /import/i }));
    await waitFor(() => expect(onImport).toHaveBeenCalledWith(file));
    await screen.findByText(/2 created/);
  });

  it("shows per-row errors", async () => {
    const onImport = vi.fn().mockResolvedValue({
      created: 0,
      errors: [{ row: 2, error: "shares: bad" }],
    });
    render(<ImportCsvDialog open onClose={() => {}} onImport={onImport} />);
    const input = screen.getByLabelText(/csv file/i) as HTMLInputElement;
    const file = new File(["bad"], "x.csv", { type: "text/csv" });
    Object.defineProperty(input, "files", { value: [file] });
    fireEvent.change(input);
    fireEvent.click(screen.getByRole("button", { name: /import/i }));
    await screen.findByText(/row 2/i);
    await screen.findByText(/shares: bad/);
  });
});
```

- [ ] **Step 2: Implement.**

```tsx
// frontend/src/portfolio/ImportCsvDialog.tsx
import * as React from "react";
import type { ImportReport } from "../api/portfolio";

export interface ImportCsvDialogProps {
  open: boolean;
  onClose: () => void;
  onImport: (file: File) => Promise<ImportReport>;
}

export const ImportCsvDialog: React.FC<ImportCsvDialogProps> = ({
  open,
  onClose,
  onImport,
}) => {
  const [file, setFile] = React.useState<File | null>(null);
  const [busy, setBusy] = React.useState(false);
  const [report, setReport] = React.useState<ImportReport | null>(null);

  if (!open) return null;

  const submit = async () => {
    if (!file) return;
    setBusy(true);
    try {
      const r = await onImport(file);
      setReport(r);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="import csv"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-6 flex flex-col gap-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[--color-text-primary]">
          Import holdings from CSV
        </h2>
        <p className="text-sm text-[--color-text-secondary]">
          Columns: <code>ticker,shares,cost_basis,currency,notes</code>. Only <code>ticker</code>{" "}
          is required.
        </p>
        <label className="flex flex-col gap-1 text-sm">
          CSV file
          <input
            type="file"
            accept=".csv,text/csv"
            aria-label="csv file"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        {report && (
          <div className="text-sm">
            <div className="font-medium text-[--color-text-primary]">
              {report.created} created
            </div>
            {report.errors.length > 0 && (
              <ul className="mt-2 space-y-1 text-[--color-feedback-error]">
                {report.errors.map((e) => (
                  <li key={e.row}>
                    Row {e.row}: {e.error}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1 text-sm text-[--color-text-secondary]"
          >
            Close
          </button>
          <button
            type="button"
            disabled={!file || busy}
            onClick={submit}
            className="px-3 py-1 text-sm rounded bg-[--color-accent-primary] text-white disabled:opacity-50"
          >
            {busy ? "Importing…" : "Import"}
          </button>
        </div>
      </div>
    </div>
  );
};
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/ImportCsvDialog.test.tsx
cd .. && git add frontend/src/portfolio/ImportCsvDialog.tsx frontend/src/portfolio/ImportCsvDialog.test.tsx
git commit -m "feat(portfolio): CSV import dialog with per-row error display"
```

---

## Task 18: `AnalyticsCards` + `PriceRefreshButton`

**Files:**
- Create: `frontend/src/portfolio/AnalyticsCards.tsx` + test
- Create: `frontend/src/portfolio/PriceRefreshButton.tsx`

- [ ] **Step 1: Test.**

```tsx
// frontend/src/portfolio/AnalyticsCards.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AnalyticsCards } from "./AnalyticsCards";

describe("AnalyticsCards", () => {
  it("renders totals", () => {
    render(
      <AnalyticsCards
        analytics={{
          total_market_value: "3350",
          total_cost_basis: "3000",
          total_unrealized_pnl: "350",
          total_unrealized_pnl_pct: "11.67",
          position_count: 2,
          by_group: {},
        }}
      />,
    );
    expect(screen.getByText(/3,350/)).toBeInTheDocument();
    expect(screen.getByText(/\+11.67%/)).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows loading state", () => {
    render(<AnalyticsCards analytics={null} />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Implement both.**

```tsx
// frontend/src/portfolio/AnalyticsCards.tsx
import * as React from "react";
import type { Analytics } from "../api/portfolio";

export interface AnalyticsCardsProps {
  analytics: Analytics | null;
}

function fmtMoney(raw: string | undefined): string {
  if (!raw) return "—";
  const n = Number(raw);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

export const AnalyticsCards: React.FC<AnalyticsCardsProps> = ({ analytics }) => {
  if (!analytics) {
    return (
      <div className="px-6 py-3 text-sm text-[--color-text-tertiary]">Loading analytics…</div>
    );
  }
  const pnl = Number(analytics.total_unrealized_pnl);
  const pct = Number(analytics.total_unrealized_pnl_pct);
  const tone =
    pnl >= 0 ? "text-[--color-feedback-success]" : "text-[--color-feedback-error]";
  return (
    <div className="grid grid-cols-1 md:grid-cols-4 gap-3 px-6 py-3">
      <Card label="Market value" value={fmtMoney(analytics.total_market_value)} />
      <Card label="Cost basis" value={fmtMoney(analytics.total_cost_basis)} />
      <Card
        label="Unrealized P&L"
        value={`${fmtMoney(analytics.total_unrealized_pnl)} (${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%)`}
        tone={tone}
      />
      <Card label="Positions" value={String(analytics.position_count)} />
    </div>
  );
};

const Card: React.FC<{ label: string; value: string; tone?: string }> = ({
  label,
  value,
  tone,
}) => (
  <div className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] px-4 py-3">
    <div className="text-xs text-[--color-text-secondary]">{label}</div>
    <div className={`text-base font-semibold text-[--color-text-primary] ${tone ?? ""}`}>
      {value}
    </div>
  </div>
);
```

```tsx
// frontend/src/portfolio/PriceRefreshButton.tsx
import * as React from "react";
import { RefreshCw } from "lucide-react";
import { refreshPrices, type RefreshError } from "../api/portfolio";

export interface PriceRefreshButtonProps {
  onRefreshed?: () => void;
}

export const PriceRefreshButton: React.FC<PriceRefreshButtonProps> = ({
  onRefreshed,
}) => {
  const [busy, setBusy] = React.useState(false);
  const [cooldown, setCooldown] = React.useState<number | null>(null);

  const handle = async () => {
    setBusy(true);
    try {
      await refreshPrices();
      onRefreshed?.();
    } catch (err) {
      const re = err as RefreshError;
      if (typeof re.retryAfter === "number") setCooldown(re.retryAfter);
    } finally {
      setBusy(false);
    }
  };

  React.useEffect(() => {
    if (cooldown === null) return;
    if (cooldown <= 0) {
      setCooldown(null);
      return;
    }
    const t = window.setTimeout(() => setCooldown((c) => (c === null ? null : c - 1)), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  return (
    <button
      type="button"
      className="flex items-center gap-1 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] disabled:opacity-50"
      onClick={handle}
      disabled={busy || cooldown !== null}
      aria-label="refresh prices"
    >
      <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
      {cooldown !== null ? `Retry in ${cooldown}s` : "Refresh"}
    </button>
  );
};
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/AnalyticsCards.test.tsx
cd .. && git add frontend/src/portfolio/AnalyticsCards.tsx frontend/src/portfolio/AnalyticsCards.test.tsx frontend/src/portfolio/PriceRefreshButton.tsx
git commit -m "feat(portfolio): analytics cards + price refresh button"
```

---

## Task 19: `PortfolioShell` + `PortfolioPage`

**Files:**
- Create: `frontend/src/portfolio/PortfolioShell.tsx`
- Create: `frontend/src/pages/PortfolioPage.tsx`
- Test: `frontend/src/portfolio/PortfolioShell.test.tsx`

- [ ] **Step 1: Test (shell composes the pieces correctly).**

```tsx
// frontend/src/portfolio/PortfolioShell.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { PortfolioShell } from "./PortfolioShell";

const mockFetch = vi.fn();
beforeEach(() => {
  mockFetch.mockReset();
  (globalThis as unknown as { fetch: typeof fetch }).fetch = mockFetch;
  window.localStorage.clear();
});

function queue(responses: Response[]) {
  for (const r of responses) mockFetch.mockResolvedValueOnce(r);
}

describe("PortfolioShell", () => {
  it("renders empty state when holdings and analytics are empty", async () => {
    queue([
      new Response("[]", { status: 200 }),
      new Response(
        JSON.stringify({
          total_market_value: "0",
          total_cost_basis: "0",
          total_unrealized_pnl: "0",
          total_unrealized_pnl_pct: "0",
          position_count: 0,
          by_group: {},
        }),
        { status: 200 },
      ),
    ]);
    render(
      <MemoryRouter>
        <PortfolioShell />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.queryByText(/loading analytics/i)).toBeNull());
    expect(screen.getByText(/Your portfolio is empty/)).toBeInTheDocument();
  });

  it("toggles between list and card view", async () => {
    queue([
      new Response(
        JSON.stringify([
          {
            id: "1",
            ticker: "AAPL",
            name: "Apple",
            shares: "10",
            cost_basis: "150",
            currency: "USD",
            notes: null,
            groups: [],
            added_at: "",
            updated_at: "",
            last_price: "180",
            previous_close: "178",
            change_pct: "1.12",
          },
        ]),
        { status: 200 },
      ),
      new Response(
        JSON.stringify({
          total_market_value: "1800",
          total_cost_basis: "1500",
          total_unrealized_pnl: "300",
          total_unrealized_pnl_pct: "20",
          position_count: 1,
          by_group: {},
        }),
        { status: 200 },
      ),
    ]);
    render(
      <MemoryRouter>
        <PortfolioShell />
      </MemoryRouter>,
    );
    await screen.findByText("AAPL");
    fireEvent.click(screen.getByRole("button", { name: /grid/i }));
    expect(screen.getAllByRole("button", { name: /open AAPL/i }).length).toBe(1);
  });
});
```

- [ ] **Step 2: Implement the shell.**

```tsx
// frontend/src/portfolio/PortfolioShell.tsx
import * as React from "react";
import { useNavigate } from "react-router-dom";
import { SearchAndAdd } from "./SearchAndAdd";
import { GroupTabs } from "./GroupTabs";
import { SortControl } from "./SortControl";
import { ViewToggle, type ViewMode } from "./ViewToggle";
import { HoldingsList } from "./HoldingsList";
import { HoldingsGrid } from "./HoldingsGrid";
import { AddEditDrawer } from "./AddEditDrawer";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { AnalyticsCards } from "./AnalyticsCards";
import { PriceRefreshButton } from "./PriceRefreshButton";
import { useHoldings } from "./useHoldings";
import { useAnalytics } from "./useAnalytics";
import { useLocalPref } from "./useLocalPref";
import { useSortedHoldings, type SortOption } from "./useSortedHoldings";
import {
  importHoldingsCsv,
  exportHoldingsCsvUrl,
  type Holding,
} from "../api/portfolio";

export const PortfolioShell: React.FC = () => {
  const navigate = useNavigate();
  const { holdings, create, remove, update, refresh } = useHoldings();
  const { analytics, refresh: refreshAnalytics } = useAnalytics();
  const [view, setView] = useLocalPref<ViewMode>("portfolio.view", "list");
  const [group, setGroup] = useLocalPref<string>("portfolio.group", "All");
  const [sort, setSort] = useLocalPref<SortOption>(
    `portfolio.sort.${group}`,
    "alpha_asc",
  );
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<Holding | null>(null);
  const [importOpen, setImportOpen] = React.useState(false);

  const allGroups = React.useMemo(() => {
    const s = new Set<string>();
    for (const h of holdings) for (const g of h.groups) s.add(g);
    return Array.from(s).sort();
  }, [holdings]);

  const sorted = useSortedHoldings(holdings, { group, sort });

  const openChat = (ticker: string) =>
    navigate(`/departments/equity-research?ticker=${encodeURIComponent(ticker)}`);

  const addFromSearch = async (p: { ticker: string; name: string }) => {
    await create({ ticker: p.ticker, name: p.name });
    await refreshAnalytics();
  };

  const searchImpl = React.useCallback(
    async (q: string) => {
      const res = await fetch(`/api/portfolio/search?q=${encodeURIComponent(q)}`, {
        credentials: "include",
      });
      if (!res.ok) return [];
      return (await res.json()) as { ticker: string; name: string; exchange?: string }[];
    },
    [],
  );

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex items-center px-6 border-b border-[--color-border-subtle]">
        <h1 className="text-xl font-semibold text-[--color-text-primary]">Portfolio</h1>
      </header>

      <AnalyticsCards analytics={analytics} />

      <div className="flex items-center gap-3 px-6 py-3 border-b border-[--color-border-subtle]">
        <SearchAndAdd
          search={searchImpl}
          existingTickers={new Set(holdings.map((h) => h.ticker))}
          onAdd={addFromSearch}
        />
        <button
          type="button"
          className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
          onClick={() => {
            setEditing(null);
            setDrawerOpen(true);
          }}
        >
          + Add manually
        </button>
        <button
          type="button"
          className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
          onClick={() => setImportOpen(true)}
        >
          Import CSV
        </button>
        <a
          className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
          href={exportHoldingsCsvUrl()}
          download="portfolio.csv"
        >
          Export CSV
        </a>
        <ViewToggle mode={view} onChange={setView} />
      </div>

      <GroupTabs
        groups={allGroups}
        selected={group}
        onSelect={setGroup}
        onCreate={(name) => {
          // A group exists as soon as a holding has it in its `groups`
          // array; creating an empty group is a no-op but we switch to it
          // so the user can add holdings via the add drawer.
          setGroup(name);
        }}
        onRename={() => { /* v1 no-op; full rename via add/edit drawer */ }}
        onDelete={() => { /* v1 no-op */ }}
      />

      <div className="flex items-center justify-between px-6 py-2">
        <SortControl value={sort} onChange={setSort} />
        <PriceRefreshButton
          onRefreshed={() => {
            void refresh();
            void refreshAnalytics();
          }}
        />
      </div>

      <div className="flex-1 overflow-y-auto">
        {view === "list" ? (
          <HoldingsList
            holdings={sorted}
            onEdit={(h) => {
              setEditing(h);
              setDrawerOpen(true);
            }}
            onRemove={async (id) => {
              await remove(id);
              await refreshAnalytics();
            }}
            onOpenChat={openChat}
          />
        ) : (
          <HoldingsGrid holdings={sorted} onOpenChat={openChat} />
        )}
      </div>

      <AddEditDrawer
        open={drawerOpen}
        mode={editing ? "edit" : "create"}
        initial={
          editing
            ? {
                ticker: editing.ticker,
                shares: editing.shares,
                cost_basis: editing.cost_basis,
                currency: editing.currency,
                notes: editing.notes,
                groups: editing.groups,
              }
            : undefined
        }
        onClose={() => setDrawerOpen(false)}
        onSubmit={async (d) => {
          if (editing) {
            await update(editing.id, d);
          } else {
            await create({ ...d });
          }
          await refreshAnalytics();
        }}
      />

      <ImportCsvDialog
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={async (file) => {
          const r = await importHoldingsCsv(file);
          await refresh();
          await refreshAnalytics();
          return r;
        }}
      />
    </div>
  );
};
```

```tsx
// frontend/src/pages/PortfolioPage.tsx
import { PortfolioShell } from "../portfolio/PortfolioShell";

export default function PortfolioPage() {
  return <PortfolioShell />;
}
```

- [ ] **Step 3: Verify + commit.**

```bash
cd frontend && npm test -- portfolio/PortfolioShell.test.tsx
cd .. && git add frontend/src/portfolio/PortfolioShell.tsx frontend/src/portfolio/PortfolioShell.test.tsx frontend/src/pages/PortfolioPage.tsx
git commit -m "feat(portfolio): PortfolioShell composition + PortfolioPage route entry"
```

---

## Task 20: Register the `/portfolio` route + sidebar nav entry

**Files:**
- Modify: `frontend/src/router.tsx`
- Modify: `frontend/src/components/Sidebar.tsx` (if absent add an entry; else update)

- [ ] **Step 1: Add the route.**

Inside `router.tsx` add `{ path: "/portfolio", element: <PortfolioPage /> }` (or equivalent shape) alongside the other department pages. Import `PortfolioPage` lazily if the shell uses `React.lazy`.

- [ ] **Step 2: Add the sidebar entry (icon `BarChart2`).** Insert alongside other department nav items, routing to `/portfolio`.

- [ ] **Step 3: Smoke test via dev server.**

```bash
cd frontend && npm run dev
# Open http://localhost:5173/portfolio and verify page mounts and displays an empty state.
```

- [ ] **Step 4: Verify and commit.**

```bash
cd frontend && npm test -- --run
cd .. && git add frontend/src/router.tsx frontend/src/components/Sidebar.tsx
git commit -m "feat(portfolio): register /portfolio route + sidebar entry"
```

---

## Task 21: Cross-plan integration — document the MB hook

**Files:**
- Modify: `planning/implementation-plans/README.md` (note the shipped helper)
- Modify: `planning/implementation-plans/endpoint-contract-matrix.md` (append rows for `/portfolio/*`)
- Modify: `planning/implementation-plans/route-authorization-matrix.md` (append rows for `/portfolio/*`)
- Modify: `planning/projectStructure.md` (record `services/portfolio.py` + frontend module)

- [ ] **Step 1: Append rows to endpoint-contract-matrix.md.**

For each of:
- `GET /portfolio/holdings`
- `POST /portfolio/holdings`
- `PUT /portfolio/holdings/{id}`
- `DELETE /portfolio/holdings/{id}`
- `POST /portfolio/holdings/import`
- `GET /portfolio/holdings/export`
- `GET /portfolio/analytics`
- `POST /portfolio/refresh-prices`
- `GET /portfolio/search`

Fill columns: backend function (`build_portfolio_router.*`), frontend client (`api/portfolio.ts.*`), auth dep (`build_require_active_user`), DTO names, owning plan (`Plan 21`), test file (`test_portfolio_routes.py`).

- [ ] **Step 2: Append rows to route-authorization-matrix.md.** All routes: `authenticated`, `owner-scoped` (holdings filtered by `user_id`), `must-change-password` → **blocked**, mounted in both personal and company.

- [ ] **Step 3: Document the cross-plan helper.** Under a new "Cross-plan helpers" section in README.md:

```
- `openlia_server.services.portfolio.get_reference_holdings(db, user_id) -> list[ReferenceHolding]`
  — consumed by Plan 16 (Morning Briefing Reference Portfolio toggle). Returns
  a lightweight projection `{ticker, name, shares, currency}`. No import of
  the full `HoldingDTO` class required.
```

- [ ] **Step 4: Commit.**

```bash
git add planning/implementation-plans/README.md planning/implementation-plans/endpoint-contract-matrix.md planning/implementation-plans/route-authorization-matrix.md planning/projectStructure.md
git commit -m "docs(plan): Plan 21 endpoint + auth matrix rows + MB reference-holdings helper"
```

---

## Task 22: Final acceptance — merge gate

- [ ] **Step 1:** One-line pre-PR sanity.

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
cd frontend && npm run build && npm test -- --run
```

Expected: all green, frontend builds without type errors.

- [ ] **Step 2:** Flip the README status row.

```
| 21 | 7 | Portfolio page | Done (YYYY-MM-DD) | 2026-04-23-phase-21-portfolio.md |
```

- [ ] **Step 3:** Open the PR.

```bash
gh pr create --base main --head feat/phase-21-portfolio --title "feat(phase-21): Portfolio page" --body "$(cat <<'EOF'
## Summary
- Ships the Portfolio page: holdings CRUD, group tabs, list/card views, per-group sort, analytics cards, CSV import/export, and on-demand price refresh with a 30s cooldown.
- Intraday quotes are cached in a process-local TTL (60s) wrapping the configured financial adapter.
- Adds `services.portfolio.get_reference_holdings(db, user_id)` for Plan 16's Reference Portfolio toggle.

## Test plan
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`
- [ ] `cd frontend && npm run build && npm test -- --run`
- [ ] Manual: dev server → `/portfolio` → add/edit/remove holding, import a 3-row CSV, export, toggle list/card, switch groups, refresh prices (expect 429 on second click within 30s).
EOF
)"
```

- [ ] **Step 4:** After merge, update `README.md` row to Done with the merge date. Rebuild the status table.

---

## Checklist — spec coverage

Every numbered bullet in `PortfolioPageSpec.md §Page Functionalities` maps to at least one task above:

1. **Ticker Search and Add** → Tasks 14 (SearchAndAdd), 15 (`/portfolio/search`), 19 (shell wiring).
2. **Ticker Remove** → Tasks 2 (service), 5 (route), 11 (list view remove button), 19 (shell).
3. **Groups** → Tasks 2 (notes JSON codec), 13 (GroupTabs), 19 (shell group state).
4. **View Modes** → Tasks 13 (ViewToggle), 9 (`useLocalPref`), 19 (shell).
5. **Sort Order** → Tasks 9 (`useSortedHoldings`), 13 (SortControl), 19 (per-group localStorage key).
6. **Real-Time Price Data** → Tasks 1 (`PortfolioPriceProvider`), 5 (list/analytics routes fold in quotes), 10 (Sparkline/AreaChart), 18 (PriceRefreshButton).
7. **Ticker Detail Navigation** → Tasks 11 + 12 (`onOpenChat` → `/departments/equity-research?ticker=...`).

Cross-cutting:
- **Empty / Loading / Market Closed / Error states** — Tasks 11, 12, 18 handle graceful degradation when `last_price` is null or the adapter errors.
- **Accessibility** — every interactive component declares `role`, `aria-label`, or `aria-selected`.
- **Responsive behaviour** — Tailwind breakpoints on Card View (`grid-cols-1 md:grid-cols-2 lg:grid-cols-3`); List View hides sparkline under `md`.

## Checklist — scope addenda beyond the spec

The request explicitly asks for CRUD + intraday refresh + analytics; the spec's Non-Goals section disables these. Plan 21 ships them anyway per the request, reusing shipped columns on `PortfolioHolding` (`shares`, `cost_basis`, `currency`, `notes`, `added_at`, `updated_at`) without a migration:

- CSV import/export → Tasks 4 (service), 5 (route), 17 (dialog).
- Analytics (totals + allocation + P&L) → Tasks 3 (service), 5 (route), 18 (cards).
- Cross-plan MB helper → Task 2 (`get_reference_holdings`), Task 21 (documentation).

## Rollback

If Task 22's merge gate fails on the aggregate test suite, bisect by reverting task commits in reverse order starting from Task 20 (route registration) — earlier tasks have no runtime side effects until the router is mounted in Task 6 and the frontend route lands in Task 20. The `PortfolioPriceProvider` is instantiated only when `app.state.financial_adapter` is set, so a partial revert that leaves Tasks 1–5 in place cannot crash the server on a fresh environment without an adapter.
