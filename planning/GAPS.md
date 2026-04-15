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

### Gaps

- **No framework JSON or style guide needed**: RS is a dashboard department and does not generate text reports.
- **X API v2 access tier unverified**: Need to verify which X API tier is required for hourly tweet volume the dashboard needs.
- **FMP social sentiment endpoint availability**: The `/api/v4/historical/social-sentiment` endpoint may require a specific FMP plan.
- **NLP batch classification accuracy**: Batch classification of 30 items per call may reduce accuracy vs per-item. Needs testing during implementation.
- **Engagement weighting formula**: Exact formula for converting likes/retweets/follower count into contribution weights needs to be defined during implementation.

### Remaining Tasks

- Implementation plan for the dashboard design (pending user review of spec).
- Build batch NLP classification pipeline with structured prompt template.
- Build metrics computation engine (12 metrics, Pandas-based).

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

- **Secrets encryption at rest**: `config_store` plans to hold API keys in plaintext for v1. Upgrade path to server-derived key encryption is not yet designed.
- **`openlia wizard reset` CLI**: Referenced in the spec's error-handling section as the manual escape hatch for re-running the wizard or converting modes. Not yet implemented and not yet specced under the CLI surface.
- **`--color-surface-info` design token**: The MCP authentication info card uses this token. May need to be added to the app's token set if missing.
- **Step 3 AI Models section needs rewrite**: `llm-provider-design.md` supersedes the current Primary + Review two-slot structure with a three-tier structure (Thinking + Everyday + Quick) and adds Google Gemini to the provider list. Required edits enumerated under Cross-References in `llm-provider-design.md`.
- **Step 6 Review copy**: The AI Review model is now the Quick tier (formerly called "Review model"); wording needs updating.
- **Env var surface**: `OPENLIA_LLM_PRIMARY_*` / `OPENLIA_LLM_REVIEW_*` rows need to be replaced with the three-tier triplet plus per-department override env vars per `llm-provider-design.md`.

### Remaining Tasks

- Implementation plan for the wizard (pending user review of spec).
- Implement `GET /setup/status` and the 14 other `/setup/*` endpoints per the spec.
- Wire the wizard's mode selection + access-control output to the server's bind-and-auth startup behavior (requires server restart after company-mode completion).
- Apply the Cross-References edits from `llm-provider-design.md` to `SetupWizardSpec.md` (Step 3, Step 6, Configuration Storage sections).

### Open Questions

- **Review model cost visibility**: Should Step 3 show an estimated per-run cost for the review model based on manifest size and provider pricing? Useful on paid APIs; adds UI complexity.
- **Review cancel behavior**: If the user clicks "Back to Data Providers" during a running review, should the in-flight LLM call be cancelled server-side (save tokens) or allowed to complete (save latency on return)? Current plan: cancel.
- **Cross-browser resume**: Wizard state is DB-backed and unauthenticated in personal mode. Should a second browser on the same machine seamlessly resume, or require take-over confirmation? Current plan: take-over confirmation.
- **Post-completion mode switching**: The v1 non-goal says switching modes requires `openlia wizard reset` + env flip. Should Settings offer a gentler in-app path in a later version?

---

## LLM Provider & Configuration System

Full spec exists: `planning/specs/systems/llm-provider-design.md`. Defines the six-provider surface (OpenAI, Anthropic, Gemini, OpenRouter, OpenAI-compatible, Ollama), the three-tier model-role structure (Thinking / Everyday / Quick), per-department tier defaults with rationale, per-user BYO override for company mode, the runtime resolution order, shared connection-testing flow, and runtime failure handling (retry with backoff for transient errors, fail loudly for non-transient).

### Gaps

- **Shipped tier default model names need confirmation**: Current spec lists `gpt-5.4-pro` / `gpt-5.4` / `gpt-5.4-mini`, `claude-opus-4-6` / `claude-sonnet-4-6` / `claude-haiku-4-5`, `gemini-3.1-pro` / `gemini-3-flash` / `gemini-3.1-flash-lite`. Confirm exact variant names against each provider's docs before shipping.
- **Capability map maintenance cadence**: `core/llm/capabilities.py` is manually maintained per release. Dev Notes flag reconsidering after 2–3 releases of actual maintenance experience.
- **Secrets encryption at rest**: Inherited from Setup Wizard. Plaintext SQLite in v1.

### Remaining Tasks

- User review of `llm-provider-design.md` before implementation planning.
- Apply required cross-reference edits to `SetupWizardSpec.md` (Step 3 three-tier slots, Step 6 Quick-tier wording, env var surface) and `SettingsPageSpec.md` (add Models section, sidebar nav entry).
- Confirm or update `planning/projectStructure.md` to list the `core/openlia/llm/` file layout.
- Implementation plan for the provider abstraction, adapter modules, resolver, capability system, and `/settings/models/*` API surface.

### Open Questions

- **Model defaults freshness**: Shipped defaults risk going stale between releases. Current plan relies on the wizard's live-populated Model dropdown (from each provider's `/v1/models`) so users are one click away from a current model even if the shipped default is stale. Acceptable?
- **Test-completion cost debounce**: Every Save on a tier card runs a 1-token test completion. Should rapid sequential Saves coalesce into one test?
- **Data-provider BYO parity**: The LLM spec allows per-user BYO key overrides in company mode. Data providers remain admin-only per `data-provider-design.md`. Should data providers adopt the same hybrid pattern in a future iteration?

---

## LLM Runtime / Execution (Planned)

Planned as part 2 of the LLM system series, following `llm-provider-design.md`. Not yet specced.

### Remaining Tasks

- Brainstorm and draft `planning/specs/systems/llm-runtime-execution-design.md` covering:
  - Prompt assembly (system + user + framework injection per department).
  - Loading of `planning/frameworks/*.json` and `planning/frameworks/*_style_guide.md` into LLM calls.
  - Tool schema construction from the data-provider surface and how departments invoke tools.
  - Backend→frontend SSE streaming protocol (token events, tool-call events, error events, report-thumbnail events).
  - Web search as a department capability (distinct from configuration-time model discovery, which was rejected in the configuration spec).

---

## Design Specs Pending Review

- **Data provider system design** (`planning/specs/systems/data-provider-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Report rendering pipeline design** (`planning/specs/systems/report-rendering-pipeline-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Macro Research Dalio dashboards design** (`planning/specs/systems/macro-research-dalio-dashboards-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Retail Sentiment dashboard design** (`planning/specs/systems/retail-sentiment-dashboard-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Formula engine DSL design** (`planning/specs/systems/formula-engine-design.md`): Spec written. Pending user review and commit before implementation planning.
- **Setup Wizard design** (`planning/specs/pages/SetupWizardSpec.md`): Spec written and committed. Pending user review before implementation planning.
- **LLM Provider & Configuration System design** (`planning/specs/systems/llm-provider-design.md`): Spec written. Pending user review and commit before implementation planning. Part 1 of 2 in the LLM system series.

---

## Cross-Cutting

### Remaining Tasks

- **Style extraction procedure**: `planning/specs/style_extraction_procedure.md` describes the extraction pipeline. The pipeline scripts (`scripts/extraction/pipeline.py`, `prompts.py`) exist but are not yet integrated into the core package. Needs to be moved to `packages/core/src/openlia/reports/style_extraction/` and exposed via a server route.
- **Rendering pipeline framework registry**: The report rendering pipeline spec needs to be updated to reference all three EqR framework files (`stock_initiation.json`, `stock_update.json`, `sector_research.json`) once the spec is approved and implementation begins.

### Open Questions

- None currently.
