# Resolver Redesign — User-Picks, LLM-Glues

Status: Design — locked 2026-05-02

Supersedes the auto-resolve sections (§4.4, §7) of `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md` and the wizard flow described in `docs/superpowers/plans/2026-04-30-adapter-resolver-grounding.md`. The data model, dispatcher, transport, and built-in template machinery from the original spec stay intact and are referenced rather than restated.

## Table of contents

1. Why this redesign
2. Scope and what does not change
3. Trigger: when manual resolution is required
4. Resolve screen composition
5. Resolution modes
6. The per-need LLM call
7. Smoke-call gate
8. Heterogeneous responses and `field_map`
9. Mutability and post-wizard admin
10. Storage and audit trail
11. Operational mechanics
12. Override semantics on template upgrades
13. Out of scope and deferred

---

## 1. Why this redesign

The shipped resolver auto-maps a `RunnerNeed` onto a connector callable using a single LLM call. Built-in templates ship pre-baked specs; custom connectors run the LLM at wizard time with no user pick involved. The May 1 review of Day-1 catalog templates surfaced the dominant ongoing risk: hallucinated tool names, speculative method codes, and silent semantic mismatches that pass structural validation but fail at dept-run time.

This redesign flips the LLM's role. The user picks the endpoint or the URL; the LLM validates and glues. The LLM is no longer a chooser, it is a translator and a guard. One LLM call per need.

## 2. Scope and what does not change

Unchanged from the connector dataflow spec:
- Connector data model (`Connector` row, multi-mode launch, secrets, source enum)
- Per-department `<dept>.needs.yaml` declarations and the `RunnerNeed` dataclass
- Built-in templates and pre-baked `runner_specs` for catalog connectors
- Dispatcher, transport protocols, and runtime invocation of `CallableSpec`
- Connector add/canary flow (entering keys, install-time validation)

Changed by this redesign:
- The wizard step that turns connector inventory into resolved specs
- The post-LLM validation gate (now also gates `field_map` and dept-side `from_dict` constructibility for `list[dict]` shapes)
- The shape of `CallableSpec` (adds `field_map` field)
- Per-need YAML (adds `canonical_keys`)
- A new admin panel for post-wizard spec management
- Two new audit tables

## 3. Trigger: when manual resolution is required

Granularity is **per need**, not per connector or per category.

A need is auto-resolved if any installed catalog connector's pre-baked `runner_specs` covers it. The Day-1 catalog covers all 12 declared needs, so a pure-catalog install requires zero manual resolution.

A need requires manual resolution if no installed catalog connector covers it. Mixed installs are partial: e.g., catalog FMP plus a custom news provider auto-resolves financial needs from FMP and surfaces news needs for manual input. Catalog-covered rows are still rendered on the resolve screen (see §4) so the user can audit and override them.

## 4. Resolve screen composition

The screen lists every need across the two need-bearing departments (`macro_research` × 11, `retail_sentiment` × 1). Twelve rows, always.

Three row states:
- **Resolved (catalog)** — pre-baked spec from a built-in template. Read-only by default, with an Edit button.
- **Resolved (manual)** — user picked + LLM glued + smoke passed. Editable.
- **Unresolved** — needs user input. Resolve form expanded inline.

Edit on a resolved row drops the spec to draft state. The current spec stays live until the new spec passes its smoke call. Failed edits do not break a working resolution.

The wizard cannot finish until every row is in a resolved state.

## 5. Resolution modes

### 5.1 Connector + endpoint

Default mode for needs satisfied by a structured API.

User flow:
1. Pick a connector from the dropdown (filtered to installed connectors).
2. Type to search the connector's cached endpoints. Searches over `cached_tools` for MCP sources and `cached_python_callables` for python_lib. Selecting one fixes the endpoint identifier.
3. Optional: type a freeform hint for the LLM (e.g., "pass `country` as ISO3", "use `period=annual`"). The hint is fed verbatim into the LLM prompt.
4. Click Save.

Type-to-search is required because catalog connectors expose 80+ endpoints; a scrollable dropdown is unusable.

The LLM authors the full `CallableSpec`: `param_bindings`, `constants`, `transforms`, `result_path`, and (for `list[dict]` shapes) `field_map`. The user does not bind parameters or define transforms manually; that cognitive load stays with the LLM.

### 5.2 Websearch

Available only when an installed connector has `category = web_search` (Firecrawl from catalog or custom).

User flow:
1. Click "Resolve via websearch."
2. Provide a URL.
3. Optional: type a freeform hint (e.g., "look for the cell labeled 'Total reserves' in the third table").
4. Click Save.

If no `web_search` connector is installed, this mode is disabled with a "Install a web_search connector first" notice. There is no core HTTP fetcher; websearch is a constrained sub-mode of §5.1 that auto-fixes the connector to the user's `web_search` connector and the endpoint to its scrape callable. The LLM authors a Firecrawl JSON-extraction schema and the same `CallableSpec` shape.

## 6. The per-need LLM call

Inputs:
- The full `RunnerNeed` (id, description, shape, parameters, `canonical_keys`)
- The user-picked connector and endpoint identifier (or URL for websearch)
- The endpoint's cached schema (`input_schema` for MCP, signature for python_lib) or for websearch, the URL only
- The user's freeform hint, if any

Output: a candidate `CallableSpec` plus an optional warning string.

The LLM is asked to:
1. Bind need parameters to callable arguments, applying transforms from the allowlist where needed.
2. Author `result_path` to walk the response into the need's shape.
3. For `list[dict]` shapes, author `field_map` mapping endpoint per-item keys to the need's `canonical_keys`.
4. Self-assess whether the picked endpoint is semantically appropriate for the need. If it judges the pick wrong (category error, e.g., quote endpoint for a debt-to-GDP need), emit a one-line warning.

Validation gate after the LLM call:
- Tool/method exists in the cache.
- Each `param_binding.to_arg` is a real arg on the callable.
- Each transform is in the allowlist (extended to: `upper`, `lower`, `country_iso2_to_iso3`, `to_float`, `to_int`, `strip`, `list_first`, `iso_date`).
- Constants are JSON-serializable.
- `field_map` keys cover every required canonical key for the need's shape.

LLM call resilience:
- Transient failures (network, 5xx, 429): auto-retry 2× with exponential backoff.
- Malformed JSON output: auto-retry 1× with a format reminder.
- Validation gate failure: auto-retry 1× feeding the specific validation error back into the prompt.
- Retries exhausted: surface "LLM resolution failed: {reason}" with a Retry button. No skip.

LLM warning behavior: a warning is non-blocking. The resolve form shows it inline with a confirmation: "I think this endpoint returns X but the need expects Y — proceed anyway?" If the user confirms, the spec is saved with `manually_overridden = true`.

Model selection inherits the existing adapter resolver config. No new config knob.

## 7. Smoke-call gate

Every Save click triggers an automatic smoke call against the candidate spec. **Hard block on failure.** Cadence is per-need: one Save = one LLM call + one smoke call. Saves are not batched.

The smoke call uses canonical test arguments:
- `ticker → "AAPL"`
- `country → "US"`
- `since_iso → today − 7 days`
- `limit → 1`
- `window_days → 7`

These are stored as a system-defined table and reused with the existing connector-level canary check. The user does not type test values; the canonical set ships with the system. Limitation: the smoke call only proves the spec works for these canonical inputs, not for the user's actual portfolio. Same limitation as the existing connector canary; not a regression.

The smoke call panel always shows the actual request and response, collapsed by default. Expand surfaces the raw JSON for debugging.

### 7.1 Failure classification and recovery

The smoke result is classified into typed buckets, each with targeted recovery actions:

| Bucket | Trigger | Recovery actions |
|---|---|---|
| Auth | 401, 403 | "Open connector settings" link. **Spec is preserved** — fixing the key in connector settings and clicking Retry re-validates the same spec. No re-pick. |
| Schema miss | 200 with response body, but `result_path` walk fails or returns wrong type | "Run LLM again with hint", "Pick different endpoint", "Try different URL" |
| Empty result | Response is `[]`, `null`, or `{}` for the canonical args | Same as schema miss |
| Bad params | 400 with response indicating param rejection | Same as schema miss |
| Transient | timeout, 429, 5xx | 2× silent backoff retry, then "Retry" button |

The raw error and raw response body are always visible regardless of bucket.

There is no "skip" button. Hard block applies even when the user is sure the LLM is wrong; they must produce a spec that smoke-passes.

## 8. Heterogeneous responses and `field_map`

The existing executor normalizes most heterogeneity through `param_bindings`, `transforms`, and `result_path`. The remaining gap is **per-item field renaming for `list[dict]`-shaped needs**.

Concrete failure mode the gap creates: user picks a custom social connector for `social_posts`. The endpoint returns `[{"text": ..., "post_url": ..., "ts": ...}]`. The LLM's spec extracts the list correctly. Smoke call passes (it is a `list[dict]`). The dept's run later fails with `KeyError` because `RawSocialPost.from_dict` expects `content` / `url` / `posted_at`.

### 8.1 Closing the gap

Two new artifacts close the gap:

**Per-need `canonical_keys`.** Each need with shape `list[dict]` declares the canonical key set its dept-side adapter expects. Added to `<dept>.needs.yaml`:

```yaml
needs:
  - id: social_posts
    shape: list[dict]
    canonical_keys:
      content: "Post body text"
      url: "Permalink to the post"
      posted_at: "ISO-8601 timestamp"
      author: "Username or handle"
    parameters:
      - name: ticker
        required: true
      ...
```

The 12 existing needs each get a one-time annotation. Needs with non-list shapes have no `canonical_keys`.

**`CallableSpec.field_map`.** A new optional field on the spec, used only for `list[dict]` shapes:

```json
{
  "tool_name": null,
  "method": "search_posts",
  "param_bindings": { ... },
  "result_path": "data.items",
  "field_map": {
    "content": "text",
    "url": "post_url",
    "posted_at": "ts",
    "author": "user.handle"
  },
  "shape": "list[dict]"
}
```

The `field_map` keys are the canonical keys; values are the dotted paths into the per-item dict. The executor walks `result_path` to the list, then for each item produces a dict keyed by `field_map` keys, using the dotted-path values to extract.

The LLM authors `field_map` as part of its single per-need call.

### 8.2 Smoke validation extension

For `list[dict]` shapes, after the structural shape check passes, the smoke pipeline takes the first list item and pipes it through the dept's `from_dict` adapter (or equivalent constructor). A `KeyError` or `TypeError` at this point is classified as a **schema miss** and produces a typed failure with the offending key surfaced in the message.

This catches field-map mismatches that the structural shape check would silently let through.

### 8.3 Catalog `runner_specs` regeneration

Existing built-in template `runner_specs` need a one-time regeneration pass to add `field_map` for their `list[dict]` needs. Most templates' fields will match canonical keys (since canonical keys are derived from these specs); these get an empty `field_map = {}`. Templates with name divergence get a populated map.

## 9. Mutability and post-wizard admin

Edit is available in two surfaces:

- **In wizard.** Every row's Edit button opens the resolve form (§5.1 or §5.2 depending on current mode). User can change endpoint, hint, or switch modes.
- **Post-wizard.** A new `ResolutionsAdminPanel` mounts under Settings, mirroring the existing `ConnectorsAdminPanel` pattern. Same per-need rows, same Edit + smoke-call flow. Renders the same React component as the wizard's resolve screen with no other changes.

Two operational rules apply to all edits:

1. **Edit drops the spec to draft.** New LLM call required, new smoke call required. Validation gates from §6 and §7 reapply. There is no direct edit of `CallableSpec` fields — that would bypass the validation gate.
2. **Old spec stays live until the new one passes smoke.** A failed edit does not break a working dept. The draft is kept separate from the live spec until smoke-pass commits the swap.

## 10. Storage and audit trail

### 10.1 New fields on `RunnerCallableSpec`

```sql
ALTER TABLE runner_callable_specs ADD COLUMN resolution_mode TEXT NOT NULL DEFAULT 'catalog_baked';
  -- enum: 'catalog_baked' | 'manual_endpoint' | 'manual_websearch'
ALTER TABLE runner_callable_specs ADD COLUMN connector_id INTEGER REFERENCES connectors(id);
ALTER TABLE runner_callable_specs ADD COLUMN user_inputs JSON;
  -- e.g., { "callable_id": "FMP.real_time_quote", "url": null, "hint": "use period=annual" }
ALTER TABLE runner_callable_specs ADD COLUMN llm_warning TEXT;
ALTER TABLE runner_callable_specs ADD COLUMN manually_overridden BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE runner_callable_specs ADD COLUMN last_smoke_at TIMESTAMP;
```

The existing `spec` JSON column gains the optional `field_map` key; no schema change required for the JSON.

### 10.2 Audit tables

```sql
CREATE TABLE resolver_call_log (
  id INTEGER PRIMARY KEY,
  spec_id INTEGER NOT NULL REFERENCES runner_callable_specs(id),
  prompt_inputs JSON NOT NULL,    -- need + inventory + user inputs
  raw_output JSON,                -- LLM's raw JSON response
  validation_errors JSON,          -- post-LLM validation gate output
  attempt INTEGER NOT NULL,        -- 1-indexed; >1 means a retry per §6 resilience
  created_at TIMESTAMP NOT NULL
);

CREATE TABLE smoke_call_log (
  id INTEGER PRIMARY KEY,
  spec_id INTEGER NOT NULL REFERENCES runner_callable_specs(id),
  request_args JSON NOT NULL,
  response_body JSON,              -- capped at 32KB
  status TEXT NOT NULL,            -- 'success' | 'auth' | 'schema_miss' | 'empty' | 'bad_params' | 'transient'
  error_message TEXT,
  created_at TIMESTAMP NOT NULL
);
```

Size budget: 12 needs × ~4 edits per user per year × ~2 logs per edit = ~100 rows per user per year. Trivial.

The `ResolutionsAdminPanel` reads recent rows from both tables to render a per-spec history view.

## 11. Operational mechanics

- **LLM model** inherits the existing adapter config; no new knob.
- **Wizard resumability** is automatic. Each per-need save commits its row to the DB on smoke success. Closing the browser and reopening resumes from the same row. Client-side wizard step pointer stays in `sessionStorage` matching the existing `DeptResolvePanel` pattern.
- **Order of operations**: connector add → secrets → connector canary → cached endpoints populated → user reaches resolve step → per-row LLM + smoke + save → all 12 rows resolved → finish wizard.
- **One spec per need.** Multi-source merge, fallback chains, and redundancy are not in this design.

## 12. Override semantics on template upgrades

User overrides always win. A future built-in template release that ships a corrected `runner_specs` mapping (e.g., a `# TODO(verify):` mark gets fixed) does **not** clobber an existing user override on that need.

When a template upgrade is detected and an override exists, the resolutions admin panel surfaces a non-blocking notice: "Catalog has a new mapping for `debt_gdp` from FMP. [Click to revert to default]." The user must explicitly click revert. Default is silent preservation of the override.

## 13. Out of scope and deferred

These items are intentionally not in this design and are tracked for revisit with telemetry:

- **Runtime caching for websearch resolutions.** Per-spec TTL, cache storage choice (Redis vs. SQLite vs. memory), invalidation strategy. Today every dept run hits the URL fresh. Defer until cost telemetry justifies a design.
- **Inline "Fix this resolution" link from dept-run failures.** When a dept run fails because a spec returns bad data, deep-link from the run-error UI into the resolve form for that need. Excellent UX, expanded scope. Defer until the admin panel from §9 exists and dept-run error UX is in place.
- **Multi-source merge or fallback per need.** Try EventRegistry first, fall back to Firecrawl scrape if it fails; or merge results from two sources. Each is its own design problem (priority, dedup, schema reconciliation). Defer.
