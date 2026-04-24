# Gaps, Remaining Tasks, and Open Questions

Tracks all known gaps, incomplete work, and open questions across the project. Updated as items are identified or resolved.

---

## Equity Research Department (EqR)

### Gaps

- **Stock initiation framework instructions not enriched**: The `stock_initiation_framework.json` section instructions are basic (originally translated from a Chinese template). No professional stock initiation report corpus is available to run the extraction pipeline against. The instructions work but lack the depth and specificity of the stock update and sector research frameworks, which were enriched from professional report examples.

### Remaining Tasks

- None currently.

### Open Questions

- Should we acquire a set of professional stock initiation reports (e.g., Goldman Sachs, Morgan Stanley initiation coverage) to run the extraction pipeline and enrich the framework instructions? This would bring them to parity with the other two modes.

---

## Earnings Update Department (EU)

### Gaps

- **No example corpus**: No professional earnings report examples have been collected for extraction. The framework and style guide were written from the Chinese/English template (`EarningsReporttemplate.md`) and IB convention knowledge, not extracted from professional examples. Running the extraction pipeline on real sell-side earnings notes could enrich the section instructions.

### Remaining Tasks

- None currently. Framework and style guide are complete.

### Open Questions

- The EqR stock update mode also covers earnings events. The key difference: EU is a standalone post-earnings assessment focused on the scorecard (beat/miss, guidance, thesis check), while EqR stock update is a broader investment note that may be triggered by earnings but also by other events (contract wins, capex changes, management changes). If overlap becomes confusing to users, consider clarifying the distinction in the UI or merging into a single flow.

---

## Morning Briefing Department (MB)

### Gaps

- **No example corpus**: No professional morning briefing examples have been collected for extraction. The framework and style guide were written from the page spec and bulge bracket IB morning note conventions (Goldman Sachs, JPMorgan, Morgan Stanley, Citi), not extracted from professional examples. Running the extraction pipeline on real sell-side morning notes could further enrich the section instructions.

### Remaining Tasks

- None currently. Framework and style guide are complete.

### Open Questions

- The framework uses 7 standard sections (Executive Summary, Global Macro, Country News, Market News, Sector News, Stock News, Upcoming Preview) plus user-defined custom sections. The page spec also allows users to uncheck sections entirely. Need to confirm the server-side template builder correctly strips unchecked sections before passing to the LLM.
- The Reference Portfolio toggle in Upcoming Preview creates a dependency on the Portfolio page. Need to confirm the data flow: does the LLM receive portfolio holdings as context, or does the server pre-fetch upcoming catalysts for portfolio tickers?

---

## Portfolio Page

### Gaps

- None currently.

### Remaining Tasks

- None currently.

### Open Questions

- Should there be a confirmation prompt before opening a new Equity Research chat session if the user already has an active session for that department?

---

## Macro Research Department (MR)

Department redesigned from chat-based report generator to five framework-driven dashboards based on Ray Dalio's macro methodology. Design spec: `planning/specs/systems/macro-research-dalio-dashboards-design.md`.

### Gaps

- **No framework JSON or style guide needed**: MR no longer generates text reports. The five dashboards (Debt Cycle, Four Seasons, All-Weather Portfolio, World Order, Five Forces) use formula engine evaluation (T1/T2), computational risk math (T3), and LLM assessment (T4/T5) instead. No `macro_research_framework.json` or style guide required.
- **EODHD macro indicator availability unverified**: Debt-to-GDP and interest/revenue may not be available as direct EODHD endpoints. May need to compute from multiple economic event data points or hardcode with manual update on release.
- **DXY proxy unverified**: EODHD may not carry DXY directly. UUP (ETF) is a proxy. Need to verify ticker availability during implementation.
- **IMF COFER data for T4**: Quarterly with a lag. Reserve composition chart will use hardcoded snapshots updated on COFER release. Could fetch from IMF API if user provides access.
- **Formula engine not yet implemented**: Design is now documented in `planning/specs/systems/formula-engine-design.md` (shared module for PT and MR T1/T2). Implementation pending.

### Remaining Tasks

- Implementation plan for the dashboard design (pending user review of spec).
- Build the shared formula engine module per `planning/specs/systems/formula-engine-design.md` (usable by both PT and MR T1/T2).
- Build YAML prompt templates for T4/T5 LLM assessments with Dalio's framework as system context.

### Open Questions

- **T4/T5 LLM cost**: Each assessment run consumes LLM tokens. Weekly runs may be expensive depending on model. Settings should show estimated cost per run.
- **Smart Mode threshold adjustment frequency**: Smart Mode piggybacks on T4/T5 LLM runs. If T4/T5 are set to quarterly, threshold adjustments are also quarterly. Should Smart Mode have its own independent schedule?

---

## Retail Sentiment Department (RS)

Department redesigned from a 3-metric dashboard into a 12-metric sentiment monitoring platform with 3 analytical tabs, batch LLM classification, and cross-source validation. Design spec: `planning/specs/systems/retail-sentiment-dashboard-design.md`.

**Status (2026-04-24):** spec amended. v1 ships a subset of the design; full design is now the v2 target. The "Shipped v1 Scope" matrix at the top of the spec is the source of truth -- read it before planning any follow-up work here.

### Gaps

- **No framework JSON or style guide needed**: RS is a dashboard department and does not generate text reports.
- **X API v2 access tier unverified**: Need to verify which X API tier is required for hourly tweet volume the dashboard needs.
- **FMP social sentiment endpoint availability**: The `/api/v4/historical/social-sentiment` endpoint may require a specific FMP plan.
- **NLP batch classification accuracy**: Batch classification of 30 items per call may reduce accuracy vs per-item. Needs testing during v2 implementation.
- **Engagement weighting formula**: Exact formula for converting likes/retweets/follower count into contribution weights needs to be defined during v2 implementation.

### Remaining Tasks

- **v2 follow-on bundle (~2 days, next):** `rs_classification_log` migration, `batch_classify` prompt section, `LlmClassifier` wrapper, audit writes from `rs_runner.py`.
- **v2 full (deferred):** `JobType.RS_SNAPSHOT` + scheduler executor + `/schedule` endpoints, Evidence Tab, Insights Tab, Settings drawer, Metrics Deep Dive panel, metrics 8-12, narrative synthesis prompt + LLM call.

### Open Questions

- **Reliability matrix calibration**: Predictive strength and timeliness scores are estimated from literature. Should these be calibrated with backtesting data in a future version?
- **X API cost**: Basic tier ($100/month) may be insufficient. Need to estimate required volume per watchlist size.

---

## Panic Thermometer

Full spec exists: `planning/specs/pages/departments/PanicThermometerPageSpec.md`. Dashboard department with formula engine, data context panels, threshold-based rules, composite scoring, per-panel settings, preset libraries, import/export.

### Gaps

- **Formula engine not yet implemented**: The formula engine DSL is fully designed in `planning/specs/systems/formula-engine-design.md` (shared with MR T1/T2). Implementation pending.

### Remaining Tasks

- Implementation plan for the Panic Thermometer page.
- Build the shared formula engine module per `planning/specs/systems/formula-engine-design.md`.

### Open Questions

- None currently. Spec is complete.

---

## Data Requirements (All Departments)

Data requirements have been added to all department and page specs. Each spec declares basic (required) and advanced (optional) data requirements in a consistent format for the setup wizard to map configured providers against.

### Requirement Types Across All Departments

| Type | Used By |
|---|---|
| `stock_quote` | Secretary, EqR, EU, MB, PT, MR, RS, Portfolio |
| `company_profile` | Secretary, EqR, Portfolio |
| `company_news` | Secretary, EqR, EU, MB, PT, MR, RS |
| `historical_prices` | Secretary, EqR, EU, MB, PT, MR, RS |
| `financial_statements` | EqR, EU |
| `economic_events` | Secretary, MB, PT, MR |
| `macro_indicators` | MB, MR |
| `earnings_dates` | EU |
| `earnings_transcripts` | EU |
| `earnings_data` | EqR |
| `analyst_ratings` | EqR, EU |
| `insider_transactions` | EqR |
| `intraday_prices` | Portfolio |
| `social_sentiment` | RS |
| `options_data` | RS |
| `short_interest` | RS |
| `institutional_holdings` | RS |

The full requirements manifest (`packages/core/src/openlia/data/manifest/requirements.yaml`) will be the union of all department requirements. The setup wizard maps each configured provider's capabilities against this manifest to determine which departments and features are available.

---

## Setup Wizard

Full spec exists: `planning/specs/pages/SetupWizardSpec.md`. Dual-mode wizard (personal / company) with mode selector on welcome, AI model + data provider configuration, AI review for department readiness, env-var precedence with read-only field rendering, and DB-canonical configuration storage.

### Gaps

- ~~**Secrets encryption at rest**: `config_store` plans to hold API keys in plaintext for v1. Upgrade path to server-derived key encryption is not yet designed.~~ **Resolved by DB design Section 5 (2026-04-15)**: AES-256-GCM at rest in `llm_providers.api_key_encrypted` / `data_providers.api_key_encrypted` / `web_search_providers.api_key_encrypted`, keyed by `OPENLIA_SECRET_KEY` env var or `~/.openlia/secret.key` (0600), row-`id` as AAD, `openlia secrets rotate-key` CLI for rotation. `config_store` no longer holds API keys.
- ~~**`openlia wizard reset` CLI**: Referenced in the spec's error-handling section as the manual escape hatch for re-running the wizard or converting modes. Not yet implemented and not yet specced under the CLI surface.~~ **Resolved (2026-04-16):** Specced in `cli-surface-design.md`.
- **`--color-surface-info` design token**: The MCP authentication info card uses this token. May need to be added to the app's token set if missing.
- Cross-reference edits from `llm-provider-design.md` and `llm-runtime-design.md` are **applied** (2026-04-14): Step 3 rewritten to the three-tier structure with Gemini added, Step 4 Web Search tab added, Step 6 copy clarifies the Quick tier runs the AI review, and the env-var surface carries the three-tier triplet plus per-department overrides.

### Remaining Tasks

- Implementation plan for the wizard (pending user review of spec).
- Implement `GET /setup/status` and the 14 other `/setup/*` endpoints per the spec.
- Wire the wizard's mode selection + access-control output to the server's bind-and-auth startup behavior (requires server restart after company-mode completion).
- ~~Apply the Cross-References edits from `llm-provider-design.md` to `SetupWizardSpec.md` (Step 3, Step 6, Configuration Storage sections).~~ Done 2026-04-14.

### Open Questions

- **Review model cost visibility**: Should Step 3 show an estimated per-run cost for the review model based on manifest size and provider pricing? Useful on paid APIs; adds UI complexity.
- **Review cancel behavior**: If the user clicks "Back to Data Providers" during a running review, should the in-flight LLM call be cancelled server-side (save tokens) or allowed to complete (save latency on return)? Current plan: cancel.
- **Cross-browser resume**: Wizard state is DB-backed and unauthenticated in personal mode. Should a second browser on the same machine seamlessly resume, or require take-over confirmation? Current plan: take-over confirmation.
- **Post-completion mode switching**: The v1 non-goal says switching modes requires `openlia wizard reset` + env flip. Should Settings offer a gentler in-app path in a later version?

---

## LLM Provider & Configuration System

Full spec exists: `planning/specs/systems/llm-provider-design.md`. Defines the six-provider surface (OpenAI, Anthropic, Gemini, OpenRouter, OpenAI-compatible, Ollama), the three-tier model-role structure (Thinking / Everyday / Quick), per-department tier defaults with rationale, admin-managed model roster with `user_llm_preferences` pointer table (no per-user BYO keys), the runtime resolution order (user preference → tier default → any enabled → `TierNotConfiguredError`), shared connection-testing flow, and runtime failure handling (retry with backoff for transient errors, fail loudly for non-transient).

### Gaps

- **Shipped tier default model names need confirmation**: Current spec lists `gpt-5.4-pro` / `gpt-5.4` / `gpt-5.4-mini`, `claude-opus-4-6` / `claude-sonnet-4-6` / `claude-haiku-4-5`, `gemini-3.1-pro` / `gemini-3-flash` / `gemini-3.1-flash-lite`. Confirm exact variant names against each provider's docs before shipping.
- **Capability map maintenance cadence**: `core/llm/capabilities.py` is manually maintained per release. Dev Notes flag reconsidering after 2–3 releases of actual maintenance experience.
- ~~**Secrets encryption at rest**: Inherited from Setup Wizard. Plaintext SQLite in v1.~~ **Resolved by DB design Section 5 (2026-04-15)**: AES-256-GCM at rest in `llm_providers.api_key_encrypted`, keyed by `OPENLIA_SECRET_KEY` / `~/.openlia/secret.key`.

### Remaining Tasks

- User review of `llm-provider-design.md` before implementation planning.
- ~~Apply required cross-reference edits to `SetupWizardSpec.md` (Step 3 three-tier slots, Step 6 Quick-tier wording, env var surface) and `SettingsPageSpec.md` (add Models section, sidebar nav entry).~~ Done 2026-04-14.
- ~~Confirm or update `planning/projectStructure.md` to list the `core/openlia/llm/` file layout.~~ Done 2026-04-14.
- Implementation plan for the provider abstraction, adapter modules, resolver, capability system, and `/settings/models/*` API surface.

### Open Questions

- **Model defaults freshness**: Shipped defaults risk going stale between releases. Current plan relies on the wizard's live-populated Model dropdown (from each provider's `/v1/models`) so users are one click away from a current model even if the shipped default is stale. Acceptable?
- **Test-completion cost debounce**: Every Save on a tier card runs a 1-token test completion. Should rapid sequential Saves coalesce into one test?
- **Per-user BYO keys (v2)**: Both LLM and data providers are admin-only in v1. Should v2 allow per-user BYO keys for LLM providers so users can bring their own API keys?

---

## LLM Runtime / Execution System

Full spec exists: `planning/specs/systems/llm-runtime-design.md`. Part 2 of 2 in the LLM system series. Defines three runners (`ChatRunner`, `ReportRunner`, `BatchRunner`) under `core/openlia/llm/runtime/`, per-department YAML prompt authoring (Jinja2-templated), framework JSON + style-guide markdown injection for report runs, tool-schema construction (requirement-named data tools + `find_more_data` meta-tool + `web_search`), the `chat.*` / `report.*` SSE event taxonomy, hybrid web-search sourcing (provider-native first, user-configured Brave / Tavily / Serper / You.com fallback, unavailable otherwise), and cancellation via client disconnect.

### Gaps

- All six cross-reference edits from the runtime spec are **applied** (2026-04-14): `Capabilities.web_search_native` and the `Capability.web_search` enum value are in `llm-provider-design.md`; `search` is a fourth category in `data-provider-design.md`; `SetupWizardSpec.md` Step 4 has a Web Search tab; `report-rendering-pipeline-design.md` carries the `report.*` dot-namespaced taxonomy including `report.tool_call` and a full `ReportSchema` payload on `report.complete`; `ChatInterfaceSpec.md` has an Event Handling section; `planning/projectStructure.md` lists the `runtime/` subdirectory, the per-department YAML prompt files, and the `reports/frameworks/` sibling directory.
- **Framework / style-guide file migration**: `planning/frameworks/*.json` and `*_style_guide.md` still need to physically move into the package at `packages/core/src/openlia/reports/frameworks/`. `planning/` is dev-only and excluded from Python package builds.

### Remaining Tasks

- User review of `llm-runtime-design.md` before implementation planning.
- ~~Apply the six cross-reference edits enumerated above.~~ Done 2026-04-14.
- Implementation plan for the runtime layer (runners, prompt loader, tool dispatcher, web-search adapter, SSE event types, cancellation helper).

### Open Questions

- **Prompt caching effectiveness**: The system / user split is designed to maximize prompt-cache hit rates across providers. Dev note flags validating cache-hit rates in the first few weeks of production telemetry and revisiting the YAML structure if hits are poor.
- **`find_more_data` latency in reports**: The expansion meta-tool adds ~1-2s per call (Quick-tier catalog search). Bursty use during report generation could inflate total time. Consider caching expansion results per `(department, description)` for the lifetime of a generation call.
- **Batch-runner concurrency default**: Default `concurrency=8` is a guess. RS classifies hundreds of social posts per dashboard refresh; could saturate rate-limited tiers. Instrument batch duration and 429 counts; tune per department if needed.
- **Native web-search cost visibility**: Anthropic and OpenAI bill native web-search on top of completion tokens. Surface a one-liner in Settings → Models when native web search is active so users aren't surprised by bills.
- **v2 user-authored custom tools**: Runtime spec dev note flags a future iteration allowing users to register arbitrary tools (user OpenAPI specs, general MCP tool servers, hand-written Python callables) per department. Design considerations: capability gating, interaction with per-department mappings, expansion-budget accounting, and name-collision rules with requirement tools.

---

## Database Design

Full spec exists: `planning/specs/systems/database-design.md` (29 tables, 11 sections). Key decisions:

- **Scope**: Comprehensive — all persistent application state lives in SQLite. No provider response caching in v1.
- **Engine**: SQLite only for v1 (Postgres dropped). Rationale: self-hosted, single-admin, low write volume, zero-ops.
- **Schema architecture**: Hybrid (Approach 1) — relational core tables + JSON columns for flexible substructure + a narrow KV escape hatch (`config_store`).
- **Tenancy**: Option A — single schema with a synthetic `local` user row for personal mode; company mode rows key off real user IDs.
- **Auth (v1)**: Argon2id password hashing, DB-backed opaque session tokens, invite-only registration (multi-use invites with optional usage cap), admin-approved password reset flow via `password_reset_requests` table — user initiates from login page, admin approves and delivers one-time link out-of-band, no SMTP required.
- **OAuth / SMTP**: Not in v1. Planned for v2.
- **LLM config granularity**: Admin configures zero-or-many models per tier (Thinking / Everyday / Quick) — no hard requirement to populate every tier. Setup Wizard and Settings show a soft reminder to configure at least one model per tier. Each user picks a preferred model per tier from the admin's roster. Departments calling into an unconfigured tier surface a clear "not configured" error rather than silently downgrading. No per-user BYO keys in v1.
- **Data provider config**: Admin-only. Per-category multi-provider fallback already in `data-provider-design.md` is unchanged; no per-user BYO.
- **Deployment posture**: Company mode defaults to HTTPS domain from v1. Three recommended recipes: Cloudflare Tunnel (default), Docker + Caddy (self-managed reverse proxy), and LAN-only (fallback for IT-constrained shops). New env vars `OPENLIA_TRUST_PROXY_HEADERS` and `OPENLIA_COOKIE_SECURE` cover proxied deployments.

### Remaining Tasks (cross-spec edits)

All cross-spec edits from the DB design have been applied (2026-04-15). Status below for reference.

- ~~**`planning/specs/components/AccountManagementSpec.md`** — full rewrite: invite-only registration, admin-approved password reset, direct admin reset, admin user lifecycle.~~ Done 2026-04-15.
- ~~**`planning/specs/pages/LoginPageSpec.md`** — dropped Google OAuth, added Reset Password page, Must Change Password view, invite-gated registration.~~ Done 2026-04-15.
- ~~**`planning/specs/pages/SetupWizardSpec.md`** — zero-or-many models per tier, soft reminders, encryption-at-rest notes, `OPENLIA_SECRET_KEY`/`OPENLIA_TRUST_PROXY_HEADERS`/`OPENLIA_COOKIE_SECURE` env vars, invite-only as v1 default, deployment guidance.~~ Done 2026-04-15.
- ~~**`planning/specs/pages/SettingsPageSpec.md`** — Models section rewritten (read-only roster + per-tier picker for users, admin link), Admin section added (invites, users, reset requests, model CRUD, data provider CRUD), Account section updated (removed Google OAuth refs, added `must_change_password` flow).~~ Done 2026-04-15.
- ~~**`planning/specs/systems/llm-provider-design.md`** — removed `user_llm_overrides`, added `user_llm_preferences` pointer table, restructured to DB tables (`llm_providers`/`llm_models`), updated resolver to 4-step order with `TierNotConfiguredError`, replaced plaintext secrets with AES-256-GCM, removed tier-level env vars.~~ Done 2026-04-15.
- ~~**`planning/specs/systems/data-provider-design.md`** — scrubbed per-user BYO language (user→admin throughout), added encryption-at-rest cross-reference, added DB table references (`data_providers`, `data_provider_requirement_mapping`).~~ Done 2026-04-15.
- ~~**`planning/specs/systems/llm-runtime-design.md`** — added `TierNotConfiguredError` handling in all three runners, dedicated SSE error events for unconfigured tiers.~~ Done 2026-04-15.
- ~~**`planning/specs/pages/departments/PanicThermometerPageSpec.md`** — replaced `window.storage` with DB-backed `pt_user_configs`/`pt_presets` tables.~~ Done 2026-04-15.
- ~~**`planning/specs/systems/macro-research-dalio-dashboards-design.md`** — added DB persistence cross-reference (`mr_dashboard_state`, `mr_assessment_cache`).~~ Done 2026-04-15.
- ~~**`planning/specs/systems/retail-sentiment-dashboard-design.md`** — added DB persistence cross-reference (`rs_user_config`, `rs_snapshots`, `rs_classification_log`).~~ Done 2026-04-15.
- ~~**`planning/specs/components/ChatHistorySpec.md`** — populated with DB table references (`chat_sessions`, `chat_messages`, `chat_attachments`) and key behavior outline.~~ Done 2026-04-15.
- ~~**`planning/PLAN.md`** — dropped Postgres (SQLite only v1), added deployment recipes reference, updated backup note.~~ Done 2026-04-15.
- ~~**`planning/projectStructure.md`** — confirmed no Postgres references. `db/models.py`, `db/migrations/` (Alembic), `db/session.py` are already the canonical paths.~~ Done 2026-04-15.

### Open Questions (v2 horizon)

- **Google OAuth return in v2**: When v2 adds OAuth, re-introduce the `auth_accounts` table (user_id, provider, provider_user_id, linked_at). Flow: first-time OAuth login auto-links to an existing email match (if admin opted in) or creates a new pending-approval user (if open registration is enabled). Library: `authlib`.
- **Cloudflare Access SSO integration**: For company deployments behind Cloudflare Tunnel, offering "trust Cloudflare Access JWT" as an auth mode would remove the need for OpenLIA's own login page entirely. Design question: do we read `Cf-Access-Jwt-Assertion` and auto-provision users, or treat CF Access as a separate auth mode?
- **SMTP as optional v2 feature**: If added, it would automate delivery of approved password-reset links and invite emails (currently admin delivers out-of-band). Gate behind an env var so personal-mode deployments don't need it.

---

## Background Task Scheduling System

Full spec exists: `planning/specs/systems/background-task-scheduling-design.md`. APScheduler 4.x with in-memory job store, running inside the FastAPI process. Four job types: MB briefing (user cron), EU scan (user cron), MR assessment (user cron -- weekly/quarterly), nightly maintenance (system interval). Per-user independent schedules. DB is source of truth; APScheduler rebuilt on startup. Missed job catch-up within 6-hour grace window. Retry 3x with exponential backoff, then failure record visible to user. Polling-based notifications via `user_notifications` table.

### Gaps

- None currently. Spec is complete.

### Remaining Tasks

- Implementation plan for the scheduling system (pending user review of spec).
- All cross-reference edits applied (2026-04-16): `PLAN.md` (APScheduler resolved), `projectStructure.md` (scheduler/ directory), `database-design.md` (`eu_schedules`, `job_runs`, `user_notifications` tables + maintenance sweep updates), `EarningsUpdatePageSpec.md` (scan schedule configuration section), `SideBarSpec.md` (notification polling mechanism formalized), `AccountManagementSpec.md` (`user_notifications` and schedule tables added to user-scoped data contract), `macro-research-dalio-dashboards-design.md` (news trigger manual-only in v1).

### Open Questions

1. **EU scan efficiency at scale.** Bulk earnings-calendar API call vs per-ticker lookups. Depends on data provider capabilities.
2. **Concurrent report generation limit.** Global concurrency cap for simultaneous ReportRunner calls from scheduled jobs. Consider `OPENLIA_SCHEDULER_MAX_CONCURRENT_JOBS` env var.
3. **Job run retention.** Completed runs pruned at 90 days, failed runs kept longer for audit. Final retention policy TBD during implementation.

---

## CLI Surface

Full spec exists: `planning/specs/systems/cli-surface-design.md`. Typer-based CLI registered as `openlia` via `[project.scripts]`. Commands: `serve` (start server), `admin` (9 user/invite/session management subcommands, company-mode only), `wizard reset` (re-run setup), `secrets rotate-key` (re-encrypt API keys), `maintenance` (manual pruning sweep). All non-serve commands connect directly to the DB without requiring the server to be running.

### Gaps

- None currently. Spec is complete.

### Remaining Tasks

- Implementation plan for the CLI (pending user review of spec).

### Open Questions

1. **Auto-migrate on startup.** Should `serve` auto-run Alembic migrations, or require an explicit `openlia db upgrade` command? Current plan: auto-upgrade for simplicity.
2. **Admin commands while server is running.** Current plan: safe with WAL mode. Exception: `secrets rotate-key` requires exclusive access.

---

## Design Specs Pending Review

- **Database design** (`planning/specs/systems/database-design.md`): Spec written (2026-04-15). 29 tables across auth, config, content, infrastructure, and dashboard categories. All cross-spec edits applied. Pending user review before implementation planning.
- **Data provider system design** (`planning/specs/systems/data-provider-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Report rendering pipeline design** (`planning/specs/systems/report-rendering-pipeline-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Macro Research Dalio dashboards design** (`planning/specs/systems/macro-research-dalio-dashboards-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Retail Sentiment dashboard design** (`planning/specs/systems/retail-sentiment-dashboard-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Formula engine DSL design** (`planning/specs/systems/formula-engine-design.md`): Spec written. Pending user review and commit before implementation planning.
- **Setup Wizard design** (`planning/specs/pages/SetupWizardSpec.md`): Spec written and committed. Pending user review before implementation planning.
- **LLM Provider & Configuration System design** (`planning/specs/systems/llm-provider-design.md`): Spec written and committed. Pending user review before implementation planning. Part 1 of 2 in the LLM system series.
- **LLM Runtime / Execution System design** (`planning/specs/systems/llm-runtime-design.md`): Spec written and committed. Pending user review before implementation planning. Part 2 of 2 in the LLM system series.
- **Background Task Scheduling System design** (`planning/specs/systems/background-task-scheduling-design.md`): Spec written (2026-04-16). APScheduler 4.x, per-user schedules, four job types, polling notifications. All cross-spec edits applied. Pending user review before implementation planning.
- **CLI Surface design** (`planning/specs/systems/cli-surface-design.md`): Spec written (2026-04-16). Typer-based CLI with `serve`, `admin` (9 subcommands), `wizard reset`, `secrets rotate-key`, `maintenance`. Consolidates commands already defined across other specs. Cross-spec edits applied. Pending user review before implementation planning.

---

## Cross-Cutting

### Remaining Tasks

- **Style extraction procedure**: `planning/specs/style_extraction_procedure.md` describes the extraction pipeline. The pipeline scripts (`scripts/extraction/pipeline.py`, `prompts.py`) exist but are not yet integrated into the core package. Needs to be moved to `packages/core/src/openlia/reports/style_extraction/` and exposed via a server route.

### Open Questions

- None currently.
