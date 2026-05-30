# Earnings Update v2 — Dynamic Data Sources (Phase 1) — Design

**Date:** 2026-05-30
**Branch:** `feat/eu-v2-dynamic-data-sources` (stacks on `feat/earnings-update-v2-frontend`, PR #214)
**Status:** Approved design, awaiting spec review before implementation plan.

## Problem

The Earnings Update v2 settings modal ("Data sources" section,
`frontend/src/components/earnings-update/ReportSettingsModal.tsx`) renders three
**hardcoded** toggles — Financial data, Earnings calendar, Web search — regardless
of what the user has actually configured. The list never changes. The user wants it
to reflect the data sources they have configured and to change accordingly.

## Key architectural constraints (from investigation)

Two facts shape the whole design:

1. **The connector dispatcher is not wired into report engines.** The dispatcher
   subsystem (`openlia.connectors.dispatch`, MCP/CLI/python-lib transports,
   `RunnerCallableSpec`, `fetch_need`) is fully built and wired into the
   Secretary/chat runner, but **not** into `report_eu` / `report_v3`. Those engines
   build a static EODHD transport bundle (`build_eu_v2_transports`) and never read
   the connector registry. Routing arbitrary configured connectors to the EU engine
   is a from-scratch bridge — **deferred to Phase 2**.

2. **The connector registry and the engine's env keys are decoupled.** Installing an
   EODHD connector stores its key in the DB (`Connector.secrets["EODHD_API_KEY"]`);
   the EU engine reads `os.getenv("EODHD_API_KEY")` only. So:
   - env key set, zero registry rows → engine **works** (common in personal mode);
   - connector installed, env unset → engine **cannot** see the key → broken report.

   Therefore the Data Sources list must reflect **effective availability** (what the
   engine can actually use), not the registry alone — otherwise env-only users see an
   empty list and lose working toggles.

## Decisions (locked with user)

- **Source of truth for the list:** effective availability = installed registry
  connectors + env-key sources + model-native web search.
- **Build depth now:** Phase 1 only — dynamic UI + availability + a small secret
  bridge. Real per-connector routing is Phase 2 (sketched, not built).
- **Persistence:** keep the three existing booleans
  (`financial_enabled` / `calendar_enabled` / `web_search_enabled`). No migration.
- **Other connectors:** show a muted footnote naming configured-but-not-yet-routable
  connectors.

## Phase 1 scope

The EU engine keeps exactly three capability slots. Phase 1 makes each slot
**availability-gated and provider-labeled**, driven by env + registry + model
capabilities, with a backend bridge so an installed EODHD connector's key actually
works.

### 1. Availability rules

| Slot | `available` when | `provider_label` |
| --- | --- | --- |
| **Financial data** (`financial_enabled`) | `EODHD_API_KEY` env set **OR** a `validated` connector with `provider_id == "eodhd"` exists | `"EODHD"` |
| **Earnings calendar** (`calendar_enabled`) | same condition as Financial (EODHD provides the calendar) | `"EODHD"` |
| **Web search** (`web_search_enabled`) | `capabilities_for(provider_kind, model).web_search_native == True` for the user's current settings | `"via {model}"` |

`unavailable_reason` strings (shown on disabled toggles):
- Financial / Earnings calendar: `"Set EODHD_API_KEY or install the EODHD connector in Settings → Connectors."`
- Web search: `"The selected model does not support web search."`

**Phase 1 deliberately does not** make non-EODHD financial connectors (FMP, Finnhub),
news connectors, or web_search-category connectors count toward availability — the
engine cannot route them yet (Phase 2). They appear only in the muted footnote (§4).

### 2. Backend: EODHD secret bridge

So that an installed EODHD connector is honestly usable, resolve the EODHD key from
**env first, then the validated EODHD connector's stored secret**.

- New helper in `eu_v2_wiring.py`:
  `resolve_eodhd_api_key(db: Session) -> str | None`
  returns `os.getenv("EODHD_API_KEY")` or, failing that, the
  `secrets["EODHD_API_KEY"]` of the first `validated` connector with
  `provider_id == "eodhd"` (via `connectors_service.list_connectors`).
- `build_eu_v2_transports` gains an optional `api_key: str | None = None` parameter.
  When provided it is used directly; when `None` it falls back to the current
  `os.getenv` behavior (preserves all existing call sites and tests).
- `eu_v2_run_service` (which holds the `db` session) resolves the key via
  `resolve_eodhd_api_key(db)` and passes it into `build_eu_v2_transports(api_key=...)`.

This is the only engine-side change in Phase 1. It does **not** touch the dispatcher.

### 3. Backend: data-sources endpoint

New route on the EU v2 router:

`GET /api/departments/earnings-update/v2/data-sources` → `DataSourcesOut`

```python
class DataSourceSlot(BaseModel):
    available: bool
    provider_label: str | None
    unavailable_reason: str | None

class OtherConnector(BaseModel):
    display_name: str
    category: str  # financial | news | social | web_search

class DataSourcesOut(BaseModel):
    financial: DataSourceSlot
    earnings_calendar: DataSourceSlot
    web_search: DataSourceSlot
    other_connectors: list[OtherConnector]  # configured but not yet routable (Phase 2)
```

Computation (service: `eu_v2_settings.compute_data_sources` or a new
`eu_v2_data_sources.py`):
- Read the user's current `EuSettings` (for `provider_kind` / `model`).
- `eodhd_available = resolve_eodhd_api_key(db) is not None`.
- `financial` / `earnings_calendar`: `available = eodhd_available`, label `"EODHD"`.
- `web_search`: `available = capabilities_for(settings.provider_kind, settings.model).web_search_native`,
  label `f"via {settings.model}"`.
- `other_connectors`: every `validated` connector that is **not** the EODHD financial
  source already represented above — i.e. all validated connectors except the
  `provider_id == "eodhd"` one. Each contributes `{display_name, category}`.

Gated by the existing `_eu_v2_gate` (503 when `EARNINGS_ENGINE_VERSION != v2`),
same as the other EU v2 routes.

### 4. Frontend

**API client** (`frontend/src/api/earnings-update.ts`):
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
export const getEuDataSources = () =>
  fetchJson<DataSourcesInfo>("/api/departments/earnings-update/v2/data-sources");
```

**Hook** (`frontend/src/hooks/useEuDataSources.ts`): fetches on mount and exposes
`{ dataSources, loading, error, refresh }`. The modal calls `refresh()` whenever the
selected model changes (model flips web-search availability).

**Modal** (`ReportSettingsModal.tsx`, "Data sources" section):
- For each of the three slots, render the existing `Toggle` but:
  - label = `t(slot title) + " · " + provider_label` when available
    (e.g. "Financial data · EODHD", "Web search · via claude-opus-4-8");
  - when `available === false`: render the toggle **disabled**, forced visually off,
    with the `unavailable_reason` shown as muted helper text beneath it; do not let it
    be turned on.
- **Empty state:** when all three slots are unavailable, replace the toggle group with
  a muted message: "No data sources available. Configure a data provider in
  Settings → Connectors, or pick a model with web search." (i18n key).
- **Muted footnote:** when `other_connectors` is non-empty, render below the group:
  "Also configured: {names} — routing for these arrives in a later update."
  (`names` = comma-joined `display_name`s; i18n key with interpolation).
- Saving still persists the three booleans. A slot that is unavailable is saved as
  `false` (cannot be on).

All new strings added to both `en.json` and `zh-TW.json` under
`earnings.settings_modal.*`.

### 5. Run-time enforcement

In `eu_v2_run_service` (where `EnabledConnectors` is built from settings), AND-gate
each toggle with live availability so a stored `true` for a now-unavailable source
cannot reach the engine:
- `financial = settings.financial_enabled and eodhd_available`
- `earnings_calendar = settings.calendar_enabled and eodhd_available`
- `web_search = settings.web_search_enabled and capabilities_for(...).web_search_native`

This keeps the engine honest even if settings were saved while a source was available
and it later disappeared.

## As-built note (i18n refinement)

To keep all user-facing text localizable (en + zh-TW), the §3 endpoint delivers
`unavailable_reason` as a stable **code** (`eodhd_unconfigured` | `model_no_web_search`,
plus a client-side `ds_reason_unknown` fallback for any future code), not an English
sentence, and `provider_label` as the raw provider/model identity (`"EODHD"` or the
model id). The settings modal composes the displayed strings client-side: the slot
label is `"{base} · {provider}"` (web search wraps the model in the localized
`ds_via` = "via {{provider}}"), and the reason text resolves `ds_reason_{code}` with a
graceful fallback. The four reason/label/empty/footnote strings live in both locale
files.

## Phase 2 (sketch only — NOT in this plan)

- Wire `openlia.connectors.dispatch.Dispatcher` into `report_eu` (pass it into the
  runner / catalog builder).
- Data Sources becomes true per-connector toggles across all categories.
- Migrate the three booleans → an enabled-connector-id set (migration).
- Route each enabled connector's tools to the LLM; reconcile prefixed tool names and
  the citation ledger.

## Testing

**Backend**
- `compute_data_sources` availability matrix: env-only / EODHD-connector-only /
  both / neither; model with vs without `web_search_native`.
- `resolve_eodhd_api_key`: env set; env unset + validated EODHD connector; env unset +
  no connector (None); ignores non-`validated` EODHD rows.
- `other_connectors` excludes the EODHD financial source and includes other validated
  connectors.
- Endpoint returns 503 when the gate is off; 200 with the computed shape when on.
- `eu_v2_run_service` AND-gating: stored `true` + unavailable source → engine receives
  `false`.

**Frontend**
- `useEuDataSources` fetch + `refresh` on model change.
- Modal: available slot renders provider label + enabled toggle; unavailable slot
  renders disabled + reason and cannot be toggled on; empty state when all
  unavailable; footnote shows when `other_connectors` non-empty and hidden when empty.

## Non-goals

- Any dispatcher / connector-routing wiring into the engine (Phase 2).
- Per-connector persistence or migrations.
- Supporting non-EODHD financial providers at run time.
- Changing the weekly calendar sync / dispatch trigger (it already depends on EODHD).
