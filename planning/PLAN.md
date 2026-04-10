# 1. Project Description

## Project Overview
OpenLia is an open-source, self-hosted AI investor assistant that provides real-time financial and market information with emphasis on speed, accuracy, and conciseness. Instead of a single chatbot, OpenLia uses multiple specialized LLM agents -- called Departments -- that each focus on a specific domain, similar to how departments in a company operate.

## Target Audience
OpenLia targets two user groups:
- Individual retail investors who want specialized, high-quality financial research tools they can run locally.
- Companies and teams that want to deploy OpenLia on an internal network so all employees can access it as a shared research tool.

## Distribution Model
OpenLia is an open-source project distributed as a self-hosted application. Users install and run it in their own environment with their own API keys. OpenLia is not a hosted SaaS product -- there is no central server, no subscription, and no data leaves the user's machine or network.

The project is published as:
- A Python package on PyPI (`pip install openlia`) for the full application. This installs both the core library and the server, providing the `openlia` CLI command (including `openlia serve`). Developers who only want the library layer for programmatic use can install `pip install openlia-core`.
- A Docker image for easy deployment of the full application (server + built frontend).

## Deployment Modes
OpenLia supports two deployment modes from the same codebase, controlled by configuration:

**Personal mode:** A single user installs the package, starts the server, and opens the web UI in their browser on `localhost`. On first launch, a setup wizard in the web UI guides the user through entering API keys and selecting their LLM provider -- no `.env` file editing required. No authentication.

**Company mode:** An administrator deploys OpenLia (typically via Docker) on an internal server. Shared API keys are configured as environment variables. Authentication is enabled so multiple employees can access the web UI over the internal network, each with their own chat history, portfolio, and saved reports.

## Project Language: Departments
Each specialized LLM agent is referred to as a `Department`. Each department focuses on a single domain or task for the highest quality and efficiency.


# 2. System Architecture

## Three-Layer Design
OpenLia is built as three independent layers. This separation ensures the core logic is reusable, the server is a thin wrapper, and the frontend is interchangeable.

### Library Layer (Python Package)
The core of OpenLia. Contains all department agents, prompt management, LLM abstraction, data fetching, and report generation logic. This layer has zero web dependencies -- no HTTP, no sessions, no user management. It is a pure Python package that can be imported and used in scripts, notebooks, or other applications independently.

Test: `from openlia import StockResearchDepartment` should work in a Jupyter notebook with only `openlia-core` installed and no server running.

### Server Layer (FastAPI)
A FastAPI application that wraps the library layer and exposes it over HTTP. Handles:
- REST API endpoints for all department interactions
- Real-time response streaming via Server-Sent Events (SSE) for chat interactions, allowing token-by-token output in the UI
- User session and authentication management (when enabled)
- API key configuration and management (server-side, not client-side)
- Request queuing and rate limiting for shared deployments
- Chat history and report storage via local database
- Background task scheduling for departments that run on a schedule (Morning Briefing, Earnings Report daily scans). Scheduler library is [TBD -- evaluate APScheduler, Celery, or similar based on spec review]
- CORS middleware configured to allow the frontend dev server during development

In personal mode, the server binds to `localhost`. In company mode, it binds to `0.0.0.0` and is accessible across the network.

### Database
SQLite is the default database for all deployments. It requires zero configuration, stores data in a single file, and ships with Python. For company deployments with high concurrency needs, PostgreSQL is supported as an optional alternative, configured via environment variable. The database stores chat history, user accounts (company mode), portfolio data, saved reports, and server-side configuration set via the setup wizard.

### Frontend Layer (Web UI)
Built with React, TypeScript, and Vite. The UI communicates with the server layer via REST API for data operations and SSE for streaming chat responses. The UI is identical regardless of deployment mode. Design and layout follow the patterns of LLM products like Claude and ChatGPT, with department-specific pages, a sidebar for navigation, and a file viewer for reports.

In development, Vite runs a dev server with a proxy to the FastAPI backend. In production (Docker), the React app is built into static files and served directly by FastAPI -- no separate frontend server is needed.

## LLM Abstraction
OpenLia is model-agnostic. The LLM layer is abstracted behind a common interface so users can configure any provider (OpenAI, Anthropic, open-source models via Ollama, OpenRouter, etc.) through configuration. This allows users to choose based on their quality, cost, privacy, or compliance requirements. No provider is hardcoded.

## Data Source Adapters
EODHD is the default and primary financial data provider. Data source integrations follow a curated adapter pattern: each supported provider has a dedicated adapter module with provider-specific logic. Department prompts are tuned per provider for maximum data quality. To add a new data source, a contributor writes a new adapter module in `core/data/` and a corresponding set of prompts. Arbitrary or untested providers are not supported via autodiscovery -- each integration is intentional and tested.

## Authentication
Authentication is disabled in personal mode and enabled in company mode via configuration. The specific auth method (session-based, OAuth/SSO, or other) is [TBD -- evaluate based on spec review of AccountManagementSpec.md and target company deployment environments].

## Configuration
Configuration can be set through two paths that write to the same server-side config store:
- **Setup wizard (default):** On first launch, the web UI presents a guided setup flow where the user enters API keys and selects their LLM provider. Settings can be changed later in the Settings page.
- **`.env` file or environment variables (advanced):** Developers and administrators can configure OpenLia through a `.env` file or environment variables (for Docker). This path takes precedence over the wizard if both are set.

Configuration includes:
- LLM provider and API key
- Data source API keys (EODHD, NewsAPI, social media APIs)
- Deployment mode (personal or company)
- Authentication settings (enabled/disabled, auth method)
- Server bind address and port


# 3. Product Functionalities - Departments

## Secretary
The Secretary serves as the general chatbot, where the user can ask it any question for quick and general answers. These include quick summaries of market news, stock updates, and more.
@planning/specs/pages/departments/SecretaryPageSpec.md

## Stock Research Department (SR)
The Stock Research Department, or SR, takes a ticker or company name and generates a research report on that company.
@planning/specs/pages/departments/StockResearchPageSpec.md

## Earnings Report Department (ER)
The Earnings Report Department, or ER, keeps track of a list of tickers or companies and conducts a daily scan to see if companies on that list have released new earnings report. If yes, then the ER will produce an analysis report on the earnings report. In addition to watchlists, ER also allows user request an on-demand earnings report anytime.
@planning/specs/pages/departments/EarningsReportsPageSpec.md

## Morning Briefing Department (MB)
The Morning Briefing Department, or MB, produces a daily morning briefing before the market open to summarize key overnight news.
@planning/specs/pages/departments/MorningBriefingsPageSpec.md

## Retail Sentiment Department (RS)
The Retail Sentiment Department, or RS, monitors social media platforms to analyze market sentiments. It produces three outputs: an overall market sentiment reading, per-stock sentiment scores for watchlist companies, and an auto-detected list of stocks whose discussion volume has spiked meaningfully over the past 7 days.
@planning/specs/pages/departments/RetailSentimentPageSpec.md

## Macro Research Department (MR)
When triggered by the user with a specific question or scope, the Macro Research Department, or MR, applies structured macroeconomic analytical frameworks to current data and produces a deep, framework-driven macro report.
@planning/specs/pages/departments/MacroResearchPageSpec.md


# 4. Product Functionalities - Other Pages

## Portfolio
The Portfolio keeps track of stocks, companies, industries, topics, etc. that the user is interested in. Departments will reference the Portfolio to adjust the contents and topics they cover in their reports.
@planning/specs/pages/PortfolioPageSpec.md

## Repository (Repo)
Whenever a report is generated, the user will have the option to save it to the repository. The repository, or repo, will store the reports that the user saved, with metadata tags such as date created, which department created, etc, to allow the user to find the report easily.
@planning/specs/pages/RepositoryPageSpec.md

## Settings
The settings page allows the user to edit preferences and settings. In company mode, this includes user-specific preferences. Instance-wide settings (API keys, auth config) are managed by the administrator through environment variables, not through the UI.
@planning/specs/pages/SettingsPageSpec.md


# 5. Product Functionalities - Utility Tools

## User Management
In personal mode, there is no login -- the single user has direct access. In company mode, authentication is enabled and users log in to access their own chat history, portfolio, and saved reports. User data is stored locally on the server (SQLite or PostgreSQL), not in a third-party cloud.
@planning/specs/UtilityTools/AccountManagementSpec.md

## Chat History
Each Department manages its own chat history, allowing the user to revisit previous conversations with that department. Chat history is stored in the local database.
@planning/specs/UtilityTools/ChatHistorySpec.md

## FileViewer
Each time a report is generated, a report thumbnail is shown in the chat. Clicking it opens a preview window on the right side of the screen with the chat on the left. The preview window allows scrolling and reading through the report.
@planning/specs/UtilityTools/FileViewerSpec.md

## File Download
Users can download reports to their local computer by clicking the download button on the report thumbnail or in the FileViewer window.
@planning/specs/UtilityTools/FileDownloadSpec.md

## SaveToRepo
Users can save reports to the Repository by clicking the save button on the report thumbnail or in the FileViewer window. Saving records the generation time and originating department for metadata management.
@planning/specs/UtilityTools/SaveToRepoSpec.md

## Side Bar
A sidebar on the left side of the page allows the user to navigate between departments, portfolio, repository, and settings.
@planning/specs/UtilityTools/SideBarSpec.md


# 6. Extension Functionalities (Ignore for now)
- Send morning briefings to user through text messages or email
- Allow user to upload reports for LLM to analyze and generate new report framework/template
- Buy vs Sell Debate
- Allow user to build their own departments


# 7. User Interface
The frontend UI design and layout descriptions for each page are found in @planning/specs/pages/. These descriptions serve as the basis for building the frontend pages.


# 8. Data Sources
OpenLia uses the following APIs as data sources. Users supply their own API keys for each service they want to enable.

## LLM Provider
OpenLia is model-agnostic. Users configure their preferred LLM provider and API key. Supported providers include OpenAI, Anthropic, OpenRouter, Ollama (local models), and any OpenAI-compatible API. The LLM abstraction layer handles routing to the configured provider.

## EODHD
- 75 tools available: historical prices, live quotes, fundamentals, technicals, macro indicators, news/sentiment, insider transactions, earnings/IPO calendars, US Treasury yields, ESG, options, risk scoring
- Key tools: resolve_ticker, get_fundamentals_data, get_historical_stock_prices, get_technical_indicators, get_company_news, get_upcoming_earnings
- Docs: https://eodhd.com/financial-apis/mcp-server-for-financial-data-by-eodhd

## NewsAPI
- Base URL: https://newsapi.org/v2/
- Endpoints: /everything (full archive search), /top-headlines (breaking news by category/country)
- Key params: q, sources, domains, from/to dates, language, sortBy (relevancy/popularity/publishedAt)
- Free tier: 100 req/day, no commercial use, 1-month lookback
- Docs: https://newsapi.org/docs

## Social Media API
- X (Twitter): API data used for retail sentiment analysis


# 9. Report Frameworks
Each Department follows a specialized framework for drafting reports. Report frameworks are pending design and will be added to the department spec files as they are developed.


# 10. Installation and Setup

## Quick Start (Personal Mode)
```
pip install openlia
openlia serve                    # starts server on localhost:8000
```
Open http://localhost:8000 in your browser. On first launch, the setup wizard will guide you through entering your API keys and selecting an LLM provider. Alternatively, power users can configure via a `.env` file before starting the server.

`pip install openlia` installs both the core library and the server package, and registers the `openlia` CLI command via `[project.scripts]` in the server's `pyproject.toml`.

## Docker Deployment (Company Mode)
```
docker pull openlia
docker run -d \
  -e LLM_PROVIDER=openai \
  -e LLM_API_KEY=sk-... \
  -e EODHD_API_KEY=... \
  -e AUTH_ENABLED=true \
  -p 8000:8000 \
  openlia
```
Accessible to all machines on the network at http://<server-ip>:8000.

The Docker image uses a multi-stage build: the first stage builds the React frontend into static files, the second stage installs the Python packages and bundles the built frontend. The final image serves everything from a single FastAPI process. Specific base image and build details are [TBD -- determine during Dockerfile implementation].

## Developer Usage (Library Only)
```
pip install openlia-core
```
```python
from openlia import StockResearchDepartment

sr = StockResearchDepartment(config="path/to/.env")
report = sr.run(ticker="AAPL")
```
This installs only the core library with no web dependencies. Useful for scripting, notebooks, and integration into other applications.


# 11. Project Building Process

## Spec Files
The spec files for pages, utility tools, and other design choices are located in @planning/specs/. These spec files lay out the purpose, functionalities, design, and configuration for each feature. Coding agents should review the spec files to plan implementations. Spec files are updated manually, then communicated to coding agents for revisions.

## Master Plan
The Master Plan provides a checklist for all features to be implemented (departments, utility tools, other pages, etc.) along with sub-tasks. The checklist is updated as features are implemented or new features are planned.

## Progress Logs
Before each commit, a new log file is created with details of changes in that commit: implementation details, files or processes changed, and open questions for future steps.


# 12. Coding Standards
1. Use latest versions of libraries and idiomatic approaches as of today
2. Keep it simple - NEVER over-engineer, ALWAYS simplify, NO unnecessary defensive programming. No extra features - focus on simplicity.
3. Be concise. Keep README minimal. IMPORTANT: no emojis ever
4. When hitting issues, always identify root cause before trying a fix. Do not guess. Prove with evidence, then fix the root cause.
5. **Dependency Management:** Always use `uv` for package management and script execution (`uv add`, `uv run`). Do not use `pip` or manual `venv` environments.
6. **Type Hinting:** Use modern, strict Python type hints for all function signatures to maintain code clarity.
7. **Error Handling:** Fail fast and loudly. Raise specific exceptions with contextual data rather than swallowing errors.
8. **Linting & Formatting:** Use `ruff` for all formatting and linting to maintain a clean, consistent codebase.
9. **Testing:** Build only necessary tests, aim for 80% coverage but it is not a hard requirement.
10. **Ambiguity:** When something is ambiguous, ask questions for clarification instead of assuming or guessing.
11. **Debugging Process:** For debugging, ALWAYS follow these exact 5 steps:
    1. Reproduce the problem
    2. Prove you reproduced the problem
    3. Find root cause
    4. Fix it
    5. Prove you fixed it

#13. Project Structure
The project structure is laid out is this document: @planning/projectStructure.md
