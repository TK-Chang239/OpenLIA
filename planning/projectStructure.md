# OpenLia - Project Directory Structure

Authoritative directory layout for the OpenLIA repository. Regenerated from current spec state (April 2026). When a spec adds a module, also update this file so the tree stays canonical.

```
openlia/
├── pyproject.toml              # Root uv workspace (not an installable package)
├── uv.lock                     # Shared lockfile (auto-generated)
├── ruff.toml                   # Shared lint/format config
├── .env.example                # Template for env vars (OPENLIA_* keys, secret key, etc.)
├── .gitignore
├── LICENSE
├── README.md
├── Dockerfile
├── docker-compose.yml
│
│   ============================================================
│   PACKAGES - Installable Python packages (the three layers)
│   ============================================================
│
├── packages/
│   │
│   │   --------------------------------------------------------
│   │   CORE - Library layer (pure Python, zero web deps)
│   │   `pip install openlia-core` installs this package alone
│   │   `pip install openlia` installs core + server + CLI
│   │   --------------------------------------------------------
│   │
│   ├── core/
│   │   ├── pyproject.toml          # Package: "openlia-core"
│   │   ├── src/
│   │   │   └── openlia/
│   │   │       ├── __init__.py
│   │   │       │
│   │   │       ├── departments/                # All department agents
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py                 # Base department class + DEFAULT_TIER
│   │   │       │   ├── health.py               # Pure dept-health derivation (active|disabled + reason)
│   │   │       │   ├── loader.py               # YAML loader for `<dept>.needs.yaml`
│   │   │       │   ├── secretary.py
│   │   │       │   ├── secretary.routing_context.md       # Runtime-router prompt context (spec §8)
│   │   │       │   ├── equity_research.py
│   │   │       │   ├── equity_research.routing_context.md
│   │   │       │   ├── earnings_update.py
│   │   │       │   ├── earnings_update.routing_context.md
│   │   │       │   ├── morning_briefing.py
│   │   │       │   ├── morning_briefing.routing_context.md
│   │   │       │   ├── macro_research.needs.yaml          # MR deterministic-runner needs (spec §5.4)
│   │   │       │   ├── retail_sentiment.needs.yaml        # RS deterministic-runner needs
│   │   │       │   │
│   │   │       │   ├── macro_research/         # MR is a sub-package (5 dashboards + LLM assessments)
│   │   │       │   │   ├── __init__.py         # MacroResearchDepartment + get_current_snapshot() public API
│   │   │       │   │   ├── formula_config.py   # T1/T2 indicator configurations for the formula engine
│   │   │       │   │   ├── risk_math.py        # T3 All-Weather risk contribution calculations
│   │   │       │   │   ├── presets.py          # Dalio defaults, Conservative, Relaxed
│   │   │       │   │   ├── prompts/            # YAML prompts for T4 / T5 LLM assessments
│   │   │       │   │   └── schemas.py          # Pydantic models for dashboard state, assessment outputs, MRSnapshot
│   │   │       │   │
│   │   │       │   ├── retail_sentiment/       # RS is a sub-package (12 metrics + NLP classification)
│   │   │       │   │   ├── __init__.py         # RetailSentimentDepartment
│   │   │       │   │   ├── metrics.py          # Computation for all 12 metrics (Pandas-based)
│   │   │       │   │   ├── classifier.py       # Batch NLP classification: prompt build, parse, retry, fallback
│   │   │       │   │   └── schemas.py          # Pydantic models for metric data, evidence items, signals
│   │   │       │   │
│   │   │       │   └── panic_thermometer/      # PT is a sub-package (5 panels + formula-engine evaluation)
│   │   │       │       ├── __init__.py         # PanicThermometerDepartment
│   │   │       │       ├── panels/             # One module per panel — fetches data, builds context, calls engine
│   │   │       │       │   ├── oil.py
│   │   │       │       │   ├── inflation.py
│   │   │       │       │   ├── fed_language.py
│   │   │       │       │   ├── wage_growth.py
│   │   │       │       │   └── diplomacy.py
│   │   │       │       └── presets.py          # Report defaults, MA-relative, Volatility-adjusted libraries
│   │   │       │
│   │   │       ├── llm/                        # LLM provider adapters + runtime (see llm-provider-design.md, llm-runtime-design.md)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── base.py                 # LLMProvider protocol
│   │   │       │   ├── openai.py
│   │   │       │   ├── anthropic.py
│   │   │       │   ├── gemini.py
│   │   │       │   ├── openrouter.py
│   │   │       │   ├── openai_compat.py        # OpenAI-compatible catch-all (DeepSeek, Groq, vLLM, ...)
│   │   │       │   ├── ollama.py               # Local model adapter
│   │   │       │   ├── capabilities.py         # Shipped capability map (per provider/model family)
│   │   │       │   ├── model_defaults.py       # Shipped tier defaults per provider (wizard pre-selection only)
│   │   │       │   ├── resolver.py             # Tier/department → ready LLMProvider
│   │   │       │   ├── exceptions.py           # LLMProviderError, AuthError, ModelNotFoundError, TierNotConfiguredError
│   │   │       │   │
│   │   │       │   └── runtime/                # Execution layer (llm-runtime-design.md)
│   │   │       │       ├── __init__.py         # ChatRunner, ReportRunner, BatchRunner exports
│   │   │       │       ├── chat.py
│   │   │       │       ├── report.py
│   │   │       │       ├── batch.py
│   │   │       │       ├── prompts.py          # YAML loader + Jinja2 renderer
│   │   │       │       ├── router.py           # Runtime router — picks per-conversation tool subset (spec §8)
│   │   │       │       ├── escalation.py       # `request_additional_tools` mid-conversation re-route (spec §8.5)
│   │   │       │       ├── tools.py            # ToolDispatcher (requirement tools, web_search)
│   │   │       │       ├── web_search.py       # Native-or-configured web search adapter
│   │   │       │       ├── events.py           # SSE event dataclasses (chat.*, report.*)
│   │   │       │       ├── messages.py         # ChatMessage, ReportRequest, BatchItem
│   │   │       │       └── cancellation.py     # CancellationToken + grace-period helpers
│   │   │       │
│   │   │       ├── formula/                    # Shared formula engine (see formula-engine-design.md)
│   │   │       │   ├── __init__.py             # Public API re-exports
│   │   │       │   ├── tokenizer.py
│   │   │       │   ├── parser.py
│   │   │       │   ├── ast_nodes.py
│   │   │       │   ├── evaluator.py
│   │   │       │   ├── functions.py            # The 9 built-in functions
│   │   │       │   ├── derived.py              # Reserved-scalar computation (ma20/50/200, atr_14, streak_days, ...)
│   │   │       │   ├── rules.py                # Rule set evaluation
│   │   │       │   ├── exceptions.py
│   │   │       │   └── types.py                # Pydantic models: Rule, RuleSet, PanelResult, FormulaResult
│   │   │       │
│   │   │       ├── connectors/                 # Connector subsystem v2 (see specsv2/2026-04-27-connector-dataflow-design.md)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── types.py                # Category, ConnectorSource, LaunchSpec, RunnerNeed, CallableSpec
│   │   │       │   ├── transports/             # MCP + python_lib transports (uniform CallableTransport interface)
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   ├── base.py             # CallableTransport protocol
│   │   │       │   │   ├── cli_mcp.py          # Local stdio MCP servers (uvx, npx)
│   │   │       │   │   ├── remote_mcp.py       # SSE / streamable-HTTP remote MCP
│   │   │       │   │   └── python_lib.py       # In-process callable invocation
│   │   │       │   ├── adapter/                # Wizard-time LLM adapter (Need -> CallableSpec)
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   ├── prompts.py
│   │   │       │   │   ├── canary.py           # Canary execution + shape-match check
│   │   │       │   │   └── introspect.py       # python_lib module introspection
│   │   │       │   └── catalog/                # Day-1 provider templates (deferred — see plan §13.5)
│   │   │       │
│   │   │       ├── prompts/                    # Department prompt templates (YAML, Jinja2)
│   │   │       │   ├── secretary.yaml
│   │   │       │   ├── equity_research.yaml
│   │   │       │   ├── earnings_update.yaml
│   │   │       │   ├── morning_briefing.yaml
│   │   │       │   ├── macro_research.yaml         # T4 / T5 batch assessments
│   │   │       │   ├── retail_sentiment.yaml       # batch classification
│   │   │       │   ├── retail_sentiment_classify.yaml
│   │   │       │   ├── retail_sentiment_insights.yaml
│   │   │       │   └── shared/
│   │   │       │       ├── voice.yaml.j2           # Jinja2 includes for shared voice
│   │   │       │       └── output_discipline.yaml.j2
│   │   │       │
│   │   │       ├── reports/                    # Report generation (see report-rendering-pipeline-design.md)
│   │   │       │   ├── __init__.py
│   │   │       │   ├── schema.py               # Pydantic models for report schema (all block types)
│   │   │       │   ├── assembler.py            # LLM output → report schema JSON
│   │   │       │   ├── validator.py            # Validates filled schema against block type rules
│   │   │       │   ├── templates/              # Report rendering templates
│   │   │       │   ├── frameworks/             # Framework JSON + style-guide markdown (shipped with package)
│   │   │       │   │   ├── __init__.py
│   │   │       │   │   ├── loader.py           # Load framework, apply user customizations
│   │   │       │   │   ├── stock_initiation.json
│   │   │       │   │   ├── stock_initiation_style_guide.md
│   │   │       │   │   ├── stock_update.json
│   │   │       │   │   ├── stock_update_style_guide.md
│   │   │       │   │   ├── sector_research.json
│   │   │       │   │   ├── sector_research_style_guide.md
│   │   │       │   │   ├── earnings_update.json
│   │   │       │   │   ├── earnings_update_style_guide.md
│   │   │       │   │   ├── morning_briefing.json
│   │   │       │   │   └── morning_briefing_style_guide.md
│   │   │       │   └── style_extraction/       # Pipeline for deriving custom style guides from user PDFs
│   │   │       │       ├── __init__.py
│   │   │       │       ├── pipeline.py         # Resumable 4-phase runner
│   │   │       │       └── prompts.py          # All 4 phase prompts as Python constants
│   │   │       │
│   │   │       ├── config.py                   # Config loader (.env / env vars)
│   │   │       └── exceptions.py
│   │   │
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── test_departments/
│   │       ├── test_llm/                       # Includes test_runtime/ for router + escalation
│   │       ├── test_connectors/                # Transports, adapter, canary, introspect, types
│   │       ├── test_formula/                   # Engine tests + streak fixtures
│   │       └── test_reports/
│   │
│   │   --------------------------------------------------------
│   │   SERVER - FastAPI server + Typer CLI
│   │   Depends on core. Owns HTTP, auth, sessions, DB, scheduler.
│   │   --------------------------------------------------------
│   │
│   └── server/
│       ├── pyproject.toml              # Package: "openlia" (registers `openlia` script)
│       ├── src/
│       │   └── openlia_server/
│       │       ├── __init__.py
│       │       ├── app.py              # FastAPI app factory (lifespan-managed scheduler)
│       │       ├── cli.py                  # Typer app: serve, admin, wizard, secrets, maintenance
│       │       │
│       │       ├── routes/             # API endpoints — thin handlers, delegate to core/services
│       │       │   ├── __init__.py
│       │       │   ├── setup.py            # /setup/* wizard endpoints (Plan 10)
│       │       │   ├── auth.py             # login, logout, password change, password reset request/redeem
│       │       │   ├── admin.py            # invites, user CRUD, lockout settings, audit log views
│       │       │   ├── settings.py         # user/admin settings + setup wizard API
│       │       │   ├── connectors.py       # /api/connectors CRUD + revalidate (connector v2)
│       │       │   ├── runner_specs.py     # /api/connectors/{id}/proposed-specs/{resolve,approve}
│       │       │   ├── dept_health.py      # GET /api/dept-health + 409 gate helper
│       │       │   ├── departments.py      # Department chat endpoints (SSE)
│       │       │   ├── reports.py          # GET /reports/{id}, POST /reports/{id}/export/pdf
│       │       │   ├── repository.py       # Save/list/delete saved reports
│       │       │   ├── portfolio.py        # Portfolio CRUD
│       │       │   ├── morning_briefing.py # MB schedule CRUD + briefing endpoints
│       │       │   ├── earnings_update.py  # EU schedule CRUD + scan endpoints
│       │       │   ├── macro_research.py   # MR dashboard state, settings, trigger assessment
│       │       │   ├── retail_sentiment.py # RS metrics, evidence, signals, settings
│       │       │   ├── panic_thermometer.py# PT panel data + formula validation/preview
│       │       │   └── jobs.py             # GET /jobs/history, POST /jobs/{run_id}/retry
│       │       │
│       │       ├── middleware/         # Request processing
│       │       │   ├── __init__.py
│       │       │   ├── auth.py             # Session cookie validation; toggleable for personal mode
│       │       │   ├── rate_limit.py       # Login/registration brute-force throttling
│       │       │   └── wizard_gate.py      # require_wizard_active / require_wizard_session (Plan 10)
│       │       │
│       │       ├── db/                 # Persistence layer (see database-design.md)
│       │       │   ├── __init__.py
│       │       │   ├── models.py           # SQLAlchemy models for all 29+ tables
│       │       │   ├── session.py          # Engine + sessionmaker
│       │       │   ├── crypto.py           # AES-256-GCM helpers for llm_providers.api_key_encrypted
│       │       │   └── migrations/         # Alembic migrations
│       │       │
│       │       ├── scheduler/          # Background task scheduling (see background-task-scheduling-design.md)
│       │       │   ├── __init__.py         # SchedulerService export
│       │       │   ├── service.py          # Init, startup, shutdown, hot-reload (APScheduler 4.x)
│       │       │   ├── executors.py        # Job executors: mb_briefing, eu_scan, mr_assessment, system_maintenance
│       │       │   └── recovery.py         # Crash recovery + missed-job catch-up
│       │       │
│       │       └── services/           # Business logic between routes and core
│       │           ├── __init__.py
│       │           ├── wizard.py                # WizardService — status, token, mode, identity, finish (Plan 10)
│       │           ├── auth/                    # Package: passwords, tokens, sessions, registration, login, password_reset, events, signup_policy
│       │           ├── connectors_service.py    # Connector CRUD + validation (calls into core/connectors)
│       │           ├── runner_specs_service.py  # Wizard-time adapter resolve + approve (RunnerCallableSpec persistence)
│       │           ├── dept_health.py           # Cached DepartmentHealth map, mutation-driven invalidation
│       │           ├── dispatcher_factory.py    # Build CallableTransport per connector launch mode
│       │           ├── chat.py                  # Chat history persistence + retrieval
│       │           ├── portfolio.py
│       │           ├── repository.py            # Saved-report repository service
│       │           └── report_export.py         # Playwright PDF generation
│       │
│       └── tests/
│           ├── __init__.py
│           ├── test_routes/
│           ├── test_middleware/
│           ├── test_services/
│           ├── test_scheduler/
│           └── e2e/                        # End-to-end smoke matrix (wizard, runner activation, 409 gate, atomic disable, escalation)
│
│
│   ============================================================
│   FRONTEND - React + TypeScript + Vite (not a Python package)
│   ============================================================
│
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── public/
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       │
│       ├── api/                        # fetchJson + typed endpoint modules
│       │   ├── client.ts               # fetchJson wrapper
│       │   ├── auth.ts                 # login, logout, logoutAll, register, getSignupPolicy, requestPasswordReset, consumePasswordReset, changePassword
│       │   └── notifications.ts        # getUnread, markRead
│       │
│       ├── auth/                       # AuthProvider + useAuth + 4-state status machine
│       │   ├── AuthContext.tsx         # status: loading|authenticated|unauthenticated|personal; mustChangePassword flag
│       │   └── passwordStrength.ts     # pure fn: StrengthLevel 0–4
│       │
│       ├── router/                     # createBrowserRouter tree
│       │   ├── routes.tsx              # browser router: public auth routes + ProtectedRoute > MustChangePasswordGate > AppLayout
│       │   ├── ProtectedRoute.tsx      # redirects unauthenticated to /login (children API)
│       │   └── MustChangePasswordGate.tsx  # intercepts protected routes when mustChangePassword===true
│       │
│       ├── layouts/                    # AppLayout (Sidebar + Outlet)
│       │
│       ├── components/
│       │   ├── sidebar/                # Sidebar shell, NavItem, useCollapsed, useNotificationPoll, navData
│       │   ├── primitives/             # Button, Input, Card, Banner, FormField, PasswordInput, PasswordStrengthMeter
│       │   ├── auth/                   # Auth form components (Plan 9)
│       │   │   ├── AuthLayout.tsx      # full-screen centered layout with LIA wordmark
│       │   │   ├── AuthCard.tsx        # bordered card, max-width 420px
│       │   │   ├── LoginForm.tsx
│       │   │   ├── RegisterForm.tsx
│       │   │   ├── ForgotPasswordForm.tsx
│       │   │   ├── ResetPasswordForm.tsx
│       │   │   └── MustChangePasswordForm.tsx
│       │   ├── report/                 # Report renderer (see report-rendering-pipeline-design.md) — added Plan 13+
│       │   │   ├── ReportRenderer.tsx
│       │   │   ├── ReportCover.tsx
│       │   │   ├── TableOfContents.tsx
│       │   │   ├── ReportSection.tsx
│       │   │   ├── BlockRenderer.tsx
│       │   │   ├── blocks/             # TextBlock, TableBlock, MetricCardsBlock, GroupBlock, ...
│       │   │   ├── charts/             # ECharts wrappers for Line, Bar, Area, Pie, Candlestick, Waterfall, ...
│       │   │   └── furniture/          # ReportHeader, ReportFooter, ScrollTracker, ReportSkeleton
│       │   ├── MacroResearch/          # Scorecard, QuadrantMap, GradientBar, ForceRow, StageTimeline, ... — added Plan 19+
│       │   └── RetailSentiment/        # MetricCard, GaugeArc, HeatMap, ScoreImpactBar, ... — added Plan 20+
│       │
│       ├── setup/                      # Setup Wizard — WizardShell, steps, WizardContext (Plan 10)
│       │   ├── WizardContext.tsx       # WizardProvider + useWizard hook
│       │   ├── WizardShell.tsx         # card + header + progress bar chrome
│       │   ├── WizardFooter.tsx        # Back / Next buttons
│       │   ├── WizardProgress.tsx      # progress bar
│       │   └── steps/                  # one file per wizard step
│       │
│       ├── pages/
│       │   ├── SetupPage.tsx           # /setup route — picks step from WizardContext
│       │   ├── LoginPage.tsx           # redirects if already authenticated
│       │   ├── RegisterPage.tsx        # invite-gated; requires ?invite= param
│       │   ├── ForgotPasswordPage.tsx
│       │   ├── ResetPasswordPage.tsx   # requires ?token= param
│       │   ├── account/                # Account section (Plan 9)
│       │   │   ├── AccountProfile.tsx  # read-only user info from useAuth()
│       │   │   ├── ChangePasswordForm.tsx
│       │   │   └── SessionsPanel.tsx   # sign out all other devices
│       │   └── departments/            # Department pages; replaced by Plans 13–20
│       │
│       └── styles/
│           ├── tokens.css              # Design-system CSS variables (light + dark)
│           └── global.css             # Tailwind entry
│
│
│   ============================================================
│   PLANNING - Specs, plans, and project management docs
│   ============================================================
│
├── planning/
│   ├── PLAN.md                         # Master plan (architecture overview)
│   ├── projectStructure.md             # This file
│   ├── GAPS.md                         # Open gaps and discrepancy tracking
│   │
│   ├── specs/
│   │   ├── pages/                      # Per-page UI specs
│   │   │   ├── LoginPageSpec.md
│   │   │   ├── SetupWizardSpec.md
│   │   │   ├── PortfolioPageSpec.md
│   │   │   ├── RepositoryPageSpec.md
│   │   │   ├── SettingsPageSpec.md
│   │   │   ├── template.md
│   │   │   └── departments/
│   │   │       ├── SecretaryPageSpec.md
│   │   │       ├── EquityResearchPageSpec.md
│   │   │       ├── EarningsUpdatePageSpec.md
│   │   │       ├── MorningBriefingsPageSpec.md
│   │   │       ├── RetailSentimentPageSpec.md
│   │   │       ├── MacroResearchPageSpec.md
│   │   │       └── PanicThermometerPageSpec.md
│   │   │
│   │   ├── components/                 # Shared component specs (renamed from utility_tools/)
│   │   │   ├── AccountManagementSpec.md
│   │   │   ├── ChatHistorySpec.md
│   │   │   ├── ChatInterfaceSpec.md
│   │   │   ├── FileViewerSpec.md
│   │   │   ├── FileDownloadSpec.md
│   │   │   ├── SaveToRepoSpec.md
│   │   │   └── SideBarSpec.md
│   │   │
│   │   ├── systems/                    # Cross-cutting system designs
│   │   │   ├── database-design.md
│   │   │   ├── cli-surface-design.md
│   │   │   ├── background-task-scheduling-design.md
│   │   │   ├── llm-provider-design.md
│   │   │   ├── llm-runtime-design.md
│   │   │   ├── formula-engine-design.md
│   │   │   ├── report-rendering-pipeline-design.md
│   │   │   ├── macro-research-dalio-dashboards-design.md
│   │   │   └── retail-sentiment-dashboard-design.md
│   │   │
│   │   └── style_extraction_procedure.md   # Procedure + future-feature design for style extraction
│   │
│   │   The connector subsystem's authoritative design lives outside `planning/specs/`
│   │   in `docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md`. The
│   │   legacy `connector-dataflow-design.md` was retired in Phase 1 of the v2 reshape.
│   │
│   └── logs/                           # Progress logs (one per commit, optional)
│
│
│   ============================================================
│   ROOT TOOLING
│   ============================================================
│
└── .github/
    └── workflows/
        └── ci.yml                      # CI: lint (ruff), test (pytest), build
```


## Runtime user-data layout

Created on first run by the server / wizard (not committed; lives outside the repo):

```
~/.openlia/
├── openlia.db                  # SQLite database (see database-design.md)
└── secret.key                  # Auto-generated AES-256 key for API-key encryption (only when OPENLIA_SECRET_KEY is unset)
```

Connector-related artifacts (provider catalogs, dept needs, routing-context prompts, runtime callable specs) ship inside `packages/core/` or live in DB tables (`connectors`, `runner_callable_specs`); they no longer require an on-disk overlay under `~/.openlia/`.


## Database tables (catalog)

Defined in `database-design.md`. Grouped by concern:

| Group | Tables |
|---|---|
| Identity & auth | `users`, `sessions`, `signup_invites`, `signup_policy`, `password_reset_requests`, `auth_events` |
| LLM config | `llm_providers`, `llm_models`, `user_llm_preferences` |
| Connectors v2 | `connectors`, `runner_callable_specs` |
| Chat & reports | `chat_sessions`, `chat_messages`, `chat_attachments`, `reports`, `report_versions` |
| Portfolio | `portfolio_holdings`, `watchlists`, `watchlist_items` |
| Setup & config | `wizard_state`, `config_store` |
| Department state | `pt_user_configs`, `pt_presets`, `mr_dashboard_state`, `mr_assessment_cache`, `rs_user_config`, `rs_snapshots`, `fe_saved_formulas` |
| Scheduler | `mb_schedules`, `eu_schedules`, `job_runs`, `user_notifications` |

The legacy `data_providers` and `data_provider_requirement_mapping` tables were dropped in connector-redesign-v2; the new `connectors` row carries the multi-mode `LaunchSpec` JSON and `runner_callable_specs` records the resolved `(department_id, need_id) -> CallableSpec` mapping.

Lockout columns (`failed_login_attempts`, `locked_until`) live on `users`. The lockout feature is toggleable via `config_store` key `auth.lockout.enabled`.


## CLI surface

Defined in `cli-surface-design.md`. Single entry point registered as `openlia` in the server package's `[project.scripts]`:

```
openlia                           # help
openlia serve                     # start FastAPI
openlia admin list-users
openlia admin unlock <email>
openlia admin lockout {enable|disable|status}
openlia admin reset-password <email>
openlia admin disable-user <email>
openlia admin enable-user <email>
openlia admin revoke-sessions <email>
openlia admin create-invite [--label] [--expires] [--max-uses]
openlia admin list-invites
openlia admin revoke-invite <token-or-id>
openlia wizard reset
openlia secrets rotate-key
openlia maintenance               # run pruning sweep manually
```

CLI commands write to the same `auth_events` log as their web-admin equivalents. They are distinguished by `actor_user_id = NULL` and `metadata.source = "cli"`.


## Root pyproject.toml (uv workspace)

Not itself an installable package; declares the workspace and shared tool config.

```toml
[build-system]
requires = ["uv_build>=0.9.5,<0.10.0"]
build-backend = "uv_build"

[tool.uv.workspace]
members = ["packages/*"]

[tool.uv]
package = false
```


## Package dependency graph

```
core (openlia-core)     -- zero web dependencies, pure Python
  ^
  |
server (openlia)        -- depends on core via workspace reference, provides CLI
  ^
  |
frontend                -- talks to server via REST + SSE, no Python dependency
```

Server `pyproject.toml` references core as a workspace dependency and registers the CLI:

```toml
[project]
name = "openlia"
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "apscheduler>=4.0",
    "argon2-cffi>=23.1",
    "typer>=0.12",
]

[project.scripts]
openlia = "openlia_server.cli:main"

[tool.uv.sources]
openlia-core = { workspace = true }
```


## Key design rules

1. **core has zero web imports.** No FastAPI, uvicorn, requests-with-FastAPI-context, or anything HTTP-framework-specific inside `packages/core/`. Test: `from openlia.departments.equity_research import EquityResearchDepartment` must work in a Jupyter notebook with only `openlia-core` installed, no server running.

2. **Server is a thin wrapper.** Routes call core methods or service-layer helpers and return the result. Business logic — including report generation, chat orchestration, and dashboard evaluation — lives in core. Auth, session management, scheduler orchestration, and DB persistence live in the server's `services/` and `scheduler/`, not in route handlers.

3. **Cross-department reads go through public APIs, not data scraping.** When one department needs another's state (e.g., MB reading MR's framework statuses), it calls a typed entry point on the other department's class — see `MacroResearchDepartment.get_current_snapshot()`. Departments never reach into each other's DB tables directly.

4. **Frontend is decoupled.** Communicates only through the server's REST + SSE API. Could be replaced with a different UI without touching any Python code.

5. **Config flows one direction.** Env vars (`OPENLIA_*`) and `.env` are read by `core/config.py`. The server passes config to core at startup. Admin-managed runtime config (LLM providers, data providers, schedules) lives in the database. The frontend never touches config directly.

6. **Frameworks ship with the package.** Report frameworks (`packages/core/src/openlia/reports/frameworks/*.json`) and their style guides (`*_style_guide.md`) are shipped artifacts. They were originally drafted under `planning/frameworks/` and have been migrated into the package so they are present in installed wheels and Docker images. Custom user style guides (from the style-extraction pipeline) live alongside user/org settings, not under `planning/`.

7. **Planning docs are not shipped.** The `planning/` directory is for development only. It is excluded from Python package builds and Docker images.

8. **Scheduler lives in the server, not core.** Background jobs depend on the DB, the FastAPI lifecycle, and user session context. Core remains scheduler-agnostic — its runners and department classes are callable from any context (CLI, tests, scheduler, request handlers).

9. **Audit trail is shared between CLI and UI.** Both surfaces emit the same `event_type` to `auth_events`. The `actor_user_id` field (NULL for CLI) and `metadata.source` field (`"cli"` vs `"web"`) carry the source distinction.

10. **Self-service account deletion is out of scope for v1.** Admin-only hard delete via DB / CLI. See `AccountManagementSpec.md` § 16 Non-Goals.
