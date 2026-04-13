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
- **Formula engine not yet shared**: The formula engine DSL shared between Panic Thermometer and MR T1/T2 needs to be extracted into a shared core module. Currently only designed in the PT spec.

### Remaining Tasks

- Implementation plan for the dashboard design (pending user review of spec).
- Extract formula engine into shared module usable by both Panic Thermometer and MR T1/T2.
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

- **Formula engine not yet implemented**: The formula engine DSL (safe expression evaluator with operators, built-in functions) is designed in the spec but not yet built. Will be shared with MR T1/T2.

### Remaining Tasks

- Implementation plan for the Panic Thermometer page.
- Build the shared formula engine module in `packages/core/`.

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

## Design Specs Pending Review

- **Data provider system design** (`planning/specs/systems/data-provider-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Report rendering pipeline design** (`planning/specs/systems/report-rendering-pipeline-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Macro Research Dalio dashboards design** (`planning/specs/systems/macro-research-dalio-dashboards-design.md`): Spec written and committed. Pending user review before implementation planning.
- **Retail Sentiment dashboard design** (`planning/specs/systems/retail-sentiment-dashboard-design.md`): Spec written and committed. Pending user review before implementation planning.

---

## Cross-Cutting

### Remaining Tasks

- **Style extraction procedure**: `planning/specs/style_extraction_procedure.md` describes the extraction pipeline. The pipeline scripts (`scripts/extraction/pipeline.py`, `prompts.py`) exist but are not yet integrated into the core package. Needs to be moved to `packages/core/src/openlia/reports/style_extraction/` and exposed via a server route.
- **Rendering pipeline framework registry**: The report rendering pipeline spec needs to be updated to reference all three EqR framework files (`stock_initiation.json`, `stock_update.json`, `sector_research.json`) once the spec is approved and implementation begins.

### Open Questions

- None currently.
