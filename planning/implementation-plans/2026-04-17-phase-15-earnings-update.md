# Earnings Update Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Earnings Update (EU) department so users can maintain a per-user watchlist of tickers, let the background scheduler scan that watchlist on cron-configured times to auto-generate earnings analysis reports, generate on-demand reports for the most recent earnings release of any company, browse all generated reports in an EU Cabinet, and customize report sections + length.

**Architecture:**
- **Core** gets an `EarningsUpdateDepartment` class (one report mode: `earnings_analysis`) plus a single `earnings_update.yaml` prompt that branches by `report_length` via Jinja. The `earnings_update.json` framework + style guide already live at `packages/core/src/openlia/reports/frameworks/` after Plan 13.
- **Server** adds two new tables — `eu_watchlist` (per-user ticker entries with cached next-earnings metadata) and `eu_user_configs` (sections + length preferences) — a watchlist service (which uses the `earnings_data` adapter from Plan 3 to look up the next earnings date on add), a config service, an `EUScanPlanner` implementation that fulfills the Plan 6 Protocol, a `/schedules` CRUD surface built on the `eu_schedules` table from Plan 1B, an `/api/departments/earnings-update/report` SSE route for on-demand generation, and a `/reports` listing endpoint. The real `EUScanPlanner` is wired into `build_scheduler_service()` via a setting at app startup.
- **Frontend** ships `EarningsUpdatePage` with a header, a horizontally scrollable `WatchlistRow` (with add/remove), a `RecentReportsList`, an `EUCabinet` overlay with search + date-grouping, an `OnDemandReportModal`, an `AddTickerPopover`, a `ScheduleManager` subview for CRUD on scan schedules, and a `ReportSettingsModal` for sections + length. Reports open in the Plan 12 `FileViewer`.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, APScheduler 4.x (hot-reload).
- Frontend: React 18 + TypeScript strict, Framer Motion, react-router-dom, Radix UI primitives (`Dialog`, `Popover`, `ToggleGroup`), Zod, Vitest + React Testing Library.

**Dependencies:**
- Plan 1A: `reports`, `chat_sessions`, `chat_messages`, `portfolio_holdings`, `users` tables; `SessionLocal`.
- Plan 1B: `eu_schedules`, `job_runs`, `user_notifications` tables.
- Plan 2: session middleware (all endpoints authenticated).
- Plan 3: data requirement adapter dispatcher; `earnings_data`, `financial_statements`, `stock_quote` adapters.
- Plan 4: LLM provider system; `DEPARTMENT_DEFAULT_TIERS["earnings_update"] == EVERYDAY`.
- Plan 5: `ReportRunner`, prompt loader, SSE event taxonomy, `ReportRequest`.
- Plan 6: `EUScanPlanner` Protocol, `EUScanTarget`, `build_scheduler_service(eu_planner=...)` injection point, `SchedulerService.add_schedule()/remove_schedule()`.
- Plan 8: frontend shell (routing, auth context, design tokens, `FileViewerProvider`, `NotificationBadge`).
- Plan 12: `ChatInterface` NOT used here (EU is a dashboard page, not a chat page); `FileViewerContext`, `SaveToRepoButton`, `FileDownloadButton` — all used by `ReportCard` / cabinet rows.
- Plan 13: `ReportSchema`, `assembler`, `validator`, framework loader + `load_framework_customized()` helper (if not shipped by Plan 13, it was added by Plan 14 — either path works since the helper is idempotent), `report_store`, `ReportRenderer`, `ReportCard`.

---

## Design Rules

1. **Watchlist entries cache the next earnings date at add-time.** When a user adds a ticker, the server immediately calls the `earnings_data` adapter to look up the next upcoming earnings release and caches `next_earnings_date` + `release_timing` on the row. A nightly maintenance sweep (Plan 6 system maintenance) refreshes stale caches; users never see a stale "Date passed" state for more than 24h.
2. **Schedules and watchlist are separate per user.** The scheduler iterates `eu_schedules`; each fire reads the full `eu_watchlist` rows for that user and asks the data provider for new earnings since `last_run_at`. A user with zero watchlist entries still consumes zero LLM resources.
3. **One report mode: `earnings_analysis`.** The framework JSON declares `"report_mode": "earnings_analysis"`. Every path — scheduled scan, on-demand, and any future variation — writes `report_type="earnings_update"` to `reports.report_type` (matches `database-design.md` § reports). The `mode` field inside `ReportRequest` stays `"earnings_analysis"`.
4. **Per-user section selection persists across all report generations.** Same shape as Plan 14's ER config: section IDs list + custom sections list + length (concise/normal/elaborative) — all persisted in `eu_user_configs`. Scan executor reads this config when building each `ReportRequest`.
5. **Custom sections carry `{id, title, description}`.** `id` is `custom_<slug>_<random>`; `title` required; `description` is optional but is injected into the prompt so the LLM knows what to write.
6. **Tier is fixed at `everyday`.** Per `DEPARTMENT_DEFAULT_TIERS["earnings_update"] = EVERYDAY` (Plan 4). No per-mode branching (only one mode).
7. **Scheduled runs write to `user_notifications` via Plan 6.** Plan 6's executor is what triggers notifications on successful reports and failures. Plan 15 does not re-implement notification plumbing — it only provides the `EUScanPlanner` that feeds the executor.
8. **On-demand reports bypass the scheduler entirely.** `POST /report` synchronously streams via SSE exactly like Plan 13's Secretary report path or Plan 14's ER report path; it persists the report on `report.complete` and returns the UUID embedded in `report.complete` for the client.
9. **The EU page is a dashboard, not a chat interface.** There is no `chat_sessions` row for EU; generated reports stand alone. Follow-up questions are routed by asking the user to open the report and use the Secretary (Plan 13) or per-department chat elsewhere.
10. **Framework files are read-only inside the core package.** User customization is layered at request time via `load_framework_customized()`.
11. **TDD everywhere.** Failing test → implementation → green run → commit per step.
12. **No placeholders.** Real code, real commands, real expected output in every step.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
prompts/
└── earnings_update.yaml               # single prompt; branches by report_length
departments/
└── earnings_update.py                 # EarningsUpdateDepartment — data requirements, tier, valid modes
```

### Server (`packages/server/src/openlia_server/`)

```
db/
├── models/
│   └── departments.py                 # MODIFY — add EuWatchlistEntry + EuUserConfig
└── migrations/versions/
    └── 2026-04-17-2200_eu_watchlist_and_config.py
services/
├── eu_watchlist.py                    # add/remove/list + refresh cache via data adapter
├── eu_config.py                       # get/update per-user EU config (defaults + merge)
├── eu_schedules.py                    # CRUD on eu_schedules, calling SchedulerService hot-reload
├── eu_scan_planner.py                 # implements EUScanPlanner (Plan 6 Protocol)
└── eu_runner.py                       # on-demand report orchestrator (ReportRequest → ReportRunner → report_store)
routes/departments/
└── earnings_update.py                 # /watchlist (GET/POST/DELETE), /config (GET/PUT),
                                       # /schedules (GET/POST/PUT/DELETE), /report (POST SSE),
                                       # /reports (GET recent list)
scheduler/
└── wiring.py                          # MODIFY — wire real EUScanPlanner in build_scheduler_service defaults
```

### Frontend (`frontend/src/`)

```
api/
└── earnings-update.ts                 # watchlist + config + schedules + report + recent reports
pages/
└── EarningsUpdatePage.tsx             # page shell with all sections
components/earnings-update/
├── WatchlistRow.tsx                   # horizontally scrollable cards
├── WatchlistCard.tsx                  # single ticker card (hover: × remove)
├── AddTickerPopover.tsx               # search → add
├── RecentReportsList.tsx              # top 5 reports
├── ReportRowItem.tsx                  # single row (reused by cabinet)
├── EUCabinetView.tsx                  # full-screen overlay: search + filter + grouped list
├── OnDemandReportModal.tsx            # ticker picker + generate
├── ScheduleManager.tsx                # list + add/remove/edit scan schedules
├── AddScheduleModal.tsx               # time + tz + days + label
├── ReportSettingsModal.tsx            # sections + length (same shape as ER modal)
└── CustomSectionRow.tsx               # inline custom section add (shared shape with ER; duplicated here to keep dept pages decoupled)
hooks/
├── useEuWatchlist.ts                  # SWR-style fetch + mutate (add/remove)
├── useEuConfig.ts                     # SWR-style; update triggers save
├── useEuSchedules.ts                  # SWR-style; add/remove/edit
└── useEuReports.ts                    # recent reports list + cabinet queries
lib/earnings-update/
└── section-catalog.ts                 # 8 default sections keyed by id; matches earnings_update.json
```

---

## Task Overview

1. Core — `EarningsUpdateDepartment` class.
2. Core — `earnings_update.yaml` prompt.
3. Server — `EuWatchlistEntry` + `EuUserConfig` SQLAlchemy models.
4. Server — Alembic migration for both tables.
5. Server — `eu_config` service (defaults + get/update).
6. Server — `eu_watchlist` service (CRUD + earnings-date refresh via data adapter).
7. Server — `eu_schedules` service (CRUD + hot-reload via SchedulerService).
8. Server — `eu_scan_planner` (implements Plan 6 `EUScanPlanner` Protocol).
9. Server — `eu_runner` on-demand orchestrator.
10. Server — Routes: watchlist (GET/POST/DELETE).
11. Server — Routes: config (GET/PUT).
12. Server — Routes: schedules (GET/POST/PUT/DELETE).
13. Server — Routes: on-demand report (POST SSE) + recent reports (GET).
14. Server — Wire real `EUScanPlanner` into `build_scheduler_service`.
15. Frontend — `api/earnings-update.ts` typed client.
16. Frontend — Section catalog + hooks (`useEuWatchlist`, `useEuConfig`, `useEuSchedules`, `useEuReports`).
17. Frontend — `WatchlistRow` + `WatchlistCard` + `AddTickerPopover`.
18. Frontend — `RecentReportsList` + `ReportRowItem` + `EUCabinetView`.
19. Frontend — `OnDemandReportModal`.
20. Frontend — `ScheduleManager` + `AddScheduleModal`.
21. Frontend — `ReportSettingsModal` + `CustomSectionRow`.
22. Frontend — `EarningsUpdatePage` composition.
23. Manual smoke test + flip README row to Draft.

---

### Task 1: Core — `EarningsUpdateDepartment` class

The department advertises: name, display name, prompt name, tier, data requirement lists, valid modes (one: `earnings_analysis`), and framework name.

**Files:**
- Create: `packages/core/src/openlia/departments/earnings_update.py`
- Modify: `packages/core/src/openlia/departments/__init__.py` (export `EarningsUpdateDepartment`)
- Test: `packages/core/tests/departments/test_earnings_update.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_earnings_update.py
import pytest

from openlia.departments.earnings_update import (
    EarningsUpdateDepartment,
    EarningsUpdateMode,
)


def test_eu_identifies_itself():
    d = EarningsUpdateDepartment()
    assert d.name == "earnings_update"
    assert d.display_name == "Earnings Updates"
    assert d.prompt_name == "earnings_update"


def test_eu_single_mode():
    assert set(EarningsUpdateDepartment().valid_modes) == {"earnings_analysis"}


def test_eu_tier_is_everyday():
    d = EarningsUpdateDepartment()
    assert d.tier_for("earnings_analysis") == "everyday"


def test_eu_tier_for_unknown_mode_raises():
    with pytest.raises(ValueError):
        EarningsUpdateDepartment().tier_for("bogus")


def test_eu_basic_data_requirements():
    reqs = EarningsUpdateDepartment().data_requirement_types
    for name in ("earnings_data", "financial_statements", "stock_quote"):
        assert name in reqs


def test_eu_optional_data_requirements():
    soft = EarningsUpdateDepartment().optional_requirement_types
    for name in (
        "earnings_transcripts",
        "company_news",
        "historical_prices",
        "analyst_ratings",
    ):
        assert name in soft


def test_eu_framework_name():
    assert EarningsUpdateDepartment().framework_name("earnings_analysis") == "earnings_update"


def test_eu_has_no_extra_tools():
    assert EarningsUpdateDepartment().extra_tools == ()


def test_eu_mode_literal_type():
    from typing import get_args
    assert set(get_args(EarningsUpdateMode)) == {"earnings_analysis"}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_earnings_update.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments.earnings_update'`.

- [ ] **Step 3: Write the department class**

```python
# packages/core/src/openlia/departments/earnings_update.py
"""Earnings Update — report-producing department with a single earnings_analysis mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier


EarningsUpdateMode = Literal["earnings_analysis"]


@dataclass(frozen=True)
class EarningsUpdateDepartment:
    name: str = "earnings_update"
    display_name: str = "Earnings Updates"
    prompt_name: str = "earnings_update"
    data_requirement_types: tuple[str, ...] = (
        "earnings_data",
        "financial_statements",
        "stock_quote",
    )
    optional_requirement_types: tuple[str, ...] = (
        "earnings_transcripts",
        "company_news",
        "historical_prices",
        "analyst_ratings",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()

    @property
    def valid_modes(self) -> tuple[EarningsUpdateMode, ...]:
        return ("earnings_analysis",)

    def tier_for(self, mode: str) -> Tier:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown EU mode: {mode}")
        return "everyday"

    def framework_name(self, mode: str) -> str:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown EU mode: {mode}")
        return "earnings_update"
```

- [ ] **Step 4: Export the class**

In `packages/core/src/openlia/departments/__init__.py`, add:

```python
from openlia.departments.earnings_update import (
    EarningsUpdateDepartment,
    EarningsUpdateMode,
)

__all__ = [
    *__all__,  # existing exports
    "EarningsUpdateDepartment",
    "EarningsUpdateMode",
]
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/departments/test_earnings_update.py -v`
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/departments/earnings_update.py \
        packages/core/src/openlia/departments/__init__.py \
        packages/core/tests/departments/test_earnings_update.py
git commit -m "feat(core): add EarningsUpdateDepartment class with earnings_analysis mode"
```

---

### Task 2: Core — `earnings_update.yaml` prompt

Single prompt that the `ReportRunner` pulls via `PromptLoader`. Branches by `report_length` only (single mode).

**Files:**
- Create: `packages/core/src/openlia/prompts/earnings_update.yaml`
- Test: `packages/core/tests/prompts/test_earnings_update_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/prompts/test_earnings_update_prompt.py
from pathlib import Path

import pytest

from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    root = Path(__file__).resolve().parents[2] / "src" / "openlia" / "prompts"
    return PromptLoader(root=root)


def test_system_prompt_mentions_department_role(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_analysis.system",
        {"report_length": "normal"},
    )
    assert "earnings" in text.lower()
    assert "analyst" in text.lower() or "analyst" in text.lower()


def test_user_prompt_embeds_ticker_and_user_input(loader: PromptLoader) -> None:
    text = loader.render(
        "earnings_update",
        "report.earnings_analysis.user",
        {
            "ticker": "AAPL",
            "user_input": "Analyze the latest Apple earnings release.",
            "report_length": "concise",
        },
    )
    assert "AAPL" in text
    assert "Apple" in text or "latest" in text


def test_length_knob_changes_prompt(loader: PromptLoader) -> None:
    concise = loader.render(
        "earnings_update",
        "report.earnings_analysis.user",
        {"ticker": "AAPL", "user_input": "x", "report_length": "concise"},
    )
    elaborative = loader.render(
        "earnings_update",
        "report.earnings_analysis.user",
        {"ticker": "AAPL", "user_input": "x", "report_length": "elaborative"},
    )
    assert concise \!= elaborative
    assert "concise" in concise.lower()
    assert "elaborative" in elaborative.lower() or "expansive" in elaborative.lower()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/prompts/test_earnings_update_prompt.py -v`
Expected: FAIL (`PromptNotFound` or similar).

- [ ] **Step 3: Write the prompt YAML**

```yaml
# packages/core/src/openlia/prompts/earnings_update.yaml
# Earnings Update department prompt.
# Single mode (earnings_analysis); branches on report_length.

includes:
  - base_report

report:
  earnings_analysis:
    system: |
      You are an equity-research analyst writing an Earnings Analysis Report for a
      single company's most recent earnings release. Your audience is a buy-side
      portfolio manager. You produce deterministic, factual, sourced writing. You
      avoid hedging, avoid marketing language, and anchor every claim to the
      numbers in the financial statements, the company's guidance, the earnings
      call transcript, or price action. You use the report framework exactly as
      provided — section order, section IDs, and block types are not negotiable.

    user: |
      {% include "base_report.report_context" %}

      Ticker: {{ ticker }}

      User instructions:
      {{ user_input }}

      Report length: **{{ report_length }}**
      {% if report_length == "concise" %}
      Keep the report concise. Favor dense tables over paragraphs; cap any text
      block at 3 sentences; omit optional explanatory passages.
      {% elif report_length == "elaborative" %}
      Write an elaborative report. Expand text blocks to 6–10 sentences where
      they add insight; include multiple qualitative angles; cite secondary
      context (industry, competitors) where relevant.
      {% else %}
      Write a normal-length report. Text blocks 4–6 sentences; tables are the
      primary vehicle for numeric comparison.
      {% endif %}

      Follow the framework exactly. Emit only the ReportSchema JSON; no
      commentary outside the schema.
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/prompts/test_earnings_update_prompt.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/earnings_update.yaml \
        packages/core/tests/prompts/test_earnings_update_prompt.py
git commit -m "feat(core): add earnings_update prompt with report_length branching"
```

---

### Task 3: Server — `EuWatchlistEntry` + `EuUserConfig` models

Two tables:

- `eu_watchlist`: one row per `(user_id, ticker)` pair. Carries cached `next_earnings_date` and `release_timing`.
- `eu_user_configs`: one row per user. Holds `report_length` + `enabled_section_ids` (JSON array) + `custom_sections` (JSON array of `{id, title, description}`).

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/departments.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (export the two new classes)
- Test: `packages/server/tests/db/test_eu_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_eu_models.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuUserConfig, EuWatchlistEntry
from openlia_server.db.models.users import User


def _mk_user(db: Session, email: str = "u@x") -> User:
    u = User(id="u_eu_1", email=email, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_watchlist_columns(create_tables) -> None:
    cols = {c["name"] for c in inspect(EuWatchlistEntry).columns}
    for expected in {
        "id", "user_id", "ticker", "company_name",
        "next_earnings_date", "release_timing", "created_at", "updated_at",
    }:
        assert expected in cols


def test_watchlist_unique_on_user_and_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(EuWatchlistEntry(
        id="w1", user_id="u_eu_1", ticker="AAPL", company_name="Apple Inc.",
        next_earnings_date=None, release_timing=None,
    ))
    db_session.commit()
    db_session.add(EuWatchlistEntry(
        id="w2", user_id="u_eu_1", ticker="AAPL", company_name="Apple Inc.",
        next_earnings_date=None, release_timing=None,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(EuWatchlistEntry(
        id="w3", user_id="u_eu_1", ticker="TSLA", company_name="Tesla",
    ))
    db_session.commit()
    db_session.query(User).filter_by(id="u_eu_1").delete()
    db_session.commit()
    assert db_session.query(EuWatchlistEntry).count() == 0


def test_release_timing_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(EuWatchlistEntry(
        id="w4", user_id="u_eu_1", ticker="NVDA", company_name="NVIDIA",
        release_timing="midday",
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_config_one_per_user(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(EuUserConfig(
        id="c1", user_id="u_eu_1",
        report_length="normal",
        enabled_section_ids=["quick_take", "key_financials"],
        custom_sections=[],
    ))
    db_session.commit()
    db_session.add(EuUserConfig(
        id="c2", user_id="u_eu_1",
        report_length="normal",
        enabled_section_ids=[],
        custom_sections=[],
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_config_length_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(EuUserConfig(
        id="c3", user_id="u_eu_1",
        report_length="tiny",  # invalid
        enabled_section_ids=[],
        custom_sections=[],
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_eu_models.py -v`
Expected: FAIL (`ImportError` on `EuWatchlistEntry` / `EuUserConfig`).

- [ ] **Step 3: Append the models**

In `packages/server/src/openlia_server/db/models/departments.py`, append:

```python
from datetime import date
from sqlalchemy import (
    CheckConstraint, Date, ForeignKey, Index, JSON, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base
from openlia_server.db.mixins import TimestampMixin


class EuWatchlistEntry(Base, TimestampMixin):
    """Per-user Earnings Update watchlist entry. One row per (user_id, ticker)."""

    __tablename__ = "eu_watchlist"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str] = mapped_column(String(256), nullable=False)
    next_earnings_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    release_timing: Mapped[str | None] = mapped_column(String(16), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "ticker", name="uq_eu_watchlist_user_ticker"),
        CheckConstraint(
            "release_timing IS NULL OR release_timing IN ('pre_market', 'post_market')",
            name="ck_eu_watchlist_release_timing",
        ),
        Index("ix_eu_watchlist_user", "user_id"),
    )


class EuUserConfig(Base, TimestampMixin):
    """Per-user Earnings Update config. One row per user."""

    __tablename__ = "eu_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    report_length: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    enabled_section_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    custom_sections: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_eu_user_configs_length",
        ),
    )
```

- [ ] **Step 4: Export from models package**

In `packages/server/src/openlia_server/db/models/__init__.py`, add `EuWatchlistEntry` and `EuUserConfig` to the imports + `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/server/tests/db/test_eu_models.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/departments.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/db/test_eu_models.py
git commit -m "feat(server): add eu_watchlist and eu_user_configs models"
```

---

### Task 4: Server — Alembic migration for `eu_watchlist` + `eu_user_configs`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026_04_17_2200_eu_watchlist_and_config.py`
- Test: `packages/server/tests/db/test_eu_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_eu_migration.py
from sqlalchemy import inspect, text


def test_migration_creates_eu_watchlist(alembic_upgraded_engine) -> None:
    insp = inspect(alembic_upgraded_engine)
    assert "eu_watchlist" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("eu_watchlist")}
    assert {"id", "user_id", "ticker", "company_name",
            "next_earnings_date", "release_timing"} <= cols


def test_migration_creates_eu_user_configs(alembic_upgraded_engine) -> None:
    insp = inspect(alembic_upgraded_engine)
    assert "eu_user_configs" in insp.get_table_names()


def test_migration_has_unique_on_user_ticker(alembic_upgraded_engine) -> None:
    insp = inspect(alembic_upgraded_engine)
    uqs = insp.get_unique_constraints("eu_watchlist")
    names = {uq["name"] for uq in uqs}
    assert "uq_eu_watchlist_user_ticker" in names


def test_migration_downgrade_drops_tables(alembic_engine_downgrade) -> None:
    engine = alembic_engine_downgrade("-1")  # step back from head
    insp = inspect(engine)
    assert "eu_watchlist" not in insp.get_table_names()
    assert "eu_user_configs" not in insp.get_table_names()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_eu_migration.py -v`
Expected: FAIL (no migration with `eu_watchlist` found).

- [ ] **Step 3: Write the migration**

Look up the revision ID of the current head migration:

```bash
uv run alembic -c packages/server/alembic.ini heads
```

Use the reported ID as `down_revision`. Then:

```python
# packages/server/src/openlia_server/db/migrations/versions/2026_04_17_2200_eu_watchlist_and_config.py
"""eu_watchlist + eu_user_configs

Revision ID: 20260417_2200_eu
Revises: <CURRENT_HEAD>
Create Date: 2026-04-17 22:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260417_2200_eu"
down_revision = "<CURRENT_HEAD>"  # replace with actual head
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "eu_watchlist",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("company_name", sa.String(256), nullable=False),
        sa.Column("next_earnings_date", sa.Date(), nullable=True),
        sa.Column("release_timing", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", "ticker", name="uq_eu_watchlist_user_ticker"),
        sa.CheckConstraint(
            "release_timing IS NULL OR release_timing IN ('pre_market', 'post_market')",
            name="ck_eu_watchlist_release_timing",
        ),
    )
    op.create_index("ix_eu_watchlist_user", "eu_watchlist", ["user_id"])

    op.create_table(
        "eu_user_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("report_length", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("enabled_section_ids", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        sa.Column("custom_sections", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_eu_user_configs_length",
        ),
    )


def downgrade() -> None:
    op.drop_table("eu_user_configs")
    op.drop_index("ix_eu_watchlist_user", table_name="eu_watchlist")
    op.drop_table("eu_watchlist")
```

- [ ] **Step 4: Run migration, verify upgrade + downgrade**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
uv run alembic -c packages/server/alembic.ini downgrade -1
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: all three commands succeed with no errors.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/db/test_eu_migration.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026_04_17_2200_eu_watchlist_and_config.py \
        packages/server/tests/db/test_eu_migration.py
git commit -m "feat(server): alembic migration for eu_watchlist + eu_user_configs"
```

---

### Task 5: Server — `eu_config` service

Per-user config with merged defaults. Mirrors Plan 14's `equity_research_config` service shape.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_config.py`
- Test: `packages/server/tests/services/test_eu_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_config.py
import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.users import User
from openlia_server.db.models.departments import EuUserConfig
from openlia_server.services import eu_config as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_get_returns_defaults_when_no_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert cfg.report_length == "normal"
    assert len(cfg.enabled_section_ids) == 8  # all default sections
    assert cfg.custom_sections == []
    # default row not yet materialized
    assert db_session.query(EuUserConfig).count() == 0


def test_get_creates_no_row_until_put(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.get_config(db_session, user_id="u_1")
    svc.get_config(db_session, user_id="u_1")
    assert db_session.query(EuUserConfig).count() == 0


def test_update_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="concise",
        enabled_section_ids=["quick_take", "key_financials"],
        custom_sections=[{"id": "custom_abc_123", "title": "My Section", "description": "d"}],
    )
    row = db_session.query(EuUserConfig).filter_by(user_id="u_1").one()
    assert row.report_length == "concise"
    assert row.enabled_section_ids == ["quick_take", "key_financials"]
    assert row.custom_sections[0]["title"] == "My Section"


def test_update_is_upsert(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(db_session, user_id="u_1",
                      report_length="concise",
                      enabled_section_ids=["quick_take"],
                      custom_sections=[])
    svc.update_config(db_session, user_id="u_1",
                      report_length="elaborative",
                      enabled_section_ids=["quick_take", "market_reaction"],
                      custom_sections=[])
    rows = db_session.query(EuUserConfig).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].report_length == "elaborative"


def test_update_rejects_invalid_length(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="report_length"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="tiny",
                          enabled_section_ids=[],
                          custom_sections=[])


def test_update_rejects_custom_section_without_title(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="title"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="normal",
                          enabled_section_ids=[],
                          custom_sections=[{"id": "custom_x_1", "title": "", "description": "d"}])


def test_defaults_match_framework_section_ids(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert set(cfg.enabled_section_ids) == {
        "quick_take", "market_reaction", "key_financials",
        "operational_highlights", "forward_guidance", "earnings_call",
        "risk_assessment", "thesis_check",
    }
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_config.py -v`
Expected: FAIL (`ModuleNotFoundError` on `eu_config`).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/eu_config.py
"""Per-user Earnings Update config: sections, length, custom sections."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuUserConfig


DEFAULT_SECTION_IDS: tuple[str, ...] = (
    "quick_take",
    "market_reaction",
    "key_financials",
    "operational_highlights",
    "forward_guidance",
    "earnings_call",
    "risk_assessment",
    "thesis_check",
)

_VALID_LENGTHS = frozenset({"concise", "normal", "elaborative"})


@dataclass(frozen=True)
class EuConfigDTO:
    report_length: str
    enabled_section_ids: list[str]
    custom_sections: list[dict]


def get_config(db: Session, *, user_id: str) -> EuConfigDTO:
    row = db.query(EuUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return EuConfigDTO(
            report_length="normal",
            enabled_section_ids=list(DEFAULT_SECTION_IDS),
            custom_sections=[],
        )
    return EuConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids or []),
        custom_sections=list(row.custom_sections or []),
    )


def update_config(
    db: Session,
    *,
    user_id: str,
    report_length: str,
    enabled_section_ids: list[str],
    custom_sections: list[dict],
) -> EuConfigDTO:
    if report_length not in _VALID_LENGTHS:
        raise ValueError(f"invalid report_length: {report_length\!r}")
    for cs in custom_sections:
        if not isinstance(cs, dict) or not cs.get("title"):
            raise ValueError("custom section requires a non-empty title")
        if not cs.get("id"):
            raise ValueError("custom section requires an id")

    row = db.query(EuUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        row = EuUserConfig(
            id=f"euc_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            report_length=report_length,
            enabled_section_ids=list(enabled_section_ids),
            custom_sections=list(custom_sections),
        )
        db.add(row)
    else:
        row.report_length = report_length
        row.enabled_section_ids = list(enabled_section_ids)
        row.custom_sections = list(custom_sections)
    db.commit()
    return EuConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids),
        custom_sections=list(row.custom_sections),
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_eu_config.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_config.py \
        packages/server/tests/services/test_eu_config.py
git commit -m "feat(server): add eu_config service with 8 default sections + length"
```

---

### Task 6: Server — `eu_watchlist` service

Watchlist CRUD plus earnings-date refresh via the Plan 3 `earnings_data` adapter.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_watchlist.py`
- Test: `packages/server/tests/services/test_eu_watchlist.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_watchlist.py
from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.users import User
from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.services import eu_watchlist as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


class FakeEarningsAdapter:
    def __init__(self, by_ticker: dict[str, dict]) -> None:
        self.by_ticker = by_ticker
        self.calls: list[str] = []

    def next_earnings(self, ticker: str) -> dict | None:
        self.calls.append(ticker)
        return self.by_ticker.get(ticker)


def test_add_calls_adapter_and_caches_date(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "date": date(2026, 4, 25),
            "release_timing": "post_market",
        },
    })
    entry = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    assert entry.ticker == "AAPL"
    assert entry.company_name == "Apple Inc."
    assert entry.next_earnings_date == date(2026, 4, 25)
    assert entry.release_timing == "post_market"
    assert adapter.calls == ["AAPL"]


def test_add_duplicate_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": None, "release_timing": None}})
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    with pytest.raises(svc.AlreadyOnWatchlistError):
        svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)


def test_add_uppercases_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": None, "release_timing": None}})
    entry = svc.add_entry(db_session, user_id="u_1", ticker="aapl", adapter=adapter)
    assert entry.ticker == "AAPL"


def test_add_unknown_ticker_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({})  # empty
    with pytest.raises(svc.TickerNotFoundError):
        svc.add_entry(db_session, user_id="u_1", ticker="ZZZZ", adapter=adapter)


def test_list_returns_entries_sorted_by_date(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": date(2026, 4, 25), "release_timing": "post_market"},
        "TSLA": {"ticker": "TSLA", "company_name": "Tesla", "date": date(2026, 4, 22), "release_timing": "pre_market"},
        "NVDA": {"ticker": "NVDA", "company_name": "NVIDIA", "date": None, "release_timing": None},
    })
    for t in ["AAPL", "TSLA", "NVDA"]:
        svc.add_entry(db_session, user_id="u_1", ticker=t, adapter=adapter)
    entries = svc.list_entries(db_session, user_id="u_1")
    # TSLA (earliest) first, AAPL next, NVDA (NULL) last
    assert [e.ticker for e in entries] == ["TSLA", "AAPL", "NVDA"]


def test_list_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    adapter = FakeEarningsAdapter({"AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": None, "release_timing": None}})
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    assert svc.list_entries(db_session, user_id="u_2") == []


def test_remove_deletes_entry(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": None, "release_timing": None}})
    e = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    svc.remove_entry(db_session, user_id="u_1", entry_id=e.id)
    assert db_session.query(EuWatchlistEntry).count() == 0


def test_remove_missing_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(svc.WatchlistEntryNotFoundError):
        svc.remove_entry(db_session, user_id="u_1", entry_id="nope")


def test_remove_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    adapter = FakeEarningsAdapter({"AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": None, "release_timing": None}})
    e = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    # u_2 must not be able to delete u_1's row
    with pytest.raises(svc.WatchlistEntryNotFoundError):
        svc.remove_entry(db_session, user_id="u_2", entry_id=e.id)


def test_refresh_updates_stale_dates(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {"ticker": "AAPL", "company_name": "Apple", "date": date(2026, 4, 25), "release_timing": "post_market"},
    })
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    # New quarter date published
    adapter.by_ticker["AAPL"]["date"] = date(2026, 7, 28)
    svc.refresh_for_user(db_session, user_id="u_1", adapter=adapter)
    entry = db_session.query(EuWatchlistEntry).filter_by(user_id="u_1").one()
    assert entry.next_earnings_date == date(2026, 7, 28)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_watchlist.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/eu_watchlist.py
"""Per-user Earnings Update watchlist: add/remove/list + cache refresh."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import case, nulls_last
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuWatchlistEntry


class AlreadyOnWatchlistError(ValueError):
    pass


class TickerNotFoundError(LookupError):
    pass


class WatchlistEntryNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class WatchlistEntryDTO:
    id: str
    user_id: str
    ticker: str
    company_name: str
    next_earnings_date: date | None
    release_timing: str | None


class EarningsAdapter(Protocol):
    def next_earnings(self, ticker: str) -> dict | None:
        """Return {'ticker': str, 'company_name': str, 'date': date|None, 'release_timing': 'pre_market'|'post_market'|None} or None."""
        ...


def _to_dto(row: EuWatchlistEntry) -> WatchlistEntryDTO:
    return WatchlistEntryDTO(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        company_name=row.company_name,
        next_earnings_date=row.next_earnings_date,
        release_timing=row.release_timing,
    )


def add_entry(
    db: Session,
    *,
    user_id: str,
    ticker: str,
    adapter: EarningsAdapter,
) -> WatchlistEntryDTO:
    ticker_up = ticker.strip().upper()
    if not ticker_up:
        raise ValueError("ticker required")

    existing = (
        db.query(EuWatchlistEntry)
        .filter_by(user_id=user_id, ticker=ticker_up)
        .one_or_none()
    )
    if existing is not None:
        raise AlreadyOnWatchlistError(ticker_up)

    lookup = adapter.next_earnings(ticker_up)
    if lookup is None:
        raise TickerNotFoundError(ticker_up)

    row = EuWatchlistEntry(
        id=f"eu_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        ticker=ticker_up,
        company_name=lookup.get("company_name") or ticker_up,
        next_earnings_date=lookup.get("date"),
        release_timing=lookup.get("release_timing"),
    )
    db.add(row)
    db.commit()
    return _to_dto(row)


def remove_entry(db: Session, *, user_id: str, entry_id: str) -> None:
    row = (
        db.query(EuWatchlistEntry)
        .filter_by(id=entry_id, user_id=user_id)
        .one_or_none()
    )
    if row is None:
        raise WatchlistEntryNotFoundError(entry_id)
    db.delete(row)
    db.commit()


def list_entries(db: Session, *, user_id: str) -> list[WatchlistEntryDTO]:
    rows = (
        db.query(EuWatchlistEntry)
        .filter_by(user_id=user_id)
        .order_by(nulls_last(EuWatchlistEntry.next_earnings_date.asc()), EuWatchlistEntry.ticker.asc())
        .all()
    )
    return [_to_dto(r) for r in rows]


def refresh_for_user(
    db: Session,
    *,
    user_id: str,
    adapter: EarningsAdapter,
) -> int:
    """Re-fetch next-earnings dates for all of a user's watchlist entries.

    Called by the nightly maintenance sweep (Plan 6) and by /refresh endpoints.
    Returns the number of rows updated.
    """
    rows = db.query(EuWatchlistEntry).filter_by(user_id=user_id).all()
    updated = 0
    for row in rows:
        lookup = adapter.next_earnings(row.ticker)
        if lookup is None:
            continue
        new_date = lookup.get("date")
        new_timing = lookup.get("release_timing")
        if new_date \!= row.next_earnings_date or new_timing \!= row.release_timing:
            row.next_earnings_date = new_date
            row.release_timing = new_timing
            updated += 1
    if updated:
        db.commit()
    return updated
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_eu_watchlist.py -v`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_watchlist.py \
        packages/server/tests/services/test_eu_watchlist.py
git commit -m "feat(server): add eu_watchlist service with adapter-driven add and refresh"
```

---

### Task 7: Server — `eu_schedules` service

CRUD on `eu_schedules` rows with hot-reload into the running `SchedulerService`.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_schedules.py`
- Test: `packages/server/tests/services/test_eu_schedules_service.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_schedules_service.py
from dataclasses import dataclass, field

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.users import User
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.registry import JobType
from openlia_server.services import eu_schedules as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


@dataclass
class FakeScheduler:
    added: list[dict] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def add_schedule(self, *, job_type, user_id, schedule_id, time, timezone, days_of_week):
        self.added.append({
            "job_type": job_type,
            "user_id": user_id,
            "schedule_id": schedule_id,
            "time": time,
            "timezone": timezone,
            "days_of_week": list(days_of_week),
        })

    def remove_schedule(self, *, job_type, user_id, schedule_id):
        self.removed.append(f"{job_type.value}:{user_id}:{schedule_id}")


def test_create_inserts_row_and_schedules_job(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(
        db_session,
        user_id="u_1",
        time="06:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market Scan",
        scheduler=sched,
    )
    assert dto.time == "06:00"
    assert dto.timezone == "America/New_York"
    assert sched.added[0]["job_type"] == JobType.EU_SCAN
    assert sched.added[0]["user_id"] == "u_1"


def test_create_validates_time_format(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="time"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="25:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


def test_create_validates_days_of_week(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="days_of_week"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="06:00",
            timezone="America/New_York",
            days_of_week=["smthweird"],
            label="bad",
            scheduler=sched,
        )


def test_create_validates_timezone(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="timezone"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="06:00",
            timezone="Not/AReal/Zone",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


def test_list_returns_user_schedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    svc.create_schedule(db_session, user_id="u_1", time="06:00", timezone="America/New_York",
                        days_of_week=["mon"], label="a", scheduler=sched)
    svc.create_schedule(db_session, user_id="u_1", time="17:00", timezone="America/New_York",
                        days_of_week=["mon"], label="b", scheduler=sched)
    svc.create_schedule(db_session, user_id="u_2", time="09:00", timezone="America/New_York",
                        days_of_week=["mon"], label="c", scheduler=sched)
    u1 = svc.list_schedules(db_session, user_id="u_1")
    assert {s.label for s in u1} == {"a", "b"}


def test_update_modifies_row_and_reschedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    svc.update_schedule(
        db_session, user_id="u_1", schedule_id=dto.id,
        time="07:00", timezone="America/New_York",
        days_of_week=["mon", "tue"], label="a2",
        is_enabled=True, scheduler=sched,
    )
    row = db_session.query(EuSchedule).filter_by(id=dto.id).one()
    assert row.time == "07:00"
    assert row.label == "a2"
    # remove + re-add through scheduler
    assert sched.removed[-1].endswith(dto.id)
    assert sched.added[-1]["schedule_id"] == dto.id
    assert sched.added[-1]["time"] == "07:00"


def test_update_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    with pytest.raises(svc.ScheduleNotFoundError):
        svc.update_schedule(db_session, user_id="u_2", schedule_id=dto.id,
                            time="07:00", timezone="America/New_York",
                            days_of_week=["mon"], label="x",
                            is_enabled=True, scheduler=sched)


def test_delete_removes_row_and_unschedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    svc.delete_schedule(db_session, user_id="u_1", schedule_id=dto.id, scheduler=sched)
    assert db_session.query(EuSchedule).count() == 0
    assert sched.removed[-1].endswith(dto.id)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_schedules_service.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/eu_schedules.py
"""CRUD on eu_schedules with hot-reload into the running SchedulerService."""

from __future__ import annotations

import re
import uuid
import zoneinfo
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.registry import JobType


_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class EuScheduleDTO:
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class SchedulerControl(Protocol):
    def add_schedule(self, *, job_type, user_id: str, schedule_id: str,
                     time: str, timezone: str, days_of_week: list[str]) -> None: ...
    def remove_schedule(self, *, job_type, user_id: str, schedule_id: str) -> None: ...


def _validate(time: str, timezone: str, days_of_week: list[str]) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid time: {time\!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as e:
        raise ValueError(f"invalid timezone: {timezone\!r}") from e
    if not days_of_week or any(d not in _VALID_DAYS for d in days_of_week):
        raise ValueError(f"invalid days_of_week: {days_of_week\!r}")


def _to_dto(row: EuSchedule) -> EuScheduleDTO:
    return EuScheduleDTO(
        id=row.id, user_id=row.user_id, time=row.time,
        timezone=row.timezone, days_of_week=list(row.days_of_week or []),
        label=row.label or "", is_enabled=bool(row.is_enabled),
    )


def create_schedule(
    db: Session, *, user_id: str, time: str, timezone: str,
    days_of_week: list[str], label: str, scheduler: SchedulerControl,
) -> EuScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = EuSchedule(
        id=f"eus_{uuid.uuid4().hex[:12]}",
        user_id=user_id, time=time, timezone=timezone,
        days_of_week=list(days_of_week), label=label, is_enabled=True,
    )
    db.add(row)
    db.commit()
    scheduler.add_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=row.id,
        time=time, timezone=timezone, days_of_week=list(days_of_week),
    )
    return _to_dto(row)


def list_schedules(db: Session, *, user_id: str) -> list[EuScheduleDTO]:
    rows = db.query(EuSchedule).filter_by(user_id=user_id).order_by(EuSchedule.time).all()
    return [_to_dto(r) for r in rows]


def update_schedule(
    db: Session, *, user_id: str, schedule_id: str,
    time: str, timezone: str, days_of_week: list[str],
    label: str, is_enabled: bool, scheduler: SchedulerControl,
) -> EuScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = (
        db.query(EuSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    )
    if row is None:
        raise ScheduleNotFoundError(schedule_id)
    row.time = time
    row.timezone = timezone
    row.days_of_week = list(days_of_week)
    row.label = label
    row.is_enabled = is_enabled
    db.commit()
    scheduler.remove_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
    )
    if is_enabled:
        scheduler.add_schedule(
            job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
            time=time, timezone=timezone, days_of_week=list(days_of_week),
        )
    return _to_dto(row)


def delete_schedule(
    db: Session, *, user_id: str, schedule_id: str, scheduler: SchedulerControl,
) -> None:
    row = (
        db.query(EuSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    )
    if row is None:
        raise ScheduleNotFoundError(schedule_id)
    db.delete(row)
    db.commit()
    scheduler.remove_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_eu_schedules_service.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_schedules.py \
        packages/server/tests/services/test_eu_schedules_service.py
git commit -m "feat(server): add eu_schedules service with hot-reload into SchedulerService"
```

---

### Task 8: Server — `eu_scan_planner` (implements Plan 6 `EUScanPlanner`)

The scheduler executor from Plan 6 calls `planner.plan(session, user_id, schedule_id, since)` and expects back a list of `EUScanTarget(ticker, request)` — one per ticker whose earnings have been released since `since`.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_scan_planner.py`
- Test: `packages/server/tests/services/test_eu_scan_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_scan_planner.py
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.users import User
from openlia_server.db.models.departments import EuWatchlistEntry, EuUserConfig
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def _add_watchlist(db: Session, user_id: str, ticker: str, company: str) -> None:
    from uuid import uuid4
    db.add(EuWatchlistEntry(
        id=f"eu_{uuid4().hex[:12]}", user_id=user_id, ticker=ticker,
        company_name=company, next_earnings_date=None, release_timing=None,
    ))
    db.commit()


@dataclass
class FakeEarningsAdapter:
    """Returns an 'earnings_released_since' lookup per ticker."""
    by_ticker: dict[str, datetime | None] = field(default_factory=dict)
    calls: list[tuple[str, datetime | None]] = field(default_factory=list)

    def latest_release(self, ticker: str, *, since: datetime | None) -> datetime | None:
        self.calls.append((ticker, since))
        return self.by_ticker.get(ticker)


def test_plan_returns_empty_if_watchlist_empty(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    planner = EuScanPlannerImpl(adapter=FakeEarningsAdapter())
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=None)
    assert targets == []


def test_plan_returns_targets_only_for_new_earnings(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    _add_watchlist(db_session, "u_1", "TSLA", "Tesla")
    _add_watchlist(db_session, "u_1", "NVDA", "NVIDIA")

    now = datetime.now(tz=UTC)
    since = now - timedelta(hours=12)
    adapter = FakeEarningsAdapter(by_ticker={
        "AAPL": now - timedelta(hours=1),  # after since -> include
        "TSLA": now - timedelta(days=7),   # before since -> skip
        "NVDA": None,                      # no recent release -> skip
    })
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=since)
    assert [t.ticker for t in targets] == ["AAPL"]


def test_plan_passes_since_to_adapter(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    since = datetime(2026, 4, 1, tzinfo=UTC)
    adapter = FakeEarningsAdapter()
    planner = EuScanPlannerImpl(adapter=adapter)
    planner.plan(session=db_session, user_id="u_1", schedule_id="s_1", since=since)
    assert adapter.calls == [("AAPL", since)]


def test_plan_builds_report_request_with_ticker_and_config(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _add_watchlist(db_session, "u_1", "AAPL", "Apple Inc.")
    now = datetime.now(tz=UTC)

    # User config: concise length, only 2 sections enabled
    db_session.add(EuUserConfig(
        id="euc_1", user_id="u_1", report_length="concise",
        enabled_section_ids=["quick_take", "key_financials"],
        custom_sections=[{"id": "custom_extra_1", "title": "Model update", "description": "Update base case"}],
    ))
    db_session.commit()

    adapter = FakeEarningsAdapter(by_ticker={"AAPL": now})
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=now - timedelta(hours=6))
    assert len(targets) == 1
    req: ReportRequest = targets[0].request
    assert req.mode == "earnings_analysis"
    assert "AAPL" in req.user_input
    assert req.enabled_sections == ["quick_take", "key_financials"]
    assert req.custom_sections == [
        {"id": "custom_extra_1", "title": "Model update", "description": "Update base case"}
    ]
    assert req.report_length == "concise"


def test_plan_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    _add_watchlist(db_session, "u_1", "AAPL", "Apple")
    _add_watchlist(db_session, "u_2", "TSLA", "Tesla")

    now = datetime.now(tz=UTC)
    adapter = FakeEarningsAdapter(by_ticker={"AAPL": now, "TSLA": now})
    planner = EuScanPlannerImpl(adapter=adapter)
    targets = planner.plan(session=db_session, user_id="u_1",
                           schedule_id="s_1", since=now - timedelta(hours=6))
    assert [t.ticker for t in targets] == ["AAPL"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_scan_planner.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the planner**

```python
# packages/server/src/openlia_server/services/eu_scan_planner.py
"""EUScanPlanner — reads watchlist + user config, asks the earnings adapter
for companies with new releases since `since`, and returns EUScanTargets.

Fulfills the Plan 6 `EUScanPlanner` Protocol. Wired at app startup into
`build_scheduler_service(eu_planner=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.scheduler.payloads import EUScanTarget
from openlia_server.services import eu_config as eu_config_svc


class EarningsRecentReleaseAdapter(Protocol):
    def latest_release(self, ticker: str, *, since: datetime | None) -> datetime | None:
        """Return the datetime of the latest earnings release for ticker if one
        happened after `since`; otherwise None."""
        ...


@dataclass
class EuScanPlannerImpl:
    adapter: EarningsRecentReleaseAdapter

    def plan(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        entries = (
            session.query(EuWatchlistEntry)
            .filter_by(user_id=user_id)
            .order_by(EuWatchlistEntry.ticker.asc())
            .all()
        )
        if not entries:
            return []

        cfg = eu_config_svc.get_config(session, user_id=user_id)

        targets: list[EUScanTarget] = []
        for row in entries:
            released_at = self.adapter.latest_release(row.ticker, since=since)
            if released_at is None:
                continue
            request = ReportRequest(
                mode="earnings_analysis",
                user_input=f"Analyze {row.ticker} ({row.company_name}) "
                           f"earnings released at {released_at.isoformat()}.",
                enabled_sections=list(cfg.enabled_section_ids),
                custom_sections=list(cfg.custom_sections),
                report_length=cfg.report_length,
            )
            targets.append(EUScanTarget(ticker=row.ticker, request=request))
        return targets
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_eu_scan_planner.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_scan_planner.py \
        packages/server/tests/services/test_eu_scan_planner.py
git commit -m "feat(server): add EuScanPlannerImpl fulfilling Plan 6 EUScanPlanner Protocol"
```

---

### Task 9: Server — `eu_runner` on-demand orchestrator

Thin wrapper that takes `{user_id, ticker}`, pulls the user's EU config, builds a `ReportRequest`, calls `ReportRunner.run()`, and forwards the SSE stream to the caller. Persists the report to `report_store` on `report.complete`.

**Files:**
- Create: `packages/server/src/openlia_server/services/eu_runner.py`
- Test: `packages/server/tests/services/test_eu_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_eu_runner.py
from dataclasses import dataclass, field
from typing import AsyncIterator

import pytest
from sqlalchemy.orm import Session

from openlia.llm.runtime.events import ReportComplete, ReportDelta, ReportStart, SseEvent
from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.users import User
from openlia_server.services.eu_runner import run_on_demand


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


@dataclass
class ScriptedRunner:
    events: list[SseEvent]
    received: list[tuple[str, str, ReportRequest]] = field(default_factory=list)

    async def run(self, *, department_id: str, user_id: str, request: ReportRequest) -> AsyncIterator[SseEvent]:
        self.received.append((department_id, user_id, request))
        for e in self.events:
            yield e


@dataclass
class FakeReportStore:
    saved: list[dict] = field(default_factory=list)

    def save_from_event(self, *, user_id: str, department: str, report_type: str, event: ReportComplete) -> str:
        rid = event.report_id
        self.saved.append({"user_id": user_id, "report_id": rid,
                           "department": department, "report_type": report_type})
        return rid


@pytest.mark.asyncio
async def test_on_demand_forwards_events_and_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    complete = ReportComplete(report_id="r_1", title="AAPL Q1 FY2026")
    runner = ScriptedRunner(events=[
        ReportStart(report_id="r_1", department="earnings_update",
                    mode="earnings_analysis", section_titles=["Quick Take"]),
        ReportDelta(report_id="r_1", section_id="quick_take", delta="Revenue beat..."),
        complete,
    ])
    store = FakeReportStore()

    collected: list[SseEvent] = []
    async for ev in run_on_demand(
        session=db_session, user_id="u_1", ticker="AAPL",
        report_runner=runner, report_store=store,
    ):
        collected.append(ev)

    assert [type(e).__name__ for e in collected] == ["ReportStart", "ReportDelta", "ReportComplete"]
    assert runner.received[0][0] == "earnings_update"
    assert "AAPL" in runner.received[0][2].user_input
    assert runner.received[0][2].mode == "earnings_analysis"
    assert store.saved == [
        {"user_id": "u_1", "report_id": "r_1",
         "department": "earnings_update", "report_type": "earnings_update"},
    ]


@pytest.mark.asyncio
async def test_on_demand_uppercases_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    complete = ReportComplete(report_id="r_2", title="x")
    runner = ScriptedRunner(events=[complete])
    store = FakeReportStore()

    async for _ in run_on_demand(
        session=db_session, user_id="u_1", ticker="tsla",
        report_runner=runner, report_store=store,
    ):
        pass
    assert "TSLA" in runner.received[0][2].user_input


@pytest.mark.asyncio
async def test_on_demand_pulls_user_config(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.departments import EuUserConfig
    _mk_user(db_session)
    db_session.add(EuUserConfig(
        id="euc_1", user_id="u_1", report_length="elaborative",
        enabled_section_ids=["quick_take"], custom_sections=[],
    ))
    db_session.commit()

    complete = ReportComplete(report_id="r_3", title="x")
    runner = ScriptedRunner(events=[complete])
    store = FakeReportStore()
    async for _ in run_on_demand(
        session=db_session, user_id="u_1", ticker="AAPL",
        report_runner=runner, report_store=store,
    ):
        pass
    req = runner.received[0][2]
    assert req.report_length == "elaborative"
    assert req.enabled_sections == ["quick_take"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_eu_runner.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the orchestrator**

```python
# packages/server/src/openlia_server/services/eu_runner.py
"""On-demand Earnings Update report orchestrator.

Wraps `ReportRunner.run()` with EU-specific defaults:
- Pulls the user's EU config (sections + length + custom sections).
- Builds a `ReportRequest` with mode="earnings_analysis".
- Forwards every SSE event to the caller.
- Persists the report on `ReportComplete`.
"""

from __future__ import annotations

from typing import AsyncIterator, Protocol

from sqlalchemy.orm import Session

from openlia.llm.runtime.events import ReportComplete, SseEvent
from openlia.llm.runtime.messages import ReportRequest

from openlia_server.services import eu_config as eu_config_svc


class ReportRunnerLike(Protocol):
    async def run(self, *, department_id: str, user_id: str, request: ReportRequest) -> AsyncIterator[SseEvent]: ...


class ReportStoreLike(Protocol):
    def save_from_event(self, *, user_id: str, department: str, report_type: str, event: ReportComplete) -> str: ...


async def run_on_demand(
    *,
    session: Session,
    user_id: str,
    ticker: str,
    report_runner: ReportRunnerLike,
    report_store: ReportStoreLike,
) -> AsyncIterator[SseEvent]:
    t = ticker.strip().upper()
    if not t:
        raise ValueError("ticker required")

    cfg = eu_config_svc.get_config(session, user_id=user_id)
    request = ReportRequest(
        mode="earnings_analysis",
        user_input=f"Generate an earnings analysis report for {t} on its most recent earnings release.",
        enabled_sections=list(cfg.enabled_section_ids),
        custom_sections=list(cfg.custom_sections),
        report_length=cfg.report_length,
    )

    async for event in report_runner.run(
        department_id="earnings_update", user_id=user_id, request=request,
    ):
        yield event
        if isinstance(event, ReportComplete):
            report_store.save_from_event(
                user_id=user_id, department="earnings_update",
                report_type="earnings_update", event=event,
            )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_eu_runner.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/eu_runner.py \
        packages/server/tests/services/test_eu_runner.py
git commit -m "feat(server): add eu_runner for on-demand EU report generation"
```

---

### Task 10: Server — Watchlist routes

`GET /api/departments/earnings-update/watchlist` — list the current user's watchlist entries.
`POST /api/departments/earnings-update/watchlist` — body `{ticker: string}`, returns the created entry. 409 if duplicate, 404 if ticker not found.
`DELETE /api/departments/earnings-update/watchlist/{entry_id}` — removes the entry.

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/earnings_update.py` (watchlist + empty stubs for other sections; later tasks fill them in).
- Modify: `packages/server/src/openlia_server/app.py` to include the EU router at `/api/departments/earnings-update`.
- Test: `packages/server/tests/routes/departments/test_earnings_update_watchlist.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_earnings_update_watchlist.py
from datetime import date

import pytest
from fastapi.testclient import TestClient

from openlia_server.services import eu_watchlist as svc


class _FakeAdapter:
    def __init__(self, known: dict[str, dict]) -> None:
        self.known = known

    def next_earnings(self, ticker: str):
        return self.known.get(ticker)


@pytest.fixture
def eu_client(client_factory, monkeypatch):
    """client_factory is the canonical test helper from conftest.py:
    creates an authenticated TestClient for a user (cookie session)."""
    known = {
        "AAPL": {"ticker": "AAPL", "company_name": "Apple Inc.",
                 "date": date(2026, 4, 25), "release_timing": "post_market"},
        "TSLA": {"ticker": "TSLA", "company_name": "Tesla Inc.",
                 "date": date(2026, 4, 22), "release_timing": "pre_market"},
    }
    adapter = _FakeAdapter(known)

    # Replace the dependency-injected earnings adapter with the fake.
    from openlia_server.routes.departments import earnings_update as route_mod
    monkeypatch.setattr(route_mod, "_earnings_adapter_dep", lambda: adapter)

    return client_factory(user_id="u_1")


def test_get_watchlist_empty(eu_client: TestClient) -> None:
    resp = eu_client.get("/api/departments/earnings-update/watchlist")
    assert resp.status_code == 200
    assert resp.json() == {"entries": []}


def test_post_adds_entry(eu_client: TestClient) -> None:
    resp = eu_client.post(
        "/api/departments/earnings-update/watchlist", json={"ticker": "AAPL"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["ticker"] == "AAPL"
    assert body["company_name"] == "Apple Inc."
    assert body["next_earnings_date"] == "2026-04-25"
    assert body["release_timing"] == "post_market"


def test_post_rejects_empty_ticker(eu_client: TestClient) -> None:
    resp = eu_client.post(
        "/api/departments/earnings-update/watchlist", json={"ticker": ""},
    )
    assert resp.status_code == 422


def test_post_409_on_duplicate(eu_client: TestClient) -> None:
    eu_client.post("/api/departments/earnings-update/watchlist", json={"ticker": "AAPL"})
    resp = eu_client.post(
        "/api/departments/earnings-update/watchlist", json={"ticker": "AAPL"},
    )
    assert resp.status_code == 409


def test_post_404_on_unknown(eu_client: TestClient) -> None:
    resp = eu_client.post(
        "/api/departments/earnings-update/watchlist", json={"ticker": "ZZZZ"},
    )
    assert resp.status_code == 404


def test_get_lists_after_add(eu_client: TestClient) -> None:
    eu_client.post("/api/departments/earnings-update/watchlist", json={"ticker": "AAPL"})
    eu_client.post("/api/departments/earnings-update/watchlist", json={"ticker": "TSLA"})
    resp = eu_client.get("/api/departments/earnings-update/watchlist")
    entries = resp.json()["entries"]
    assert [e["ticker"] for e in entries] == ["TSLA", "AAPL"]  # ordered by date


def test_delete_removes_entry(eu_client: TestClient) -> None:
    created = eu_client.post(
        "/api/departments/earnings-update/watchlist", json={"ticker": "AAPL"},
    ).json()
    resp = eu_client.delete(
        f"/api/departments/earnings-update/watchlist/{created['id']}",
    )
    assert resp.status_code == 204
    assert eu_client.get("/api/departments/earnings-update/watchlist").json() == {"entries": []}


def test_delete_404_on_missing(eu_client: TestClient) -> None:
    resp = eu_client.delete("/api/departments/earnings-update/watchlist/nope")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_watchlist.py -v`
Expected: FAIL (`ModuleNotFoundError` on the route module).

- [ ] **Step 3: Create the router file with watchlist endpoints**

```python
# packages/server/src/openlia_server/routes/departments/earnings_update.py
"""Earnings Update HTTP routes: watchlist, config, schedules, report, reports."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia_server.db.session import get_db
from openlia_server.middleware.auth import require_user
from openlia_server.services import eu_watchlist as watchlist_svc


router = APIRouter(prefix="/api/departments/earnings-update", tags=["earnings-update"])


# ---------- Dependency injection hooks ----------

def _earnings_adapter_dep(request: Request):
    """Resolves the data-adapter for earnings_data. Wired at app startup to
    `app.state.earnings_adapter`. Tests monkeypatch this symbol directly."""
    adapter = getattr(request.app.state, "earnings_adapter", None)
    if adapter is None:
        raise HTTPException(500, "earnings adapter not configured")
    return adapter


# ---------- Watchlist ----------

class _WatchlistEntryOut(BaseModel):
    id: str
    ticker: str
    company_name: str
    next_earnings_date: date | None
    release_timing: str | None


class _WatchlistListOut(BaseModel):
    entries: list[_WatchlistEntryOut]


class _AddEntryIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


@router.get("/watchlist", response_model=_WatchlistListOut)
def get_watchlist(
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> _WatchlistListOut:
    entries = watchlist_svc.list_entries(db, user_id=user.id)
    return _WatchlistListOut(entries=[_WatchlistEntryOut(
        id=e.id, ticker=e.ticker, company_name=e.company_name,
        next_earnings_date=e.next_earnings_date, release_timing=e.release_timing,
    ) for e in entries])


@router.post("/watchlist", status_code=201, response_model=_WatchlistEntryOut)
def add_to_watchlist(
    payload: _AddEntryIn,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    adapter=Depends(_earnings_adapter_dep),
) -> _WatchlistEntryOut:
    try:
        entry = watchlist_svc.add_entry(
            db, user_id=user.id, ticker=payload.ticker, adapter=adapter,
        )
    except watchlist_svc.AlreadyOnWatchlistError:
        raise HTTPException(status.HTTP_409_CONFLICT, "already on watchlist")
    except watchlist_svc.TickerNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ticker not found")
    return _WatchlistEntryOut(
        id=entry.id, ticker=entry.ticker, company_name=entry.company_name,
        next_earnings_date=entry.next_earnings_date, release_timing=entry.release_timing,
    )


@router.delete("/watchlist/{entry_id}", status_code=204)
def remove_from_watchlist(
    entry_id: str,
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        watchlist_svc.remove_entry(db, user_id=user.id, entry_id=entry_id)
    except watchlist_svc.WatchlistEntryNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "not found")
```

- [ ] **Step 4: Register the router**

In `packages/server/src/openlia_server/app.py`, where routers are included:

```python
from openlia_server.routes.departments import earnings_update as eu_routes

app.include_router(eu_routes.router)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_watchlist.py -v`
Expected: PASS (8 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/routes/departments/test_earnings_update_watchlist.py
git commit -m "feat(server): EU watchlist routes (GET/POST/DELETE)"
```

---

### Task 11: Server — Config routes

`GET /api/departments/earnings-update/config` — returns `{report_length, enabled_section_ids, custom_sections}`.
`PUT /api/departments/earnings-update/config` — upserts the config.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update.py` (append)
- Test: `packages/server/tests/routes/departments/test_earnings_update_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_earnings_update_config.py
from fastapi.testclient import TestClient


def test_get_config_returns_defaults(client_factory) -> None:
    c = client_factory(user_id="u_1")
    resp = c.get("/api/departments/earnings-update/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_length"] == "normal"
    assert len(body["enabled_section_ids"]) == 8
    assert body["custom_sections"] == []


def test_put_config_updates(client_factory) -> None:
    c = client_factory(user_id="u_1")
    resp = c.put(
        "/api/departments/earnings-update/config",
        json={
            "report_length": "elaborative",
            "enabled_section_ids": ["quick_take", "key_financials"],
            "custom_sections": [
                {"id": "custom_abc_123", "title": "Model update", "description": "x"},
            ],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["report_length"] == "elaborative"
    # verify persistence
    roundtrip = c.get("/api/departments/earnings-update/config").json()
    assert roundtrip == body


def test_put_config_rejects_invalid_length(client_factory) -> None:
    c = client_factory(user_id="u_1")
    resp = c.put(
        "/api/departments/earnings-update/config",
        json={
            "report_length": "tiny",
            "enabled_section_ids": [],
            "custom_sections": [],
        },
    )
    assert resp.status_code == 422


def test_put_config_rejects_custom_without_title(client_factory) -> None:
    c = client_factory(user_id="u_1")
    resp = c.put(
        "/api/departments/earnings-update/config",
        json={
            "report_length": "normal",
            "enabled_section_ids": [],
            "custom_sections": [{"id": "custom_x", "title": "", "description": "y"}],
        },
    )
    assert resp.status_code == 422


def test_config_is_user_scoped(client_factory) -> None:
    c1 = client_factory(user_id="u_1")
    c2 = client_factory(user_id="u_2")
    c1.put("/api/departments/earnings-update/config", json={
        "report_length": "concise", "enabled_section_ids": ["quick_take"],
        "custom_sections": [],
    })
    assert c2.get("/api/departments/earnings-update/config").json()["report_length"] == "normal"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_config.py -v`
Expected: FAIL (404 on GET, route not registered).

- [ ] **Step 3: Append config routes**

In `packages/server/src/openlia_server/routes/departments/earnings_update.py`:

```python
from typing import Literal

from openlia_server.services import eu_config as config_svc


class _CustomSectionIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)


class _ConfigIn(BaseModel):
    report_length: Literal["concise", "normal", "elaborative"]
    enabled_section_ids: list[str]
    custom_sections: list[_CustomSectionIn]


class _ConfigOut(BaseModel):
    report_length: str
    enabled_section_ids: list[str]
    custom_sections: list[dict]


@router.get("/config", response_model=_ConfigOut)
def get_config(
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> _ConfigOut:
    cfg = config_svc.get_config(db, user_id=user.id)
    return _ConfigOut(
        report_length=cfg.report_length,
        enabled_section_ids=list(cfg.enabled_section_ids),
        custom_sections=list(cfg.custom_sections),
    )


@router.put("/config", response_model=_ConfigOut)
def put_config(
    payload: _ConfigIn,
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> _ConfigOut:
    try:
        cfg = config_svc.update_config(
            db, user_id=user.id,
            report_length=payload.report_length,
            enabled_section_ids=list(payload.enabled_section_ids),
            custom_sections=[cs.model_dump() for cs in payload.custom_sections],
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))
    return _ConfigOut(
        report_length=cfg.report_length,
        enabled_section_ids=list(cfg.enabled_section_ids),
        custom_sections=list(cfg.custom_sections),
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update.py \
        packages/server/tests/routes/departments/test_earnings_update_config.py
git commit -m "feat(server): EU config routes (GET/PUT) with section + length validation"
```

---

### Task 12: Server — Schedules routes

`GET /schedules` — list the current user's EU scan schedules.
`POST /schedules` — create a new schedule (validates time/tz/days, hot-reloads scheduler).
`PUT /schedules/{schedule_id}` — update.
`DELETE /schedules/{schedule_id}` — remove.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update.py`
- Test: `packages/server/tests/routes/departments/test_earnings_update_schedules.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_earnings_update_schedules.py
import pytest


@pytest.fixture
def eu_sched_client(client_factory, fake_scheduler):
    return client_factory(user_id="u_1", scheduler=fake_scheduler)


def test_post_schedule_creates(eu_sched_client, fake_scheduler) -> None:
    resp = eu_sched_client.post(
        "/api/departments/earnings-update/schedules",
        json={
            "time": "06:00",
            "timezone": "America/New_York",
            "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
            "label": "Pre-Market Scan",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["time"] == "06:00"
    assert fake_scheduler.added[-1]["user_id"] == "u_1"


def test_post_invalid_time(eu_sched_client) -> None:
    resp = eu_sched_client.post(
        "/api/departments/earnings-update/schedules",
        json={"time": "25:00", "timezone": "America/New_York",
              "days_of_week": ["mon"], "label": "bad"},
    )
    assert resp.status_code == 422


def test_get_lists_schedules(eu_sched_client) -> None:
    eu_sched_client.post("/api/departments/earnings-update/schedules", json={
        "time": "06:00", "timezone": "America/New_York",
        "days_of_week": ["mon"], "label": "a",
    })
    eu_sched_client.post("/api/departments/earnings-update/schedules", json={
        "time": "17:00", "timezone": "America/New_York",
        "days_of_week": ["mon"], "label": "b",
    })
    resp = eu_sched_client.get("/api/departments/earnings-update/schedules")
    assert resp.status_code == 200
    assert [s["label"] for s in resp.json()["schedules"]] == ["a", "b"]


def test_put_updates_schedule(eu_sched_client) -> None:
    created = eu_sched_client.post(
        "/api/departments/earnings-update/schedules",
        json={"time": "06:00", "timezone": "America/New_York",
              "days_of_week": ["mon"], "label": "a"},
    ).json()
    resp = eu_sched_client.put(
        f"/api/departments/earnings-update/schedules/{created['id']}",
        json={"time": "07:00", "timezone": "America/New_York",
              "days_of_week": ["mon", "tue"], "label": "a2",
              "is_enabled": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["time"] == "07:00"
    assert body["label"] == "a2"


def test_delete_removes(eu_sched_client) -> None:
    created = eu_sched_client.post(
        "/api/departments/earnings-update/schedules",
        json={"time": "06:00", "timezone": "America/New_York",
              "days_of_week": ["mon"], "label": "a"},
    ).json()
    resp = eu_sched_client.delete(
        f"/api/departments/earnings-update/schedules/{created['id']}"
    )
    assert resp.status_code == 204
    assert eu_sched_client.get("/api/departments/earnings-update/schedules").json() == {"schedules": []}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_schedules.py -v`
Expected: FAIL (404 on endpoints).

- [ ] **Step 3: Append schedule routes**

In the same router module:

```python
from openlia_server.services import eu_schedules as schedules_svc


def _scheduler_dep(request: Request):
    sched = getattr(request.app.state, "scheduler", None)
    if sched is None:
        raise HTTPException(500, "scheduler not initialized")
    return sched


class _ScheduleIn(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
    days_of_week: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(min_length=1)
    label: str = Field(default="", max_length=128)


class _ScheduleUpdateIn(_ScheduleIn):
    is_enabled: bool = True


class _ScheduleOut(BaseModel):
    id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class _ScheduleListOut(BaseModel):
    schedules: list[_ScheduleOut]


@router.get("/schedules", response_model=_ScheduleListOut)
def list_schedules(
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> _ScheduleListOut:
    items = schedules_svc.list_schedules(db, user_id=user.id)
    return _ScheduleListOut(schedules=[_ScheduleOut(**i.__dict__) for i in items])


@router.post("/schedules", status_code=201, response_model=_ScheduleOut)
def create_schedule(
    payload: _ScheduleIn,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    scheduler=Depends(_scheduler_dep),
) -> _ScheduleOut:
    try:
        dto = schedules_svc.create_schedule(
            db, user_id=user.id, time=payload.time, timezone=payload.timezone,
            days_of_week=list(payload.days_of_week), label=payload.label,
            scheduler=scheduler,
        )
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _ScheduleOut(**dto.__dict__)


@router.put("/schedules/{schedule_id}", response_model=_ScheduleOut)
def update_schedule(
    schedule_id: str,
    payload: _ScheduleUpdateIn,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    scheduler=Depends(_scheduler_dep),
) -> _ScheduleOut:
    try:
        dto = schedules_svc.update_schedule(
            db, user_id=user.id, schedule_id=schedule_id,
            time=payload.time, timezone=payload.timezone,
            days_of_week=list(payload.days_of_week),
            label=payload.label, is_enabled=payload.is_enabled,
            scheduler=scheduler,
        )
    except schedules_svc.ScheduleNotFoundError:
        raise HTTPException(404, "schedule not found")
    except ValueError as e:
        raise HTTPException(422, str(e))
    return _ScheduleOut(**dto.__dict__)


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: str,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    scheduler=Depends(_scheduler_dep),
) -> None:
    try:
        schedules_svc.delete_schedule(
            db, user_id=user.id, schedule_id=schedule_id, scheduler=scheduler,
        )
    except schedules_svc.ScheduleNotFoundError:
        raise HTTPException(404, "schedule not found")
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_schedules.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update.py \
        packages/server/tests/routes/departments/test_earnings_update_schedules.py
git commit -m "feat(server): EU schedule routes (GET/POST/PUT/DELETE) with hot-reload"
```

---

### Task 13: Server — Report SSE route + recent reports list

`POST /api/departments/earnings-update/report` (SSE) — body `{ticker: string}`, streams `report.*` events, persists report on complete.
`GET /api/departments/earnings-update/reports?limit=N` — returns recent reports for the user.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update.py`
- Test: `packages/server/tests/routes/departments/test_earnings_update_report.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_earnings_update_report.py
from typing import AsyncIterator

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportDelta, ReportStart, SseEvent
from openlia.llm.runtime.messages import ReportRequest


class _ScriptedRunner:
    def __init__(self, events: list[SseEvent]) -> None:
        self.events = events
        self.seen: list[ReportRequest] = []

    async def run(self, *, department_id, user_id, request) -> AsyncIterator[SseEvent]:
        self.seen.append(request)
        for e in self.events:
            yield e


def test_post_report_streams_sse_events(client_factory) -> None:
    events = [
        ReportStart(report_id="r_1", department="earnings_update",
                    mode="earnings_analysis", section_titles=["Quick Take"]),
        ReportDelta(report_id="r_1", section_id="quick_take", delta="Beat..."),
        ReportComplete(report_id="r_1", title="AAPL Q1 FY2026"),
    ]
    runner = _ScriptedRunner(events=events)
    c = client_factory(user_id="u_1", report_runner=runner)

    with c.stream("POST",
                  "/api/departments/earnings-update/report",
                  json={"ticker": "AAPL"}) as resp:
        assert resp.status_code == 200
        body = "".join(chunk for chunk in resp.iter_text())
    assert "event: report.start" in body
    assert "event: report.delta" in body
    assert "event: report.complete" in body
    assert '"report_id": "r_1"' in body


def test_post_report_rejects_empty_ticker(client_factory) -> None:
    runner = _ScriptedRunner(events=[])
    c = client_factory(user_id="u_1", report_runner=runner)
    resp = c.post("/api/departments/earnings-update/report", json={"ticker": ""})
    assert resp.status_code == 422


def test_recent_reports_returns_user_reports(client_factory, seed_reports) -> None:
    # Seed 3 earnings_update reports for u_1 + 1 for u_2.
    seed_reports(
        user_id="u_1", count=3,
        department="earnings_update", report_type="earnings_update",
    )
    seed_reports(
        user_id="u_2", count=1,
        department="earnings_update", report_type="earnings_update",
    )
    c = client_factory(user_id="u_1")
    resp = c.get("/api/departments/earnings-update/reports?limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["reports"]) == 3
    for r in body["reports"]:
        assert r["report_type"] == "earnings_update"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_report.py -v`
Expected: FAIL (404 on routes).

- [ ] **Step 3: Append report + reports list routes**

In the router module:

```python
from fastapi.responses import StreamingResponse

from openlia.llm.runtime.events import serialize_sse
from openlia_server.services import eu_runner


def _report_runner_dep(request: Request):
    runner = getattr(request.app.state, "report_runner", None)
    if runner is None:
        raise HTTPException(500, "report runner not initialized")
    return runner


def _report_store_dep(request: Request):
    store = getattr(request.app.state, "report_store", None)
    if store is None:
        raise HTTPException(500, "report store not initialized")
    return store


class _ReportIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


@router.post("/report")
async def generate_report(
    payload: _ReportIn,
    user=Depends(require_user),
    db: Session = Depends(get_db),
    runner=Depends(_report_runner_dep),
    store=Depends(_report_store_dep),
):
    async def gen():
        async for event in eu_runner.run_on_demand(
            session=db, user_id=user.id, ticker=payload.ticker,
            report_runner=runner, report_store=store,
        ):
            yield serialize_sse(event)

    return StreamingResponse(gen(), media_type="text/event-stream")


# ---------- Recent reports list ----------

from openlia_server.db.models.reports import Report


class _RecentReportOut(BaseModel):
    id: str
    title: str
    subject: str | None
    report_type: str
    created_at: str


class _ReportsListOut(BaseModel):
    reports: list[_RecentReportOut]


@router.get("/reports", response_model=_ReportsListOut)
def list_recent_reports(
    limit: int = 5,
    user=Depends(require_user),
    db: Session = Depends(get_db),
) -> _ReportsListOut:
    limit = max(1, min(limit, 200))
    rows = (
        db.query(Report)
        .filter_by(user_id=user.id, department="earnings_update")
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    return _ReportsListOut(reports=[_RecentReportOut(
        id=r.id, title=r.title, subject=r.subject, report_type=r.report_type,
        created_at=r.created_at.isoformat(),
    ) for r in rows])
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_earnings_update_report.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/earnings_update.py \
        packages/server/tests/routes/departments/test_earnings_update_report.py
git commit -m "feat(server): EU on-demand SSE report endpoint + recent reports list"
```

---

### Task 14: Server — Wire real `EuScanPlannerImpl` into `build_scheduler_service`

Plan 6 ships `StubEUScanPlanner` by default (raises `DepartmentPayloadBuilderNotWired`). Plan 15 replaces it with the real implementation at app startup.

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py`
- Modify: `packages/server/src/openlia_server/app.py` (pass adapter into planner constructor at startup)
- Test: `packages/server/tests/scheduler/test_wiring_eu_planner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/scheduler/test_wiring_eu_planner.py
from dataclasses import dataclass, field
from datetime import UTC, datetime

from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl


@dataclass
class _StubRunner:
    async def run(self, **kwargs): yield  # unreachable; placeholder


@dataclass
class _StubStore:
    saved: list[dict] = field(default_factory=list)
    def save_from_event(self, **kwargs): self.saved.append(kwargs)


class _NoopAdapter:
    def latest_release(self, ticker, *, since): return None


def test_wiring_accepts_real_eu_planner(session_factory) -> None:
    planner = EuScanPlannerImpl(adapter=_NoopAdapter())
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        report_runner=_StubRunner(),
        report_store=_StubStore(),
        eu_planner=planner,
    )
    assert svc is not None
```

- [ ] **Step 2: Run the test to confirm it fails or currently passes**

Run: `uv run pytest packages/server/tests/scheduler/test_wiring_eu_planner.py -v`
Expected: PASS — Plan 6 already accepts an `eu_planner` kwarg. This test is a regression guard; it proves that the real `EuScanPlannerImpl` is structurally compatible with the wiring Protocol.

- [ ] **Step 3: Update app startup to inject the real planner**

In `packages/server/src/openlia_server/app.py`, inside the `lifespan`:

```python
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl

# Inside lifespan():
eu_planner = EuScanPlannerImpl(adapter=app.state.earnings_recent_adapter)
app.state.scheduler = build_scheduler_service(
    session_factory=app.state.session_factory,
    settings=scheduler_settings,
    report_runner=app.state.report_runner,
    report_store=app.state.report_store,
    eu_planner=eu_planner,
    # ... other planners/builders from other plans
)
```

`earnings_recent_adapter` is the adapter that exposes a `latest_release(ticker, since)` method. It is resolved from the `earnings_data` data-provider adapter (Plan 3); a tiny wrapper adapts the Plan 3 interface to the one Plan 15 requires. If Plan 3's adapter already exposes a compatible method, use it directly.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/scheduler/test_wiring_eu_planner.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/wiring.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/scheduler/test_wiring_eu_planner.py
git commit -m "feat(server): wire EuScanPlannerImpl into scheduler at app startup"
```

---

### Task 15: Frontend — `api/earnings-update.ts` typed client

All EU HTTP calls + an SSE helper. Matches the server contract from Tasks 10–13.

**Files:**
- Create: `frontend/src/api/earnings-update.ts`
- Test: `frontend/src/api/__tests__/earnings-update.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/api/__tests__/earnings-update.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  fetchWatchlist,
  addWatchlistEntry,
  removeWatchlistEntry,
  fetchConfig,
  updateConfig,
  fetchSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
  fetchRecentReports,
  startOnDemandReport,
} from "../earnings-update";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("earnings-update api client", () => {
  it("fetchWatchlist calls GET /watchlist", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ entries: [] }), { status: 200 }),
    );
    const r = await fetchWatchlist();
    expect(r).toEqual({ entries: [] });
    expect(spy.mock.calls[0][0]).toBe("/api/departments/earnings-update/watchlist");
  });

  it("addWatchlistEntry posts ticker", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        id: "x", ticker: "AAPL", company_name: "Apple Inc.",
        next_earnings_date: "2026-04-25", release_timing: "post_market",
      }), { status: 201 }),
    );
    const r = await addWatchlistEntry("AAPL");
    expect(r.ticker).toBe("AAPL");
  });

  it("removeWatchlistEntry DELETEs", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await removeWatchlistEntry("xyz");
    expect(spy.mock.calls[0][0]).toBe("/api/departments/earnings-update/watchlist/xyz");
    expect(spy.mock.calls[0][1]?.method).toBe("DELETE");
  });

  it("updateConfig sends full body", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        report_length: "concise", enabled_section_ids: [], custom_sections: [],
      }), { status: 200 }),
    );
    await updateConfig({
      report_length: "concise",
      enabled_section_ids: ["quick_take"],
      custom_sections: [],
    });
    expect(spy.mock.calls[0][1]?.method).toBe("PUT");
    const body = JSON.parse((spy.mock.calls[0][1] as RequestInit).body as string);
    expect(body.enabled_section_ids).toEqual(["quick_take"]);
  });

  it("createSchedule posts", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(new Response(JSON.stringify({
      id: "s1", time: "06:00", timezone: "America/New_York",
      days_of_week: ["mon"], label: "a", is_enabled: true,
    }), { status: 201 }));
    const r = await createSchedule({
      time: "06:00", timezone: "America/New_York",
      days_of_week: ["mon"], label: "a",
    });
    expect(r.id).toBe("s1");
  });

  it("startOnDemandReport opens an SSE stream", async () => {
    // EventSource mock
    const events: string[] = [];
    const fakeES = {
      addEventListener: (name: string, fn: (e: any) => void) => {
        if (name === "report.complete") {
          setTimeout(() => fn({ data: '{"report_id":"r_1","title":"AAPL"}' }), 0);
        }
      },
      close: () => events.push("closed"),
    };
    vi.stubGlobal("EventSource", vi.fn(() => fakeES));

    const result = await startOnDemandReport({ ticker: "AAPL" });
    expect(result.report_id).toBe("r_1");
    expect(events).toContain("closed");
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/api/__tests__/earnings-update.test.ts`
Expected: FAIL (`Cannot find module '../earnings-update'`).

- [ ] **Step 3: Write the client**

```ts
// frontend/src/api/earnings-update.ts
export type ReleaseTiming = "pre_market" | "post_market" | null;

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string;
  next_earnings_date: string | null;
  release_timing: ReleaseTiming;
}

export interface CustomSection {
  id: string;
  title: string;
  description: string;
}

export type ReportLength = "concise" | "normal" | "elaborative";

export interface EuConfig {
  report_length: ReportLength;
  enabled_section_ids: string[];
  custom_sections: CustomSection[];
}

export interface EuSchedule {
  id: string;
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
  is_enabled: boolean;
}

export interface RecentReport {
  id: string;
  title: string;
  subject: string | null;
  report_type: string;
  created_at: string;
}

const BASE = "/api/departments/earnings-update";

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const r = await fetch(input, init);
  if (\!r.ok) throw new HttpError(r.status, await r.text());
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export class HttpError extends Error {
  constructor(public status: number, public body: string) {
    super(`HTTP ${status}: ${body}`);
  }
}

// ----- Watchlist -----

export const fetchWatchlist = () =>
  json<{ entries: WatchlistEntry[] }>(`${BASE}/watchlist`);

export const addWatchlistEntry = (ticker: string) =>
  json<WatchlistEntry>(`${BASE}/watchlist`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker }),
  });

export const removeWatchlistEntry = (entryId: string) =>
  json<void>(`${BASE}/watchlist/${entryId}`, { method: "DELETE" });

// ----- Config -----

export const fetchConfig = () => json<EuConfig>(`${BASE}/config`);

export const updateConfig = (cfg: EuConfig) =>
  json<EuConfig>(`${BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });

// ----- Schedules -----

export const fetchSchedules = () =>
  json<{ schedules: EuSchedule[] }>(`${BASE}/schedules`);

export const createSchedule = (payload: Omit<EuSchedule, "id" | "is_enabled">) =>
  json<EuSchedule>(`${BASE}/schedules`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const updateSchedule = (id: string, payload: Omit<EuSchedule, "id">) =>
  json<EuSchedule>(`${BASE}/schedules/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteSchedule = (id: string) =>
  json<void>(`${BASE}/schedules/${id}`, { method: "DELETE" });

// ----- Reports -----

export const fetchRecentReports = (limit = 5) =>
  json<{ reports: RecentReport[] }>(`${BASE}/reports?limit=${limit}`);

// SSE wrapper: resolves on `report.complete`, rejects on `report.error`.
export function startOnDemandReport(
  payload: { ticker: string },
  onEvent?: (name: string, data: any) => void,
): Promise<{ report_id: string; title: string }> {
  return new Promise((resolve, reject) => {
    const url = `${BASE}/report`;
    // Note: we use fetch+POST here in prod, but tests can stub EventSource.
    const es = new EventSource(
      `${url}?ticker=${encodeURIComponent(payload.ticker)}`,
    );
    es.addEventListener("report.start", (ev: MessageEvent) =>
      onEvent?.("report.start", JSON.parse(ev.data)));
    es.addEventListener("report.delta", (ev: MessageEvent) =>
      onEvent?.("report.delta", JSON.parse(ev.data)));
    es.addEventListener("report.complete", (ev: MessageEvent) => {
      const data = JSON.parse(ev.data);
      onEvent?.("report.complete", data);
      es.close();
      resolve(data);
    });
    es.addEventListener("report.error", (ev: MessageEvent) => {
      const data = JSON.parse(ev.data);
      onEvent?.("report.error", data);
      es.close();
      reject(new Error(data?.message ?? "report failed"));
    });
  });
}
```

> **Note on SSE + POST:** `EventSource` only supports GET. The actual production client should use the same `useSseStream` helper the rest of the app uses (fetch + ReadableStream) — mirror the Plan 14 ER report flow. The test above stubs `EventSource` for brevity; implement the real client using the shared SSE helper and update the test accordingly. **This note is the only place the plan defers — you MUST consult the existing SSE helper implementation before finalizing.**

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/api/__tests__/earnings-update.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/earnings-update.ts frontend/src/api/__tests__/earnings-update.test.ts
git commit -m "feat(frontend): add earnings-update typed api client"
```

---

### Task 16: Frontend — Section catalog + hooks

- Section catalog (`lib/earnings-update/section-catalog.ts`): source-of-truth mapping of the 8 default section IDs to human titles + 1-line descriptions (shown in `ReportSettingsModal`).
- Hooks: `useEuWatchlist`, `useEuConfig`, `useEuSchedules`, `useEuReports` — thin wrappers with React state + `fetch*`/`mutate` helpers.

**Files:**
- Create: `frontend/src/lib/earnings-update/section-catalog.ts`
- Create: `frontend/src/hooks/useEuWatchlist.ts`
- Create: `frontend/src/hooks/useEuConfig.ts`
- Create: `frontend/src/hooks/useEuSchedules.ts`
- Create: `frontend/src/hooks/useEuReports.ts`
- Test: `frontend/src/lib/earnings-update/__tests__/section-catalog.test.ts`
- Test: `frontend/src/hooks/__tests__/useEuWatchlist.test.tsx`
- Test: `frontend/src/hooks/__tests__/useEuConfig.test.tsx`

- [ ] **Step 1: Write the failing catalog test**

```ts
// frontend/src/lib/earnings-update/__tests__/section-catalog.test.ts
import { describe, expect, it } from "vitest";

import { EU_SECTION_CATALOG, DEFAULT_EU_SECTIONS } from "../section-catalog";

describe("EU section catalog", () => {
  it("exposes 8 default sections", () => {
    expect(DEFAULT_EU_SECTIONS.length).toBe(8);
  });

  it("has catalog entries for every default id", () => {
    for (const id of DEFAULT_EU_SECTIONS) {
      const entry = EU_SECTION_CATALOG[id];
      expect(entry).toBeDefined();
      expect(entry.title.length).toBeGreaterThan(0);
    }
  });

  it("catalog ids match framework JSON", () => {
    // This test will fail if someone renames an id in catalog but not in
    // `earnings_update.json`. We repeat the framework ids inline to avoid
    // reading the json from the frontend bundle.
    const frameworkIds = [
      "quick_take", "market_reaction", "key_financials",
      "operational_highlights", "forward_guidance", "earnings_call",
      "risk_assessment", "thesis_check",
    ];
    expect(DEFAULT_EU_SECTIONS).toEqual(frameworkIds);
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/lib/earnings-update/__tests__/section-catalog.test.ts`
Expected: FAIL.

- [ ] **Step 3: Write the catalog**

```ts
// frontend/src/lib/earnings-update/section-catalog.ts
export interface SectionCatalogEntry {
  title: string;
  description: string;
}

export const EU_SECTION_CATALOG: Record<string, SectionCatalogEntry> = {
  quick_take: {
    title: "Quick Take",
    description: "1–3 sentence verdict and investment implication.",
  },
  market_reaction: {
    title: "Post-Earnings Market Reaction",
    description: "Price change, volume, and immediate analyst response.",
  },
  key_financials: {
    title: "Key Financials vs Consensus",
    description: "Revenue/EPS/margins vs estimate, prior quarter, and year ago.",
  },
  operational_highlights: {
    title: "Operational Highlights and Drivers",
    description: "Beats, misses, watch items, and segment breakdown.",
  },
  forward_guidance: {
    title: "Forward Guidance",
    description: "New vs prior guidance, vs street, and guidance quality.",
  },
  earnings_call: {
    title: "Earnings Call Key Points",
    description: "Management commentary, Q&A highlights, tone.",
  },
  risk_assessment: {
    title: "Risk Assessment",
    description: "Upside and downside risks specific to this quarter.",
  },
  thesis_check: {
    title: "Investment Thesis Check",
    description: "How this quarter affects each thesis pillar + rating.",
  },
};

export const DEFAULT_EU_SECTIONS: readonly string[] = [
  "quick_take",
  "market_reaction",
  "key_financials",
  "operational_highlights",
  "forward_guidance",
  "earnings_call",
  "risk_assessment",
  "thesis_check",
] as const;
```

- [ ] **Step 4: Run the catalog test**

Expected: PASS.

- [ ] **Step 5: Write the failing watchlist hook test**

```tsx
// frontend/src/hooks/__tests__/useEuWatchlist.test.tsx
import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import { useEuWatchlist } from "../useEuWatchlist";

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("useEuWatchlist", () => {
  it("loads entries on mount", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [
      { id: "1", ticker: "AAPL", company_name: "Apple Inc.",
        next_earnings_date: "2026-04-25", release_timing: "post_market" },
    ] });
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    expect(result.current.entries[0].ticker).toBe("AAPL");
  });

  it("add() calls api and prepends entry", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "addWatchlistEntry").mockResolvedValue({
      id: "2", ticker: "TSLA", company_name: "Tesla",
      next_earnings_date: null, release_timing: null,
    });
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => { await result.current.add("TSLA"); });
    expect(result.current.entries.map(e => e.ticker)).toContain("TSLA");
  });

  it("remove() optimistically removes then resyncs on failure", async () => {
    vi.spyOn(api, "fetchWatchlist")
      .mockResolvedValueOnce({ entries: [{
        id: "1", ticker: "AAPL", company_name: "Apple",
        next_earnings_date: null, release_timing: null,
      }]})
      .mockResolvedValueOnce({ entries: [{
        id: "1", ticker: "AAPL", company_name: "Apple",
        next_earnings_date: null, release_timing: null,
      }]});
    vi.spyOn(api, "removeWatchlistEntry").mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useEuWatchlist());
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
    await expect(result.current.remove("1")).rejects.toThrow();
    await waitFor(() => expect(result.current.entries).toHaveLength(1));
  });
});
```

- [ ] **Step 6: Write the hook**

```ts
// frontend/src/hooks/useEuWatchlist.ts
import { useCallback, useEffect, useState } from "react";

import {
  WatchlistEntry,
  addWatchlistEntry,
  fetchWatchlist,
  removeWatchlistEntry,
} from "../api/earnings-update";

export function useEuWatchlist() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchWatchlist();
      setEntries(r.entries);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const add = useCallback(async (ticker: string) => {
    const entry = await addWatchlistEntry(ticker);
    setEntries((prev) => [entry, ...prev]);
  }, []);

  const remove = useCallback(async (entryId: string) => {
    const snapshot = entries;
    setEntries((prev) => prev.filter((e) => e.id \!== entryId));
    try {
      await removeWatchlistEntry(entryId);
    } catch (e) {
      setEntries(snapshot);
      throw e;
    }
  }, [entries]);

  return { entries, loading, error, refresh, add, remove };
}
```

- [ ] **Step 7: Write `useEuConfig`, `useEuSchedules`, `useEuReports` analogously**

```ts
// frontend/src/hooks/useEuConfig.ts
import { useCallback, useEffect, useState } from "react";
import { EuConfig, fetchConfig, updateConfig } from "../api/earnings-update";

export function useEuConfig() {
  const [config, setConfig] = useState<EuConfig | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void (async () => {
      setConfig(await fetchConfig());
      setLoading(false);
    })();
  }, []);

  const save = useCallback(async (next: EuConfig) => {
    const saved = await updateConfig(next);
    setConfig(saved);
    return saved;
  }, []);

  return { config, loading, save };
}
```

```ts
// frontend/src/hooks/useEuSchedules.ts
import { useCallback, useEffect, useState } from "react";
import {
  EuSchedule, createSchedule, deleteSchedule,
  fetchSchedules, updateSchedule,
} from "../api/earnings-update";

export function useEuSchedules() {
  const [schedules, setSchedules] = useState<EuSchedule[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setSchedules((await fetchSchedules()).schedules);
    setLoading(false);
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const create = useCallback(async (payload: Omit<EuSchedule, "id" | "is_enabled">) => {
    const s = await createSchedule(payload);
    setSchedules((prev) => [...prev, s].sort((a, b) => a.time.localeCompare(b.time)));
    return s;
  }, []);

  const update = useCallback(async (id: string, payload: Omit<EuSchedule, "id">) => {
    const s = await updateSchedule(id, payload);
    setSchedules((prev) => prev.map((x) => (x.id === id ? s : x)));
    return s;
  }, []);

  const remove = useCallback(async (id: string) => {
    await deleteSchedule(id);
    setSchedules((prev) => prev.filter((x) => x.id \!== id));
  }, []);

  return { schedules, loading, refresh, create, update, remove };
}
```

```ts
// frontend/src/hooks/useEuReports.ts
import { useCallback, useEffect, useState } from "react";
import { RecentReport, fetchRecentReports } from "../api/earnings-update";

export function useEuReports(limit = 5) {
  const [reports, setReports] = useState<RecentReport[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setReports((await fetchRecentReports(limit)).reports);
    setLoading(false);
  }, [limit]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { reports, loading, refresh };
}
```

- [ ] **Step 8: Run all tests**

Run: `cd frontend && npx vitest run src/hooks/__tests__/useEuWatchlist.test.tsx src/hooks/__tests__/useEuConfig.test.tsx src/lib/earnings-update/__tests__/section-catalog.test.ts`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib/earnings-update/ frontend/src/hooks/useEu*.ts frontend/src/hooks/__tests__/useEu*.test.tsx frontend/src/lib/earnings-update/__tests__/
git commit -m "feat(frontend): add EU section catalog + watchlist/config/schedules/reports hooks"
```

---

### Task 17: Frontend — `WatchlistRow`, `WatchlistCard`, `AddTickerPopover`

**Files:**
- Create: `frontend/src/components/earnings-update/WatchlistCard.tsx`
- Create: `frontend/src/components/earnings-update/WatchlistRow.tsx`
- Create: `frontend/src/components/earnings-update/AddTickerPopover.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/WatchlistCard.test.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/WatchlistRow.test.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/AddTickerPopover.test.tsx`

- [ ] **Step 1: Write the failing `WatchlistCard` test**

```tsx
// frontend/src/components/earnings-update/__tests__/WatchlistCard.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WatchlistCard } from "../WatchlistCard";

const baseEntry = {
  id: "1",
  ticker: "AAPL",
  company_name: "Apple Inc.",
  next_earnings_date: "2026-04-25",
  release_timing: "post_market" as const,
};

describe("WatchlistCard", () => {
  it("renders ticker, company, date, timing badge", () => {
    render(<WatchlistCard entry={baseEntry} onRemove={() => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("Apple Inc.")).toBeInTheDocument();
    expect(screen.getByText(/Apr 25/)).toBeInTheDocument();
    expect(screen.getByText(/Post-Market/i)).toBeInTheDocument();
  });

  it("renders Date passed state when date is in the past", () => {
    render(<WatchlistCard
      entry={{ ...baseEntry, next_earnings_date: "2025-01-01" }}
      onRemove={() => {}} />);
    expect(screen.getByText(/Date passed/i)).toBeInTheDocument();
  });

  it("calls onRemove when × is clicked", () => {
    const onRemove = vi.fn();
    render(<WatchlistCard entry={baseEntry} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith("1");
  });

  it("renders N/A when no earnings date cached", () => {
    render(<WatchlistCard
      entry={{ ...baseEntry, next_earnings_date: null, release_timing: null }}
      onRemove={() => {}} />);
    expect(screen.getByText(/—|N\/A|Pending/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the `WatchlistCard` component**

```tsx
// frontend/src/components/earnings-update/WatchlistCard.tsx
import { X } from "lucide-react";

import { WatchlistEntry } from "../../api/earnings-update";

interface Props {
  entry: WatchlistEntry;
  onRemove: (id: string) => void;
}

function formatDate(iso: string | null): string {
  if (\!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short", day: "numeric",
  });
}

function isPast(iso: string | null): boolean {
  if (\!iso) return false;
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}

export function WatchlistCard({ entry, onRemove }: Props) {
  const overdue = isPast(entry.next_earnings_date);
  return (
    <div
      role="group"
      aria-label={`Watchlist entry ${entry.ticker}`}
      className={[
        "group flex-shrink-0 w-[148px] bg-[--color-bg-elevated]",
        "border rounded-[--radius-lg] p-3 flex flex-col gap-1 relative",
        overdue
          ? "border-[--color-feedback-error]"
          : "border-[--color-border-subtle] hover:border-[--color-border-secondary] hover:shadow-sm",
        "transition-all duration-[--duration-fast]",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={() => onRemove(entry.id)}
        aria-label={`Remove ${entry.ticker}`}
        className={[
          "absolute right-1 top-1 p-1 rounded opacity-0 group-hover:opacity-100",
          "text-[--color-text-tertiary] hover:text-[--color-text-primary]",
          "transition-opacity duration-[--duration-fast]",
        ].join(" ")}
      >
        <X size={14} />
      </button>
      <div className="text-base font-semibold text-[--color-text-primary]">
        {entry.ticker}
      </div>
      <div className="text-xs text-[--color-text-secondary] truncate">
        {entry.company_name}
      </div>
      <div className="text-sm font-medium text-[--color-text-primary] mt-1">
        {formatDate(entry.next_earnings_date)}
      </div>
      {overdue ? (
        <span className="text-xs rounded-full px-2 py-0.5 bg-[--color-surface-hover] text-[--color-text-tertiary]">
          Date passed
        </span>
      ) : entry.release_timing ? (
        <span
          className={[
            "text-xs rounded-full px-2 py-0.5 w-fit",
            entry.release_timing === "pre_market"
              ? "bg-[--color-info]/10 text-[--color-info]"
              : "bg-[--color-warning]/10 text-[--color-warning]",
          ].join(" ")}
        >
          {entry.release_timing === "pre_market" ? "Pre-Market" : "Post-Market"}
        </span>
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Write the failing `AddTickerPopover` test**

```tsx
// frontend/src/components/earnings-update/__tests__/AddTickerPopover.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddTickerPopover } from "../AddTickerPopover";

describe("AddTickerPopover", () => {
  it("submits uppercased ticker on Add click", async () => {
    const onAdd = vi.fn().mockResolvedValue(undefined);
    render(<AddTickerPopover onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add ticker/i }));
    const input = await screen.findByPlaceholderText(/ticker symbol/i);
    fireEvent.change(input, { target: { value: "aapl" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(onAdd).toHaveBeenCalledWith("AAPL");
  });

  it("shows error on 409", async () => {
    const onAdd = vi.fn().mockRejectedValue(Object.assign(new Error("x"), { status: 409 }));
    render(<AddTickerPopover onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: /add ticker/i }));
    const input = await screen.findByPlaceholderText(/ticker symbol/i);
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.click(screen.getByRole("button", { name: /^add$/i }));
    expect(await screen.findByText(/already watching/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Write `AddTickerPopover`**

```tsx
// frontend/src/components/earnings-update/AddTickerPopover.tsx
import { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Plus } from "lucide-react";

import { HttpError } from "../../api/earnings-update";

interface Props {
  onAdd: (ticker: string) => Promise<void>;
}

export function AddTickerPopover({ onAdd }: Props) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setErr(null);
    const ticker = value.trim().toUpperCase();
    if (\!ticker) return;
    setSubmitting(true);
    try {
      await onAdd(ticker);
      setValue("");
      setOpen(false);
    } catch (e) {
      const status = (e as HttpError).status;
      if (status === 409) setErr(`Already watching ${ticker}`);
      else if (status === 404) setErr(`Ticker ${ticker} not found`);
      else setErr("Failed to add ticker");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="flex items-center gap-1 border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-7 hover:border-[--color-border-primary]"
          aria-label="Add ticker"
        >
          <Plus size={14} /> Add Ticker
        </button>
      </Popover.Trigger>
      <Popover.Content
        align="end"
        sideOffset={4}
        className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] p-3 w-[280px] shadow-md"
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") void handleSubmit(); }}
          placeholder="Ticker symbol or company name"
          className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm text-[--color-text-primary]"
        />
        {err ? (
          <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
        ) : null}
        <div className="flex justify-end mt-3">
          <button
            type="button"
            onClick={() => void handleSubmit()}
            disabled={submitting}
            className="text-sm bg-[--color-accent-primary] text-white h-7 px-3 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
          >
            Add
          </button>
        </div>
      </Popover.Content>
    </Popover.Root>
  );
}
```

- [ ] **Step 5: Write `WatchlistRow` + its test**

```tsx
// frontend/src/components/earnings-update/__tests__/WatchlistRow.test.tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WatchlistRow } from "../WatchlistRow";

describe("WatchlistRow", () => {
  it("renders empty-state when no entries", () => {
    render(<WatchlistRow entries={[]} onAdd={async () => {}} onRemove={async () => {}} />);
    expect(screen.getByText(/Add companies to your watchlist/i)).toBeInTheDocument();
  });

  it("renders a card per entry", () => {
    const entries = [
      { id: "1", ticker: "AAPL", company_name: "Apple",
        next_earnings_date: "2026-04-25", release_timing: "post_market" as const },
      { id: "2", ticker: "TSLA", company_name: "Tesla",
        next_earnings_date: "2026-04-22", release_timing: "pre_market" as const },
    ];
    render(<WatchlistRow entries={entries} onAdd={async () => {}} onRemove={async () => {}} />);
    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
  });
});
```

```tsx
// frontend/src/components/earnings-update/WatchlistRow.tsx
import { WatchlistEntry } from "../../api/earnings-update";

import { AddTickerPopover } from "./AddTickerPopover";
import { WatchlistCard } from "./WatchlistCard";

interface Props {
  entries: WatchlistEntry[];
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

export function WatchlistRow({ entries, onAdd, onRemove }: Props) {
  return (
    <section>
      <header className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Watchlist
        </h3>
        <AddTickerPopover onAdd={onAdd} />
      </header>
      {entries.length === 0 ? (
        <div className="mx-6 mb-4 border border-dashed border-[--color-border-subtle] rounded-[--radius-lg] h-[120px] flex items-center justify-center text-sm text-[--color-text-tertiary]">
          Add companies to your watchlist to track upcoming earnings
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto px-6 pb-4" style={{ scrollSnapType: "x mandatory" }}>
          {entries.map((e) => (
            <WatchlistCard key={e.id} entry={e} onRemove={(id) => void onRemove(id)} />
          ))}
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 6: Run tests**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/earnings-update/Watchlist* \
        frontend/src/components/earnings-update/AddTickerPopover.tsx \
        frontend/src/components/earnings-update/__tests__/
git commit -m "feat(frontend): WatchlistRow, WatchlistCard, AddTickerPopover"
```

---

### Task 18: Frontend — `RecentReportsList`, `ReportRowItem`, `EUCabinetView`

**Files:**
- Create: `frontend/src/components/earnings-update/ReportRowItem.tsx`
- Create: `frontend/src/components/earnings-update/RecentReportsList.tsx`
- Create: `frontend/src/components/earnings-update/EUCabinetView.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/RecentReportsList.test.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/EUCabinetView.test.tsx`

- [ ] **Step 1: Write the failing `RecentReportsList` test**

```tsx
// frontend/src/components/earnings-update/__tests__/RecentReportsList.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RecentReportsList } from "../RecentReportsList";

const reports = [
  { id: "r1", title: "Apple Inc. — Q1 FY2026 Earnings", subject: "AAPL",
    report_type: "earnings_update", created_at: "2026-04-09T12:00:00Z" },
  { id: "r2", title: "Tesla Inc. — Q1 FY2026 Earnings", subject: "TSLA",
    report_type: "earnings_update", created_at: "2026-04-08T12:00:00Z" },
];

describe("RecentReportsList", () => {
  it("renders a row per report", () => {
    render(<RecentReportsList reports={reports} onOpenReport={() => {}} onOpenCabinet={() => {}} />);
    expect(screen.getAllByRole("button", { name: /open/i }).length).toBeGreaterThanOrEqual(2);
  });

  it("empty state when no reports", () => {
    render(<RecentReportsList reports={[]} onOpenReport={() => {}} onOpenCabinet={() => {}} />);
    expect(screen.getByText(/will appear here/i)).toBeInTheDocument();
  });

  it("Open Cabinet link calls onOpenCabinet", () => {
    const onOpenCabinet = vi.fn();
    render(<RecentReportsList reports={reports} onOpenReport={() => {}} onOpenCabinet={onOpenCabinet} />);
    fireEvent.click(screen.getByText(/Open Cabinet/i));
    expect(onOpenCabinet).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Write the components**

```tsx
// frontend/src/components/earnings-update/ReportRowItem.tsx
import { RecentReport } from "../../api/earnings-update";

interface Props {
  report: RecentReport;
  onOpen: (id: string) => void;
  showExtras?: boolean;  // cabinet-only Download / Remove buttons
  onDownload?: (id: string) => void;
  onRemove?: (id: string) => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function ReportRowItem({ report, onOpen, showExtras, onDownload, onRemove }: Props) {
  return (
    <div
      role="row"
      className="flex items-center gap-4 px-6 py-3.5 border-b border-[--color-border-subtle] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-fast]"
    >
      <span className="text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0">
        {report.subject ?? "—"}
      </span>
      <span className="flex-1 text-base text-[--color-text-primary]">
        {report.title}
      </span>
      <span className="text-sm text-[--color-text-secondary] flex-shrink-0">
        {formatDate(report.created_at)}
      </span>
      <button
        type="button"
        onClick={() => onOpen(report.id)}
        className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover] ml-2"
      >
        Open
      </button>
      {showExtras ? (
        <>
          <button type="button" onClick={() => onDownload?.(report.id)}
                  className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-2">↓</button>
          <button type="button" onClick={() => onRemove?.(report.id)}
                  className="text-sm text-[--color-text-secondary] hover:text-[--color-feedback-error] ml-2">×</button>
        </>
      ) : null}
    </div>
  );
}
```

```tsx
// frontend/src/components/earnings-update/RecentReportsList.tsx
import { RecentReport } from "../../api/earnings-update";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RecentReport[];
  onOpenReport: (id: string) => void;
  onOpenCabinet: () => void;
}

export function RecentReportsList({ reports, onOpenReport, onOpenCabinet }: Props) {
  return (
    <section>
      <header className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Recent Reports
        </h3>
        <button
          type="button"
          onClick={onOpenCabinet}
          className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]"
        >
          Open Cabinet →
        </button>
      </header>
      {reports.length === 0 ? (
        <div className="mx-6 mb-4 text-center py-8 text-sm text-[--color-text-tertiary]">
          On-Demand reports and automated reports will appear here
        </div>
      ) : (
        <div>
          {reports.map((r) => (
            <ReportRowItem key={r.id} report={r} onOpen={onOpenReport} />
          ))}
        </div>
      )}
    </section>
  );
}
```

```tsx
// frontend/src/components/earnings-update/EUCabinetView.tsx
import { useMemo, useState } from "react";

import { RecentReport } from "../../api/earnings-update";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RecentReport[];
  onBack: () => void;
  onOpenReport: (id: string) => void;
  onDownload: (id: string) => void;
  onRemove: (id: string) => Promise<void>;
}

function monthKey(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "long", year: "numeric" });
}

export function EUCabinetView({ reports, onBack, onOpenReport, onDownload, onRemove }: Props) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    if (\!needle) return reports;
    return reports.filter((r) =>
      (r.subject ?? "").toLowerCase().includes(needle) ||
      r.title.toLowerCase().includes(needle),
    );
  }, [q, reports]);

  const groups = useMemo(() => {
    const acc: Record<string, RecentReport[]> = {};
    for (const r of filtered) {
      const k = monthKey(r.created_at);
      (acc[k] ??= []).push(r);
    }
    return Object.entries(acc);
  }, [filtered]);

  return (
    <div className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto">
      <header className="flex items-center justify-between h-14 px-6 border-b border-[--color-border-subtle]">
        <button type="button" onClick={onBack} className="text-sm text-[--color-accent-primary]">
          ← Back to Earnings Updates
        </button>
        <h2 className="text-xl font-semibold">EU Cabinet</h2>
        <span className="w-32" />
      </header>
      <div className="px-6 py-4">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search reports..."
          className="w-full bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 text-sm text-[--color-text-primary]"
        />
      </div>
      {groups.map(([k, items]) => (
        <div key={k}>
          <h3 className="text-sm font-medium text-[--color-text-secondary] px-6 py-2">{k}</h3>
          {items.map((r) => (
            <ReportRowItem
              key={r.id} report={r} onOpen={onOpenReport}
              showExtras onDownload={onDownload}
              onRemove={(id) => void onRemove(id)}
            />
          ))}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 3: Write `EUCabinetView` test**

```tsx
// frontend/src/components/earnings-update/__tests__/EUCabinetView.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EUCabinetView } from "../EUCabinetView";

const reports = [
  { id: "r1", title: "Apple Inc. — Q1 FY2026 Earnings", subject: "AAPL",
    report_type: "earnings_update", created_at: "2026-04-09T12:00:00Z" },
  { id: "r2", title: "Tesla Inc. — Q1 FY2026 Earnings", subject: "TSLA",
    report_type: "earnings_update", created_at: "2026-03-08T12:00:00Z" },
];

describe("EUCabinetView", () => {
  it("groups reports by month", () => {
    render(<EUCabinetView reports={reports} onBack={() => {}}
      onOpenReport={() => {}} onDownload={() => {}} onRemove={async () => {}} />);
    expect(screen.getByText(/April 2026/)).toBeInTheDocument();
    expect(screen.getByText(/March 2026/)).toBeInTheDocument();
  });

  it("search filters reports", () => {
    render(<EUCabinetView reports={reports} onBack={() => {}}
      onOpenReport={() => {}} onDownload={() => {}} onRemove={async () => {}} />);
    fireEvent.change(screen.getByPlaceholderText(/search reports/i), { target: { value: "tesla" } });
    expect(screen.queryByText(/Apple Inc\./)).toBeNull();
    expect(screen.getByText(/Tesla Inc\./)).toBeInTheDocument();
  });

  it("back button fires", () => {
    const onBack = vi.fn();
    render(<EUCabinetView reports={reports} onBack={onBack}
      onOpenReport={() => {}} onDownload={() => {}} onRemove={async () => {}} />);
    fireEvent.click(screen.getByText(/Back to Earnings Updates/));
    expect(onBack).toHaveBeenCalled();
  });
});
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/RecentReportsList.test.tsx src/components/earnings-update/__tests__/EUCabinetView.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/Recent* \
        frontend/src/components/earnings-update/ReportRowItem.tsx \
        frontend/src/components/earnings-update/EUCabinetView.tsx \
        frontend/src/components/earnings-update/__tests__/
git commit -m "feat(frontend): RecentReportsList, ReportRowItem, EUCabinetView"
```

---

### Task 19: Frontend — `OnDemandReportModal`

Triggered from the page header "+ On-Demand Report" button. User enters a ticker; pressing Generate calls `startOnDemandReport(...)` which streams SSE and resolves to `{report_id, title}`. The modal shows an inline progress indicator while the stream is open.

**Files:**
- Create: `frontend/src/components/earnings-update/OnDemandReportModal.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnDemandReportModal } from "../OnDemandReportModal";

describe("OnDemandReportModal", () => {
  it("generate button disabled until ticker entered", () => {
    render(<OnDemandReportModal
      open onClose={() => {}} onReportReady={() => {}} startReport={async () => ({ report_id: "x", title: "t" })}
    />);
    const btn = screen.getByRole("button", { name: /generate report/i });
    expect(btn).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: "AAPL" } });
    expect(btn).toBeEnabled();
  });

  it("calls startReport and onReportReady with result", async () => {
    const startReport = vi.fn().mockResolvedValue({ report_id: "r_1", title: "AAPL" });
    const onReportReady = vi.fn();
    render(<OnDemandReportModal open onClose={() => {}} onReportReady={onReportReady} startReport={startReport} />);
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: "aapl" } });
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    await waitFor(() => expect(onReportReady).toHaveBeenCalledWith({ report_id: "r_1", title: "AAPL" }));
    expect(startReport).toHaveBeenCalledWith({ ticker: "AAPL" });
  });

  it("shows error when startReport rejects", async () => {
    const startReport = vi.fn().mockRejectedValue(new Error("boom"));
    render(<OnDemandReportModal open onClose={() => {}} onReportReady={() => {}} startReport={startReport} />);
    fireEvent.change(screen.getByPlaceholderText(/ticker/i), { target: { value: "AAPL" } });
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText(/failed|boom/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the modal**

```tsx
// frontend/src/components/earnings-update/OnDemandReportModal.tsx
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  onReportReady: (result: { report_id: string; title: string }) => void;
  startReport: (payload: { ticker: string }) => Promise<{ report_id: string; title: string }>;
}

export function OnDemandReportModal({ open, onClose, onReportReady, startReport }: Props) {
  const [ticker, setTicker] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleGenerate() {
    setErr(null);
    setSubmitting(true);
    try {
      const result = await startReport({ ticker: ticker.trim().toUpperCase() });
      onReportReady(result);
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? "Failed to generate report");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (\!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-1">
            On-Demand Earnings Update
          </Dialog.Title>
          <Dialog.Description className="text-sm text-[--color-text-secondary] mb-4">
            Generate an earnings analysis for a company's most recently released
            earnings report.
          </Dialog.Description>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker symbol (e.g. AAPL)"
            className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-3 h-9 text-sm text-[--color-text-primary]"
          />
          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
          ) : null}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={\!ticker.trim() || submitting}
              onClick={() => void handleGenerate()}
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {submitting ? "Generating..." : "Generate Report"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 3: Run the tests**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/earnings-update/OnDemandReportModal.tsx \
        frontend/src/components/earnings-update/__tests__/OnDemandReportModal.test.tsx
git commit -m "feat(frontend): OnDemandReportModal with streaming generate flow"
```

---

### Task 20: Frontend — `ScheduleManager` + `AddScheduleModal`

A settings subview listing current scan schedules (row-per-schedule) with Add / Edit / Remove controls.

**Files:**
- Create: `frontend/src/components/earnings-update/AddScheduleModal.tsx`
- Create: `frontend/src/components/earnings-update/ScheduleManager.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/AddScheduleModal.test.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/ScheduleManager.test.tsx`

- [ ] **Step 1: Write the failing `AddScheduleModal` test**

```tsx
// frontend/src/components/earnings-update/__tests__/AddScheduleModal.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddScheduleModal } from "../AddScheduleModal";

describe("AddScheduleModal", () => {
  it("submits valid schedule", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<AddScheduleModal open onClose={() => {}} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText(/time/i), { target: { value: "06:00" } });
    fireEvent.change(screen.getByLabelText(/timezone/i), { target: { value: "America/New_York" } });
    fireEvent.click(screen.getByLabelText(/mon/i));
    fireEvent.change(screen.getByLabelText(/label/i), { target: { value: "Pre-Market Scan" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).toHaveBeenCalledWith({
      time: "06:00",
      timezone: "America/New_York",
      days_of_week: ["mon"],
      label: "Pre-Market Scan",
    });
  });

  it("requires at least one day selected", () => {
    const onSave = vi.fn();
    render(<AddScheduleModal open onClose={() => {}} onSave={onSave} />);
    fireEvent.change(screen.getByLabelText(/time/i), { target: { value: "06:00" } });
    fireEvent.change(screen.getByLabelText(/timezone/i), { target: { value: "America/New_York" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(onSave).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Write the modal**

```tsx
// frontend/src/components/earnings-update/AddScheduleModal.tsx
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
type Day = (typeof DAYS)[number];

interface Props {
  open: boolean;
  onClose: () => void;
  onSave: (payload: {
    time: string;
    timezone: string;
    days_of_week: Day[];
    label: string;
  }) => Promise<void>;
  initial?: {
    time: string; timezone: string; days_of_week: Day[]; label: string;
  };
}

export function AddScheduleModal({ open, onClose, onSave, initial }: Props) {
  const [time, setTime] = useState(initial?.time ?? "06:00");
  const [timezone, setTimezone] = useState(
    initial?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
  );
  const [days, setDays] = useState<Day[]>(initial?.days_of_week ?? []);
  const [label, setLabel] = useState(initial?.label ?? "");
  const [err, setErr] = useState<string | null>(null);

  function toggleDay(d: Day) {
    setDays((prev) => (prev.includes(d) ? prev.filter((x) => x \!== d) : [...prev, d]));
  }

  async function handleSave() {
    if (days.length === 0) {
      setErr("Select at least one day");
      return;
    }
    setErr(null);
    await onSave({ time, timezone, days_of_week: days, label });
    onClose();
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (\!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[420px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-4">
            {initial ? "Edit Schedule" : "Add Schedule"}
          </Dialog.Title>
          <label className="block text-sm mb-2">
            Time
            <input
              aria-label="time"
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm"
            />
          </label>
          <label className="block text-sm mb-2">
            Timezone
            <input
              aria-label="timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm w-[200px]"
            />
          </label>
          <fieldset className="my-2">
            <legend className="text-sm">Days</legend>
            <div className="flex gap-2 flex-wrap">
              {DAYS.map((d) => (
                <label key={d} className="text-xs flex items-center gap-1">
                  <input
                    type="checkbox"
                    aria-label={d}
                    checked={days.includes(d)}
                    onChange={() => toggleDay(d)}
                  />
                  {d.toUpperCase()}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block text-sm mb-2">
            Label
            <input
              aria-label="label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm w-[240px]"
            />
          </label>
          {err ? (
            <p className="text-xs text-[--color-feedback-error]">{err}</p>
          ) : null}
          <div className="flex justify-end gap-2 mt-4">
            <button type="button" onClick={onClose}
                    className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]">
              Cancel
            </button>
            <button type="button" onClick={() => void handleSave()}
                    className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover]">
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 3: Write `ScheduleManager`**

```tsx
// frontend/src/components/earnings-update/ScheduleManager.tsx
import { useState } from "react";

import { EuSchedule } from "../../api/earnings-update";

import { AddScheduleModal } from "./AddScheduleModal";

interface Props {
  schedules: EuSchedule[];
  onCreate: (p: Omit<EuSchedule, "id" | "is_enabled">) => Promise<unknown>;
  onUpdate: (id: string, p: Omit<EuSchedule, "id">) => Promise<unknown>;
  onRemove: (id: string) => Promise<unknown>;
}

export function ScheduleManager({ schedules, onCreate, onUpdate, onRemove }: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<EuSchedule | null>(null);

  return (
    <section className="px-6 pt-5 pb-4">
      <header className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Scan Schedules
        </h3>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-7 hover:border-[--color-border-primary]"
        >
          + Add Schedule
        </button>
      </header>
      {schedules.length === 0 ? (
        <div className="border border-dashed border-[--color-border-subtle] rounded-[--radius-md] py-6 text-center text-sm text-[--color-text-tertiary]">
          No scan schedules configured. Earnings reports will not be detected automatically.
        </div>
      ) : (
        <ul className="border border-[--color-border-subtle] rounded-[--radius-md] divide-y divide-[--color-border-subtle]">
          {schedules.map((s) => (
            <li key={s.id} className="flex items-center justify-between px-4 py-3">
              <div className="text-sm">
                <span className="font-medium">{s.time}</span>{" "}
                <span className="text-[--color-text-secondary]">{s.timezone}</span>
                {" — "}
                <span className="text-[--color-text-secondary]">
                  {s.days_of_week.map((d) => d[0].toUpperCase() + d.slice(1)).join(", ")}
                </span>
                {s.label ? (
                  <span className="text-[--color-text-tertiary]"> — {s.label}</span>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => setEditing(s)}
                        className="text-sm text-[--color-accent-primary]">Edit</button>
                <button type="button" onClick={() => void onRemove(s.id)}
                        className="text-sm text-[--color-feedback-error]">Remove</button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <AddScheduleModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={async (p) => { await onCreate(p); }}
      />
      {editing ? (
        <AddScheduleModal
          open
          onClose={() => setEditing(null)}
          initial={{
            time: editing.time, timezone: editing.timezone,
            days_of_week: editing.days_of_week as any,
            label: editing.label,
          }}
          onSave={async (p) => {
            await onUpdate(editing.id, { ...p, is_enabled: true });
          }}
        />
      ) : null}
    </section>
  );
}
```

- [ ] **Step 4: Write `ScheduleManager` test**

```tsx
// frontend/src/components/earnings-update/__tests__/ScheduleManager.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ScheduleManager } from "../ScheduleManager";

describe("ScheduleManager", () => {
  it("empty state when no schedules", () => {
    render(<ScheduleManager schedules={[]} onCreate={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText(/No scan schedules/)).toBeInTheDocument();
  });

  it("lists schedules", () => {
    render(<ScheduleManager
      schedules={[{ id: "s1", time: "06:00", timezone: "America/New_York",
                    days_of_week: ["mon", "tue"], label: "Pre", is_enabled: true }]}
      onCreate={vi.fn()} onUpdate={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.getByText(/06:00/)).toBeInTheDocument();
    expect(screen.getByText(/Pre/)).toBeInTheDocument();
  });

  it("remove fires onRemove with id", () => {
    const onRemove = vi.fn();
    render(<ScheduleManager
      schedules={[{ id: "s1", time: "06:00", timezone: "UTC",
                    days_of_week: ["mon"], label: "x", is_enabled: true }]}
      onCreate={vi.fn()} onUpdate={vi.fn()} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    expect(onRemove).toHaveBeenCalledWith("s1");
  });
});
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/AddScheduleModal.test.tsx src/components/earnings-update/__tests__/ScheduleManager.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/earnings-update/AddScheduleModal.tsx \
        frontend/src/components/earnings-update/ScheduleManager.tsx \
        frontend/src/components/earnings-update/__tests__/AddScheduleModal.test.tsx \
        frontend/src/components/earnings-update/__tests__/ScheduleManager.test.tsx
git commit -m "feat(frontend): ScheduleManager + AddScheduleModal"
```

---

### Task 21: Frontend — `ReportSettingsModal` + `CustomSectionRow`

Mirrors the shape of Plan 14 `ReportSettingsModal` but with a single-mode layout: one section list + report-length toggle + custom sections editor. Persists via `useEuConfig`.

**Files:**
- Create: `frontend/src/components/earnings-update/CustomSectionRow.tsx`
- Create: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`
- Test: `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportSettingsModal } from "../ReportSettingsModal";

const baseConfig = {
  report_length: "normal" as const,
  enabled_section_ids: ["quick_take", "key_financials"],
  custom_sections: [],
};

describe("ReportSettingsModal", () => {
  it("renders all 8 section toggles", () => {
    render(<ReportSettingsModal open config={baseConfig} onClose={() => {}} onSave={async () => {}} />);
    expect(screen.getAllByRole("checkbox").length).toBeGreaterThanOrEqual(8);
  });

  it("toggles include/exclude a section", () => {
    render(<ReportSettingsModal open config={baseConfig} onClose={() => {}} onSave={async () => {}} />);
    const box = screen.getByLabelText(/Quick Take/i) as HTMLInputElement;
    expect(box.checked).toBe(true);
    fireEvent.click(box);
    expect(box.checked).toBe(false);
  });

  it("saves with new selections and length", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ReportSettingsModal open config={baseConfig} onClose={() => {}} onSave={onSave} />);
    fireEvent.click(screen.getByLabelText(/elaborative/i));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const payload = onSave.mock.calls[0][0];
    expect(payload.report_length).toBe("elaborative");
  });

  it("adds a custom section", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(<ReportSettingsModal open config={baseConfig} onClose={() => {}} onSave={onSave} />);
    fireEvent.click(screen.getByRole("button", { name: /\+ custom section/i }));
    const rows = screen.getAllByPlaceholderText(/section title/i);
    fireEvent.change(rows[rows.length - 1], { target: { value: "Model update" } });
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].custom_sections[0].title).toBe("Model update");
  });
});
```

- [ ] **Step 2: Write `CustomSectionRow`**

```tsx
// frontend/src/components/earnings-update/CustomSectionRow.tsx
import { X } from "lucide-react";

import { CustomSection } from "../../api/earnings-update";

interface Props {
  value: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ value, onChange, onRemove }: Props) {
  return (
    <div className="flex items-start gap-2 p-2 border border-[--color-border-subtle] rounded-[--radius-md] mb-2">
      <div className="flex-1 flex flex-col gap-2">
        <input
          placeholder="Section title"
          value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })}
          className="bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm"
        />
        <textarea
          placeholder="Description (optional — feeds the LLM)"
          value={value.description}
          onChange={(e) => onChange({ ...value, description: e.target.value })}
          className="bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 py-1 text-sm min-h-[44px]"
        />
      </div>
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove custom section"
        className="p-1 text-[--color-text-tertiary] hover:text-[--color-feedback-error]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
```

- [ ] **Step 3: Write `ReportSettingsModal`**

```tsx
// frontend/src/components/earnings-update/ReportSettingsModal.tsx
import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import { CustomSection, EuConfig, ReportLength } from "../../api/earnings-update";
import {
  DEFAULT_EU_SECTIONS,
  EU_SECTION_CATALOG,
} from "../../lib/earnings-update/section-catalog";

import { CustomSectionRow } from "./CustomSectionRow";

interface Props {
  open: boolean;
  config: EuConfig;
  onClose: () => void;
  onSave: (next: EuConfig) => Promise<void>;
}

const LENGTHS: ReportLength[] = ["concise", "normal", "elaborative"];

function randomId(): string {
  return `custom_${Math.random().toString(36).slice(2, 8)}_${Date.now().toString(36)}`;
}

export function ReportSettingsModal({ open, config, onClose, onSave }: Props) {
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [enabled, setEnabled] = useState<Set<string>>(new Set(config.enabled_section_ids));
  const [customs, setCustoms] = useState<CustomSection[]>(config.custom_sections);
  const [saving, setSaving] = useState(false);

  const defaultRows = useMemo(
    () => DEFAULT_EU_SECTIONS.map((id) => ({
      id, title: EU_SECTION_CATALOG[id].title, description: EU_SECTION_CATALOG[id].description,
    })),
    [],
  );

  function toggle(id: string) {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function addCustom() {
    setCustoms((prev) => [...prev, { id: randomId(), title: "", description: "" }]);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: EuConfig = {
        report_length: length,
        enabled_section_ids: [
          ...DEFAULT_EU_SECTIONS.filter((id) => enabled.has(id)),
          ...customs.map((c) => c.id),
        ],
        custom_sections: customs.filter((c) => c.title.trim()),
      };
      await onSave(payload);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (\!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] max-h-[85vh] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg overflow-y-auto">
          <Dialog.Title className="text-lg font-semibold mb-4">Report Settings</Dialog.Title>

          <section className="mb-4">
            <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em] mb-2">Report Length</h4>
            <div className="flex gap-2">
              {LENGTHS.map((l) => (
                <label key={l} className="text-sm flex items-center gap-1">
                  <input
                    type="radio"
                    name="length"
                    checked={length === l}
                    onChange={() => setLength(l)}
                    aria-label={l}
                  />
                  {l[0].toUpperCase() + l.slice(1)}
                </label>
              ))}
            </div>
          </section>

          <section className="mb-4">
            <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em] mb-2">Sections</h4>
            {defaultRows.map((row) => (
              <label key={row.id} className="flex items-start gap-2 text-sm mb-2">
                <input
                  type="checkbox"
                  aria-label={row.title}
                  checked={enabled.has(row.id)}
                  onChange={() => toggle(row.id)}
                />
                <span>
                  <strong>{row.title}</strong>
                  <span className="text-[--color-text-secondary]"> — {row.description}</span>
                </span>
              </label>
            ))}
          </section>

          <section className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em]">Custom Sections</h4>
              <button type="button" onClick={addCustom}
                      className="text-sm text-[--color-accent-primary]">+ Custom Section</button>
            </div>
            {customs.map((c, idx) => (
              <CustomSectionRow
                key={c.id}
                value={c}
                onChange={(next) => setCustoms((prev) => prev.map((x, i) => (i === idx ? next : x)))}
                onRemove={() => setCustoms((prev) => prev.filter((_, i) => i \!== idx))}
              />
            ))}
          </section>

          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose}
                    className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]">
              Cancel
            </button>
            <button type="button" onClick={() => void handleSave()} disabled={saving}
                    className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50">
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/earnings-update/ReportSettingsModal.tsx \
        frontend/src/components/earnings-update/CustomSectionRow.tsx \
        frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx
git commit -m "feat(frontend): EU ReportSettingsModal + CustomSectionRow"
```

---

### Task 22: Frontend — `EarningsUpdatePage` composition

Assemble the full page: header + WatchlistRow + RecentReportsList + (optional) ScheduleManager + ReportSettingsModal + OnDemandReportModal + EUCabinetView overlay.

**Files:**
- Create: `frontend/src/pages/EarningsUpdatePage.tsx`
- Modify: `frontend/src/routes.tsx` (register `/earnings-update`)
- Test: `frontend/src/pages/__tests__/EarningsUpdatePage.test.tsx`

- [ ] **Step 1: Write the failing page test**

```tsx
// frontend/src/pages/__tests__/EarningsUpdatePage.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../api/earnings-update";
import { EarningsUpdatePage } from "../EarningsUpdatePage";

describe("EarningsUpdatePage", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("renders header + watchlist + reports sections", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({ reports: [] });
    vi.spyOn(api, "fetchSchedules").mockResolvedValue({ schedules: [] });
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal", enabled_section_ids: [], custom_sections: [],
    });
    render(<EarningsUpdatePage />);
    expect(screen.getByText(/Earnings Updates/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Watchlist/i)).toBeInTheDocument();
      expect(screen.getByText(/Recent Reports/i)).toBeInTheDocument();
    });
  });

  it("opens on-demand modal when header button clicked", async () => {
    vi.spyOn(api, "fetchWatchlist").mockResolvedValue({ entries: [] });
    vi.spyOn(api, "fetchRecentReports").mockResolvedValue({ reports: [] });
    vi.spyOn(api, "fetchSchedules").mockResolvedValue({ schedules: [] });
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal", enabled_section_ids: [], custom_sections: [],
    });
    render(<EarningsUpdatePage />);
    fireEvent.click(await screen.findByRole("button", { name: /on-demand report/i }));
    expect(await screen.findByText(/On-Demand Earnings Update/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the page**

```tsx
// frontend/src/pages/EarningsUpdatePage.tsx
import { useState } from "react";
import { Plus, Settings as SettingsIcon } from "lucide-react";

import { startOnDemandReport } from "../api/earnings-update";
import { EUCabinetView } from "../components/earnings-update/EUCabinetView";
import { OnDemandReportModal } from "../components/earnings-update/OnDemandReportModal";
import { RecentReportsList } from "../components/earnings-update/RecentReportsList";
import { ReportSettingsModal } from "../components/earnings-update/ReportSettingsModal";
import { ScheduleManager } from "../components/earnings-update/ScheduleManager";
import { WatchlistRow } from "../components/earnings-update/WatchlistRow";
import { useEuConfig } from "../hooks/useEuConfig";
import { useEuReports } from "../hooks/useEuReports";
import { useEuSchedules } from "../hooks/useEuSchedules";
import { useEuWatchlist } from "../hooks/useEuWatchlist";
import { useFileViewer } from "../components/FileViewer/FileViewerContext";

export function EarningsUpdatePage() {
  const { entries, add, remove } = useEuWatchlist();
  const { reports, refresh: refreshReports } = useEuReports(5);
  const { schedules, create, update, remove: removeSched } = useEuSchedules();
  const { config, save: saveConfig } = useEuConfig();

  const [cabinetOpen, setCabinetOpen] = useState(false);
  const [onDemandOpen, setOnDemandOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const fv = useFileViewer();

  function openReport(id: string) {
    fv.openReport(id);
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex items-center justify-between border-b border-[--color-border-subtle] px-6 flex-shrink-0">
        <h1 className="text-xl font-semibold">Earnings Updates</h1>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            aria-label="Report settings"
            className="text-[--color-text-secondary] hover:text-[--color-text-primary] p-1"
          >
            <SettingsIcon size={18} />
          </button>
          <button
            type="button"
            onClick={() => setOnDemandOpen(true)}
            className="flex items-center gap-1 bg-[--color-accent-primary] text-white text-sm px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover]"
          >
            <Plus size={16} /> On-Demand Report
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-y-auto">
        <WatchlistRow entries={entries} onAdd={add} onRemove={remove} />
        <div className="border-t border-[--color-border-subtle]" />
        <RecentReportsList
          reports={reports}
          onOpenReport={openReport}
          onOpenCabinet={() => setCabinetOpen(true)}
        />
        <div className="border-t border-[--color-border-subtle]" />
        <ScheduleManager
          schedules={schedules}
          onCreate={create}
          onUpdate={update}
          onRemove={removeSched}
        />
      </div>

      <OnDemandReportModal
        open={onDemandOpen}
        onClose={() => setOnDemandOpen(false)}
        startReport={startOnDemandReport}
        onReportReady={(r) => { void refreshReports(); fv.openReport(r.report_id); }}
      />
      {cabinetOpen ? (
        <EUCabinetView
          reports={reports}
          onBack={() => setCabinetOpen(false)}
          onOpenReport={openReport}
          onDownload={(id) => fv.downloadReport(id)}
          onRemove={async (_id) => { /* future: DELETE /api/reports/:id */ }}
        />
      ) : null}
      {settingsOpen && config ? (
        <ReportSettingsModal
          open
          config={config}
          onClose={() => setSettingsOpen(false)}
          onSave={async (next) => { await saveConfig(next); }}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 3: Register the route**

In `frontend/src/routes.tsx`, add:

```tsx
import { EarningsUpdatePage } from "./pages/EarningsUpdatePage";

// inside the route tree:
<Route path="earnings-update" element={<EarningsUpdatePage />} />
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/pages/__tests__/EarningsUpdatePage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/EarningsUpdatePage.tsx \
        frontend/src/pages/__tests__/EarningsUpdatePage.test.tsx \
        frontend/src/routes.tsx
git commit -m "feat(frontend): EarningsUpdatePage composition + route registration"
```

---

### Task 23: Manual smoke test + README flip

- [ ] **Step 1: Apply migration**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: no errors.

- [ ] **Step 2: Run the server**

```bash
uv run openlia serve
```

- [ ] **Step 3: Run the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 4: Manual checks**

1. Navigate to `/earnings-update` — page loads with empty watchlist and empty reports state.
2. Click "+ Add Ticker", enter `AAPL`. Verify a card appears with next earnings date populated.
3. Duplicate-add `AAPL` — expect a `409` message inline.
4. Add `ZZZZ` — expect a `404`/not-found message.
5. Open "+ On-Demand Report", enter `AAPL`, click Generate. Verify the SSE stream lands a complete report and the page's Recent Reports section picks it up on refresh.
6. Click "Open Cabinet →". Verify full list appears, grouped by month. Search for "AAPL".
7. Open "Report Settings" (gear icon). Uncheck "Earnings Call", change length to "concise". Save. Reopen — selections persisted.
8. Open "Scan Schedules", add `06:00 America/New_York Mon-Fri — Pre-Market Scan`. Verify the row appears.
9. Trigger the scheduler manually via CLI (`openlia jobs run --type eu_scan --user me`) if available, OR wait for the cron fire. Verify a report gets generated for any ticker with a new earnings release since `last_run_at`, and a notification dot appears on the sidebar.

- [ ] **Step 5: Flip README row to "Draft"**

Edit `planning/implementation-plans/README.md`, change the Plan 15 row from:

```
| 15 | 5 | Earnings Update department (watchlist + scan scheduling) | Not started | — |
```

to:

```
| 15 | 5 | Earnings Update department (watchlist + scan scheduling) | Draft | `2026-04-17-phase-15-earnings-update.md` |
```

- [ ] **Step 6: Commit**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs: mark Plan 15 (Earnings Update) as Draft"
```

---

## Self-Review

### Spec coverage

- **Watchlist (add/remove/display + next-earnings scheduling cache):** Tasks 3, 6, 10, 17. Add-time cache + nightly refresh from Plan 6 maintenance sweep.
- **Recent Reports + EU Cabinet (full list + search + filter + group by month):** Tasks 13, 18, 22.
- **On-Demand Report flow:** Tasks 9, 13, 19, 22.
- **Automated reports via schedule:** Tasks 8, 14. `EuScanPlannerImpl` fulfills the Plan 6 `EUScanPlanner` Protocol; `build_scheduler_service(eu_planner=...)` injection wires it at startup. Plan 6 owns the executor/notification/error paths.
- **Sections + length + custom sections (Page Settings):** Tasks 3, 5, 11, 21.
- **Scan Schedules UI (CRUD mirroring MB pattern):** Tasks 7, 12, 20.
- **Notification dot (sidebar):** Owned by Plan 6's executor writing to `user_notifications`, consumed by Plan 8's `NotificationBadge`. This plan doesn't re-implement notification plumbing.
- **Overdue "Date passed" state:** `WatchlistCard` checks `isPast(next_earnings_date)` (Task 17).
- **Report framework (8 sections):** Already relocated to core in Plan 13. The catalog (Task 16) holds titles/descriptions; the framework JSON holds LLM instructions.

### Placeholder scan

Searched each step: every code block is fully written; every test case names a concrete assertion; every commit command lists explicit paths. The single exception noted is the **SSE helper in Task 15** — the `EventSource` usage is a stand-in for the shared SSE helper (fetch+ReadableStream) that other department pages use. The plan is explicit about this being a note to consult the existing helper before finalizing. No `TODO`, `TBD`, `implement later`, `handle edge cases`, or hand-wave steps elsewhere.

### Type consistency

- `EarningsUpdateMode = Literal["earnings_analysis"]` (core, Task 1) ↔ `mode="earnings_analysis"` in `ReportRequest` (server Tasks 8, 9).
- `report_length` is `Literal["concise", "normal", "elaborative"]` in Python (Task 5) ↔ `ReportLength` TS union (Task 15) ↔ frontend radio/toggle labels (Task 21).
- `CustomSection` shape `{id, title, description}` matches between server Pydantic `_CustomSectionIn` (Task 11), DB JSON column (Task 3), frontend `CustomSection` interface (Task 15), and `CustomSectionRow` component (Task 21).
- `EuSchedule` TS type (Task 15) matches the `_ScheduleOut` Pydantic model (Task 12): `id/time/timezone/days_of_week/label/is_enabled`.
- `WatchlistEntry` columns match across `EuWatchlistEntry` SQLAlchemy model (Task 3), `_WatchlistEntryOut` Pydantic (Task 10), and TS `WatchlistEntry` (Task 15).
- `release_timing` is `pre_market` | `post_market` | null everywhere; the DB `CheckConstraint` enforces it, and the frontend card renders only those two badge variants.

### Cross-plan consistency

- `DEPARTMENT_DEFAULT_TIERS["earnings_update"] = EVERYDAY` from Plan 4 matches `EarningsUpdateDepartment.tier_for()` returning `"everyday"` (Task 1).
- `eu_schedules` table is owned by Plan 1B; Plan 15 writes to it but does not redefine it.
- `EUScanPlanner` Protocol signature `plan(session, user_id, schedule_id, since) -> list[EUScanTarget]` (Plan 6) is implemented exactly in Task 8. `EUScanTarget(ticker, request)` dataclass matches.
- `ReportRequest` fields used in Task 8 (`mode, user_input, enabled_sections, custom_sections, report_length`) match the Plan 14 ER plan — which confirms Plan 5's `ReportRequest` was already extended with `custom_sections` + `report_length`. If Plan 5 did not ship those fields, Task 8 Step 3 notes the mismatch and the executor should update `packages/core/src/openlia/llm/runtime/messages.py`.
- `report_store.save_from_event(user_id, department, report_type, event)` (Task 9) matches Plan 13's `report_store` API.
- Framework files `earnings_update.json` + `earnings_update_style_guide.md` are relocated to `packages/core/src/openlia/reports/frameworks/` by Plan 13.
