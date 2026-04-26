# Setup Wizard — Models Step Redesign and Adapter Fixes

Date: 2026-04-25
Trigger: manual browser smoke of the personal-mode wizard surfaced bugs in
the local-dev SPA flow and rough edges in the AI-models step UX.

## Summary

Five issues fixed and one wizard-step redesigned. All changes are local-dev-
ready behind the existing wizard gate; no DB migration; no API contract
break. Frontend test suite 731/731 passing; LLM adapter tests 212/212.

## Local dev / SPA fixes (pre-cursor to the redesign)

These were blocking the user from progressing through the wizard at all.

1. **`frontend/dist` path resolution off-by-one**
   - `_mount_frontend` resolved to `/Users/tkchang/Projects/frontend/dist`
     instead of `/Users/tkchang/Projects/OpenLIA/frontend/dist` (5 `..` vs.
     4). Fixed in `packages/server/src/openlia_server/app.py`.

2. **Wizard cookie path was `/setup`, not `/`**
   - Browser hits `/api/setup/*`, so the wizard session cookie wasn't sent
     and every request after Mode came back 409. Changed to `path="/"` in
     `routes/setup.py:_set_wizard_cookie`.

3. **SPA fallback was over-eager and method-narrow**
   - `_API_PREFIXES` constant was used to decide whether the SPA fallback
     should serve `index.html`. SPA route names like `/setup` and `/admin`
     collided with the API-prefix list. Replaced with a scope-flag set by
     the strip-prefix middleware (`scope["openlia_was_api"]`). The fallback
     is also now `@app.api_route(..., methods=["GET","POST","PUT","PATCH",
     "DELETE"])` so unmatched non-GET requests return 404 (not 405).

4. **Test fixture leaked SPA into prefix-strip tests**
   - `test_api_prefix_strip.py` started serving the real `frontend/dist`
     in some matrices. Pinned the test to a non-existent dist via
     `monkeypatch.setenv("OPENLIA_FRONTEND_DIST", str(tmp_path / "nope"))`.

## OpenAI reasoning-model compatibility

5. **`max_tokens` rejected by `o1`/`o3`/`o4`/`gpt-5` family**
   - Newer OpenAI reasoning models reject the legacy `max_tokens` field and
     also reject any non-default `temperature`. The adapter now detects the
     model prefix and routes accordingly:
     - `_is_reasoning_model(model)` returns true for `o1`, `o3`, `o4`,
       `gpt-5`.
     - For reasoning models, `generate()` sends `max_completion_tokens` and
       omits `temperature`.
     - For everything else, the legacy `max_tokens` + `temperature` payload
       is preserved.
   - Edited: `packages/core/src/openlia/llm/adapters/openai.py`
   - Coverage: `packages/core/tests/test_llm/test_adapter_openai.py` 8/8.

6. **OpenRouter / upstream-min `max_output_tokens >= 16`**
   - Several upstream providers reachable through OpenRouter enforce a
     minimum output token budget of 16. The wizard's connection probe used
     `max_tokens=1`, which got rejected as
     `"Invalid 'max_output_tokens': integer below minimum value"`.
   - Bumped the probe to `max_tokens=16` in every adapter's
     `test_connection`:
     - `openai.py`, `openai_compat.py`, `openrouter.py`, `anthropic.py`,
       `gemini.py`, `ollama.py`.
   - Coverage: `packages/core/tests/test_llm/` 212/212.

## Models-step UX redesign (the headline change)

The original "AI Models" wizard step required, per tier entry: a provider
dropdown (openai / anthropic / gemini / openrouter / openai_compat /
ollama), a model id, and an api key. This was repetitive (one key reused
across many tier entries) and put the burden of picking the right adapter
on the user.

New design splits the step into two screens within the same `models` step
(no `STEP_ORDER` change, no DB migration):

### Screen A — API Keys

`frontend/src/setup/steps/KeysScreen.tsx`

- User adds N keys; each has:
  - A user-chosen **label** (free text, must be unique within this wizard
    run).
  - The **API key** itself.
  - Optional **Base URL** under an "Advanced" disclosure, for self-hosted /
    proxy endpoints (vLLM, Together, Groq, llama.cpp, custom OpenRouter
    relays, etc.).
- No provider dropdown.
- Per-key actions: **Edit** (pencil) and **Delete** (trash).
- Next is gated on `keys.length > 0` and no editor open.

### Screen B — AI Models per tier

`frontend/src/setup/steps/TiersScreen.tsx`

- For each required tier (thinking / everyday / quick), user adds entries:
  - **Key dropdown** (keys are picked by their label).
  - **Model id** as free text.
- "Test & Save" runs the connection test; the inline error is now visible
  with a retry button (the previous UI hid it).
- Per-entry actions: **Edit** (re-tests on save) and **Delete**.
- Next is gated on ≥1 green entry per required tier (unchanged).

### Adapter auto-routing

`frontend/src/setup/steps/inferProvider.ts`

The frontend infers the adapter `kind` before calling the backend:

- **Override**: any base_url set → `openai_compat` (vLLM/Together/Groq all
  speak the OpenAI Chat Completions schema).
- **Primary signal — model id prefix**:
  - `claude-*`, `anthropic.*` → `anthropic`
  - `gemini-*` → `gemini`
  - `gpt-*`, `o1-*`, `o3-*`, `o4-*`, `chatgpt-*` → `openai`
  - contains `/` (e.g. `meta-llama/llama-3.1-70b`) → `openrouter`
- **Secondary signal — key prefix**:
  - `sk-ant-*` → `anthropic`
  - `sk-or-*` → `openrouter`
  - `sk-*` → `openai`
- Last-ditch fallback: `openai_compat`.

The backend `POST /api/setup/models` payload is unchanged; the frontend
expands tier entries into the existing `(provider, model, api_key,
base_url)` shape at save time. This keeps `wizard_models.save_models` and
the `_SetupTierEntryIn` schema intact.

### Cascading deletes

Removing an API key on Screen A automatically removes any tier entry that
referenced it on Screen B. Implemented in `ModelsStep.updateKeys`.

### Files

New:
- `frontend/src/setup/steps/inferProvider.ts`
- `frontend/src/setup/steps/KeysScreen.tsx`
- `frontend/src/setup/steps/TiersScreen.tsx`

Replaced:
- `frontend/src/setup/steps/ModelsStep.tsx` (now a screen switcher)
- `frontend/src/setup/steps/ModelsStep.test.tsx` (covers the new flow)

Deleted:
- `frontend/src/setup/steps/TierSlotCard.tsx` (folded into `TiersScreen`)

## Verification

- `npm run build`: clean
- `npx tsc -b`: no errors
- `npx vitest run src/setup/steps/ModelsStep.test.tsx`: 2/2 passing
- `npx vitest run`: 731/731 passing (one unrelated pre-existing unhandled
  rejection in `SettingsShellBlocker.test.tsx`, not introduced here)
- `uv run pytest packages/core/tests/test_llm/`: 212/212 passing
- Manual browser smoke (personal mode, OpenRouter `sk-or-v1-*` key): wizard
  advances through Identity → API Keys → AI Models → Providers without
  errors; per-tier connection tests succeed against the live OpenRouter
  endpoint.

## What this does *not* change

- No backend route changes (`POST /api/setup/models`, `POST
  /api/setup/models/test` schemas unchanged).
- No DB migration; `wizard_state.current_step="models"` still represents
  the whole keys+tiers flow.
- No CLI changes.
- No effect on the post-wizard Settings → Models page.

## Follow-ups

- Persisting partially-entered keys across a browser refresh during the
  wizard run is still client-state-only; refresh discards the in-progress
  list. Out of scope for this fix; flagged for the wizard-state spec.
- The "Advanced: set custom base URL" disclosure on Screen A could remember
  per-session preference, but the user-facing benefit is small.

---

## 2026-04-25 (later same day) — Providers + Review fixes

A second manual smoke pass through the freshly-redesigned wizard surfaced
seven more issues. All fixed; no DB migration; no API contract break.

### 7. EODHD (and every other builtin provider) returned 400 on save

`POST /api/setup/providers` failed with `400 invalid_provider` /
`"api_key mode requires base_url"` whenever the user picked a builtin
provider in the wizard. The wizard frontend doesn't ask for a base URL on
the "builtin" mode (by design — the user picked from a known catalog), but
`services.data_providers.create_provider` requires one for `API_KEY` mode.

Fix: introduced `_DEFAULT_BASE_URLS` in
`packages/server/src/openlia_server/services/wizard_providers.py` and
inject the canonical URL when builtin mode omits it. Covers `eodhd`,
`fmp`, `finnhub`, `yfinance`, `newsapi_ai`, `newsapi_org`, `mediastack`,
`reddit`, `x`, `brave`, `tavily`, `serper`.

### 8. Failed provider Test & Save showed no error message

Server returns `200 {ok: false, entry_id, error}` when the row is created
but the live health check fails. The frontend treated that as success and
auto-closed the form, leaving an "error" pill on a row with no
explanation.

Fix:
- `frontend/src/api/setup.ts` widened `addProvider`'s response type to
  include `error?: string | null`.
- `frontend/src/setup/steps/AddProviderForm.tsx` now passes the error up
  via `onSaved(testError)`.
- `frontend/src/setup/steps/ProvidersStep.tsx` renders a dismissable red
  banner above the rows when `testError` is set.

### 9. No way to fix a provider's API key without deleting the row

Reds-pill provider rows had only a Trash icon. If the user typo'd a key,
the only recovery was delete + re-add.

Fix: `frontend/src/setup/steps/ProviderRow.tsx` now has a Pencil icon
that reveals an inline password input. Save calls `PATCH /providers/:id`
with the new key, then `POST /providers/:id/test` to refresh status; the
parent `ProvidersStep` consumes the test result and surfaces failures in
the same banner.

### 10. Going Back from Providers → Models wiped local state

`ModelsStep` held `keys` and `tiers` in component state; navigating
forward unmounted the component, so Back rendered an empty Keys screen
even though the data had already been persisted server-side via
`POST /setup/models`.

Fix: `frontend/src/setup/steps/ModelsStep.tsx` now hydrates
`{screen, keys, tiers}` from `sessionStorage` on mount, persists on every
state change, and clears the slot once `saveModels` succeeds. Test file
gained a `beforeEach(() => sessionStorage.clear())` so the new
hydration doesn't bleed across tests.

### 11. `POST /api/setup/review/run` returned 500

`packages/server/src/openlia_server/services/wizard_review.py:120`
called `capabilities_for(row.provider_kind, row.model_ref,
row.capability_override)` positionally, but the function uses `*` and
requires keyword-only args. Synchronous `TypeError` → 500 from the route
handler (the asyncio task wasn't even scheduled).

Fix: pass `provider_kind=`, `model=`, `override=` as kwargs.

### 12. Wizard catalog listed adapters that weren't in the registry

`AddProviderForm`'s catalog included `reddit`, `x`, `brave`, `tavily`,
`serper`, but `packages/core/src/openlia/data/adapters/__init__.py`
didn't register them, so `create_provider` raised
`UnknownProviderKindError` → 400 even after the base-url fix.

Fix: added `RedditAdapter`, `XAdapter`, `BraveSearchAdapter`,
`TavilyAdapter`, `SerperAdapter` to
`packages/core/src/openlia/data/adapters/_stub.py` (extending the
existing `_StubAdapter` pattern) and registered them in
`adapters/__init__.py`. Calling `fetch` raises `DataNotAvailable` until
real implementations land.

### 13. Review step blocked Finish forever when any department was "blocked"

The EODHD adapter declares 5 capabilities (`stock_quote`,
`historical_prices`, `company_profile`, `company_news`,
`company_fundamentals`) but several departments require capabilities
that no shipped adapter currently exposes — notably `social_sentiment`
(retail_sentiment) and `macro_indicator` / `macro_indicators`
(macro_research, morning_briefing). EODHD's HTTP API has both endpoints,
but extending the adapter is out of scope for this pass.

Decision: surface the gap, don't gate the wizard. Users can finish
setup; blocked departments stay disabled at runtime until a covering
adapter is added.

Fix: `frontend/src/setup/steps/ReviewStep.tsx`
- `nextDisabled={state !== "complete"}` (dropped the `|| blocked`
  clause).
- Replaced the "Go back to Data Providers" message with a yellow warning
  banner enumerating each blocked department and what it needs:
  > N departments will be unavailable: <ul>retail sentiment — needs
  > social_sentiment</ul>… You can finish setup now. To enable these
  > later, add a provider that covers the missing capabilities in
  > Settings → Data Providers.
- Test file updated: the old "Finish disabled when blocked" assertion
  now asserts Finish is enabled and the banner renders.

### Verification (this pass)

- `npx vitest run src/setup/steps/{ProvidersStep,ModelsStep,ReviewStep}.test.tsx`:
  7/7 passing.
- `uv run pytest packages/core/tests/test_data/`: 70/70 passing.
- `npm run build`: clean.
- Manual browser smoke (personal mode, OpenRouter quick-tier model,
  EODHD financial provider): wizard advanced through Identity → Keys →
  Tiers → Providers → Review → Finish. Blocked-departments banner
  rendered correctly for retail_sentiment, macro_research,
  morning_briefing. EODHD API key edit + retest worked end-to-end.

### What this still does *not* change

- The EODHD adapter's capability set. Sentiment + macro endpoints exist
  on the EODHD service but aren't wired into the adapter; this is
  flagged as a follow-up below.
- Backend payload shapes for any wizard route.
- The `wizard_state.current_step="models"` semantics or any other
  step-flow contract.

### Follow-ups (added this pass)

- ~~Extend `EODHDAdapter` with `social_sentiment` and `macro_indicator`
  capabilities + corresponding `fetch` branches against
  `/sentiments?s={ticker}` and `/macro-indicator/{country}` so retail
  sentiment + macro research can run on the default provider set.~~ **Done
  in pass 3 below — additionally added economic_events, earnings_data,
  insider_transactions, analyst_ratings, dividends, splits, ipo_calendar.**
- Stub adapters for `reddit`, `x`, `brave`, `tavily`, `serper` are
  registry-only; their `fetch` raises `DataNotAvailable`. Implement at
  least one social-media + one web-search adapter so their categories
  aren't silently inert.
- Reset path: there is no UI/CLI affordance to send the wizard back to
  the setup stage after `wizard.completed=true`. Today the workaround
  is `mv ~/.openlia/openlia.db ~/.openlia/openlia.db.bak-<ts>` and
  restart the server; consider a `openlia admin reset-wizard` CLI
  command (or a Settings → Danger zone button) for testing/dev.

---

## 2026-04-25 (pass 3, evening) — Capability vocabulary + EODHD/FMP coverage

User flagged that EODHD configured as the sole provider showed
`earnings_data`, `financial_statements`, and `economic_events` as **unmet**
on the wizard review page, even though EODHD's public API obviously serves
all three. Root-cause analysis surfaced two distinct bugs in the
review-step deterministic resolver pipeline.

### 14. Capability-string vocabulary divergence

`packages/server/.../services/wizard_review.py:_try_deterministic_review`
does strict set-membership matching:
`by_capability.get(req)` against the union of each adapter's declared
`capabilities` ClassVar. Departments invented one set of strings; adapters
invented another. No shared glossary, so semantically-identical types
didn't match.

Concrete drift (before):

| Where | String used |
|---|---|
| `departments/equity_research.py`, `departments/earnings_update.py` | `financial_statements` |
| `data/adapters/{eodhd,fmp,finnhub,yfinance}.py` | `company_fundamentals` |
| `data/adapters/{fmp,finnhub}.py` | `earnings_calendar`, `economic_calendar` |
| `departments/{earnings_update,morning_briefing}.py` | `earnings_data`, `economic_events` |
| `departments/morning_briefing.py:optional` | `macro_indicators` (typo) |
| `departments/macro_research.py` | `macro_indicator` (singular) |

Fix — single canonical name per type, adapter-side renamed to match the
department-side vocabulary (department names are more domain-precise):

| Renamed from | To |
|---|---|
| `company_fundamentals` | `financial_statements` |
| `earnings_calendar` | `earnings_data` |
| `economic_calendar` | `economic_events` |
| `macro_indicators` (typo) | `macro_indicator` |

Files touched: 4 adapters (`eodhd.py`, `fmp.py`, `finnhub.py`,
`yfinance.py`), `data/manifest/requirements.yaml`,
`departments/morning_briefing.py`, plus 6 test files
(`test_data/test_adapters/*` and 2 server tests).

### 15. EODHD adapter under-declared its API surface

EODHD's REST API exposes `/economic-events`, `/calendar/earnings`,
`/macro-indicator/{country}`, `/insider-transactions`, `/sentiments`,
`/div/{ticker}`, `/splits/{ticker}`, `/calendar/ipos`, plus an
`AnalystRatings` sub-block of `/fundamentals/{ticker}` — none of which the
shipped adapter routed. After the rename in #14, those gaps were still the
reason departments showed unmet.

Fix — extended `capabilities` from 5 → 14 and refactored `fetch()` from
an inline `if/elif` chain to a `_route()` dispatcher with a
`_REQUIRES_SYMBOL` set so symbol-optional endpoints (economic_events,
ipo_calendar, earnings_data, insider_transactions, macro_indicator) work
without a phantom symbol parameter. Sub-block extraction generalized via
`_FUNDAMENTALS_BLOCK = {"financial_statements": "Financials",
"analyst_ratings": "AnalystRatings"}` so two capabilities share one
upstream call to `/fundamentals/{ticker}` and slice down to the relevant
block.

New EODHD capabilities:

| Capability | Endpoint |
|---|---|
| `economic_events` | `GET /economic-events` |
| `earnings_data` | `GET /calendar/earnings` |
| `macro_indicator` | `GET /macro-indicator/{country}` (alpha-3) |
| `insider_transactions` | `GET /insider-transactions` |
| `social_sentiment` | `GET /sentiments?s={tickers}` |
| `analyst_ratings` | `/fundamentals/{ticker}` → AnalystRatings block |
| `dividends` | `GET /div/{ticker}` |
| `splits` | `GET /splits/{ticker}` |
| `ipo_calendar` | `GET /calendar/ipos` |

### 16. FMP adapter — added analyst_ratings + macro_indicator

While the FMP adapter already declared 23 capabilities, it was missing the
two that several departments care about most. Added:

| Capability | Endpoint |
|---|---|
| `analyst_ratings` | v3 `GET /rating/{symbol}` |
| `macro_indicator` | v4 `GET /economic?name={indicator}` (defaults to `GDP`) |

`macro_indicator` joined `_V4_CAPABILITIES` so the existing v3/v4 base-URL
splitter routes it correctly.

### Tests

13 new tests for EODHD and 4 for FMP cover each new capability's URL,
query-param shaping, and (for fundamentals sub-blocks) the
"missing block raises DataNotAvailable" path. The pre-existing
`test_fetch_rejects_unknown_capability` was updated since
`insider_transactions` is now declared — it asserts on
`"not_a_real_capability"` instead.

Two server tests updated for the new coverage:
- `test_routes/test_data_providers_routes.py:test_auto_map_returns_summary`
  no longer asserts `insider_transactions` ∈ unmet (EODHD covers it now).
- `test_services/test_data_providers.py:test_auto_map_populates_mappings_for_every_basic_and_advanced_type`
  same change.

### Verification (pass 3)

- `uv run pytest packages/server/tests/ packages/core/tests/`: **2156
  passing**.
- `uv run ruff check` on changed adapter + test files: clean.

### What this changes for the user-visible review page

With EODHD configured as the sole financial provider, these department
basics now resolve in the deterministic stage (no LLM call) and show as
**ready** on the review screen instead of blocked:

- `equity_research`: `financial_statements` (was unmet — vocabulary)
- `earnings_update`: `earnings_data`, `financial_statements`
- `morning_briefing`: `economic_events`
- `panic_thermometer`: `economic_events`
- `macro_research`: `macro_indicator`
- `retail_sentiment`: `social_sentiment`

The blocked-department banner from issue #13 will accordingly show a
shorter list (or none) on a default EODHD-only personal-mode setup.

### Follow-ups (pass 3)

- Consider a single `RequirementType` constant module
  (`openlia.data.capability_types`) to lock the vocabulary so future
  adapters/departments can't drift again. Skipped for now since the
  current rename + tests catch the issue at suite time.
- Other adapters (Finnhub, yfinance, FMP) still have their own gaps
  relative to their underlying APIs (e.g. yfinance has no `earnings_data`
  routing despite the `earnings` module). Lower priority — EODHD is the
  default.
