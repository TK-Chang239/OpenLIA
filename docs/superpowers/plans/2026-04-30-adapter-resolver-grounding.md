# Adapter LLM Accuracy + Wizard Resolve Flow Redesign

**Date:** 2026-04-30
**Branch:** `refactor/connector-redesign-v2`
**Status:** Feature-complete on branch (`67dbf83`). All four phases shipped; live verification confirmed verbatim slug emission against the EODHD MCP grounding repo (`debt_gdp → debt_percent_gdp`, `cpi_yoy → inflation_consumer_prices_annual`).

**Shipped commits in order:**
- `bc4a669`, `8c2153b`, `e4a8aa5`, `b870b2b` — Phase A: resolver tools, grounding clone service, agentic LLM client.
- `71cc956`, `b4b1bd8` — Phase B: per-department resolver service, dept routes, grounding migration, connector grounding fields.
- `fb46fbd`, `232d00f` — Phase C foundation: grounding URL panel, per-dept Review panels, dept-level approve, change-detection hint.
- `d4eebe0` — grounding clone on save + agentic factory wired into dept resolve.
- `5d761ac`, `2b34080` — verified end-to-end and fixed two real bugs (tool round-trip pairing, verbatim slug discipline).
- `5bedae7` — connection pool hardened against TLS faults under sustained load.
- `a16fcc1`, `99b8898`, `f6aaa0d` — Phase C continuation: per-need re-resolve, live tool-call log, try-a-different-connector.
- `67dbf83` — sweep cleanup; surfaced and fixed missing `TRANSIENT_NETWORK_ERRORS` import in 5 adapters.

## Problem we're solving

Three stacked failures in today's resolver:

1. **Hallucinated constants.** Resolving `debt_gdp` against EODHD-MCP, the LLM emitted `constants: {"indicator": "debt_gdp"}`. The real EODHD slug is `debt_percent_gdp`. The slug exists only in the MCP server's source code (`ALLOWED_INDICATORS` set in `app/tools/get_macro_indicator.py`), never in the `tools/list` payload OpenLIA caches. The LLM had no way to know.

2. **Per-connector tunnel vision.** Today the resolver runs once per connector add and only sees that one connector's tools. So `geopolitical_news` gets resolved to EODHD's `get_company_news` (wrong) instead of NewsAPI's news endpoints (right) — because at resolve time, NewsAPI wasn't part of the inventory.

3. **Eager, per-connector triggering.** Resolve fires immediately on each connector add. Users get partial proposals before they've finished configuring; back-nav and reordering are confusing; same need can resolve to different connectors as more are added.

Plus a discovered bug: `shape_match` is meaningless for MCP runners because the canary doesn't unwrap MCP's `CallToolResult` envelope. (Tracked separately, not in this plan.)

## What's changing

### 1. Grounding sources, user-supplied at connector-add time

Three optional fields per connector:
- **`source_repo_url`** — GitHub repo URL (works for both MCP-server repos and python-library repos; meaning is determined by the connector's `source` field)
- **`source_repo_revision`** — defaults to `main`/`HEAD`, user-overridable
- **`openapi_url`** — direct URL to an OpenAPI/Swagger spec

No `tool_files_path` — the LLM finds files itself (see #3).

When any of these are supplied, OpenLIA fetches the content and makes it available to the resolver as grounding context.

### 2. Local git clone (not lazy fetch)

Repos are shallow-cloned to `~/.openlia/connector_repos/<connector_id>/` on save. Subsequent reads are local filesystem ops, not network calls. Faster, no rate limits, deterministic, simpler tool implementation. Re-cloned only on user-initiated refresh or revision change.

OpenAPI specs are fetched once and cached in DB as parsed JSON.

### 3. Agentic resolver with tool-use

Resolver becomes multi-turn. The LLM gets three tools:
- `list_directory(path)` — returns entries in a path under the clone root
- `read_file(path)` — returns file contents (capped at 200KB)
- `search_files(pattern)` — ripgrep-style grep over the clone

The LLM navigates the clone on its own to find the enum lists / parameter taxonomies it needs. No path defaults, no auto-detection — the LLM does the looking.

Bounded by a 10-turn budget per resolve to prevent loops.

### 4. Per-department resolve, not per-connector

One resolve call per **runner-bearing** department (Macro Research, Retail Sentiment). Inventory in that prompt is **the union of all tools from all connectors whose category matches the department's required ∪ optional categories**.

Output: one proposal per `(department_id, need_id)`, each carrying the chosen `connector_id`. Cross-connector resolution is now first-class — `geopolitical_news` can pick NewsAPI even when other needs in the same dept pick EODHD.

### 5. Explicit `unsatisfiable` outcomes

The resolver's response schema gains an `unsatisfiable: true` flag per need. When no connector in scope provides the data (e.g., PMI on EODHD-only setup), the LLM emits this rather than producing a wrong-but-plausible spec. Review card surfaces it cleanly: "No configured connector provides this data."

### 6. Resolve runs only on user-initiated button click

- Connector page: add connectors. They validate. **No resolve.**
- User clicks Next → goes to Review page. Still no resolve yet.
- Review page has a per-department "Resolve [Dept Name]" button (and a "Resolve all departments" convenience). Clicking initiates the resolve loop.
- Loading UX: spinner with stage indicator and streaming tool-call log.

### 7. Non-destructive back-navigation

If user goes back from Review and edits connectors, **existing proposals are not invalidated**. Review page detects "connectors changed since last resolve" per department and surfaces a re-resolve hint. User chooses which (if any) departments to re-run.

### 8. Chat departments unchanged

Equity Research, Earnings Update, Morning Briefing, Secretary, Panic Thermometer have no needs YAML and no resolve step. They route tools dynamically at runtime via the chat router. Review page only shows panels for runner-bearing departments.

## Rationale per change

| Change | Why |
|---|---|
| Grounding from user-supplied URLs | The MCP `tools/list` protocol is structurally lossy when validation lives in Python guards (e.g., `if x not in ALLOWED: raise`). The information must enter the prompt some way. User-supplied URLs make the user's existing knowledge directly useful and scale into a future "supported connectors" registry that just pre-fills these fields. |
| Local clone | Network fetches inside an agentic loop introduce latency, rate limits, and transient failures. Filesystem ops are deterministic and cheap. |
| Agentic with tool-use | Repos differ in layout. Auto-detect ladders are brittle. The LLM, given filesystem tools, navigates correctly the way a developer would — read `__init__.py`, follow imports, find the validator. Higher accuracy than two-shot orchestration. |
| Per-department resolve | A department's needs span connectors. NewsAPI satisfies what EODHD can't. Per-connector resolve can't see across the boundary; per-department can. |
| `unsatisfiable` outcome | Forcing the LLM to emit something for every need produces canary failures and confusing wrong-tool picks. An honest "no" is more useful than a polite wrong. |
| User-initiated button | Wizards aren't transactions. Users want to configure, review, then commit to expensive operations. Auto-running on Next conflates "I'm done adding" with "spend money on resolution now." |
| Non-destructive back-nav | If proposals are durable, the user can refine connectors without re-paying for resolves. Forces nothing they didn't ask for. |

## What the new process looks like end-to-end

**Wizard flow from a fresh OpenLIA install:**

1. **LLM Models step.** User configures providers/models. (Existing.)
2. **Connectors step.**
   - User clicks "Add connector," picks provider (`eodhd`), source (`remote_mcp`), supplies URL + API key.
   - OpenLIA validates: connects, calls `tools/list`, caches inventory.
   - **Optional grounding panel appears** post-validation: "Improve adapter accuracy" with three fields (GitHub URL, revision, OpenAPI URL). User fills any combination or skips.
   - On save with grounding URLs: shallow clone fires in background; OpenAPI fetched and parsed. Connector status reflects "Validated" with sub-status "Grounding fetched" or "Grounding pending."
   - User adds more connectors. Each validates the same way.
   - **No resolves run during this step.**
3. **User clicks Next → Review step.**
   - Review page shows one panel per runner-bearing department (currently Macro Research, Retail Sentiment).
   - Each panel: list of needs, current proposals (initially empty), and a "Resolve [Dept Name]" button.
   - "Resolve all departments" button at top.
4. **User clicks "Resolve Macro Research."**
   - Spinner appears with stage text: "Resolving 12 needs across 5 connectors…"
   - Optional: streaming tool-call log if user expands details ("Reading app/tools/get_macro_indicator.py…").
   - Backend: builds inventory from all category-matching connectors; runs agentic LLM loop; LLM reads source files via tools as needed; emits one proposal per need.
   - Spinner clears; per-need cards populate. Each card shows proposed (connector, tool, params, constants), a canary value (when canary_ok), and shape-match status. Unsatisfiable needs render as "No connector provides this."
5. **User reviews and approves.**
   - Per-card "Approve" persists the spec to `runner_callable_specs`.
   - Per-card "Re-resolve this need" runs a single-need resolve.
   - "Try a different connector" forces the LLM to pick from a restricted inventory.
6. **User clicks Next → wizard moves on.**
   - Departments with all needs satisfied are enabled.
   - Departments with unsatisfied needs are disabled with a recoverable status (return to wizard, add a covering connector).

**Back-nav case:** User on Review goes back to Connectors, adds NewsAPI, returns to Review. Macro Research panel now shows: "Connectors changed since last resolve. [Re-resolve]" alongside the existing approved proposals. Existing proposals stay. User clicks "Re-resolve" if they want NewsAPI factored in.

## Implementation order

**Phase A — backend foundations (TDD-driven)** ✅
1. Resolver tools (`list_directory`, `read_file`, `search_files`) — sandboxed filesystem ops.
2. Repo cloning service — shallow clones, SSRF guards, size caps.
3. Agentic resolver client — tool-use loop wrapping `LLMProvider.generate`, turn budget, response schema validation.

**Phase B — orchestration layer** ✅
4. Per-department resolver service — `propose_specs_for_department` builds cross-connector inventory; `propose_spec_for_need` re-resolves a single row with optional `exclude_connector_ids`.
5. Alembic migration — `source_repo_url`, `source_repo_revision`, `openapi_url`, `cached_repo_commit_sha`, `cached_openapi`, `grounding_status`, `grounding_fetched_at` on `connectors`.
6. API endpoints — `POST/GET /departments/{id}/proposed-specs[…]`. Connector add/edit endpoints accept the grounding fields.
7. Grounding clone on save (`grounding_service.ensure_clone` / `resync_clone`) + agentic factory wired into the dept resolve route.

**Phase C — frontend integration** ✅
8. Connector card grounding panel (GitHub URL, revision, OpenAPI URL).
9. Review page with per-dept resolve panels, per-need Approve / Re-resolve / Try-a-different-connector, unsatisfiable warnings, change-detection hint via sessionStorage snapshot.
10. Live tool-call log streamed via 600ms polling against `GET /departments/{id}/proposed-specs/events`.

**Phase D — verification** ✅
11. Live integration: ran `scripts/verify_grounding_resolve.py` against the live EODHD MCP grounding repo + OpenRouter thinking-tier, captured 3 real tool calls (`search_files`, `read_file × 2`), and confirmed verbatim slug emission. Two latent bugs surfaced and fixed during verification (tool-call pairing in OpenRouter adapter; system prompt verbatim discipline).

## Real bugs the verification surfaced
- `Message` had no `tool_call_id` / `tool_calls` fields — the second turn of every tool-use loop lost protocol pairing on OpenAI/OpenRouter.
- 5 LLM adapters (anthropic, gemini, ollama, openai, openai_compat) referenced `TRANSIENT_NETWORK_ERRORS` without importing it — would have crashed under any transient network failure.
- `SSLV3_ALERT_BAD_RECORD_MAC` was escaping httpx as raw `ssl.SSLError`, slipping past `except httpx.HTTPError` in every adapter — single network blip aborted the whole resolve. Hardened with `httpx.AsyncHTTPTransport(retries=2)` and a broader `TRANSIENT_NETWORK_ERRORS` tuple.

## Out of scope (deferred)
- "Supported connectors" registry (pre-fills grounding URLs for known providers).
- SSE-based event streaming (current polling at 600ms is sufficient).
- `cached_openapi` is wired into the schema but not yet fetched/parsed on save.
- The agentic factory still treats canary failures separately from spec failures; per-MCP CallToolResult unwrapping for `shape_match` accuracy is still an open item.
