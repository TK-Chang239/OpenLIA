# Data Provider System Design

Multi-provider, requirements-first data system for OpenLIA. Allows users to configure any combination of financial and news data providers while departments retain full access to each provider's unique strengths.

## Core Concepts

**Requirements-first:** OpenLIA ships with a department requirements manifest that defines what *types* of data each department needs — not specific endpoint IDs. Requirements are split into basic (must be satisfied) and advanced (optional). Provider endpoint documentation is only installed when the user configures a provider.

**Author-time mapping:** When a provider is configured, an AI reviewer maps the provider's endpoints to department requirements and persists the mappings to files. Runtime reads these files deterministically — no AI inference at report-generation time for tool selection.

**Multi-provider per category:** Users can configure multiple providers within each category (financial, news). Each requirement is fulfilled by whichever provider the user has prioritized highest that can satisfy it.

**Runtime expansion:** If the report-writing LLM needs data beyond its mapped tools, it can trigger a fast AI search across all active provider catalogs to find and temporarily add relevant endpoints.


## Provider Categories

Three categories of data providers:

| Category | Purpose | Examples | Required |
|----------|---------|----------|----------|
| Financial | Market data, fundamentals, technicals, earnings, options | FMP, EODHD, Finnhub, yfinance | Yes |
| News | Headlines, article search, political events, sector news | NewsAPI.ai, Mediastack, NewsAPI.org | Yes |
| Social Media | Social posts, trending tickers, retail discussion volume | X (Twitter), Reddit | No |

Financial and news providers are required — OpenLIA will not start without at least one of each. Social media providers are optional and primarily serve the Retail Sentiment department.


## Department Data Access Patterns

Departments fall into two categories based on how they access data:

**Tool-calling departments** receive mapped tools and the runtime expansion meta-tool. The LLM decides which tools to call and when.
- Secretary
- Stock Research
- Earnings Report
- Macro Research
- Morning Briefing

**Pre-fetch departments** follow a fixed data recipe. Code fetches specific data before the LLM runs — no tool-calling.
- Panic Thermometer
- Retail Sentiment (social media APIs + provider sentiment endpoints — see Retail Sentiment section below)


## Configuration

### Provider Entry

Each configured provider is represented by a `ProviderEntry`:

```python
class ProviderEntry(BaseModel):
    id: str                                    # e.g. "fmp", "eodhd", "finnhub"
    category: Literal["financial", "news"]
    mode: Literal["api_key", "mcp"]
    api_key: SecretStr | None = None
    base_url: HttpUrl | None = None            # required for api_key mode
    mcp_url: HttpUrl | None = None             # required for mcp mode
    mcp_auth_header: str | None = None

class DataProvidersConfig(BaseModel):
    financial: list[ProviderEntry]             # ordered by user priority (first = highest)
    news: list[ProviderEntry]                  # ordered by user priority (first = highest)
    social_media: list[ProviderEntry] = []     # optional, ordered by user priority

class ReviewConfig(BaseModel):
    model: str                                 # fast/cheap model for AI review + runtime expansion
    api_key: SecretStr | None = None

class ExpansionConfig(BaseModel):
    max_expansions_per_report: int = 15        # user-configurable in settings, unlimited for Secretary
```

Provider lists are ordered by user priority. When the AI review maps requirements to endpoints, it walks providers in priority order — the first provider that can satisfy a requirement wins. The user controls which provider is preferred for what, not the AI.

### Dual Transport

Each provider supports two configuration modes:

**API key mode:** Direct HTTP calls. OpenLIA handles request construction, auth injection, and response parsing using the provider's catalog metadata.

**MCP mode:** The user provides an MCP server URL. OpenLIA calls tools through the MCP protocol. The catalog is auto-generated from `list_tools()` at configuration time.

### Startup Validation

On startup, OpenLIA validates:
1. At least one financial provider is configured
2. At least one news provider is configured
3. All basic requirements across all non-disabled departments are satisfiable by the union of configured providers
4. Retail Sentiment availability check (see Retail Sentiment section)

If basic requirements are unmet, OpenLIA reports which requirements are missing and which departments are affected, and does not start. Departments that are disabled due to missing optional providers (e.g. Retail Sentiment) do not block startup.


## Department Requirements Manifest

Ships with OpenLIA in the package. Defines what types of data each department needs using plain-language descriptions — not provider-specific endpoint IDs. This is a contract: it tells the AI reviewer what to look for in any provider's catalog.

Requirements are split into two tiers:
- **Basic:** Must be satisfied for the department to function. OpenLIA will not start if basic requirements are unmet.
- **Advanced:** Enhance report quality when available. If the configured providers cannot satisfy an advanced requirement, the department still works — the LLM is informed which advanced data types are unavailable.

### Format

```yaml
# packages/core/src/openlia/data/manifest/requirements.yaml
#
# Department requirements manifest. Defines what data types each department
# needs. Basic requirements must be satisfied; advanced are optional.
#
# Format per department:
#   department: <department_id>
#   requirements:
#     basic:
#       - type: <data_type_name>
#         description: <plain-language description of what this data is>
#     advanced:
#       - type: <data_type_name>
#         description: <plain-language description>
#
# Example entry:
#   department: stock_research
#   requirements:
#     basic:
#       - type: stock_quote
#         description: Real-time or delayed stock price, volume, market cap
#     advanced:
#       - type: stock_grade
#         description: Analyst upgrades, downgrades, and ratings
#
# TODO: Fill in requirements for each department
departments: []
```

The `type` field is a short identifier (e.g. `stock_quote`, `company_news`, `historical_prices`). The `description` field gives the AI reviewer enough context to match against any provider's endpoint descriptions and tags, regardless of naming conventions.

### Manifest Location

```
packages/core/src/openlia/data/manifest/
├── __init__.py
├── loader.py          # Load and parse requirements.yaml
├── types.py           # Requirement, DepartmentManifest pydantic models
├── checker.py         # Validate basic requirements against active provider catalogs
├── audit.py           # Log runtime tool expansions
└── requirements.yaml  # The manifest (placeholder — to be filled in)
```


## Provider Catalogs

### What a Catalog Is

A YAML file documenting every endpoint a provider offers: path, method, parameters, response shape, tags. This is the raw material the AI reviewer searches when mapping requirements to endpoints.

### Catalog Schema

```yaml
id: fmp
display_name: Financial Modeling Prep
category: financial
version: "2026.1"
call_style: http
base_url: https://financialmodelingprep.com/api/v3
auth:
  type: query_param
  param: apikey
  secret_env: FMP_API_KEY
rate_limit:
  requests_per_minute: 3000
endpoints:
  - id: get_stock_quote
    path: /quote/{symbol}
    method: GET
    summary: Real-time stock quote
    description: Returns price, volume, market cap, day range, 52-week range,
      average volume, PE ratio, and earnings date for a given symbol.
    tags: [quote, realtime, price]
    params:
      - name: symbol
        in: path
        type: string
        required: true
    returns:
      shape: array
      fields:
        price: { type: number }
        changesPercentage: { type: number }
        volume: { type: number }
        marketCap: { type: number }
```

### Bundled Templates vs Active Catalogs

OpenLIA ships with **bundled catalog templates** for known providers inside the package. These are reference files — they are not active at install time.

```
packages/core/src/openlia/data/catalog/bundled/
├── financial/
│   ├── fmp.yaml          # placeholder — to be filled in
│   ├── eodhd.yaml        # placeholder — to be filled in
│   ├── finnhub.yaml      # placeholder — to be filled in
│   └── yfinance.yaml     # placeholder — to be filled in
├── news/
│   ├── newsapi_ai.yaml   # placeholder — to be filled in
│   ├── mediastack.yaml   # placeholder — to be filled in
│   └── newsapi_org.yaml  # placeholder — to be filled in
└── social_media/
    ├── x.yaml            # placeholder — to be filled in
    └── reddit.yaml       # placeholder — to be filled in
```

When a user configures a provider, the corresponding bundled template is copied to the **active catalog directory** in user data:

```
~/.openlia/providers/
├── financial/
│   ├── fmp.yaml          # copied from bundled when user configures FMP
│   └── eodhd.yaml        # copied from bundled when user configures EODHD
├── news/
│   └── newsapi_ai.yaml   # copied from bundled when user configures NewsAPI.ai
└── social_media/
    └── x.yaml            # copied from bundled when user configures X API
```

### Catalog Installation Paths

Three ways a catalog gets installed:

1. **Known provider (API key mode):** Bundled template is copied to `~/.openlia/providers/`. No network call needed.
2. **MCP provider:** OpenLIA calls `list_tools()` on the MCP server and generates a catalog YAML from the returned tool schemas via the discovery module.
3. **Unknown provider (API key mode):** User supplies an OpenAPI spec URL or file. OpenLIA generates a catalog from that spec.

### Catalog Module Layout

```
packages/core/src/openlia/data/catalog/
├── __init__.py
├── loader.py          # Load active catalogs from ~/.openlia/providers/
├── installer.py       # Copy bundled template, or generate from MCP/OpenAPI
├── types.py           # ProviderCatalog, Endpoint, Param pydantic models
├── discovery.py       # Build catalog from MCP list_tools
└── bundled/           # Reference templates (see above)
```


## AI Review (Author-Time Mapping)

When a user configures or changes a provider, the AI review runs to map provider endpoints to department requirements.

### Flow

```
1. Load the requirements manifest (all departments)
2. Load catalogs for all currently configured providers
3. For each department:
   a. For each requirement (basic, then advanced):
      i.  Walk configured providers in user-priority order
      ii. Search provider's catalog for endpoints matching the requirement type+description
      iii. First provider with a confident match wins — assign that endpoint
   b. If no provider matches a basic requirement: flag as unmet
   c. If no provider matches an advanced requirement: mark as unavailable
4. Persist mapping file per department to ~/.openlia/mappings/
5. Report results:
   - All basic satisfied: proceed
   - Basic unmet: warn user, list affected departments, do not allow startup
   - Advanced unavailable: informational only
```

### Mapping Output

One file per department:

```yaml
# ~/.openlia/mappings/stock_research.yaml
department: stock_research
generated_at: "2026-04-11T09:30:00Z"
review_model: gpt-4o-mini
basic:
  stock_quote:
    provider: fmp
    endpoint: get_stock_quote
    confidence: 0.95
  company_fundamentals:
    provider: eodhd
    endpoint: get_fundamentals_data
    confidence: 0.92
  historical_prices:
    provider: fmp
    endpoint: get_historical_price_full
    confidence: 0.97
  company_profile:
    provider: fmp
    endpoint: get_company_profile
    confidence: 0.94
  company_news:
    provider: newsapi_ai
    endpoint: search_articles
    confidence: 0.88
advanced:
  stock_grade:
    provider: fmp
    endpoint: get_stock_grade
    confidence: 0.96
  insider_transactions:
    provider: eodhd
    endpoint: get_insider_transactions
    confidence: 0.90
  technical_indicators:
    provider: eodhd
    endpoint: get_technical_indicators
    confidence: 0.93
  analyst_estimates: null       # no provider covers this
  institutional_holders: null   # no provider covers this
  esg_score:
    provider: eodhd
    endpoint: get_esg_data
    confidence: 0.85
```

### Re-review Triggers

The AI review re-runs when:
- A provider is added, removed, or has its priority changed
- A provider catalog is updated (e.g. new version of a bundled template)
- The user customizes report sections that change a department's data needs (section additions or deletions, not enable/disable toggles). How custom section requirements feed into the manifest is defined by the Report Framework System spec — this spec only defines that a re-review is triggered.

### Review Module Layout

```
packages/core/src/openlia/data/review/
├── __init__.py
├── service.py         # Orchestrates the review flow
├── prompts.py         # Prompts for requirement-to-endpoint matching (placeholder — needs tuning)
├── validator.py       # Confidence thresholds, unmet-requirement reporting
```


## Tool Namespacing and Runtime Dispatch

### Namespacing

All tools exposed to department LLMs are namespaced by provider ID:

```
fmp.get_stock_quote
eodhd.get_fundamentals_data
newsapi_ai.search_articles
```

This prevents collisions when multiple providers are active and makes it clear to the LLM (and in logs) which provider is being called.

### Dispatch

At runtime, the dispatch router:
1. Reads the department's mapping file
2. Builds a tool list containing only the mapped endpoints (basic + available advanced)
3. For each tool call from the LLM, routes to the correct provider using the correct transport:
   - API key mode: `http_client.py` constructs the HTTP request using catalog metadata (base_url, path, params, auth)
   - MCP mode: `mcp_client.py` forwards the call to the MCP server

### Dispatch Module Layout

```
packages/core/src/openlia/data/dispatch/
├── __init__.py
├── router.py          # Read mappings, build tool lists, route calls
├── http_client.py     # Direct HTTP calls for api_key mode providers
├── mcp_client.py      # MCP protocol calls for mcp mode providers
├── tool_call.py       # Unified ToolCall, ToolResult pydantic models
└── expansion.py       # Runtime tool expansion meta-tool
```


## Runtime Tool Expansion

A meta-tool available to tool-calling departments. If the LLM determines during report generation that it needs data not covered by its mapped tools, it can request additional tools.

### Meta-Tool Signature

```python
request_additional_tools(
    description: str,   # what the LLM is looking for
    reason: str,        # why current tools are insufficient
) -> list[ToolSchema]   # new tools now callable for this session
```

### Flow

1. LLM calls `request_additional_tools(description="...", reason="...")`
2. A fast/cheap AI model (same as the review model) searches ALL active provider catalogs for endpoints matching the description
3. Matched endpoints are added to the LLM's tool list for the current session only
4. The expansion is logged to the audit trail

### Constraints

- **15 expansions per report** (default) for all departments except Secretary. User-configurable in Settings.
- **Unlimited** for Secretary (general-purpose chatbot, unpredictable needs). Not affected by the setting.
- **Session-scoped:** Expanded tools are not persisted to the mapping files automatically
- **Audit trail:** All expansions logged with timestamp, department, description, reason, matched endpoints
- **User promotion (v1):** Users can review the audit trail and explicitly promote useful expansions to permanent mappings

### Confidence Threshold

The AI reviewer outputs a confidence score (0.0-1.0) for each requirement-to-endpoint mapping. Thresholds:
- **>= 0.7:** Accepted automatically
- **0.4 - 0.7:** Accepted with a warning shown to the user ("low-confidence match — verify this mapping")
- **< 0.4:** Treated as no match (requirement marked unmet/unavailable)

### Audit Trail

```
~/.openlia/audit/
└── expansions.jsonl    # append-only log of all runtime expansions
```

Each entry:
```json
{
  "timestamp": "2026-04-11T14:22:00Z",
  "department": "stock_research",
  "session_id": "abc123",
  "description": "insider trading activity for AAPL",
  "reason": "mapped tools don't include insider data",
  "matched": [
    {"provider": "eodhd", "endpoint": "get_insider_transactions"}
  ]
}
```


## Error Handling

Three typed errors for all data operations:

| Error | Meaning | Handling |
|-------|---------|----------|
| `DataNotAvailable` | Provider does not have the requested data | Returned as structured tool result to LLM. LLM must write "data unavailable" — never hallucinate. |
| `RateLimitError` | Provider rate limit hit | Retry with exponential backoff. If retries exhausted, convert to `DataNotAvailable`. |
| `DataSourceError` | Unexpected provider error (500, timeout, malformed response) | Log error, return `DataNotAvailable` to LLM with context. |

`DataNotAvailable` is not an exception — it is a normal tool result. The LLM's system prompt enforces that unavailable data must be stated honestly, never fabricated.


## Retail Sentiment and Social Media

The Retail Sentiment department uses a fixed pre-fetch recipe with two data sources:

1. **Social media providers (optional):** Fetch social posts, discussion volume, and trending tickers from configured social media providers (X, Reddit, etc.). These are the primary source of retail sentiment signal.
2. **Financial provider sentiment endpoints:** Fetch any sentiment-related data from configured financial providers (e.g. EODHD's `get_sentiment_data`, FMP's social sentiment endpoints). Mapped through the normal requirements manifest.

### Availability Rules

The Retail Sentiment department requires at least one source of sentiment data. Its availability depends on what the user has configured:

| Social media providers | Financial provider has sentiment | Retail Sentiment status |
|------------------------|----------------------------------|------------------------|
| Configured | Any | Enabled — uses both sources |
| Not configured | Yes | Enabled — uses financial sentiment only |
| Not configured | No | Disabled — department hidden from UI, not available |

At startup, the checker evaluates this and either enables or disables the department. If disabled, the user is informed which providers would enable it.

Both data sources are fetched before the LLM runs. How the data is combined and analyzed is a separate concern (deferred to Retail Sentiment department design).


## Python Provider: yfinance

yfinance is a Python library, not an HTTP API. It is supported as a special-case provider:

- Catalog: bundled template documents available data functions as if they were endpoints
- Transport: `python_providers/yfinance_impl.py` wraps yfinance calls in the same `ToolCall` / `ToolResult` interface
- Dispatch: router detects `call_style: python` in the catalog and routes to the Python implementation instead of HTTP/MCP

```
packages/core/src/openlia/data/python_providers/
└── yfinance_impl.py
```


## Complete File Layout

### Package files (shipped with OpenLIA)

```
packages/core/src/openlia/data/
├── __init__.py
├── catalog/
│   ├── __init__.py
│   ├── loader.py
│   ├── installer.py
│   ├── types.py
│   ├── discovery.py
│   └── bundled/
│       ├── financial/
│       │   ├── fmp.yaml              # placeholder
│       │   ├── eodhd.yaml            # placeholder
│       │   ├── finnhub.yaml          # placeholder
│       │   └── yfinance.yaml         # placeholder
│       ├── news/
│       │   ├── newsapi_ai.yaml       # placeholder
│       │   ├── mediastack.yaml       # placeholder
│       │   └── newsapi_org.yaml      # placeholder
│       └── social_media/
│           ├── x.yaml                # placeholder
│           └── reddit.yaml           # placeholder
├── manifest/
│   ├── __init__.py
│   ├── loader.py
│   ├── types.py
│   ├── checker.py
│   ├── audit.py
│   └── requirements.yaml             # placeholder
├── review/
│   ├── __init__.py
│   ├── service.py
│   ├── prompts.py                    # placeholder — needs tuning
│   └── validator.py
├── dispatch/
│   ├── __init__.py
│   ├── router.py
│   ├── http_client.py
│   ├── mcp_client.py
│   ├── tool_call.py
│   └── expansion.py
├── python_providers/
│   └── yfinance_impl.py
├── sentiment/
│   └── checker.py         # Evaluate Retail Sentiment availability
└── errors.py
```

### User data files (created at runtime)

```
~/.openlia/
├── providers/                     # Active provider catalogs
│   ├── financial/
│   ├── news/
│   └── social_media/
├── mappings/                      # AI-generated requirement-to-endpoint mappings
│   ├── secretary.yaml
│   ├── stock_research.yaml
│   ├── earnings_report.yaml
│   ├── morning_briefing.yaml
│   ├── macro_research.yaml
│   ├── retail_sentiment.yaml
│   └── panic_thermometer.yaml
└── audit/
    └── expansions.jsonl           # Runtime expansion log
```


## Placeholder Files Summary

These files need manual authoring before the system is functional:

| File | What it needs |
|------|---------------|
| `manifest/requirements.yaml` | Data type requirements for each department (basic + advanced) |
| `catalog/bundled/financial/fmp.yaml` | Full endpoint documentation for FMP |
| `catalog/bundled/financial/eodhd.yaml` | Full endpoint documentation for EODHD |
| `catalog/bundled/financial/finnhub.yaml` | Full endpoint documentation for Finnhub |
| `catalog/bundled/financial/yfinance.yaml` | Full endpoint documentation for yfinance |
| `catalog/bundled/news/newsapi_ai.yaml` | Full endpoint documentation for NewsAPI.ai |
| `catalog/bundled/news/mediastack.yaml` | Full endpoint documentation for Mediastack |
| `catalog/bundled/news/newsapi_org.yaml` | Full endpoint documentation for NewsAPI.org |
| `catalog/bundled/social_media/x.yaml` | Full endpoint documentation for X (Twitter) API |
| `catalog/bundled/social_media/reddit.yaml` | Full endpoint documentation for Reddit API |
| `review/prompts.py` | AI review prompts for requirement-to-endpoint matching |


## Deferred to Follow-Up Specs

These systems interact with the data provider system but are designed separately:

- **Report Framework System:** Section schemas, default frameworks per department, custom sections, single-pass generation. When custom sections are added/deleted, the data provider system re-runs AI review to map any new data requirements.
- **Report Visualization System:** VizSpec types, chart/table/graph tools as LLM-callable tools, rendering.
- **Report Layout System:** Jinja templates, YAML themes, PDF rendering.
