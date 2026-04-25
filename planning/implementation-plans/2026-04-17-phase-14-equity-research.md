# Equity Research Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-20 normalizations (apply before executing this plan):**
> - Runtime imports: `from openlia.llm.runtime.messages import ReportRequest`, `from openlia.llm.runtime.events import to_wire`. Reject any `openlia.runtime.*` or `serialize_sse` references.
> - `ReportRequest.length` uses the Plan 5 enum `("brief", "standard", "long")`. `er_user_configs.report_length` may use department-local values (`concise`/`normal`/`elaborative`) — map at the call site when invoking `ReportRunner`; do not retrofit Plan 5.
> - `ReportStart` / `ReportComplete` field lists are frozen (see Plan 13 normalizations). Title lives in `schema["title"]`.
> - All IDs are UUID strings — `user_id`, `report_id`, `session_id` — at DTO, path, and FK level.
> - Auth + DB: router-factory `build_require_auth(...)`, `db_session_factory`. Models from `openlia_server.db.models.auth` / `.content` / `.config`. No `current_user`/`get_db_session` helpers assumed.

**Goal:** Ship the Equity Research department (three report modes: Stock Initiation, Stock Update, Sector Research) on top of the Plan 13 report pipeline, with per-user section/length configuration, a chat surface for follow-up questions, and a settings modal that matches the spec.

**Architecture:**
- **Core** gets a single `equity_research.yaml` prompt that branches by `mode` + `report_length` via Jinja, plus an `EquityResearchDepartment` class that advertises its data requirements and tier to `ReportRunner`/`ChatRunner` from Plan 5. The three framework JSONs + style guides already live at `packages/core/src/openlia/reports/frameworks/` after Plan 13.
- **Server** adds a new `er_user_configs` table (one row per user) for report mode, report length, sections-per-mode, and custom-sections-per-mode, a config service, and three authenticated routes: `GET/PUT /departments/equity-research/config`, `POST /departments/equity-research/report` (SSE, calls `ReportRunner`, persists the resulting `ReportSchema` to `reports`), and `POST /departments/equity-research/chat` (SSE, calls `ChatRunner` for follow-ups). Frontend reaches these via `/api/...` through the Vite proxy (Plan 0 rewrite strips `/api`).
- **Frontend** ships `EquityResearchPage` with a Welcome state (suggestion chips + "From Portfolio" picker) and an Active state (chat + report cards), a `ReportSettingsModal` that switches sections per mode and supports custom sections, and a `ReportCard` chat block that opens the generated report in the Plan 12 `FileViewer`.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic.
- Frontend: React 18 + TypeScript strict, Framer Motion, react-router-dom, Radix UI primitives (`Dialog`, `Popover`, `ToggleGroup`), Zod.

**Dependencies:**
- Plan 1A: `reports`, `chat_sessions`, `chat_messages`, `portfolio_holdings` tables.
- Plan 2: session middleware (all endpoints authenticated).
- Plan 3: data requirement adapters for `stock_quote`, `company_profile`, `financial_statements`, `company_news`, `historical_prices`, `analyst_ratings`, `insider_transactions`, `earnings_data`.
- Plan 4: LLM provider system (Thinking tier — full initiation/sector picks it up; Everyday for Stock Update + chat follow-ups).
- Plan 5: `ChatRunner`, `ReportRunner`, prompt loader, SSE event taxonomy, `ReportRequest`.
- Plan 8: frontend shell (routing, auth context, design tokens, `FileViewerProvider`).
- Plan 12: `ChatInterface`, `useChatStream`, `FileViewerContext`, `SaveToRepoButton`, `FileDownloadButton`.
- Plan 13: `ReportSchema`, `assembler`, `validator`, framework loader, `report_store`, `/api/reports/{id}` endpoint, `ReportRenderer`, `ReportCard` file viewer integration, `RedirectCard` pattern.

---

## Design Rules

1. **Mode is selected server-side at request time.** The client sends `{ mode, user_input, session_id? }`. The server reads the per-user config to resolve `enabled_sections` + `custom_sections` + `report_length`, then passes everything into `ReportRunner`. Clients do not hand-assemble framework instructions.
2. **Sections-per-mode persist independently.** A user who unchecks "Risk Analysis" for Stock Initiation must still see all seven Stock Update sections on by default.
3. **Custom sections are per-mode.** They carry `{id, title, description}`. `id` is `custom_<slug>_<random>`; `title` is required; `description` is optional but feeds the LLM.
4. **Report length is a single global knob.** Concise / Normal / Elaborative. One value per user, applied to all three modes. Prompt injects a sentence accordingly.
5. **Follow-up chat shares the chat session.** After a report is generated, further messages land in the same `chat_session` row. Generating a new report forks a new session only if the user types a new ticker + clicks "generate report" again (the UI surfaces the "New report" action explicitly).
6. **Tier selection follows the spec's implicit rule:** initiation + sector research use Thinking (deep, long); stock update + chat follow-ups use Everyday. This is encoded in `EquityResearchDepartment.tier_for(mode)`.
7. **Framework files are read-only inside the core package.** User customization (enabled/custom sections, report_length) is layered on top inside the `load_framework_customized()` helper — the JSON on disk never mutates.
8. **One `reports` row per generation.** Saved automatically on `report.complete`. The save-to-repo dialog just flips `is_starred` + updates `tags`.
9. **TDD everywhere.** Every production file lands with a failing test, then implementation, then a green run, then a commit.
10. **No placeholders.** Every step contains real code, a real command, and a real expected output.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
prompts/
└── equity_research.yaml               # single prompt; branches by mode + length
departments/
└── equity_research.py                 # EquityResearchDepartment — data requirements, tier-per-mode
reports/
└── frameworks/
    ├── loader.py                      # MODIFY — add load_framework_customized()
```

### Server (`packages/server/src/openlia_server/`)

```
db/
├── models/
│   └── departments.py                 # ErUserConfig model
└── migrations/versions/
    └── 2026-04-17-2100_er_user_configs.py
services/
├── equity_research_config.py          # get/update per-user config; defaults
└── equity_research_runner.py          # thin orchestrator: config + ReportRunner + report_store
routes/departments/
└── equity_research.py                 # /config (GET/PUT), /report (POST SSE), /chat (POST SSE)
```

### Frontend (`frontend/src/`)

```
api/
└── equity-research.ts                 # fetchErConfig, updateErConfig, startReport, startChat
pages/
└── EquityResearchPage.tsx             # Welcome + Active shell
components/equity-research/
├── SuggestionChips.tsx                # AAPL/TSLA/NVDA/MSFT + From Portfolio
├── FromPortfolioPicker.tsx            # Popover with portfolio tickers
├── ReportSettingsModal.tsx            # Report Mode + Length + Sections + Custom Sections
├── CustomSectionRow.tsx               # Inline add/edit row
├── ModeToggle.tsx                     # Reusable segmented control
└── ReportCard.tsx                     # Chat-inline report thumbnail
hooks/
└── useErConfig.ts                     # SWR-style hook, invalidates on save
```

---

## Task Overview

1. Core — `EquityResearchDepartment` class (data requirements, tier-per-mode).
2. Core — `equity_research.yaml` prompt (branches by mode + length).
3. Core — `load_framework_customized()` helper (sections filter + custom sections).
4. Server — `er_user_configs` SQLAlchemy model.
5. Server — Alembic migration for `er_user_configs`.
6. Server — `equity_research_config` service.
7. Server — `GET/PUT /departments/equity-research/config` routes.
8. Server — `equity_research_runner` orchestrator service.
9. Server — `POST /departments/equity-research/report` SSE route.
10. Server — `POST /departments/equity-research/chat` SSE route.
11. Frontend — `api/equity-research.ts` typed client.
12. Frontend — `useErConfig` hook + `ModeToggle` primitive.
13. Frontend — `ReportSettingsModal` + `CustomSectionRow`.
14. Frontend — `SuggestionChips` + `FromPortfolioPicker`.
15. Frontend — `ReportCard` chat block.
16. Frontend — `EquityResearchPage` composition.
17. Manual smoke test + flip README row to Draft.

---

### Task 1: Core — `EquityResearchDepartment` class

The department advertises: name, display name, prompt name, per-mode tier mapping, data requirement lists, and the three valid modes.

**Files:**
- Create: `packages/core/src/openlia/departments/equity_research.py`
- Modify: `packages/core/src/openlia/departments/__init__.py` (export)
- Test: `packages/core/tests/departments/test_equity_research.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_equity_research.py
import pytest

from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)


def test_er_identifies_itself():
    d = EquityResearchDepartment()
    assert d.name == "equity_research"
    assert d.display_name == "Equity Research"
    assert d.prompt_name == "equity_research"


def test_er_exposes_three_modes():
    modes = set(EquityResearchDepartment().valid_modes)
    assert modes == {"stock_initiation", "stock_update", "sector_research"}


def test_er_tier_per_mode_matches_spec():
    d = EquityResearchDepartment()
    assert d.tier_for("stock_initiation") == "thinking"
    assert d.tier_for("sector_research") == "thinking"
    assert d.tier_for("stock_update") == "everyday"


def test_er_tier_for_unknown_mode_raises():
    with pytest.raises(ValueError):
        EquityResearchDepartment().tier_for("bogus")


def test_er_basic_data_requirements():
    reqs = EquityResearchDepartment().data_requirement_types
    assert "stock_quote" in reqs
    assert "company_profile" in reqs
    assert "financial_statements" in reqs


def test_er_optional_data_requirements():
    soft = EquityResearchDepartment().optional_requirement_types
    for name in (
        "company_news",
        "historical_prices",
        "analyst_ratings",
        "insider_transactions",
        "earnings_data",
    ):
        assert name in soft


def test_er_has_no_extra_tools_by_default():
    # All tool calls come from requirement mapping + runtime meta-tools.
    assert EquityResearchDepartment().extra_tools == ()


def test_er_framework_name_per_mode():
    d = EquityResearchDepartment()
    assert d.framework_name("stock_initiation") == "stock_initiation"
    assert d.framework_name("stock_update") == "stock_update"
    assert d.framework_name("sector_research") == "sector_research"


def test_er_mode_literal_type_import():
    # Type-level contract: EquityResearchMode is a Literal of the three modes.
    from typing import get_args

    assert set(get_args(EquityResearchMode)) == {
        "stock_initiation",
        "stock_update",
        "sector_research",
    }
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_equity_research.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments.equity_research'`.

- [ ] **Step 3: Write the department class**

```python
# packages/core/src/openlia/departments/equity_research.py
"""Equity Research — report-producing department with three modes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier


EquityResearchMode = Literal[
    "stock_initiation",
    "stock_update",
    "sector_research",
]


@dataclass(frozen=True)
class EquityResearchDepartment:
    name: str = "equity_research"
    display_name: str = "Equity Research"
    prompt_name: str = "equity_research"
    data_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "company_profile",
        "financial_statements",
    )
    optional_requirement_types: tuple[str, ...] = (
        "company_news",
        "historical_prices",
        "analyst_ratings",
        "insider_transactions",
        "earnings_data",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()

    @property
    def valid_modes(self) -> tuple[EquityResearchMode, ...]:
        return ("stock_initiation", "stock_update", "sector_research")

    def tier_for(self, mode: str) -> Tier:
        if mode in ("stock_initiation", "sector_research"):
            return "thinking"
        if mode == "stock_update":
            return "everyday"
        raise ValueError(f"unknown equity_research mode: {mode!r}")

    def framework_name(self, mode: str) -> str:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown equity_research mode: {mode!r}")
        return mode
```

- [ ] **Step 4: Export from `departments/__init__.py`**

Edit `packages/core/src/openlia/departments/__init__.py` to append:

```python
from openlia.departments.equity_research import (
    EquityResearchDepartment,
    EquityResearchMode,
)

__all__ = [
    "Department",
    "SecretaryDepartment",
    "EquityResearchDepartment",
    "EquityResearchMode",
]
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/core/tests/departments/test_equity_research.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/departments/equity_research.py \
        packages/core/src/openlia/departments/__init__.py \
        packages/core/tests/departments/test_equity_research.py
git commit -m "feat(equity-research): add department class with mode-aware tier selection"
```

---

### Task 2: Core — `equity_research.yaml` prompt

Single prompt file. `{{ mode }}` drives which framework instructions the runtime loads (via `ReportRunner`); the prompt only injects the section list + custom sections + length directive and the role preamble.

**Files:**
- Create: `packages/core/src/openlia/prompts/equity_research.yaml`
- Test: `packages/core/tests/prompts/test_equity_research_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/prompts/test_equity_research_prompt.py
from pathlib import Path

import jinja2
import pytest
import yaml


PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "src/openlia/prompts/equity_research.yaml"
)


@pytest.fixture
def prompt_data() -> dict:
    return yaml.safe_load(PROMPT_PATH.read_text())


def test_prompt_has_system_and_user(prompt_data):
    assert "system" in prompt_data
    assert "user" in prompt_data


def test_system_mentions_three_modes(prompt_data):
    sys = prompt_data["system"].lower()
    for mode in ("stock initiation", "stock update", "sector research"):
        assert mode in sys


def test_system_renders_with_mode_and_length():
    env = jinja2.Environment()
    tmpl = env.from_string(yaml.safe_load(PROMPT_PATH.read_text())["system"])
    rendered = tmpl.render(
        mode="stock_initiation",
        report_length="concise",
        enabled_sections=[
            {"id": "company_overview", "title": "Company Overview"},
        ],
        custom_sections=[
            {"id": "custom_esg_x1", "title": "ESG Footnote", "description": "Short ESG note."},
        ],
    )
    assert "Company Overview" in rendered
    assert "ESG Footnote" in rendered
    assert "concise" in rendered.lower() or "short" in rendered.lower()


def test_user_template_renders_user_input():
    env = jinja2.Environment()
    tmpl = env.from_string(yaml.safe_load(PROMPT_PATH.read_text())["user"])
    rendered = tmpl.render(user_input="Initiate coverage on AAPL")
    assert "AAPL" in rendered


def test_length_directive_switches_on_elaborative():
    env = jinja2.Environment()
    tmpl = env.from_string(yaml.safe_load(PROMPT_PATH.read_text())["system"])
    concise = tmpl.render(
        mode="stock_update",
        report_length="concise",
        enabled_sections=[],
        custom_sections=[],
    )
    elaborative = tmpl.render(
        mode="stock_update",
        report_length="elaborative",
        enabled_sections=[],
        custom_sections=[],
    )
    assert concise != elaborative
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/prompts/test_equity_research_prompt.py -v`
Expected: FAIL with `FileNotFoundError` for `equity_research.yaml`.

- [ ] **Step 3: Write the prompt file**

```yaml
# packages/core/src/openlia/prompts/equity_research.yaml
system: |
  You are OpenLIA Equity Research — a senior sell-side analyst covering public
  companies and industry sectors. You write report sections that look like
  professional investment-bank research (Goldman Sachs, Morgan Stanley, HSBC,
  Citi, KGI). You are currently generating a "{{ mode }}" report.

  Report modes available to this department:
  - stock_initiation — full company initiation (up to 13 sections).
  - stock_update — event or earnings note (up to 7 sections).
  - sector_research — sector or thematic analysis (up to 8 sections).

  Writing rules:
  - Thesis-first. Lead with the conclusion, then evidence.
  - Every claim cites at least one number. Never invent numbers — pull them via
    the data-requirement tools before writing.
  - Quote management in indirect speech.
  - Inline comparisons with QoQ / YoY and estimate deltas.
  - Use markdown only. Tables, lists, and code fences are allowed. No HTML.
  - Directional cell formatting uses the table renderer's `cell_style` — emit
    blocks, not inline colors.

  Length directive: produce a {{ report_length }} report. If "concise", keep
  sections tight (2-4 paragraphs per narrative section, no redundant tables).
  If "normal", use the framework's default density. If "elaborative", expand
  every section with an extra paragraph of context and add optional supporting
  tables or charts when they clarify the thesis.

  You MUST fill these sections (and no others), in the order given:
  {% for s in enabled_sections %}- {{ s.title }} (id: {{ s.id }})
  {% endfor %}
  {% if custom_sections %}
  You MUST also add these user-defined custom sections after the last framework
  section:
  {% for c in custom_sections %}- {{ c.title }} (id: {{ c.id }}){% if c.description %} — {{ c.description }}{% endif %}
  {% endfor %}
  {% endif %}
  For each section, consult the framework JSON instructions the runtime injects
  into the tool envelope. Do not write sections the user disabled. Do not add
  sections outside this list.

user: |
  {{ user_input }}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/core/tests/prompts/test_equity_research_prompt.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/equity_research.yaml \
        packages/core/tests/prompts/test_equity_research_prompt.py
git commit -m "feat(equity-research): add prompt template with mode + length + section list"
```

---

### Task 3: Core — `load_framework_customized()`

Plan 13 ships `load_framework(name) -> dict` that returns the raw framework JSON. Equity Research needs the user's filtered-and-appended view. Add `load_framework_customized(name, enabled_section_ids, custom_sections)` that returns a new dict with only the enabled sections, in original order, followed by the custom sections.

**Files:**
- Modify: `packages/core/src/openlia/reports/frameworks/loader.py`
- Test: `packages/core/tests/reports/test_framework_customization.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/reports/test_framework_customization.py
import pytest

from openlia.reports.frameworks.loader import (
    load_framework,
    load_framework_customized,
    CustomSection,
)


def test_customized_preserves_original_order():
    framework = load_framework("stock_update")
    original_ids = [s["id"] for s in framework["sections"]]
    enabled = {original_ids[2], original_ids[0]}  # out-of-order input
    result = load_framework_customized(
        "stock_update", enabled_section_ids=enabled, custom_sections=()
    )
    result_ids = [s["id"] for s in result["sections"]]
    assert result_ids == [original_ids[0], original_ids[2]]


def test_customized_appends_custom_sections_last():
    framework = load_framework("stock_update")
    first_id = framework["sections"][0]["id"]
    custom = (
        CustomSection(id="custom_esg_x1", title="ESG Footnote", description="Short note."),
    )
    result = load_framework_customized(
        "stock_update",
        enabled_section_ids={first_id},
        custom_sections=custom,
    )
    ids = [s["id"] for s in result["sections"]]
    assert ids[-1] == "custom_esg_x1"
    assert result["sections"][-1]["title"] == "ESG Footnote"
    assert "Short note." in result["sections"][-1]["instructions"]


def test_customized_rejects_unknown_section_id():
    with pytest.raises(ValueError, match="unknown section"):
        load_framework_customized(
            "stock_update",
            enabled_section_ids={"does_not_exist"},
            custom_sections=(),
        )


def test_customized_empty_enabled_keeps_only_customs():
    custom = (
        CustomSection(id="custom_only_x1", title="Only Custom", description=None),
    )
    result = load_framework_customized(
        "stock_update",
        enabled_section_ids=set(),
        custom_sections=custom,
    )
    assert [s["id"] for s in result["sections"]] == ["custom_only_x1"]


def test_customized_does_not_mutate_cached_framework():
    before = load_framework("stock_update")
    before_count = len(before["sections"])
    load_framework_customized(
        "stock_update",
        enabled_section_ids=set(),
        custom_sections=(CustomSection(id="custom_q_x1", title="Q", description="r"),),
    )
    after = load_framework("stock_update")
    assert len(after["sections"]) == before_count


def test_customized_preserves_cover_and_top_level_keys():
    framework = load_framework("stock_initiation")
    first_id = framework["sections"][0]["id"]
    result = load_framework_customized(
        "stock_initiation",
        enabled_section_ids={first_id},
        custom_sections=(),
    )
    assert result["department"] == framework["department"]
    assert result["report_mode"] == framework["report_mode"]
    assert result["cover"] == framework["cover"]
    assert result["schema_version"] == framework["schema_version"]
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest packages/core/tests/reports/test_framework_customization.py -v`
Expected: FAIL — `load_framework_customized` / `CustomSection` not defined.

- [ ] **Step 3: Extend the loader**

Append to `packages/core/src/openlia/reports/frameworks/loader.py`:

```python
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CustomSection:
    id: str
    title: str
    description: str | None


def load_framework_customized(
    name: str,
    *,
    enabled_section_ids: set[str],
    custom_sections: Iterable[CustomSection],
) -> dict:
    """Return a copy of the framework JSON with sections filtered + extended.

    Sections in the result follow the framework's original order; custom
    sections are appended after the last enabled section. The cached framework
    dict is never mutated.
    """
    base = copy.deepcopy(load_framework(name))
    known_ids = {s["id"] for s in base["sections"]}
    unknown = enabled_section_ids - known_ids
    if unknown:
        raise ValueError(
            f"unknown section ids for framework {name!r}: {sorted(unknown)}"
        )

    kept = [s for s in base["sections"] if s["id"] in enabled_section_ids]
    for c in custom_sections:
        kept.append(
            {
                "id": c.id,
                "title": c.title,
                "instructions": c.description or "",
                "blocks": [],
            }
        )
    base["sections"] = kept
    return base
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/core/tests/reports/test_framework_customization.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks/loader.py \
        packages/core/tests/reports/test_framework_customization.py
git commit -m "feat(reports): add load_framework_customized() for per-user section selection"
```

---

### Task 4: Server — `ErUserConfig` SQLAlchemy model

One row per user. Stores: selected mode, report length, `sections_by_mode` (dict of mode -> list of enabled section ids), `custom_sections_by_mode` (dict of mode -> list of `{id, title, description}`). Deletes with the user.

**Files:**
- Create: `packages/server/src/openlia_server/db/models/departments.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`
- Test: `packages/server/tests/db/models/test_er_user_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/models/test_er_user_config.py
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import ErUserConfig


def test_er_user_config_columns(create_tables):
    insp = inspect(ErUserConfig)
    cols = {c.name: c for c in insp.columns}
    assert set(cols) >= {
        "id",
        "user_id",
        "report_mode",
        "report_length",
        "sections_by_mode",
        "custom_sections_by_mode",
        "created_at",
        "updated_at",
    }
    assert cols["user_id"].unique is True


def test_er_user_config_one_per_user(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()

    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_initiation",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c2",
            user_id="u1",
            report_mode="stock_update",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_er_user_config_cascade_on_user_delete(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_update",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    db_session.commit()

    db_session.query(User).filter(User.id == "u1").delete()
    db_session.commit()

    assert db_session.query(ErUserConfig).count() == 0


def test_er_user_config_report_mode_check_constraint(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="bogus_mode",
            report_length="normal",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_er_user_config_report_length_check_constraint(create_tables, db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    db_session.add(
        ErUserConfig(
            id="c1",
            user_id="u1",
            report_mode="stock_update",
            report_length="verbose",
            sections_by_mode={},
            custom_sections_by_mode={},
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/models/test_er_user_config.py -v`
Expected: FAIL — `openlia_server.db.models.departments` module missing.

- [ ] **Step 3: Write the model**

```python
# packages/server/src/openlia_server/db/models/departments.py
"""Per-user department configuration tables."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    JSON,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base, UTCDateTime


class ErUserConfig(Base):
    """Per-user configuration for the Equity Research department."""

    __tablename__ = "er_user_configs"
    __table_args__ = (
        CheckConstraint(
            "report_mode IN ('stock_initiation','stock_update','sector_research')",
            name="ck_er_user_configs_report_mode",
        ),
        CheckConstraint(
            "report_length IN ('concise','normal','elaborative')",
            name="ck_er_user_configs_report_length",
        ),
        Index("ix_er_user_configs_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    report_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    report_length: Mapped[str] = mapped_column(String(16), nullable=False)
    sections_by_mode: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    custom_sections_by_mode: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
```

- [ ] **Step 4: Export from `db/models/__init__.py`**

Append to `packages/server/src/openlia_server/db/models/__init__.py`:

```python
from openlia_server.db.models.departments import ErUserConfig  # noqa: F401
```

And add `"ErUserConfig"` to `__all__`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/server/tests/db/models/test_er_user_config.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/departments.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/db/models/test_er_user_config.py
git commit -m "feat(db): add er_user_configs model for equity-research per-user settings"
```

---

### Task 5: Server — Alembic migration for `er_user_configs`

Creates the table on top of the existing baseline. Downgrade drops it.

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-04-17-2100_er_user_configs.py`
- Test: `packages/server/tests/db/test_er_user_configs_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_er_user_configs_migration.py
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect


def _alembic_config(db_path: str) -> Config:
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        "packages/server/src/openlia_server/db/migrations",
    )
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_er_user_configs_created_at_head(tmp_path):
    db = tmp_path / "app.db"
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "er_user_configs" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("er_user_configs")}
    assert cols >= {
        "id",
        "user_id",
        "report_mode",
        "report_length",
        "sections_by_mode",
        "custom_sections_by_mode",
        "created_at",
        "updated_at",
    }


def test_er_user_configs_downgrade_drops_table(tmp_path):
    db = tmp_path / "app.db"
    cfg = _alembic_config(str(db))
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "-1")
    engine = create_engine(f"sqlite:///{db}")
    insp = inspect(engine)
    assert "er_user_configs" not in insp.get_table_names()
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_er_user_configs_migration.py -v`
Expected: FAIL — `er_user_configs` not in table list.

- [ ] **Step 3: Generate the migration file**

Note the previous head revision; substitute it into `down_revision` below:

```python
# packages/server/src/openlia_server/db/migrations/versions/2026-04-17-2100_er_user_configs.py
"""er_user_configs

Revision ID: 2026_04_17_2100_er
Revises: <PRIOR_HEAD_REVISION_ID>
Create Date: 2026-04-17 21:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "2026_04_17_2100_er"
down_revision = "<PRIOR_HEAD_REVISION_ID>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "er_user_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("report_mode", sa.String(length=32), nullable=False),
        sa.Column("report_length", sa.String(length=16), nullable=False),
        sa.Column("sections_by_mode", sa.JSON(), nullable=False),
        sa.Column("custom_sections_by_mode", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "report_mode IN ('stock_initiation','stock_update','sector_research')",
            name="ck_er_user_configs_report_mode",
        ),
        sa.CheckConstraint(
            "report_length IN ('concise','normal','elaborative')",
            name="ck_er_user_configs_report_length",
        ),
    )
    op.create_index(
        "ix_er_user_configs_user_id", "er_user_configs", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_er_user_configs_user_id", table_name="er_user_configs")
    op.drop_table("er_user_configs")
```

Replace `<PRIOR_HEAD_REVISION_ID>` with the output of:

```bash
uv run alembic -c packages/server/src/openlia_server/db/migrations/alembic.ini current --verbose 2>/dev/null | grep "Rev:" | tail -1
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/server/tests/db/test_er_user_configs_migration.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-04-17-2100_er_user_configs.py \
        packages/server/tests/db/test_er_user_configs_migration.py
git commit -m "feat(db): add migration for er_user_configs table"
```

---

### Task 6: Server — `equity_research_config` service

CRUD service with defaults. On first `get_config()` for a user, the row is created with defaults: mode = `stock_initiation`, length = `normal`, every framework section enabled for every mode, no custom sections.

**Files:**
- Create: `packages/server/src/openlia_server/services/equity_research_config.py`
- Test: `packages/server/tests/services/test_equity_research_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_equity_research_config.py
import pytest

from openlia.reports.frameworks.loader import load_framework
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import ErUserConfig
from openlia_server.services.equity_research_config import (
    EquityResearchConfigService,
    ErConfigDTO,
    CustomSectionDTO,
)


@pytest.fixture
def user(db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    return "u1"


def test_get_config_creates_defaults_on_first_call(db_session, user):
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    assert cfg.report_mode == "stock_initiation"
    assert cfg.report_length == "normal"
    init_ids = {s["id"] for s in load_framework("stock_initiation")["sections"]}
    assert set(cfg.sections_by_mode["stock_initiation"]) == init_ids
    assert cfg.custom_sections_by_mode["stock_initiation"] == []
    assert cfg.custom_sections_by_mode["stock_update"] == []
    assert cfg.custom_sections_by_mode["sector_research"] == []


def test_get_config_idempotent(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    svc.get_config(user)
    assert db_session.query(ErUserConfig).count() == 1


def test_update_config_persists_mode_and_length(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(
        user,
        report_mode="stock_update",
        report_length="elaborative",
        sections_by_mode=None,
        custom_sections_by_mode=None,
    )
    assert updated.report_mode == "stock_update"
    assert updated.report_length == "elaborative"


def test_update_config_rejects_unknown_section_id(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    with pytest.raises(ValueError, match="unknown section"):
        svc.update_config(
            user,
            report_mode=None,
            report_length=None,
            sections_by_mode={"stock_update": ["does_not_exist"]},
            custom_sections_by_mode=None,
        )


def test_update_config_persists_custom_sections(db_session, user):
    svc = EquityResearchConfigService(db_session)
    svc.get_config(user)
    updated = svc.update_config(
        user,
        report_mode=None,
        report_length=None,
        sections_by_mode=None,
        custom_sections_by_mode={
            "stock_update": [
                CustomSectionDTO(
                    id="custom_esg_x1", title="ESG", description="note"
                ),
            ],
            "stock_initiation": [],
            "sector_research": [],
        },
    )
    update_cs = updated.custom_sections_by_mode["stock_update"]
    assert len(update_cs) == 1
    assert update_cs[0].id == "custom_esg_x1"


def test_resolve_active_returns_sections_for_selected_mode(db_session, user):
    svc = EquityResearchConfigService(db_session)
    cfg = svc.get_config(user)
    active = svc.resolve_active(cfg, mode="stock_update")
    assert active.mode == "stock_update"
    assert active.report_length == "normal"
    expected_ids = {s["id"] for s in load_framework("stock_update")["sections"]}
    assert set(active.enabled_section_ids) == expected_ids
    assert active.custom_sections == ()
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_equity_research_config.py -v`
Expected: FAIL — service module missing.

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/equity_research_config.py
"""Per-user Equity Research configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from sqlalchemy.orm import Session

from openlia.reports.frameworks.loader import CustomSection, load_framework
from openlia_server.db.models.departments import ErUserConfig


ReportMode = Literal["stock_initiation", "stock_update", "sector_research"]
ReportLength = Literal["concise", "normal", "elaborative"]

_ALL_MODES: tuple[ReportMode, ...] = (
    "stock_initiation",
    "stock_update",
    "sector_research",
)


@dataclass(frozen=True)
class CustomSectionDTO:
    id: str
    title: str
    description: str | None


@dataclass(frozen=True)
class ErConfigDTO:
    report_mode: ReportMode
    report_length: ReportLength
    sections_by_mode: dict[ReportMode, list[str]]
    custom_sections_by_mode: dict[ReportMode, list[CustomSectionDTO]]


@dataclass(frozen=True)
class ActiveReportConfig:
    mode: ReportMode
    report_length: ReportLength
    enabled_section_ids: tuple[str, ...]
    custom_sections: tuple[CustomSection, ...]


def _default_sections_for(mode: ReportMode) -> list[str]:
    return [s["id"] for s in load_framework(mode)["sections"]]


def _default_sections_by_mode() -> dict[ReportMode, list[str]]:
    return {m: _default_sections_for(m) for m in _ALL_MODES}


def _default_custom_sections() -> dict[ReportMode, list[CustomSectionDTO]]:
    return {m: [] for m in _ALL_MODES}


def _row_to_dto(row: ErUserConfig) -> ErConfigDTO:
    return ErConfigDTO(
        report_mode=row.report_mode,  # type: ignore[arg-type]
        report_length=row.report_length,  # type: ignore[arg-type]
        sections_by_mode={
            m: list(row.sections_by_mode.get(m, _default_sections_for(m)))
            for m in _ALL_MODES
        },
        custom_sections_by_mode={
            m: [
                CustomSectionDTO(id=c["id"], title=c["title"], description=c.get("description"))
                for c in row.custom_sections_by_mode.get(m, [])
            ]
            for m in _ALL_MODES
        },
    )


class EquityResearchConfigService:
    def __init__(self, db_session: Session) -> None:
        self._db = db_session

    def get_config(self, user_id: str) -> ErConfigDTO:
        row = (
            self._db.query(ErUserConfig)
            .filter(ErUserConfig.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            row = ErUserConfig(
                id=str(uuid4()),
                user_id=user_id,
                report_mode="stock_initiation",
                report_length="normal",
                sections_by_mode=_default_sections_by_mode(),
                custom_sections_by_mode={m: [] for m in _ALL_MODES},
            )
            self._db.add(row)
            self._db.commit()
        return _row_to_dto(row)

    def update_config(
        self,
        user_id: str,
        *,
        report_mode: ReportMode | None,
        report_length: ReportLength | None,
        sections_by_mode: dict[str, list[str]] | None,
        custom_sections_by_mode: dict[str, list[CustomSectionDTO]] | None,
    ) -> ErConfigDTO:
        row = (
            self._db.query(ErUserConfig)
            .filter(ErUserConfig.user_id == user_id)
            .one_or_none()
        )
        if row is None:
            self.get_config(user_id)
            row = (
                self._db.query(ErUserConfig)
                .filter(ErUserConfig.user_id == user_id)
                .one()
            )

        if report_mode is not None:
            row.report_mode = report_mode
        if report_length is not None:
            row.report_length = report_length

        if sections_by_mode is not None:
            merged = dict(row.sections_by_mode)
            for mode, ids in sections_by_mode.items():
                if mode not in _ALL_MODES:
                    raise ValueError(f"unknown mode: {mode!r}")
                known = {s["id"] for s in load_framework(mode)["sections"]}
                unknown = set(ids) - known
                if unknown:
                    raise ValueError(
                        f"unknown section ids for {mode}: {sorted(unknown)}"
                    )
                merged[mode] = list(ids)
            row.sections_by_mode = merged

        if custom_sections_by_mode is not None:
            merged_c: dict = dict(row.custom_sections_by_mode)
            for mode, customs in custom_sections_by_mode.items():
                if mode not in _ALL_MODES:
                    raise ValueError(f"unknown mode: {mode!r}")
                merged_c[mode] = [
                    {"id": c.id, "title": c.title, "description": c.description}
                    for c in customs
                ]
            row.custom_sections_by_mode = merged_c

        self._db.commit()
        return _row_to_dto(row)

    def resolve_active(
        self, cfg: ErConfigDTO, *, mode: ReportMode
    ) -> ActiveReportConfig:
        customs = tuple(
            CustomSection(id=c.id, title=c.title, description=c.description)
            for c in cfg.custom_sections_by_mode[mode]
        )
        return ActiveReportConfig(
            mode=mode,
            report_length=cfg.report_length,
            enabled_section_ids=tuple(cfg.sections_by_mode[mode]),
            custom_sections=customs,
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/server/tests/services/test_equity_research_config.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/equity_research_config.py \
        packages/server/tests/services/test_equity_research_config.py
git commit -m "feat(equity-research): add per-user config service with defaults"
```

---

### Task 7: Server — `/config` GET + PUT routes

Thin FastAPI wrappers around `EquityResearchConfigService`. Requires authenticated user. `PUT` accepts partial updates.

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/equity_research.py` (router scaffold)
- Modify: `packages/server/src/openlia_server/app.py` (mount router)
- Test: `packages/server/tests/routes/departments/test_equity_research_config_route.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_equity_research_config_route.py
def test_get_config_returns_defaults(client_auth):
    r = client_auth.get("/departments/equity-research/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_mode"] == "stock_initiation"
    assert body["report_length"] == "normal"
    assert "stock_initiation" in body["sections_by_mode"]
    assert len(body["sections_by_mode"]["stock_initiation"]) == 13


def test_put_config_partial_update_length_only(client_auth):
    client_auth.get("/departments/equity-research/config")
    r = client_auth.put(
        "/departments/equity-research/config",
        json={"report_length": "elaborative"},
    )
    assert r.status_code == 200
    assert r.json()["report_length"] == "elaborative"


def test_put_config_updates_sections_for_mode(client_auth):
    client_auth.get("/departments/equity-research/config")
    r = client_auth.put(
        "/departments/equity-research/config",
        json={
            "sections_by_mode": {
                "stock_update": ["investment_thesis", "event_analysis"]
            }
        },
    )
    assert r.status_code == 200
    assert r.json()["sections_by_mode"]["stock_update"] == [
        "investment_thesis",
        "event_analysis",
    ]


def test_put_config_rejects_unknown_section_id(client_auth):
    client_auth.get("/departments/equity-research/config")
    r = client_auth.put(
        "/departments/equity-research/config",
        json={"sections_by_mode": {"stock_update": ["bogus"]}},
    )
    assert r.status_code == 400
    assert "unknown" in r.json()["detail"].lower()


def test_put_config_adds_custom_section(client_auth):
    client_auth.get("/departments/equity-research/config")
    r = client_auth.put(
        "/departments/equity-research/config",
        json={
            "custom_sections_by_mode": {
                "stock_update": [
                    {
                        "id": "custom_esg_x1",
                        "title": "ESG Footnote",
                        "description": "Short note.",
                    }
                ]
            }
        },
    )
    assert r.status_code == 200
    customs = r.json()["custom_sections_by_mode"]["stock_update"]
    assert customs[0]["title"] == "ESG Footnote"


def test_config_requires_auth(client):
    r = client.get("/departments/equity-research/config")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_config_route.py -v`
Expected: FAIL — route 404.

- [ ] **Step 3: Write the router**

```python
# packages/server/src/openlia_server/routes/departments/equity_research.py
"""Equity Research HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.equity_research_config import (
    CustomSectionDTO,
    EquityResearchConfigService,
)


class CustomSectionPayload(BaseModel):
    id: str
    title: str
    description: str | None = None


class ErConfigPatch(BaseModel):
    report_mode: str | None = None
    report_length: str | None = None
    sections_by_mode: dict[str, list[str]] | None = None
    custom_sections_by_mode: dict[str, list[CustomSectionPayload]] | None = None


def _serialize(cfg) -> dict:
    return {
        "report_mode": cfg.report_mode,
        "report_length": cfg.report_length,
        "sections_by_mode": cfg.sections_by_mode,
        "custom_sections_by_mode": {
            mode: [
                {"id": c.id, "title": c.title, "description": c.description}
                for c in customs
            ]
            for mode, customs in cfg.custom_sections_by_mode.items()
        },
    }


def build_equity_research_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/departments/equity-research", tags=["equity-research"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/config")
    def get_config(
        user: User = require_auth,
        session: Session = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        return _serialize(svc.get_config(user.id))

    @router.put("/config")
    def put_config(
        patch: ErConfigPatch,
        user: User = require_auth,
        session: Session = Depends(session_dep),
    ) -> dict:
        svc = EquityResearchConfigService(session)
        try:
            updated = svc.update_config(
                user.id,
                report_mode=patch.report_mode,  # type: ignore[arg-type]
                report_length=patch.report_length,  # type: ignore[arg-type]
                sections_by_mode=patch.sections_by_mode,
                custom_sections_by_mode=(
                    {
                        mode: [
                            CustomSectionDTO(id=c.id, title=c.title, description=c.description)
                            for c in customs
                        ]
                        for mode, customs in patch.custom_sections_by_mode.items()
                    }
                    if patch.custom_sections_by_mode is not None
                    else None
                ),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _serialize(updated)

    return router
```

- [ ] **Step 4: Mount in `app.py`**

Add to `packages/server/src/openlia_server/app.py`:

```python
from openlia_server.routes.departments.equity_research import build_equity_research_router
app.include_router(build_equity_research_router(db_session_factory=factory, mode=mode))
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_config_route.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/equity_research.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/routes/departments/test_equity_research_config_route.py
git commit -m "feat(equity-research): add GET/PUT /config routes"
```

---

### Task 8: Server — `equity_research_runner` orchestrator service

Wires `EquityResearchConfigService` + `ReportRunner` (Plan 5) + `ReportStore` (Plan 13). Public entry point: `async def run_report(user_id, mode, user_input, session_id) -> AsyncIterator[Event]` — yields the runner's events and, on `ReportComplete`, writes the schema into `reports` via `report_store.create_report()`, then yields an additional `report.saved` event with the new `report_id`.

**Files:**
- Create: `packages/server/src/openlia_server/services/equity_research_runner.py`
- Test: `packages/server/tests/services/test_equity_research_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_equity_research_runner.py
import pytest

from openlia.llm.runtime.events import ReportComplete, ReportStart
from openlia_server.db.models.auth import User
from openlia_server.services.equity_research_runner import (
    EquityResearchRunner,
    ReportSavedEvent,
)


@pytest.fixture
def user(db_session):
    db_session.add(User(id="u1", email="u1@example.com", display_name="u1"))
    db_session.commit()
    return "u1"


@pytest.mark.asyncio
async def test_runner_yields_report_saved_after_complete(
    db_session, user, fake_report_runner
):
    fake_report_runner.queue_events(
        [
            ReportStart(report_id="r_1", department="equity_research", mode="stock_update", section_titles=["t"]),
            ReportComplete(report_id="r_1", schema={"title": "T", "sections": []}),
        ]
    )
    runner = EquityResearchRunner(
        db_session=db_session, inner=fake_report_runner
    )
    events = []
    async for e in runner.run_report(
        user_id=user,
        mode="stock_update",
        user_input="AAPL event",
        session_id=None,
    ):
        events.append(e)

    assert any(isinstance(e, ReportStart) for e in events)
    assert any(isinstance(e, ReportComplete) for e in events)
    saved = [e for e in events if isinstance(e, ReportSavedEvent)]
    assert len(saved) == 1
    assert saved[0].report_id is not None


@pytest.mark.asyncio
async def test_runner_rejects_invalid_mode(db_session, user, fake_report_runner):
    runner = EquityResearchRunner(
        db_session=db_session, inner=fake_report_runner
    )
    with pytest.raises(ValueError, match="unknown equity_research mode"):
        async for _ in runner.run_report(
            user_id=user,
            mode="bogus",
            user_input="x",
            session_id=None,
        ):
            pass


@pytest.mark.asyncio
async def test_runner_forwards_active_config_to_inner(
    db_session, user, fake_report_runner
):
    fake_report_runner.queue_events([ReportComplete(report_id="r_1", schema={"title": "t", "sections": []})])
    runner = EquityResearchRunner(
        db_session=db_session, inner=fake_report_runner
    )
    async for _ in runner.run_report(
        user_id=user,
        mode="stock_update",
        user_input="AAPL",
        session_id=None,
    ):
        pass
    last = fake_report_runner.last_request
    assert last.mode == "stock_update"
    assert last.user_input == "AAPL"
    # All 7 stock_update sections are enabled by default.
    assert len(last.enabled_sections) == 7
```

Shared fixture (append to `packages/server/tests/conftest.py`):

```python
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class _Captured:
    mode: str
    user_input: str
    enabled_sections: list
    custom_sections: list
    report_length: str


class FakeReportRunner:
    def __init__(self) -> None:
        self._queue: list = []
        self.last_request: _Captured | None = None

    def queue_events(self, events: list) -> None:
        self._queue = list(events)

    async def run(self, **kwargs: Any):
        self.last_request = _Captured(
            mode=kwargs["request"].mode,
            user_input=kwargs["request"].user_input,
            enabled_sections=list(kwargs["request"].enabled_sections),
            custom_sections=list(getattr(kwargs["request"], "custom_sections", [])),
            report_length=getattr(kwargs["request"], "report_length", "normal"),
        )
        for e in self._queue:
            yield e


@pytest.fixture
def fake_report_runner():
    return FakeReportRunner()
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `uv run pytest packages/server/tests/services/test_equity_research_runner.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the orchestrator**

```python
# packages/server/src/openlia_server/services/equity_research_runner.py
"""Equity Research orchestrator — config + ReportRunner + report_store."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from sqlalchemy.orm import Session

from openlia.departments.equity_research import EquityResearchDepartment
from openlia.llm.runtime.events import Event, ReportComplete
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.services.equity_research_config import (
    EquityResearchConfigService,
)
from openlia_server.services.report_store import ReportStore


@dataclass(frozen=True)
class ReportSavedEvent:
    type: str = "report.saved"
    report_id: str = ""


class _InnerRunner(Protocol):
    async def run(
        self, *, department_id: str, user_id: str, request: ReportRequest
    ) -> AsyncIterator[Event]: ...


class EquityResearchRunner:
    def __init__(
        self,
        *,
        db_session: Session,
        inner: _InnerRunner,
        report_store: ReportStore | None = None,
    ) -> None:
        self._db = db_session
        self._inner = inner
        self._store = report_store or ReportStore(db_session)
        self._config = EquityResearchConfigService(db_session)
        self._dept = EquityResearchDepartment()

    async def run_report(
        self,
        *,
        user_id: str,
        mode: str,
        user_input: str,
        session_id: str | None,
    ) -> AsyncIterator[Event | ReportSavedEvent]:
        if mode not in self._dept.valid_modes:
            raise ValueError(f"unknown equity_research mode: {mode!r}")

        cfg = self._config.get_config(user_id)
        active = self._config.resolve_active(cfg, mode=mode)  # type: ignore[arg-type]

        # Plan 14 stores a user-facing `report_length` in its own config table, but
        # Plan 5's `ReportRequest` uses `length` with allowed values
        # ("brief", "standard", "long"). Map here — the config row stays in its
        # own vocabulary and the runtime contract stays locked.
        _LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}
        request = ReportRequest(
            mode=active.mode,
            user_input=user_input,
            enabled_sections=list(active.enabled_section_ids),
            custom_sections=list(active.custom_sections),
            length=_LENGTH_MAP.get(active.report_length, "standard"),
        )

        last_complete: ReportComplete | None = None
        async for ev in self._inner.run(
            department_id=self._dept.name,
            user_id=user_id,
            request=request,
        ):
            if isinstance(ev, ReportComplete):
                last_complete = ev
            yield ev

        if last_complete is not None:
            report_id = self._store.create_report(
                user_id=user_id,
                department=self._dept.name,
                mode=active.mode,
                schema=last_complete.schema,
            )
            yield ReportSavedEvent(report_id=report_id)
```

Note: Plan 5 is shipped and locks the `ReportRequest` dataclass at
`openlia.llm.runtime.messages.ReportRequest`. Its fields are `mode`,
`user_input`, `enabled_sections`, `custom_sections`, `length` (allowed set
`("brief", "standard", "long")`). **Do not modify Plan 5 retroactively** — this
plan instead:
1. Keeps its own `er_user_configs.report_length` column (values `concise` /
   `normal` / `elaborative`) as the user-facing vocabulary.
2. Maps those values to `ReportRequest.length` at call-time via `_LENGTH_MAP`
   in `run_report` (see Step 3 above).
3. Does **not** add a `session_id` field to `ReportRequest`; the chat surface
   carries session state through `ChatRequest`, not `ReportRequest`.

- [ ] **Step 4: Do NOT extend `ReportRequest`**

Plan 5 is already shipped. Its `ReportRequest` at
`packages/core/src/openlia/llm/runtime/messages.py` is the single source of
truth and is **frozen** for Plans 14+. The mapping layer in Step 3 absorbs all
Plan 14 vocabulary (`report_length` → `length`). Chat session state lives on
`ChatRequest`, not `ReportRequest`. Skip this step.

- [ ] **Step 5: Run tests**

Run: `uv run pytest packages/server/tests/services/test_equity_research_runner.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/equity_research_runner.py \
        packages/server/tests/services/test_equity_research_runner.py \
        packages/server/tests/conftest.py
git commit -m "feat(equity-research): add orchestrator that wires config + runner + store"
```

---

### Task 9: Server — `POST /report` SSE route

Accepts `{mode, user_input, session_id?}`, streams `report.*` events (including the new `report.saved` with the persisted `report_id`).

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/equity_research.py`
- Test: `packages/server/tests/routes/departments/test_equity_research_report_route.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_equity_research_report_route.py
import json


def _consume_sse(iter_lines):
    events = []
    current = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current:
                events.append(json.loads("".join(current)))
                current = []
            continue
        if line.startswith("data:"):
            current.append(line[5:].lstrip())
    return events


def test_report_route_streams_start_complete_saved(client_auth, fake_llm):
    fake_llm.queue_report_response(
        schema={
            "schema_version": "1.0",
            "title": "AAPL Update",
            "sections": [],
            "cover": None,
            "page_furniture": None,
        }
    )
    r = client_auth.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "AAPL event"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert "report.start" in types
    assert "report.complete" in types
    assert types[-1] == "report.saved"
    assert events[-1]["report_id"]


def test_report_route_rejects_invalid_mode(client_auth):
    r = client_auth.post(
        "/departments/equity-research/report",
        json={"mode": "bogus", "user_input": "x"},
    )
    assert r.status_code == 400


def test_report_route_requires_auth(client):
    r = client.post(
        "/departments/equity-research/report",
        json={"mode": "stock_update", "user_input": "x"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_report_route.py -v`
Expected: FAIL — route not yet defined.

- [ ] **Step 3: Extend the router**

Add module-level imports and helpers to `packages/server/src/openlia_server/routes/departments/equity_research.py`:

```python
import json

from fastapi import Request
from fastapi.responses import StreamingResponse

from openlia.llm.runtime.events import to_wire
from openlia_server.runtime.factory import build_report_runner
from openlia_server.services.equity_research_runner import (
    EquityResearchRunner,
    ReportSavedEvent,
)


class ReportPayload(BaseModel):
    mode: str
    user_input: str
    session_id: str | None = None


def _serialize_event(ev) -> dict:
    if isinstance(ev, ReportSavedEvent):
        return {"type": "report.saved", "report_id": ev.report_id}
    # Core events already expose `type` + fields via dataclass asdict.
    from dataclasses import asdict, is_dataclass

    if is_dataclass(ev):
        data = asdict(ev)
        data.setdefault("type", type(ev).__name__.lower())
        return data
    return {"type": "unknown"}
```

Then add the route **inside `build_equity_research_router`**, before the `return router` line (so it closes over `router`, `require_auth`, and `session_dep`):

```python
    @router.post("/report")
    async def post_report(
        payload: ReportPayload,
        request: Request,
        user: User = require_auth,
        session: Session = Depends(session_dep),
    ) -> StreamingResponse:
        inner = build_report_runner(session=session)
        runner = EquityResearchRunner(db_session=session, inner=inner)

        async def stream():
            try:
                async for ev in runner.run_report(
                    user_id=user.id,
                    mode=payload.mode,
                    user_input=payload.user_input,
                    session_id=payload.session_id,
                ):
                    yield f"data: {json.dumps(_serialize_event(ev))}\n\n"
            except ValueError as exc:
                yield f"data: {json.dumps({'type': 'report.error', 'message': str(exc)})}\n\n"

        try:
            return StreamingResponse(
                stream(),
                media_type="text/event-stream",
                headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
```

The `build_report_runner(session)` factory is provided by Plan 5 at `packages/server/src/openlia_server/runtime/factory.py`. If that file does not yet exist, create it as a thin wrapper that instantiates `ReportRunner` with the production provider factory, tool dispatcher, and prompt loader.

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_report_route.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/equity_research.py \
        packages/server/tests/routes/departments/test_equity_research_report_route.py
git commit -m "feat(equity-research): add /report SSE route with persisted report_id event"
```

---

### Task 10: Server — `POST /chat` SSE route

Follow-up chat after a report is generated. Uses `ChatRunner` (Plan 5) with `EquityResearchDepartment` so the LLM has access to the same data requirement tools.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/equity_research.py`
- Test: `packages/server/tests/routes/departments/test_equity_research_chat_route.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_equity_research_chat_route.py
import json


def _consume_sse(iter_lines):
    events = []
    current = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current:
                events.append(json.loads("".join(current)))
                current = []
            continue
        if line.startswith("data:"):
            current.append(line[5:].lstrip())
    return events


def test_chat_route_streams_start_token_done(client_auth, fake_llm):
    fake_llm.queue_chat_response("AAPL guidance was in line.")
    r = client_auth.post(
        "/departments/equity-research/chat",
        json={"message": "What did guidance look like?"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert types[0] == "chat.start"
    assert "chat.token" in types
    assert types[-1] == "chat.done"


def test_chat_route_requires_auth(client):
    r = client.post(
        "/departments/equity-research/chat",
        json={"message": "hi"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_chat_route.py -v`
Expected: FAIL — route missing.

- [ ] **Step 3: Extend the router**

Add module-level imports and payload model to `packages/server/src/openlia_server/routes/departments/equity_research.py`:

```python
import json

from openlia.llm.runtime.events import to_wire
from openlia.departments.equity_research import EquityResearchDepartment
from openlia_server.runtime.chat import ChatRunner


class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None
```

Then add the route **inside `build_equity_research_router`**, before the `return router` line:

```python
    @router.post("/chat")
    async def post_chat(
        payload: ChatPayload,
        request: Request,
        user: User = require_auth,
        session: Session = Depends(session_dep),
    ) -> StreamingResponse:
        runner = ChatRunner(
            department=EquityResearchDepartment(),
            db_session=session,
            user=user,
        )
        async def stream():
            async for event in runner.run(
                message=payload.message,
                session_id=payload.session_id,
                client_disconnected=request.is_disconnected,
            ):
                yield f"data: {json.dumps(to_wire(event))}\n\n"

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_equity_research_chat_route.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/equity_research.py \
        packages/server/tests/routes/departments/test_equity_research_chat_route.py
git commit -m "feat(equity-research): add /chat SSE route for follow-up questions"
```

---

### Task 11: Frontend — `api/equity-research.ts` typed client

Fetch + mutation helpers plus a `startReport()` / `startChat()` that return `EventSource` URLs (Plan 12's `useChatStream` already knows how to consume them).

**Files:**
- Create: `frontend/src/api/equity-research.ts`
- Test: `frontend/src/api/equity-research.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/api/equity-research.test.ts
import { describe, expect, it, vi, beforeEach } from "vitest";

import {
  fetchErConfig,
  updateErConfig,
  reportStreamUrl,
  chatStreamUrl,
  type ErConfig,
} from "./equity-research";

describe("equity-research api", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("fetchErConfig GETs /config and returns typed body", async () => {
    const body: ErConfig = {
      report_mode: "stock_initiation",
      report_length: "normal",
      sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      custom_sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
    };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => body,
    } as unknown as Response);
    const result = await fetchErConfig();
    expect(result).toEqual(body);
    expect(global.fetch).toHaveBeenCalledWith(
      "/api/departments/equity-research/config",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("updateErConfig PUTs a partial patch", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ report_length: "elaborative" }),
    } as unknown as Response);
    await updateErConfig({ report_length: "elaborative" });
    const [, init] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ report_length: "elaborative" });
  });

  it("reportStreamUrl returns the POST endpoint path", () => {
    expect(reportStreamUrl()).toBe(
      "/api/departments/equity-research/report"
    );
  });

  it("chatStreamUrl returns the POST endpoint path", () => {
    expect(chatStreamUrl()).toBe("/api/departments/equity-research/chat");
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd frontend && npx vitest run src/api/equity-research.test.ts`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the client**

```typescript
// frontend/src/api/equity-research.ts
export type ReportMode =
  | "stock_initiation"
  | "stock_update"
  | "sector_research";
export type ReportLength = "concise" | "normal" | "elaborative";

export interface CustomSection {
  id: string;
  title: string;
  description: string | null;
}

export interface ErConfig {
  report_mode: ReportMode;
  report_length: ReportLength;
  sections_by_mode: Record<ReportMode, string[]>;
  custom_sections_by_mode: Record<ReportMode, CustomSection[]>;
}

export interface ErConfigPatch {
  report_mode?: ReportMode;
  report_length?: ReportLength;
  sections_by_mode?: Partial<Record<ReportMode, string[]>>;
  custom_sections_by_mode?: Partial<Record<ReportMode, CustomSection[]>>;
}

const BASE = "/api/departments/equity-research";

export async function fetchErConfig(): Promise<ErConfig> {
  const res = await fetch(`${BASE}/config`, { credentials: "include" });
  if (!res.ok) {
    throw new Error(`fetchErConfig failed: ${res.status}`);
  }
  return (await res.json()) as ErConfig;
}

export async function updateErConfig(
  patch: ErConfigPatch
): Promise<ErConfig> {
  const res = await fetch(`${BASE}/config`, {
    method: "PUT",
    credentials: "include",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      `updateErConfig failed: ${res.status} ${body.detail ?? ""}`.trim()
    );
  }
  return (await res.json()) as ErConfig;
}

export function reportStreamUrl(): string {
  return `${BASE}/report`;
}

export function chatStreamUrl(): string {
  return `${BASE}/chat`;
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run src/api/equity-research.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/equity-research.ts frontend/src/api/equity-research.test.ts
git commit -m "feat(frontend): add equity-research api client"
```

---

### Task 12: Frontend — `useErConfig` hook + `ModeToggle`

The hook loads config once and exposes `patch()`. The toggle is a reusable segmented control used for both Report Mode and Report Length.

**Files:**
- Create: `frontend/src/hooks/useErConfig.ts`
- Create: `frontend/src/components/equity-research/ModeToggle.tsx`
- Test: `frontend/src/hooks/useErConfig.test.tsx`
- Test: `frontend/src/components/equity-research/ModeToggle.test.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// frontend/src/hooks/useErConfig.test.tsx
import { renderHook, act, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useErConfig } from "./useErConfig";

describe("useErConfig", () => {
  it("loads config on mount then exposes data", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        report_mode: "stock_initiation",
        report_length: "normal",
        sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
        custom_sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
      }),
    } as unknown as Response);

    const { result } = renderHook(() => useErConfig());
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.config?.report_mode).toBe("stock_initiation");
  });

  it("patch() calls PUT then updates local state", async () => {
    const fetchMock = vi.fn();
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        report_mode: "stock_initiation",
        report_length: "normal",
        sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
        custom_sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
      }),
    } as unknown as Response);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        report_mode: "stock_update",
        report_length: "normal",
        sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
        custom_sections_by_mode: {
          stock_initiation: [],
          stock_update: [],
          sector_research: [],
        },
      }),
    } as unknown as Response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const { result } = renderHook(() => useErConfig());
    await waitFor(() => expect(result.current.loading).toBe(false));
    await act(async () => {
      await result.current.patch({ report_mode: "stock_update" });
    });
    expect(result.current.config?.report_mode).toBe("stock_update");
  });
});
```

```tsx
// frontend/src/components/equity-research/ModeToggle.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ModeToggle } from "./ModeToggle";

describe("ModeToggle", () => {
  it("renders one button per option and marks the active one", () => {
    render(
      <ModeToggle
        value="b"
        onChange={() => {}}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
          { value: "c", label: "C" },
        ]}
      />
    );
    expect(screen.getByRole("radio", { name: "B" })).toHaveAttribute(
      "aria-checked",
      "true"
    );
  });

  it("fires onChange when a different option is clicked", () => {
    const onChange = vi.fn();
    render(
      <ModeToggle
        value="a"
        onChange={onChange}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />
    );
    fireEvent.click(screen.getByRole("radio", { name: "B" }));
    expect(onChange).toHaveBeenCalledWith("b");
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd frontend && npx vitest run src/hooks/useErConfig.test.tsx src/components/equity-research/ModeToggle.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Write `ModeToggle`**

```tsx
// frontend/src/components/equity-research/ModeToggle.tsx
import clsx from "clsx";

export interface ModeToggleOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  value: T;
  options: ModeToggleOption<T>[];
  onChange: (value: T) => void;
  ariaLabel?: string;
}

export function ModeToggle<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: Props<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex rounded-md border border-[--color-border-subtle] p-0.5 bg-[--color-bg-base]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            className={clsx(
              "px-3 h-8 text-sm rounded-[--radius-sm] transition-colors",
              active
                ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
            )}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Write `useErConfig`**

```tsx
// frontend/src/hooks/useErConfig.ts
import { useCallback, useEffect, useState } from "react";

import {
  ErConfig,
  ErConfigPatch,
  fetchErConfig,
  updateErConfig,
} from "../api/equity-research";

export function useErConfig() {
  const [config, setConfig] = useState<ErConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchErConfig()
      .then((cfg) => {
        if (!cancelled) {
          setConfig(cfg);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const patch = useCallback(async (p: ErConfigPatch) => {
    const next = await updateErConfig(p);
    setConfig(next);
    return next;
  }, []);

  return { config, loading, error, patch };
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run src/hooks/useErConfig.test.tsx src/components/equity-research/ModeToggle.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useErConfig.ts \
        frontend/src/hooks/useErConfig.test.tsx \
        frontend/src/components/equity-research/ModeToggle.tsx \
        frontend/src/components/equity-research/ModeToggle.test.tsx
git commit -m "feat(frontend): add useErConfig hook and ModeToggle primitive"
```

---

### Task 13: Frontend — `ReportSettingsModal` + `CustomSectionRow`

Radix `Dialog` hosting: Report Mode toggle, Length toggle, per-mode section checkboxes, per-mode custom sections list, Cancel / Save.

**Files:**
- Create: `frontend/src/components/equity-research/ReportSettingsModal.tsx`
- Create: `frontend/src/components/equity-research/CustomSectionRow.tsx`
- Create: `frontend/src/lib/equity-research/section-catalog.ts` (frozen section titles keyed by mode+id)
- Test: `frontend/src/components/equity-research/ReportSettingsModal.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/equity-research/ReportSettingsModal.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportSettingsModal } from "./ReportSettingsModal";
import type { ErConfig } from "../../api/equity-research";

const baseConfig: ErConfig = {
  report_mode: "stock_initiation",
  report_length: "normal",
  sections_by_mode: {
    stock_initiation: ["company_overview", "industry_overview"],
    stock_update: ["investment_thesis", "event_analysis"],
    sector_research: ["sector_thesis"],
  },
  custom_sections_by_mode: {
    stock_initiation: [],
    stock_update: [],
    sector_research: [],
  },
};

describe("ReportSettingsModal", () => {
  it("renders sections for the initially selected mode", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />
    );
    expect(screen.getByLabelText("Company Overview")).toBeChecked();
    expect(screen.getByLabelText("Industry Overview")).toBeChecked();
  });

  it("switching mode replaces the visible section list", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />
    );
    fireEvent.click(screen.getByRole("radio", { name: "Stock Update" }));
    expect(screen.getByLabelText("Investment Thesis / Key Takeaway")).toBeInTheDocument();
    expect(screen.queryByLabelText("Company Overview")).not.toBeInTheDocument();
  });

  it("unchecking a section and saving calls onSave with the patched config", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />
    );
    fireEvent.click(screen.getByLabelText("Industry Overview"));
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    const patch = onSave.mock.calls[0][0];
    expect(patch.sections_by_mode.stock_initiation).toEqual([
      "company_overview",
    ]);
  });

  it("adding a custom section requires a title", () => {
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={async () => {}}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /\+ add/i }));
    const confirm = screen.getByRole("button", { name: /add section/i });
    expect(confirm).toBeDisabled();
  });

  it("changing report length toggle updates the patch on save", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <ReportSettingsModal
        open
        config={baseConfig}
        onClose={() => {}}
        onSave={onSave}
      />
    );
    fireEvent.click(screen.getByRole("radio", { name: "Elaborative" }));
    fireEvent.click(screen.getByRole("button", { name: /save settings/i }));
    await waitFor(() => expect(onSave).toHaveBeenCalled());
    expect(onSave.mock.calls[0][0].report_length).toBe("elaborative");
  });
});
```

- [ ] **Step 2: Run test**

Run: `cd frontend && npx vitest run src/components/equity-research/ReportSettingsModal.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Write the section catalog**

```typescript
// frontend/src/lib/equity-research/section-catalog.ts
import type { ReportMode } from "../../api/equity-research";

export interface SectionEntry {
  id: string;
  title: string;
}

export const SECTION_CATALOG: Record<ReportMode, SectionEntry[]> = {
  stock_initiation: [
    { id: "company_overview", title: "Company Overview" },
    { id: "industry_overview", title: "Industry Overview" },
    { id: "products_services", title: "Products and Services" },
    { id: "business_model", title: "Business Model" },
    { id: "competitive_analysis", title: "Competitive Analysis" },
    { id: "management_team", title: "Management Team" },
    { id: "advantages_weaknesses", title: "Competitive Advantages and Weaknesses" },
    { id: "risk_analysis", title: "Risk Analysis" },
    { id: "historical_financial_data", title: "Historical Financial Data" },
    { id: "financial_analysis", title: "Financial Analysis" },
    { id: "financial_projections", title: "Financial Projections" },
    { id: "valuation_analysis", title: "Valuation Analysis" },
    { id: "investment_recommendation", title: "Investment Recommendation" },
  ],
  stock_update: [
    { id: "investment_thesis", title: "Investment Thesis / Key Takeaway" },
    { id: "event_analysis", title: "Event Analysis" },
    { id: "financial_results", title: "Financial Results Summary" },
    { id: "estimate_revisions", title: "Estimate Revisions" },
    { id: "valuation_and_target", title: "Valuation and Price Target" },
    { id: "scenarios", title: "Bull / Bear / Base Scenarios" },
    { id: "risks", title: "Risks" },
  ],
  sector_research: [
    { id: "sector_thesis", title: "Sector Thesis / Key Takeaway" },
    { id: "industry_overview_sizing", title: "Industry Overview and Market Sizing" },
    { id: "key_drivers_trends", title: "Key Drivers and Trends" },
    { id: "market_data_analysis", title: "Market Data and Analysis" },
    { id: "competitive_landscape", title: "Competitive Landscape and Value Chain" },
    { id: "company_analysis_implications", title: "Company Analysis and Stock Implications" },
    { id: "valuation", title: "Valuation" },
    { id: "risks", title: "Risks" },
  ],
};

export function titleOf(mode: ReportMode, id: string): string {
  const entry = SECTION_CATALOG[mode].find((s) => s.id === id);
  return entry?.title ?? id;
}
```

These IDs must match the IDs in the three framework JSONs shipped in Plan 13. Verify each ID against `packages/core/src/openlia/reports/frameworks/<mode>.json` before committing. If any differ, fix the catalog — the framework JSON is the source of truth.

- [ ] **Step 4: Write `CustomSectionRow`**

```tsx
// frontend/src/components/equity-research/CustomSectionRow.tsx
import { X } from "lucide-react";

import type { CustomSection } from "../../api/equity-research";

interface Props {
  section: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ section, onChange, onRemove }: Props) {
  return (
    <div className="flex items-start gap-2 py-2">
      <div className="flex-1 space-y-1">
        <input
          aria-label="Custom section title"
          className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
          value={section.title}
          onChange={(e) => onChange({ ...section, title: e.target.value })}
        />
        <textarea
          aria-label="Custom section description"
          rows={2}
          className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
          value={section.description ?? ""}
          onChange={(e) =>
            onChange({ ...section, description: e.target.value || null })
          }
        />
      </div>
      <button
        type="button"
        aria-label="Remove custom section"
        onClick={onRemove}
        className="p-1 text-[--color-text-tertiary] hover:text-[--color-text-primary]"
      >
        <X size={14} />
      </button>
    </div>
  );
}
```

- [ ] **Step 5: Write `ReportSettingsModal`**

```tsx
// frontend/src/components/equity-research/ReportSettingsModal.tsx
import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { X } from "lucide-react";

import {
  type CustomSection,
  type ErConfig,
  type ErConfigPatch,
  type ReportLength,
  type ReportMode,
} from "../../api/equity-research";
import { ModeToggle } from "./ModeToggle";
import { CustomSectionRow } from "./CustomSectionRow";
import { SECTION_CATALOG } from "../../lib/equity-research/section-catalog";

const MODE_LABELS: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
};

const LENGTH_LABELS: Record<ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

interface Props {
  open: boolean;
  config: ErConfig;
  onClose: () => void;
  onSave: (patch: ErConfigPatch) => Promise<void>;
}

export function ReportSettingsModal({ open, config, onClose, onSave }: Props) {
  const [mode, setMode] = useState<ReportMode>(config.report_mode);
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [sections, setSections] = useState(config.sections_by_mode);
  const [customs, setCustoms] = useState(config.custom_sections_by_mode);
  const [pendingCustom, setPendingCustom] = useState<CustomSection | null>(null);

  const toggleSection = (id: string) => {
    const current = new Set(sections[mode]);
    if (current.has(id)) current.delete(id);
    else current.add(id);
    const ordered = SECTION_CATALOG[mode]
      .map((s) => s.id)
      .filter((sid) => current.has(sid));
    setSections({ ...sections, [mode]: ordered });
  };

  const addCustom = () => {
    if (!pendingCustom?.title) return;
    const id = `custom_${pendingCustom.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .slice(0, 32)}_${Math.random().toString(36).slice(2, 6)}`;
    const added = { ...pendingCustom, id };
    setCustoms({
      ...customs,
      [mode]: [...customs[mode], added],
    });
    setPendingCustom(null);
  };

  const save = async () => {
    const patch: ErConfigPatch = {
      report_mode: mode,
      report_length: length,
      sections_by_mode: sections,
      custom_sections_by_mode: customs,
    };
    await onSave(patch);
    onClose();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[480px] rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[--color-border-subtle]">
            <Dialog.Title className="text-lg font-semibold">
              Report Settings
            </Dialog.Title>
            <button onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>

          <div className="px-6 py-4 space-y-4">
            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Report Mode
              </label>
              <div className="mt-1">
                <ModeToggle
                  ariaLabel="Report Mode"
                  value={mode}
                  options={(Object.keys(MODE_LABELS) as ReportMode[]).map((v) => ({
                    value: v,
                    label: MODE_LABELS[v],
                  }))}
                  onChange={setMode}
                />
              </div>
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Report Length
              </label>
              <div className="mt-1">
                <ModeToggle
                  ariaLabel="Report Length"
                  value={length}
                  options={(Object.keys(LENGTH_LABELS) as ReportLength[]).map((v) => ({
                    value: v,
                    label: LENGTH_LABELS[v],
                  }))}
                  onChange={setLength}
                />
              </div>
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Sections ({MODE_LABELS[mode]} Report)
              </label>
              <ul className="mt-2 divide-y divide-[--color-border-subtle] border border-[--color-border-subtle] rounded-[--radius-md]">
                {SECTION_CATALOG[mode].map((s) => {
                  const checked = sections[mode].includes(s.id);
                  return (
                    <li key={s.id} className="px-3 py-2 flex items-center gap-2">
                      <input
                        type="checkbox"
                        id={`sec-${s.id}`}
                        checked={checked}
                        onChange={() => toggleSection(s.id)}
                      />
                      <label htmlFor={`sec-${s.id}`} className="text-sm">
                        {s.title}
                      </label>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                  Custom Sections
                </label>
                {!pendingCustom && (
                  <button
                    type="button"
                    className="text-sm text-[--color-accent-primary]"
                    onClick={() =>
                      setPendingCustom({ id: "", title: "", description: null })
                    }
                  >
                    + Add
                  </button>
                )}
              </div>
              <div className="mt-2">
                {customs[mode].map((c, i) => (
                  <CustomSectionRow
                    key={c.id}
                    section={c}
                    onChange={(next) => {
                      const copy = [...customs[mode]];
                      copy[i] = next;
                      setCustoms({ ...customs, [mode]: copy });
                    }}
                    onRemove={() => {
                      const copy = customs[mode].filter((_, j) => j !== i);
                      setCustoms({ ...customs, [mode]: copy });
                    }}
                  />
                ))}
                {pendingCustom && (
                  <div className="border border-[--color-border-subtle] rounded-[--radius-md] p-2 space-y-2">
                    <input
                      aria-label="New custom section title"
                      placeholder="Title"
                      className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
                      value={pendingCustom.title}
                      onChange={(e) =>
                        setPendingCustom({ ...pendingCustom, title: e.target.value })
                      }
                    />
                    <textarea
                      aria-label="New custom section description"
                      placeholder="Description (optional)"
                      rows={2}
                      className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
                      value={pendingCustom.description ?? ""}
                      onChange={(e) =>
                        setPendingCustom({
                          ...pendingCustom,
                          description: e.target.value || null,
                        })
                      }
                    />
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => setPendingCustom(null)}
                        className="text-sm px-2 h-7"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={addCustom}
                        disabled={!pendingCustom.title}
                        className="text-sm px-2 h-7 rounded-[--radius-sm] bg-[--color-accent-primary] text-white disabled:opacity-40"
                      >
                        Add section
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t border-[--color-border-subtle]">
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-4 rounded-[--radius-md] border border-[--color-border-subtle]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              className="h-9 px-4 rounded-[--radius-md] bg-[--color-accent-primary] text-white"
            >
              Save settings
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 6: Run tests**

Run: `cd frontend && npx vitest run src/components/equity-research/ReportSettingsModal.test.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/equity-research/section-catalog.ts \
        frontend/src/components/equity-research/ReportSettingsModal.tsx \
        frontend/src/components/equity-research/ReportSettingsModal.test.tsx \
        frontend/src/components/equity-research/CustomSectionRow.tsx
git commit -m "feat(equity-research): add Report Settings modal with mode, length, and custom sections"
```

---

### Task 14: Frontend — `SuggestionChips` + `FromPortfolioPicker`

Chips row for the Welcome state. Four static chips (AAPL/TSLA/NVDA/MSFT) and a "From Portfolio" chip that opens a popover listing `portfolio_holdings`.

**Files:**
- Create: `frontend/src/components/equity-research/SuggestionChips.tsx`
- Create: `frontend/src/components/equity-research/FromPortfolioPicker.tsx`
- Create: `frontend/src/api/portfolio.ts` (if not already present — trivial `fetchHoldings()`)
- Test: `frontend/src/components/equity-research/SuggestionChips.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/equity-research/SuggestionChips.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SuggestionChips } from "./SuggestionChips";

describe("SuggestionChips", () => {
  it("renders the four static chips plus From Portfolio", () => {
    render(<SuggestionChips onSelect={() => {}} />);
    for (const label of ["AAPL", "TSLA", "NVDA", "MSFT"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    expect(
      screen.getByRole("button", { name: /from portfolio/i })
    ).toBeInTheDocument();
  });

  it("calls onSelect with the chip label when a static chip is clicked", () => {
    const onSelect = vi.fn();
    render(<SuggestionChips onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "AAPL" }));
    expect(onSelect).toHaveBeenCalledWith("AAPL");
  });

  it("opens the portfolio picker and fires onSelect on row click", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        { ticker: "GOOG", name: "Alphabet Inc." },
        { ticker: "AMZN", name: "Amazon" },
      ],
    } as unknown as Response);
    const onSelect = vi.fn();
    render(<SuggestionChips onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: /from portfolio/i }));
    await waitFor(() =>
      expect(screen.getByText("GOOG")).toBeInTheDocument()
    );
    fireEvent.click(screen.getByText("GOOG"));
    expect(onSelect).toHaveBeenCalledWith("GOOG");
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/equity-research/SuggestionChips.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Write `api/portfolio.ts` minimal fetcher**

```typescript
// frontend/src/api/portfolio.ts
export interface PortfolioHolding {
  ticker: string;
  name: string | null;
}

export async function fetchHoldings(): Promise<PortfolioHolding[]> {
  const res = await fetch("/api/portfolio/holdings", {
    credentials: "include",
  });
  if (!res.ok) throw new Error(`fetchHoldings failed: ${res.status}`);
  return (await res.json()) as PortfolioHolding[];
}
```

If Plan 21 (Portfolio page) has not yet shipped this endpoint, Plan 14 stops requiring a populated portfolio — the picker handles an empty-list case (rendered as "No holdings yet"). The frontend still calls the endpoint; the server returns `[]` when the table is empty. If the endpoint itself is missing, the picker catches the error and renders "Portfolio unavailable" instead.

- [ ] **Step 4: Write `FromPortfolioPicker`**

```tsx
// frontend/src/components/equity-research/FromPortfolioPicker.tsx
import * as Popover from "@radix-ui/react-popover";
import { ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchHoldings, type PortfolioHolding } from "../../api/portfolio";

interface Props {
  onSelect: (ticker: string) => void;
}

export function FromPortfolioPicker({ onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [holdings, setHoldings] = useState<PortfolioHolding[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || holdings !== null || error) return;
    fetchHoldings()
      .then(setHoldings)
      .catch(() => setError("Portfolio unavailable"));
  }, [open, holdings, error]);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          From Portfolio
          <ArrowUpRight size={12} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="w-[240px] max-h-[300px] overflow-y-auto rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg p-1">
          {error && <div className="p-2 text-xs text-[--color-text-tertiary]">{error}</div>}
          {!error && holdings === null && (
            <div className="p-2 text-xs text-[--color-text-tertiary]">Loading...</div>
          )}
          {holdings && holdings.length === 0 && (
            <div className="p-2 text-xs text-[--color-text-tertiary]">No holdings yet</div>
          )}
          {holdings?.map((h) => (
            <button
              key={h.ticker}
              type="button"
              onClick={() => {
                onSelect(h.ticker);
                setOpen(false);
              }}
              className="w-full text-left px-2 py-1.5 text-sm rounded-[--radius-sm] hover:bg-[--color-surface-hover] flex justify-between"
            >
              <span className="font-medium">{h.ticker}</span>
              {h.name && (
                <span className="text-[--color-text-tertiary] truncate">{h.name}</span>
              )}
            </button>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
```

- [ ] **Step 5: Write `SuggestionChips`**

```tsx
// frontend/src/components/equity-research/SuggestionChips.tsx
import { FromPortfolioPicker } from "./FromPortfolioPicker";

const STATIC_TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT"] as const;

interface Props {
  onSelect: (value: string) => void;
}

export function SuggestionChips({ onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {STATIC_TICKERS.map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onSelect(t)}
          className="px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          {t}
        </button>
      ))}
      <FromPortfolioPicker onSelect={onSelect} />
    </div>
  );
}
```

- [ ] **Step 6: Run tests**

Run: `cd frontend && npx vitest run src/components/equity-research/SuggestionChips.test.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/portfolio.ts \
        frontend/src/components/equity-research/SuggestionChips.tsx \
        frontend/src/components/equity-research/SuggestionChips.test.tsx \
        frontend/src/components/equity-research/FromPortfolioPicker.tsx
git commit -m "feat(equity-research): add suggestion chips and from-portfolio picker"
```

---

### Task 15: Frontend — `ReportCard` chat block

Inline card that appears in the chat transcript when the server yields `report.saved`. Clicking "Open Report" opens the Plan 12 `FileViewer` with the generated report. Reuses Plan 13's `fetchReport` + `downloadReportPdf`.

**Files:**
- Create: `frontend/src/components/equity-research/ReportCard.tsx`
- Test: `frontend/src/components/equity-research/ReportCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/equity-research/ReportCard.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReportCard } from "./ReportCard";

describe("ReportCard", () => {
  it("renders the mode title and subject line", () => {
    render(
      <ReportCard
        reportId="r1"
        mode="stock_update"
        subject="AAPL"
        companyName="Apple Inc."
        createdAt="2026-04-09T12:00:00Z"
        preview="Apple reported..."
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText(/stock update report/i)).toBeInTheDocument();
    expect(screen.getByText(/AAPL/)).toBeInTheDocument();
    expect(screen.getByText(/Apple Inc\./)).toBeInTheDocument();
  });

  it("calls onOpen when Open Report is clicked", () => {
    const onOpen = vi.fn();
    render(
      <ReportCard
        reportId="r1"
        mode="stock_update"
        subject="AAPL"
        companyName="Apple Inc."
        createdAt="2026-04-09T12:00:00Z"
        preview="x"
        onOpen={onOpen}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: /open report/i }));
    expect(onOpen).toHaveBeenCalledWith("r1");
  });

  it("renders sector research label without companyName", () => {
    render(
      <ReportCard
        reportId="r2"
        mode="sector_research"
        subject="Semiconductors"
        companyName={null}
        createdAt="2026-04-09T12:00:00Z"
        preview="x"
        onOpen={() => {}}
        onDownload={() => {}}
        onSave={() => {}}
      />
    );
    expect(screen.getByText(/sector research report/i)).toBeInTheDocument();
    expect(screen.getByText(/Semiconductors/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/equity-research/ReportCard.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Write `ReportCard`**

```tsx
// frontend/src/components/equity-research/ReportCard.tsx
import { FileText } from "lucide-react";
import { format } from "date-fns";

import type { ReportMode } from "../../api/equity-research";

const MODE_TITLE: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation Report",
  stock_update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

interface Props {
  reportId: string;
  mode: ReportMode;
  subject: string;
  companyName: string | null;
  createdAt: string;
  preview: string;
  onOpen: (reportId: string) => void;
  onDownload: (reportId: string, format: "pdf" | "docx") => void;
  onSave: (reportId: string) => void;
}

export function ReportCard({
  reportId,
  mode,
  subject,
  companyName,
  createdAt,
  preview,
  onOpen,
  onDownload,
  onSave,
}: Props) {
  const date = format(new Date(createdAt), "MMM d, yyyy");
  const subjectLine = companyName
    ? `${subject}  ·  ${companyName}  ·  ${date}`
    : `${subject}  ·  ${date}`;

  return (
    <div className="max-w-[560px] rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm overflow-hidden">
      <div className="px-4 py-3 flex items-start gap-3">
        <FileText size={16} className="text-[--color-text-tertiary]" />
        <div>
          <div className="text-base font-medium text-[--color-text-primary]">
            {MODE_TITLE[mode]}
          </div>
          <div className="text-sm text-[--color-text-secondary]">
            {subjectLine}
          </div>
        </div>
      </div>
      <div className="px-4 py-3 text-sm text-[--color-text-secondary] leading-relaxed line-clamp-3">
        {preview}
      </div>
      <div className="px-4 py-2.5 flex items-center gap-2 bg-[--color-bg-base] border-t border-[--color-border-subtle]">
        <button
          type="button"
          onClick={() => onOpen(reportId)}
          className="px-3 h-7 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm"
        >
          Open Report
        </button>
        <button
          type="button"
          onClick={() => onDownload(reportId, "pdf")}
          className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm"
        >
          Download PDF
        </button>
        <button
          type="button"
          onClick={() => onSave(reportId)}
          className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm"
        >
          Save to Repo
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests**

Run: `cd frontend && npx vitest run src/components/equity-research/ReportCard.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/equity-research/ReportCard.tsx \
        frontend/src/components/equity-research/ReportCard.test.tsx
git commit -m "feat(equity-research): add inline ReportCard chat block"
```

---

### Task 16: Frontend — `EquityResearchPage` composition

Puts it all together. Welcome state with `SuggestionChips` + input; Active state with `ChatInterface` from Plan 12 driving both SSE endpoints; Report Settings button in the header; `ReportCard` rendering when the stream emits `report.saved`.

**Files:**
- Create: `frontend/src/pages/EquityResearchPage.tsx`
- Modify: `frontend/src/app/routes.tsx` (register `/equity-research`)
- Test: `frontend/src/pages/EquityResearchPage.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/EquityResearchPage.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EquityResearchPage } from "./EquityResearchPage";

vi.mock("../hooks/useChatStream", () => ({
  useChatStream: () => ({
    messages: [],
    sendMessage: vi.fn(),
    streaming: false,
  }),
}));

vi.mock("../hooks/useErConfig", () => ({
  useErConfig: () => ({
    config: {
      report_mode: "stock_initiation",
      report_length: "normal",
      sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
      custom_sections_by_mode: {
        stock_initiation: [],
        stock_update: [],
        sector_research: [],
      },
    },
    loading: false,
    patch: vi.fn().mockResolvedValue(undefined),
  }),
}));

describe("EquityResearchPage", () => {
  it("renders welcome state heading and chips", () => {
    render(<EquityResearchPage />);
    expect(
      screen.getByRole("heading", { name: /equity research/i })
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "AAPL" })).toBeInTheDocument();
  });

  it("Report Settings button opens the modal", () => {
    render(<EquityResearchPage />);
    fireEvent.click(screen.getByRole("button", { name: /report settings/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("clicking a chip fills the input and focuses it", async () => {
    render(<EquityResearchPage />);
    fireEvent.click(screen.getByRole("button", { name: "TSLA" }));
    const input = screen.getByRole("textbox");
    await waitFor(() => expect(input).toHaveValue("TSLA"));
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd frontend && npx vitest run src/pages/EquityResearchPage.test.tsx`
Expected: FAIL — component missing.

- [ ] **Step 3: Write the page**

```tsx
// frontend/src/pages/EquityResearchPage.tsx
import { Settings } from "lucide-react";
import { useRef, useState } from "react";

import { ReportSettingsModal } from "../components/equity-research/ReportSettingsModal";
import { SuggestionChips } from "../components/equity-research/SuggestionChips";
import { useErConfig } from "../hooks/useErConfig";

export function EquityResearchPage() {
  const { config, loading, patch } = useErConfig();
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [active, setActive] = useState(false);

  const onChipSelect = (value: string) => {
    setInput(value);
    inputRef.current?.focus();
  };

  const onSend = () => {
    if (!input.trim()) return;
    setActive(true);
    // Plan 12's useChatStream wiring will be injected here in the follow-up
    // wiring commit — this PR establishes the page shell and welcome state.
  };

  if (loading || !config) {
    return <div className="p-6 text-sm text-[--color-text-tertiary]">Loading…</div>;
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex-shrink-0 flex items-center justify-between border-b border-[--color-border-subtle] px-6">
        <h1 className="text-xl font-semibold">Equity Research</h1>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex items-center gap-2 h-8 px-3 text-sm border border-[--color-border-secondary] rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          <Settings size={16} /> Report Settings
        </button>
      </header>

      {!active && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-6">
          <div className="text-center">
            <h2 className="text-2xl font-semibold">Equity Research</h2>
            <p className="mt-2 text-md text-[--color-text-secondary]">
              Research companies, sectors, and market trends
            </p>
          </div>
          <SuggestionChips onSelect={onChipSelect} />
        </div>
      )}

      {active && (
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {/* Chat transcript renders here via Plan 12's ChatInterface */}
        </div>
      )}

      <div className="flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle]">
        <div className="max-w-[680px] mx-auto flex items-end gap-2">
          <textarea
            ref={inputRef}
            role="textbox"
            rows={1}
            value={input}
            placeholder={
              active
                ? "Ask a follow-up question about the company, sector, or report..."
                : "Enter a ticker, company, or sector (e.g., AAPL, Semiconductors)..."
            }
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            className="flex-1 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 text-md resize-none"
          />
          <button
            type="button"
            onClick={onSend}
            disabled={!input.trim()}
            aria-label="Send"
            className="w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white disabled:opacity-40"
          >
            ↑
          </button>
        </div>
      </div>

      <ReportSettingsModal
        open={settingsOpen}
        config={config}
        onClose={() => setSettingsOpen(false)}
        onSave={async (p) => {
          await patch(p);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Register the route**

In `frontend/src/app/routes.tsx`, add:

```tsx
import { EquityResearchPage } from "../pages/EquityResearchPage";

{
  path: "/equity-research",
  element: <EquityResearchPage />,
}
```

- [ ] **Step 5: Run tests**

Run: `cd frontend && npx vitest run src/pages/EquityResearchPage.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/EquityResearchPage.tsx \
        frontend/src/pages/EquityResearchPage.test.tsx \
        frontend/src/app/routes.tsx
git commit -m "feat(equity-research): add page shell with welcome state and settings modal"
```

---

### Task 17: Manual smoke test + flip README row to Draft

- [ ] **Step 1: Backend smoke — start the server and exercise the routes**

```bash
uv run openlia serve &
SERVER_PID=$!
sleep 2

curl -s -c cookies.txt -b cookies.txt \
  -XPOST http://localhost:8000/api/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"admin@example.com","password":"<dev_password>"}' | head

curl -s -b cookies.txt http://localhost:8000/departments/equity-research/config | jq .

curl -s -b cookies.txt -XPUT \
  http://localhost:8000/departments/equity-research/config \
  -H 'content-type: application/json' \
  -d '{"report_length":"elaborative"}' | jq .

kill $SERVER_PID
```

Expected: `report_length` flips to `elaborative` in the PUT response.

- [ ] **Step 2: Frontend smoke — dev server, welcome state, modal open**

```bash
cd frontend && npm run dev
```

Open `http://localhost:5173/equity-research`. Verify:
- Welcome heading + subtext centered.
- 4 ticker chips + "From Portfolio" chip render.
- Report Settings button opens the modal.
- Switching the mode toggle replaces the section list.
- Adding a custom section and clicking Save closes the modal; reopening shows it retained.

- [ ] **Step 3: Flip the README row to Draft**

Edit `planning/implementation-plans/README.md`:

```diff
-| 14 | 5 | Equity Research department (initiation / update / sector) | Not started | — |
+| 14 | 5 | Equity Research department (initiation / update / sector) | Draft | `2026-04-17-phase-14-equity-research.md` |
```

- [ ] **Step 4: Commit**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plans): mark Plan 14 (Equity Research) as Draft"
```

---

## Self-Review Summary

**Spec coverage:**
- Three report modes (initiation / update / sector) — Tasks 1, 3, 6, 8, 13.
- Per-mode section selection — Tasks 3, 6, 7, 13.
- Custom sections per mode — Tasks 3, 6, 7, 13.
- Report length (concise / normal / elaborative) — Tasks 2, 4, 6, 7, 13.
- LLM chatbot for follow-ups — Tasks 10, 16.
- Report save + download — inherited from Plan 13; surfaced in Task 15's `ReportCard`.
- Welcome state (suggestion chips + From Portfolio) — Task 14.
- Active state (chat pane + pinned input) — Task 16.
- Report Settings modal matching spec layout — Task 13.
- Data requirements (stock_quote / company_profile / financial_statements / news / history / analyst / insider / earnings) — Task 1 (department class declares them; runtime maps them via Plan 3).

**Type consistency:**
- `ReportMode` literal is defined identically in core (`EquityResearchMode`) and frontend (`ReportMode`). Both list the three modes; if they diverge, the type system breaks at the route boundary.
- `report_length` enum is shared across Tasks 4 (DB CHECK), 6 (service DTO), 11 (frontend type), 13 (modal).
- Section ids in `section-catalog.ts` (Task 13) must match the IDs in Plan 13's framework JSON — Task 13 Step 3 flags verification as required.

---

## Post-audit corrections (2026-04-24)

The following items were re-baselined against `EquityResearchPageSpec.md` during the Phase 14 deep audit and shipped under `fix/phase-14-equity-research`. Sections of the original plan that contradict these corrections are **superseded**.

- **Active layout (single-column)** — supersedes split-panel `<div className="flex flex-1 min-h-0">` in Task 15/16. The Active state now renders one full-width `ChatInterface`; the `ReportCard` and progress / error bubbles are injected as `extraInlineMessages`. The shared `FileViewerProvider` (Phase 12) opens the global drawer/route from the card's `Open Report` action.
- **Suggestion chip auto-submit (NEW-14-03)** — chips fill the input AND trigger `/report` POST exactly once. Old test pinning "fills only" behavior was rewritten.
- **DOCX export (NEW-14-04)** — `ReportCard` Download is now a Radix dropdown with PDF + DOCX entries. Backend `services/report_export.py:export_report_docx` and `GET /reports/{id}/docx` ship as new code paths; `python-docx` is a server-only dependency. Phase 13 P1-01 field names (`metric_cards.metrics`, `table.headers/rows`, `key_finding.content`, `rating_badge.rating`) are honoured.
- **ER chat threads `session_id` (P1-03)** — `POST /departments/equity-research/chat` accepts `session_id`, persists user/assistant messages to the chat session, and forwards the id into `ChatRunner.run`. Frontend `ChatInterface` accepts `streamUrl` + `bodyExtras` so the page can route follow-up turns to the ER-specific endpoint.
- **Per-section streaming events (NEW-14-06)** — runtime emits `report.section.start` and `report.section.complete` (plus optional `report.section.chunk`) around the writing pass. `useReportStream` tracks `sections[]` with status transitions; Active layout shows a live checklist instead of a static title list.
- **Retry button (NEW-14-07)** — error state in chat inlines `[Try again]` (`RotateCcw`) which re-issues the last `startReport(...)` via `useReportStream.retry()`.
- **Save-to-Repo from card (NEW-14-05)** — `ReportCard.onSave` calls `saveReportToRepo(reportId)` and flips the bookmark icon to filled.
- **Loading skeleton (NEW-14-08)** — initial config-load placeholder is a header-+-chip skeleton row (`animate-pulse`).

Test gap closure (NEW-14-tests):
- Backend: `test_equity_research_chat_route.py` adds session_id threading + reuse-session coverage; `test_equity_research_runner.py` adds report_length-via-resolve_active; `test_equity_research_config_route.py` adds unknown-mode 400 + PUT/GET round-trip; `test_reports.py` adds DOCX zip-header + auth coverage.
- Frontend: `EquityResearch.test.tsx`, `ReportCard.test.tsx`, `FromPortfolioPicker.test.tsx`, `useReportStream.test.tsx` add the matching SSE-happy-path / dropdown / section-reducer assertions.
