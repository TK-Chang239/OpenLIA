# Morning Briefing Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Contracts reference (do not restate — follow README.md verbatim):**
> - Cross-plan contracts locked 2026-04-20 (HTTP prefixes, `reports`/`repo_items`/`user_prefs`/`wizard_state`, runtime event imports/fields, `ReportRequest` shape).
> - Current backend contract (model imports, auth router factory, auth response shape, UUID-36 ids, LLM admin prefix, runtime imports).
> - Patterns locked after 2026-04-23 Phase 12-15 remediation (named-event SSE framing, chat stream endpoint shape, report stream endpoint shape, `useReportStream` hook, `ChatReportThumbnail` wire shape, `/reports` endpoint surface, `suggest_redirect`, scheduler "one schedule per (job_type, user_id)", `str(uuid.uuid4())` ids).
> - Ancillary lock: length-branching prompts use mapped values (`brief`/`standard`/`long`).

**Goal:** Ship the Morning Briefing (MB) department so users can (1) configure a Coverage List of 7 fixed report sections plus user-defined custom sections, (2) attach topic keywords (with optional notes) under each standard section, (3) toggle Reference Portfolio on the Upcoming Preview section, (4) configure one cron schedule per user that fires the briefing (using `days_of_week` + `label` to express multi-slot intent), (5) generate on-demand briefings via named-event SSE streaming, (6) hold follow-up chat conversations about any generated briefing through the shipped `ChatInterface`, and (7) browse previously generated briefings through the shared `/reports` surface filtered by `?department=morning_briefing`.

**Architecture:**
- **Core** registers a `MorningBriefingDepartment` (one report mode: `morning_briefing`). The prompt YAML at `packages/core/src/openlia/prompts/morning_briefing.yaml` is rewritten to branch on `ReportRequest.length` (`brief`/`standard`/`long`), render enabled sections + topic keywords + custom sections + reference portfolio context, and consume the relocated `morning_briefing.json` framework + `morning_briefing_style_guide.md` through the shared `load_framework_customized()` helper from Plan 13.
- **Server** adds one new table — `mb_user_configs` (sections + custom sections + length + reference-portfolio toggle) — a config service (`mb_config`), a schedule service (`mb_schedules`) that is hot-reloaded into the running `SchedulerService` through the shipped one-schedule-per-user `add_schedule`/`modify_schedule`/`remove_schedule` API, an `MBRequestBuilder` implementation (`mb_request_builder`) that fulfills the Plan 6 `MBRequestBuilder` Protocol by merging config + (optional) `PortfolioHolding` rows into a `ReportRequest`, an on-demand orchestrator `mb_runner.run_on_demand()`, and a `/departments/morning-briefing/*` route factory. The real `MBRequestBuilder` is wired into `build_scheduler_service(mb_builder=...)` at app startup.
- **Frontend** replaces the placeholder `pages/departments/MorningBriefing.tsx` with a full page composition: Archive View (date-grouped cards over `/reports?department=morning_briefing`), Settings View (sections + custom sections + schedule), an `OnDemandBriefingButton` that streams through `useReportStream`, a `ChatInterface` session bound to `department="morning_briefing"` for follow-up Q&A, and `ChatReportThumbnail` rendering inside the chat pane.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, APScheduler 4.x (hot-reload).
- Frontend: React 18 + TypeScript strict, Framer Motion, react-router-dom, Radix UI primitives (`Dialog`, `Popover`, `Checkbox`, `ToggleGroup`), Vitest + React Testing Library.

**Depends on:**
- Plan 1A: `reports`, `chat_sessions`, `chat_messages`, `portfolio_holdings`, `users` tables; `SessionLocal`.
- Plan 1B: `mb_schedules`, `job_runs`, `user_notifications` tables.
- Plan 2: session middleware + `build_require_auth` router factory.
- Plan 3: data requirement adapter dispatcher; `company_news`, `economic_events`, `stock_quote`, `historical_prices`, `macro_indicators` adapters.
- Plan 4: LLM provider system; `DEPARTMENT_DEFAULT_TIERS["morning_briefing"] == EVERYDAY`.
- Plan 5: `ReportRunner`, `ChatRunner`, prompt loader, SSE event taxonomy, `ReportRequest`.
- Plan 6: `MBRequestBuilder` Protocol, `StubMBRequestBuilder`, `build_scheduler_service(mb_builder=...)`, `SchedulerService.add_schedule`/`modify_schedule`/`remove_schedule` keyed by `job_key(job_type, user_id)` — **one schedule per user per job type**.
- Plan 8: frontend shell (`FileViewerProvider`, `NotificationBadge`, design tokens).
- Plan 12: `ChatInterface`, `ChatHistory`, `FileViewer`, `useChatStream`, `ChatReportThumbnail` wire shape.
- Plan 13: `ReportSchema`, framework loader, `report_store.create_report`, `ReportRenderer`, `ReportCard`, `useReportStream`, `/reports` list + filter + PDF export surface.
- Plan 15 (pattern reference only, not a runtime dep): EU mirrors the scheduled-scan + on-demand + config layout; MB reuses the shape not the code.

**Unblocks:**
- Plan 19 (Macro Research) consumes MB cross-department snapshots; MB's public consumer pattern is validated by this plan.
- Plan 21 (Portfolio): MB's Reference Portfolio toggle demonstrates the `PortfolioHolding` cross-plan read pattern.

---

## Design Rules

1. **One report mode: `morning_briefing`.** The framework JSON declares `"report_mode": "morning_briefing"`. Every path — scheduled briefing, on-demand — writes `report_type="morning_briefing"` to `reports.report_type`. `ReportRequest.mode` stays `"morning_briefing"`.
2. **Tier is fixed at `everyday`.** Per `DEPARTMENT_DEFAULT_TIERS["morning_briefing"] = EVERYDAY` (Plan 4).
3. **One schedule per (job_type, user_id).** Plan 6 `SchedulerService` rejects multiple concurrent schedules per user per `JobType`. The `mb_schedules` row therefore represents the **single** MB schedule for the user. Multi-slot intent (e.g., "Pre-Market 07:00 ET" and "Post-Market 16:30 ET") is **out of scope for v1** — v1 ships one schedule per user, with `label` and `days_of_week` expressing intent. A follow-up plan can extend the scheduler to support multiple slots.
4. **Standard section ids are framework-owned.** The 7 section ids in `morning_briefing.json` (`executive_summary`, `global_macro`, `country_news`, `market_news`, `sector_news`, `stock_news`, `upcoming_preview`) are the source of truth. The server-side request builder strips unchecked section ids from the request; the prompt renders only enabled sections.
5. **Topic keywords per section live inside `mb_user_configs.section_topics`.** Each standard section id maps to a list of `{topic: str, notes: str}`. The prompt iterates enabled sections and interpolates the topics with notes when present.
6. **Custom sections carry `{id, title, description}`.** `id` is `str(uuid.uuid4())` — no `custom_<slug>_<random>` prefixes (see README pattern #9). `title` required; `description` injected into the prompt as the LLM instruction.
7. **Reference Portfolio is a per-user toggle on Upcoming Preview.** When enabled AND the user has one or more `PortfolioHolding` rows, the request builder injects a compact list of `{ticker, name}` into `ReportRequest.custom_sections` context under a dedicated `reference_portfolio` field. If `portfolio_available` is False (Plan 21 not shipped or no holdings), the toggle is stored but has no effect; the prompt treats missing `reference_portfolio` as "skip this pass" gracefully. **This plan does not depend on Plan 21 shipping first.**
8. **Per-user length mapping.** `mb_user_configs.report_length` uses `{concise, normal, elaborative}` for user-facing display; service call-sites map to `ReportRequest.length ∈ {brief, standard, long}` via `_LENGTH_MAP`. Do not retroactively change Plan 5.
9. **Scheduled runs produce `user_notifications` via Plan 6's executor.** This plan does **not** re-implement notification plumbing — it only supplies the `MBRequestBuilder` that feeds the shipped `MBBriefingExecutor`.
10. **On-demand runs are named-event SSE.** `POST /api/departments/morning-briefing/report` streams `event: <type>\ndata: <json>\n\n` frames that terminate in `report.saved {report_id}` (persistence) or `report.error {message}` (failure). Frontend consumes via the shipped `useReportStream` hook.
11. **Chat is session-bound through the shipped `GET /api/chat/sessions/{session_id}/stream` endpoint.** The session carries `department="morning_briefing"`. This plan does not ship a bespoke `POST /chat` route for MB (README pattern #2).
12. **Framework files are read-only inside the core package.** User customization layers at request time via `load_framework_customized()`.
13. **TDD everywhere.** Failing test -> implementation -> green run -> commit per step.
14. **No placeholders.** Real code, real commands, real expected output in every step.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
prompts/
    morning_briefing.yaml               # MODIFY — full rewrite; branches on ReportRequest.length;
                                        #          renders enabled sections + topic keywords + notes;
                                        #          renders custom sections; renders reference_portfolio block.
departments/
    morning_briefing.py                 # NEW — MorningBriefingDepartment dataclass.
    __init__.py                         # MODIFY — export MorningBriefingDepartment.
reports/frameworks/
    morning_briefing.json               # READ-ONLY — already shipped in Plan 13.
    morning_briefing_style_guide.md     # READ-ONLY — already shipped in Plan 13.
```

### Server (`packages/server/src/openlia_server/`)

```
db/
    models/
        departments.py                  # MODIFY — append MbUserConfig.
        __init__.py                     # MODIFY — export MbUserConfig.
    migrations/versions/
        2026_04_23_2100_mb_user_configs.py   # NEW.
services/
    mb_config.py                        # NEW — per-user MB config (get/update with defaults).
    mb_schedules.py                     # NEW — CRUD on mb_schedules; hot-reloads SchedulerService.
    mb_request_builder.py               # NEW — implements MBRequestBuilder Protocol (Plan 6).
    mb_runner.py                        # NEW — on-demand orchestrator (ReportRequest -> ReportRunner -> report_store).
routes/departments/
    morning_briefing.py                 # NEW — /config, /schedule, /report (SSE), /chat/session.
scheduler/
    wiring.py                           # MODIFY — wire real MBRequestBuilder default in build_scheduler_service.
app.py                                  # MODIFY — register router + inject MB builder at startup.
```

### Frontend (`frontend/src/`)

```
api/
    morning-briefing.ts                 # NEW — typed HTTP client.
lib/morning-briefing/
    section-catalog.ts                  # NEW — 7 default section ids + titles + hint text.
hooks/
    useMbConfig.ts                      # NEW — SWR-style config fetch + save.
    useMbSchedule.ts                    # NEW — SWR-style schedule fetch + upsert + delete.
    useMbReports.ts                     # NEW — wraps GET /reports?department=morning_briefing.
    useMbChatSession.ts                 # NEW — resolves-or-creates the MB chat session id.
components/morning-briefing/
    MBArchiveView.tsx                   # NEW — date-grouped report cards.
    MBReportCard.tsx                    # NEW — single card with Open + Download buttons.
    MBSettingsView.tsx                  # NEW — sections + custom sections + schedule editor.
    SectionRow.tsx                      # NEW — one standard section with topic chips.
    TopicChip.tsx                       # NEW — chip with notes popover.
    NotesPopover.tsx                    # NEW — textarea + Done.
    CustomSectionRow.tsx                # NEW — editable name + description card.
    ScheduleRow.tsx                     # NEW — single schedule row (edit + remove).
    AddScheduleModal.tsx                # NEW — time + tz + days + label.
    OnDemandBriefingButton.tsx          # NEW — starts useReportStream + opens FileViewer on report.saved.
pages/departments/
    MorningBriefing.tsx                 # MODIFY — full page composition (was a stub).
```

---

## Task Overview

1. Core — `MorningBriefingDepartment` class.
2. Core — Rewrite `morning_briefing.yaml` prompt with length + section + topic + custom + reference_portfolio rendering.
3. Server — `MbUserConfig` model.
4. Server — Alembic migration for `mb_user_configs`.
5. Server — `mb_config` service.
6. Server — `mb_schedules` service (CRUD + hot-reload, enforcing one-per-user).
7. Server — `mb_request_builder` service (implements Plan 6 `MBRequestBuilder`).
8. Server — `mb_runner` on-demand orchestrator.
9. Server — `/departments/morning-briefing/config` routes (GET/PUT).
10. Server — `/departments/morning-briefing/schedule` routes (GET/PUT/DELETE).
11. Server — `/departments/morning-briefing/report` SSE route (POST, named events).
12. Server — `/departments/morning-briefing/chat/session` route (POST; resolves-or-creates the MB chat session).
13. Server — Wire real `MbRequestBuilderImpl` into `build_scheduler_service` at app startup.
14. Frontend — `api/morning-briefing.ts` typed client.
15. Frontend — Section catalog + hooks (`useMbConfig`, `useMbSchedule`, `useMbReports`, `useMbChatSession`).
16. Frontend — `MBReportCard` + `MBArchiveView`.
17. Frontend — `SectionRow` + `TopicChip` + `NotesPopover`.
18. Frontend — `CustomSectionRow`.
19. Frontend — `ScheduleRow` + `AddScheduleModal`.
20. Frontend — `MBSettingsView`.
21. Frontend — `OnDemandBriefingButton` (uses `useReportStream`).
22. Frontend — `pages/departments/MorningBriefing.tsx` composition + route registration.
23. Manual smoke test + update README + add endpoint/authorization matrix rows.

---

### Task 1: Core — `MorningBriefingDepartment` class

The department advertises: name, display name, prompt name, tier, data requirement lists, valid modes (one: `morning_briefing`), and framework name.

**Files:**
- Create: `packages/core/src/openlia/departments/morning_briefing.py`
- Modify: `packages/core/src/openlia/departments/__init__.py` (export `MorningBriefingDepartment`)
- Test: `packages/core/tests/departments/test_morning_briefing.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_morning_briefing.py
import pytest

from openlia.departments.morning_briefing import (
    MorningBriefingDepartment,
    MorningBriefingMode,
)


def test_mb_identifies_itself():
    d = MorningBriefingDepartment()
    assert d.name == "morning_briefing"
    assert d.display_name == "Morning Briefings"
    assert d.prompt_name == "morning_briefing"


def test_mb_single_mode():
    assert set(MorningBriefingDepartment().valid_modes) == {"morning_briefing"}


def test_mb_tier_is_everyday():
    d = MorningBriefingDepartment()
    assert d.tier_for("morning_briefing") == "everyday"


def test_mb_tier_for_unknown_mode_raises():
    with pytest.raises(ValueError):
        MorningBriefingDepartment().tier_for("bogus")


def test_mb_basic_data_requirements():
    reqs = MorningBriefingDepartment().data_requirement_types
    for name in ("company_news", "economic_events"):
        assert name in reqs


def test_mb_optional_data_requirements():
    soft = MorningBriefingDepartment().optional_requirement_types
    for name in (
        "stock_quote",
        "historical_prices",
        "macro_indicators",
    ):
        assert name in soft


def test_mb_framework_name():
    assert MorningBriefingDepartment().framework_name("morning_briefing") == "morning_briefing"


def test_mb_has_no_extra_tools():
    assert MorningBriefingDepartment().extra_tools == ()


def test_mb_mode_literal_type():
    from typing import get_args
    assert set(get_args(MorningBriefingMode)) == {"morning_briefing"}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_morning_briefing.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments.morning_briefing'`.

- [ ] **Step 3: Write the department class**

```python
# packages/core/src/openlia/departments/morning_briefing.py
"""Morning Briefing — report-producing department with a single morning_briefing mode."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openlia.departments.base import Tier


MorningBriefingMode = Literal["morning_briefing"]


@dataclass(frozen=True)
class MorningBriefingDepartment:
    name: str = "morning_briefing"
    display_name: str = "Morning Briefings"
    prompt_name: str = "morning_briefing"
    data_requirement_types: tuple[str, ...] = (
        "company_news",
        "economic_events",
    )
    optional_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "historical_prices",
        "macro_indicators",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()

    @property
    def valid_modes(self) -> tuple[MorningBriefingMode, ...]:
        return ("morning_briefing",)

    def tier_for(self, mode: str) -> Tier:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown MB mode: {mode}")
        return "everyday"

    def framework_name(self, mode: str) -> str:
        if mode not in self.valid_modes:
            raise ValueError(f"unknown MB mode: {mode}")
        return "morning_briefing"
```

- [ ] **Step 4: Export the class**

In `packages/core/src/openlia/departments/__init__.py`, add the import and extend `__all__`:

```python
from openlia.departments.morning_briefing import (
    MorningBriefingDepartment,
    MorningBriefingMode,
)

__all__ = [
    *__all__,  # existing exports
    "MorningBriefingDepartment",
    "MorningBriefingMode",
]
```

Also ensure `get_department("morning_briefing")` (added in Plan 13/14 for `suggest_redirect`) returns a `MorningBriefingDepartment()` instance. If the registry is a static dict, append the entry there.

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/departments/test_morning_briefing.py -v`
Expected: PASS (9 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/departments/morning_briefing.py \
        packages/core/src/openlia/departments/__init__.py \
        packages/core/tests/departments/test_morning_briefing.py
git commit -m "feat(core): add MorningBriefingDepartment class with morning_briefing mode"
```

---

### Task 2: Core — Rewrite `morning_briefing.yaml` prompt

The existing YAML at `packages/core/src/openlia/prompts/morning_briefing.yaml` is a placeholder. Rewrite to branch on `ReportRequest.length` (`brief`/`standard`/`long`), iterate enabled sections + topics + notes, iterate custom sections, and render the `reference_portfolio` context block when present. Follows the `earnings_update.yaml` canonical length-branching shape (README ancillary lock).

**Files:**
- Modify: `packages/core/src/openlia/prompts/morning_briefing.yaml`
- Test: `packages/core/tests/prompts/test_morning_briefing_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/prompts/test_morning_briefing_prompt.py
from pathlib import Path

import pytest

from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    root = Path(__file__).resolve().parents[2] / "src" / "openlia" / "prompts"
    return PromptLoader(root=root)


def test_system_prompt_mentions_briefing_role(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.system",
        {"report_length": "normal"},
    )
    assert "briefing" in text.lower()
    assert "analyst" in text.lower()


def test_user_prompt_renders_enabled_sections(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {
            "user_input": "",
            "report_length": "standard",
            "enabled_sections": ["executive_summary", "global_macro"],
            "section_topics": {
                "global_macro": [
                    {"topic": "War", "notes": "Russia-Ukraine"},
                    {"topic": "Energy", "notes": ""},
                ],
            },
            "custom_sections": [],
            "reference_portfolio": None,
        },
    )
    assert "executive_summary" in text
    assert "global_macro" in text
    assert "War" in text
    assert "Russia-Ukraine" in text
    assert "Energy" in text


def test_user_prompt_renders_custom_sections(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {
            "user_input": "",
            "report_length": "standard",
            "enabled_sections": [],
            "section_topics": {},
            "custom_sections": [
                {"id": "abc", "title": "My Macro Focus",
                 "description": "Focus on EUR and JPY crosses."},
            ],
            "reference_portfolio": None,
        },
    )
    assert "My Macro Focus" in text
    assert "EUR" in text or "JPY" in text


def test_user_prompt_includes_reference_portfolio_when_provided(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {
            "user_input": "",
            "report_length": "standard",
            "enabled_sections": ["upcoming_preview"],
            "section_topics": {},
            "custom_sections": [],
            "reference_portfolio": [
                {"ticker": "AAPL", "name": "Apple Inc."},
                {"ticker": "NVDA", "name": "NVIDIA"},
            ],
        },
    )
    assert "AAPL" in text
    assert "NVDA" in text


def test_user_prompt_omits_reference_portfolio_when_none(loader: PromptLoader) -> None:
    text = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {
            "user_input": "",
            "report_length": "standard",
            "enabled_sections": [],
            "section_topics": {},
            "custom_sections": [],
            "reference_portfolio": None,
        },
    )
    assert "Reference portfolio" not in text


def test_length_knob_changes_prompt(loader: PromptLoader) -> None:
    brief = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {"user_input": "", "report_length": "brief",
         "enabled_sections": [], "section_topics": {},
         "custom_sections": [], "reference_portfolio": None},
    )
    long_ = loader.render(
        "morning_briefing",
        "report.morning_briefing.user",
        {"user_input": "", "report_length": "long",
         "enabled_sections": [], "section_topics": {},
         "custom_sections": [], "reference_portfolio": None},
    )
    assert brief \!= long_
    assert "brief" in brief.lower()
    assert "long" in long_.lower() or "elaborative" in long_.lower()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/prompts/test_morning_briefing_prompt.py -v`
Expected: FAIL — existing YAML does not expose the `report.morning_briefing.system` / `.user` nodes with the required inputs.

- [ ] **Step 3: Rewrite the prompt YAML**

```yaml
# packages/core/src/openlia/prompts/morning_briefing.yaml
# Morning Briefing department prompt.
# Single mode (morning_briefing); branches on report_length using mapped
# values ("brief" | "standard" | "long") per the ancillary lock.

includes:
  - base_report

report:
  morning_briefing:
    system: |
      You are a Morning Briefing analyst producing a daily multi-section
      briefing for a buy-side portfolio manager. You deliver deterministic,
      sourced, numbers-anchored writing. You avoid hedging and marketing
      language. You follow the provided framework exactly — section order,
      section ids, and block types are not negotiable.

      --- STYLE GUIDE ---
      {{ style_guide }}
      --- END STYLE GUIDE ---

      {% include "shared/output_discipline.yaml.j2" %}

    user: |
      {% include "base_report.report_context" %}

      User instructions:
      {{ user_input }}

      Report length: **{{ report_length }}**
      {% if report_length == "brief" %}
      Keep the briefing brief. Favor dense bullet lists over paragraphs;
      cap any text block at 3 sentences; omit optional explanatory passages.
      {% elif report_length == "long" %}
      Write a long, elaborative briefing. Expand text blocks to 6-10
      sentences where they add insight; include multiple qualitative angles;
      cite secondary context (industry, competitors) where relevant.
      {% else %}
      Write a standard-length briefing. Text blocks 4-6 sentences; tables
      and metric cards are the primary vehicle for quantitative comparison.
      {% endif %}

      Enabled sections: {{ enabled_sections | tojson }}
      Only include sections whose id is in that list. Drop every other
      standard section from the output.

      {% if section_topics %}
      Topic keywords per section (cover only these topics, in this order):
      {% for section_id, topics in section_topics.items() %}
      - {{ section_id }}:
        {% for t in topics %}
        - {{ t.topic }}{% if t.notes %} (notes: {{ t.notes }}){% endif %}
        {% endfor %}
      {% endfor %}
      {% endif %}

      {% if custom_sections %}
      Custom sections to append after the standard sections (use the
      description as the LLM instruction for what each section should
      cover):
      {% for cs in custom_sections %}
      - id: {{ cs.id }}
        title: {{ cs.title }}
        description: {{ cs.description }}
      {% endfor %}
      {% endif %}

      {% if reference_portfolio %}
      Reference portfolio for the Upcoming Preview section. When producing
      the `upcoming_preview` section, include a "Portfolio Watch" block that
      lists each holding's upcoming catalyst within the next 5 trading days:
      {% for h in reference_portfolio %}
      - {{ h.ticker }}{% if h.name %} ({{ h.name }}){% endif %}
      {% endfor %}
      {% endif %}

      Follow the framework exactly. Emit only the ReportSchema JSON; no
      commentary outside the schema.
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/prompts/test_morning_briefing_prompt.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/morning_briefing.yaml \
        packages/core/tests/prompts/test_morning_briefing_prompt.py
git commit -m "feat(core): rewrite morning_briefing prompt with length + sections + topics + reference_portfolio"
```

---

### Task 3: Server — `MbUserConfig` model

One table: `mb_user_configs`. One row per user. Holds `report_length`, `enabled_section_ids` (JSON array), `section_topics` (JSON object mapping section_id -> list of `{topic, notes}`), `custom_sections` (JSON array of `{id, title, description}`), `reference_portfolio` (bool).

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/departments.py`
- Modify: `packages/server/src/openlia_server/db/models/__init__.py`
- Test: `packages/server/tests/db/test_mb_models.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_mb_models.py
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import MbUserConfig


def _mk_user(db: Session, user_id: str = "u_mb_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name="MB",
             password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_mb_config_columns(create_tables) -> None:
    cols = {c["name"] for c in inspect(MbUserConfig).columns}
    for expected in {
        "id", "user_id", "report_length",
        "enabled_section_ids", "section_topics",
        "custom_sections", "reference_portfolio",
        "created_at", "updated_at",
    }:
        assert expected in cols


def test_mb_config_one_per_user(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_mb_1",
        report_length="normal",
        enabled_section_ids=["executive_summary"],
        section_topics={},
        custom_sections=[],
        reference_portfolio=False,
    ))
    db_session.commit()
    db_session.add(MbUserConfig(
        id="c2", user_id="u_mb_1",
        report_length="normal",
        enabled_section_ids=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=False,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_mb_config_length_check_constraint(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c3", user_id="u_mb_1",
        report_length="tiny",  # invalid
        enabled_section_ids=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=False,
    ))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_mb_config_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c4", user_id="u_mb_1",
        report_length="normal",
        enabled_section_ids=[],
        section_topics={},
        custom_sections=[],
        reference_portfolio=False,
    ))
    db_session.commit()
    db_session.query(User).filter_by(id="u_mb_1").delete()
    db_session.commit()
    assert db_session.query(MbUserConfig).count() == 0
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_mb_models.py -v`
Expected: FAIL (`ImportError` on `MbUserConfig`).

- [ ] **Step 3: Append the model**

In `packages/server/src/openlia_server/db/models/departments.py`, append:

```python
from sqlalchemy import Boolean, CheckConstraint, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base
from openlia_server.db.mixins import TimestampMixin


class MbUserConfig(Base, TimestampMixin):
    """Per-user Morning Briefing config. One row per user."""

    __tablename__ = "mb_user_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    report_length: Mapped[str] = mapped_column(
        String(16), nullable=False, default="normal"
    )
    enabled_section_ids: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    section_topics: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    custom_sections: Mapped[list[dict]] = mapped_column(
        JSON, nullable=False, default=list
    )
    reference_portfolio: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    __table_args__ = (
        CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_mb_user_configs_length",
        ),
    )
```

- [ ] **Step 4: Export from models package**

In `packages/server/src/openlia_server/db/models/__init__.py`, add `MbUserConfig` to the imports and `__all__`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/db/test_mb_models.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/models/departments.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/tests/db/test_mb_models.py
git commit -m "feat(server): add mb_user_configs model"
```

---

### Task 4: Server — Alembic migration for `mb_user_configs`

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026_04_23_2100_mb_user_configs.py`
- Test: `packages/server/tests/db/test_mb_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_mb_migration.py
from sqlalchemy import inspect


def test_migration_creates_mb_user_configs(alembic_upgraded_engine) -> None:
    insp = inspect(alembic_upgraded_engine)
    assert "mb_user_configs" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("mb_user_configs")}
    assert {
        "id", "user_id", "report_length",
        "enabled_section_ids", "section_topics",
        "custom_sections", "reference_portfolio",
        "created_at", "updated_at",
    } <= cols


def test_migration_has_unique_on_user(alembic_upgraded_engine) -> None:
    insp = inspect(alembic_upgraded_engine)
    uqs = insp.get_unique_constraints("mb_user_configs")
    names = {uq["name"] for uq in uqs}
    # Either a named UQ or a unique index covers the constraint; accept either.
    has_uq = any("user_id" in uq.get("column_names", []) for uq in uqs)
    idx = insp.get_indexes("mb_user_configs")
    has_unique_idx = any(
        i.get("unique") and i.get("column_names") == ["user_id"] for i in idx
    )
    assert has_uq or has_unique_idx


def test_migration_downgrade_drops_table(alembic_engine_downgrade) -> None:
    engine = alembic_engine_downgrade("-1")
    insp = inspect(engine)
    assert "mb_user_configs" not in insp.get_table_names()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_mb_migration.py -v`
Expected: FAIL — no migration creating `mb_user_configs` exists yet.

- [ ] **Step 3: Write the migration**

Look up the current head revision:

```bash
uv run alembic -c packages/server/alembic.ini heads
```

Replace `<CURRENT_HEAD>` below with the reported id.

```python
# packages/server/src/openlia_server/db/migrations/versions/2026_04_23_2100_mb_user_configs.py
"""mb_user_configs

Revision ID: 20260423_2100_mb
Revises: <CURRENT_HEAD>
Create Date: 2026-04-23 21:00:00
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260423_2100_mb"
down_revision = "<CURRENT_HEAD>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mb_user_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("report_length", sa.String(16), nullable=False,
                  server_default="normal"),
        sa.Column("enabled_section_ids", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        sa.Column("section_topics", sa.JSON(), nullable=False,
                  server_default=sa.text("'{}'")),
        sa.Column("custom_sections", sa.JSON(), nullable=False,
                  server_default=sa.text("'[]'")),
        sa.Column("reference_portfolio", sa.Boolean(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "report_length IN ('concise', 'normal', 'elaborative')",
            name="ck_mb_user_configs_length",
        ),
    )


def downgrade() -> None:
    op.drop_table("mb_user_configs")
```

- [ ] **Step 4: Run migration upgrade + downgrade + upgrade**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
uv run alembic -c packages/server/alembic.ini downgrade -1
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: all three succeed without errors.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/db/test_mb_migration.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026_04_23_2100_mb_user_configs.py \
        packages/server/tests/db/test_mb_migration.py
git commit -m "feat(server): alembic migration for mb_user_configs"
```

---

### Task 5: Server — `mb_config` service

Per-user config with merged defaults: all 7 standard sections enabled, empty topics, empty customs, `normal` length, `reference_portfolio=False`.

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_config.py`
- Test: `packages/server/tests/services/test_mb_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_mb_config.py
import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import MbUserConfig
from openlia_server.services import mb_config as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id,
             password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_get_returns_defaults_when_no_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert cfg.report_length == "normal"
    assert len(cfg.enabled_section_ids) == 7
    assert cfg.section_topics == {}
    assert cfg.custom_sections == []
    assert cfg.reference_portfolio is False
    assert db_session.query(MbUserConfig).count() == 0


def test_defaults_match_framework_section_ids(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = svc.get_config(db_session, user_id="u_1")
    assert set(cfg.enabled_section_ids) == {
        "executive_summary", "global_macro", "country_news",
        "market_news", "sector_news", "stock_news", "upcoming_preview",
    }


def test_update_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(
        db_session,
        user_id="u_1",
        report_length="concise",
        enabled_section_ids=["executive_summary", "global_macro"],
        section_topics={"global_macro": [{"topic": "War", "notes": "Russia"}]},
        custom_sections=[{"id": "abc", "title": "My Macro Focus",
                          "description": "FX crosses"}],
        reference_portfolio=True,
    )
    row = db_session.query(MbUserConfig).filter_by(user_id="u_1").one()
    assert row.report_length == "concise"
    assert row.enabled_section_ids == ["executive_summary", "global_macro"]
    assert row.section_topics["global_macro"][0]["topic"] == "War"
    assert row.custom_sections[0]["title"] == "My Macro Focus"
    assert row.reference_portfolio is True


def test_update_is_upsert(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    svc.update_config(db_session, user_id="u_1",
                      report_length="concise",
                      enabled_section_ids=["executive_summary"],
                      section_topics={}, custom_sections=[],
                      reference_portfolio=False)
    svc.update_config(db_session, user_id="u_1",
                      report_length="elaborative",
                      enabled_section_ids=["global_macro"],
                      section_topics={}, custom_sections=[],
                      reference_portfolio=True)
    rows = db_session.query(MbUserConfig).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].report_length == "elaborative"
    assert rows[0].reference_portfolio is True


def test_update_rejects_invalid_length(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="report_length"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="tiny",
                          enabled_section_ids=[], section_topics={},
                          custom_sections=[], reference_portfolio=False)


def test_update_rejects_unknown_section_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="unknown section"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="normal",
                          enabled_section_ids=["not_a_section"],
                          section_topics={},
                          custom_sections=[], reference_portfolio=False)


def test_update_rejects_custom_section_without_title(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="title"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="normal",
                          enabled_section_ids=[],
                          section_topics={},
                          custom_sections=[{"id": "x", "title": "",
                                            "description": "d"}],
                          reference_portfolio=False)


def test_update_rejects_topic_without_name(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(ValueError, match="topic"):
        svc.update_config(db_session, user_id="u_1",
                          report_length="normal",
                          enabled_section_ids=["global_macro"],
                          section_topics={"global_macro": [
                              {"topic": "", "notes": "x"}]},
                          custom_sections=[], reference_portfolio=False)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_mb_config.py -v`
Expected: FAIL (`ModuleNotFoundError` on `mb_config`).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/mb_config.py
"""Per-user Morning Briefing config: sections, topics, custom sections, length, reference portfolio toggle."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from openlia_server.db.models.departments import MbUserConfig


STANDARD_SECTION_IDS: tuple[str, ...] = (
    "executive_summary",
    "global_macro",
    "country_news",
    "market_news",
    "sector_news",
    "stock_news",
    "upcoming_preview",
)

_VALID_LENGTHS = frozenset({"concise", "normal", "elaborative"})
_STANDARD_SECTION_SET = frozenset(STANDARD_SECTION_IDS)


@dataclass(frozen=True)
class MbConfigDTO:
    report_length: str
    enabled_section_ids: list[str]
    section_topics: dict[str, list[dict]]
    custom_sections: list[dict]
    reference_portfolio: bool


def get_config(db: Session, *, user_id: str) -> MbConfigDTO:
    row = db.query(MbUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return MbConfigDTO(
            report_length="normal",
            enabled_section_ids=list(STANDARD_SECTION_IDS),
            section_topics={},
            custom_sections=[],
            reference_portfolio=False,
        )
    return MbConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids or []),
        section_topics=dict(row.section_topics or {}),
        custom_sections=list(row.custom_sections or []),
        reference_portfolio=bool(row.reference_portfolio),
    )


def update_config(
    db: Session,
    *,
    user_id: str,
    report_length: str,
    enabled_section_ids: list[str],
    section_topics: dict[str, list[dict]],
    custom_sections: list[dict],
    reference_portfolio: bool,
) -> MbConfigDTO:
    if report_length not in _VALID_LENGTHS:
        raise ValueError(f"invalid report_length: {report_length\!r}")

    for sid in enabled_section_ids:
        if sid not in _STANDARD_SECTION_SET:
            raise ValueError(f"unknown section id: {sid\!r}")

    for sid, topics in section_topics.items():
        if sid not in _STANDARD_SECTION_SET:
            raise ValueError(f"unknown section id in topics: {sid\!r}")
        for t in topics:
            if not isinstance(t, dict) or not t.get("topic"):
                raise ValueError(f"topic entry requires non-empty 'topic' in section {sid\!r}")

    for cs in custom_sections:
        if not isinstance(cs, dict) or not cs.get("title"):
            raise ValueError("custom section requires a non-empty title")
        if not cs.get("id"):
            raise ValueError("custom section requires an id")

    row = db.query(MbUserConfig).filter_by(user_id=user_id).one_or_none()
    if row is None:
        row = MbUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            report_length=report_length,
            enabled_section_ids=list(enabled_section_ids),
            section_topics=dict(section_topics),
            custom_sections=list(custom_sections),
            reference_portfolio=bool(reference_portfolio),
        )
        db.add(row)
    else:
        row.report_length = report_length
        row.enabled_section_ids = list(enabled_section_ids)
        row.section_topics = dict(section_topics)
        row.custom_sections = list(custom_sections)
        row.reference_portfolio = bool(reference_portfolio)
    db.commit()
    return MbConfigDTO(
        report_length=row.report_length,
        enabled_section_ids=list(row.enabled_section_ids),
        section_topics=dict(row.section_topics),
        custom_sections=list(row.custom_sections),
        reference_portfolio=bool(row.reference_portfolio),
    )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_mb_config.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/mb_config.py \
        packages/server/tests/services/test_mb_config.py
git commit -m "feat(server): add mb_config service with 7 default sections + topics + reference portfolio"
```

---

### Task 6: Server — `mb_schedules` service

One schedule per user (Plan 6 `job_key` lock). Expose `get_schedule`, `upsert_schedule`, `delete_schedule`. The service writes the single `MbSchedule` row for the user and calls `SchedulerService.add_schedule` / `modify_schedule` / `remove_schedule` as appropriate. The shipped methods take `MbSchedule | EuSchedule` directly (see `scheduler/service.py`).

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_schedules.py`
- Test: `packages/server/tests/services/test_mb_schedules_service.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_mb_schedules_service.py
import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.services import mb_schedules as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id,
             password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


@dataclass
class FakeScheduler:
    added: list[Any] = field(default_factory=list)
    modified: list[Any] = field(default_factory=list)
    removed: list[tuple[str, str]] = field(default_factory=list)

    async def add_schedule(self, schedule):
        self.added.append(schedule)

    async def modify_schedule(self, schedule):
        self.modified.append(schedule)

    async def remove_schedule(self, *, job_type, user_id):
        self.removed.append((job_type.value, user_id))


@pytest.mark.asyncio
async def test_get_returns_none_when_no_schedule(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    dto = svc.get_schedule(db_session, user_id="u_1")
    assert dto is None


@pytest.mark.asyncio
async def test_upsert_creates_row_and_registers(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = await svc.upsert_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market",
        scheduler=sched,
    )
    assert dto.time == "07:00"
    assert dto.label == "Pre-Market"
    row = db_session.query(MbSchedule).filter_by(user_id="u_1").one()
    assert row.time == "07:00"
    assert json.loads(row.days_of_week) == ["mon", "tue", "wed", "thu", "fri"]
    assert len(sched.added) == 1
    assert len(sched.modified) == 0


@pytest.mark.asyncio
async def test_upsert_modifies_existing_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session, user_id="u_1", time="07:00",
        timezone="America/New_York", days_of_week=["mon"],
        label="a", scheduler=sched,
    )
    await svc.upsert_schedule(
        db_session, user_id="u_1", time="08:00",
        timezone="America/New_York", days_of_week=["mon", "tue"],
        label="b", scheduler=sched,
    )
    rows = db_session.query(MbSchedule).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].time == "08:00"
    assert rows[0].label == "b"
    assert len(sched.added) == 1
    assert len(sched.modified) == 1


@pytest.mark.asyncio
async def test_upsert_validates_time(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="time"):
        await svc.upsert_schedule(
            db_session, user_id="u_1", time="25:00",
            timezone="America/New_York", days_of_week=["mon"],
            label="bad", scheduler=sched,
        )


@pytest.mark.asyncio
async def test_upsert_validates_timezone(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="timezone"):
        await svc.upsert_schedule(
            db_session, user_id="u_1", time="07:00",
            timezone="Not/Real", days_of_week=["mon"],
            label="bad", scheduler=sched,
        )


@pytest.mark.asyncio
async def test_upsert_validates_days_of_week(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="days_of_week"):
        await svc.upsert_schedule(
            db_session, user_id="u_1", time="07:00",
            timezone="America/New_York", days_of_week=["funday"],
            label="bad", scheduler=sched,
        )


@pytest.mark.asyncio
async def test_delete_removes_row_and_unregisters(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session, user_id="u_1", time="07:00",
        timezone="America/New_York", days_of_week=["mon"],
        label="a", scheduler=sched,
    )
    await svc.delete_schedule(db_session, user_id="u_1", scheduler=sched)
    assert db_session.query(MbSchedule).count() == 0
    assert sched.removed[-1][1] == "u_1"


@pytest.mark.asyncio
async def test_delete_is_noop_when_missing(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.delete_schedule(db_session, user_id="u_1", scheduler=sched)
    # No row -> no error, no scheduler call.
    assert sched.removed == []


@pytest.mark.asyncio
async def test_get_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session, user_id="u_1", time="07:00",
        timezone="America/New_York", days_of_week=["mon"],
        label="a", scheduler=sched,
    )
    assert svc.get_schedule(db_session, user_id="u_1") is not None
    assert svc.get_schedule(db_session, user_id="u_2") is None
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_mb_schedules_service.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/mb_schedules.py
"""CRUD on mb_schedules. One schedule per user (Plan 6 job_key lock).

Hot-reloads the running SchedulerService via the shipped
`add_schedule` / `modify_schedule` / `remove_schedule` methods.
"""

from __future__ import annotations

import json
import re
import uuid
import zoneinfo
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.scheduler.registry import JobType


_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class MbScheduleDTO:
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class SchedulerControl(Protocol):
    async def add_schedule(self, schedule: MbSchedule) -> None: ...
    async def modify_schedule(self, schedule: MbSchedule) -> None: ...
    async def remove_schedule(self, *, job_type, user_id: str) -> None: ...


def _validate(time: str, timezone: str, days_of_week: list[str]) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid time: {time\!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"invalid timezone: {timezone\!r}") from exc
    if not days_of_week or any(d not in _VALID_DAYS for d in days_of_week):
        raise ValueError(f"invalid days_of_week: {days_of_week\!r}")


def _to_dto(row: MbSchedule) -> MbScheduleDTO:
    return MbScheduleDTO(
        id=row.id,
        user_id=row.user_id,
        time=row.time,
        timezone=row.timezone,
        days_of_week=list(json.loads(row.days_of_week or "[]")),
        label=row.label or "",
        is_enabled=bool(row.is_enabled),
    )


def get_schedule(db: Session, *, user_id: str) -> MbScheduleDTO | None:
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return None
    return _to_dto(row)


async def upsert_schedule(
    db: Session,
    *,
    user_id: str,
    time: str,
    timezone: str,
    days_of_week: list[str],
    label: str,
    scheduler: SchedulerControl,
) -> MbScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    is_new = row is None
    if row is None:
        row = MbSchedule(
            id=str(uuid.uuid4()),
            user_id=user_id,
            time=time,
            timezone=timezone,
            days_of_week=json.dumps(list(days_of_week)),
            label=label,
            is_enabled=True,
        )
        db.add(row)
    else:
        row.time = time
        row.timezone = timezone
        row.days_of_week = json.dumps(list(days_of_week))
        row.label = label
        row.is_enabled = True
    db.commit()
    db.refresh(row)

    if is_new:
        await scheduler.add_schedule(row)
    else:
        await scheduler.modify_schedule(row)

    return _to_dto(row)


async def delete_schedule(
    db: Session,
    *,
    user_id: str,
    scheduler: SchedulerControl,
) -> None:
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return
    db.delete(row)
    db.commit()
    await scheduler.remove_schedule(job_type=JobType.MB_BRIEFING, user_id=user_id)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_mb_schedules_service.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/mb_schedules.py \
        packages/server/tests/services/test_mb_schedules_service.py
git commit -m "feat(server): add mb_schedules service with one-per-user hot-reload into SchedulerService"
```

---

### Task 7: Server — `mb_request_builder` (implements Plan 6 `MBRequestBuilder`)

The scheduler executor calls `builder.build(session, user_id, schedule_id)` and expects back a `ReportRequest`. The builder reads config + (optional) portfolio holdings when `reference_portfolio` is on, then maps config vocab to runtime vocab.

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_request_builder.py`
- Test: `packages/server/tests/services/test_mb_request_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_mb_request_builder.py
import pytest
from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import PortfolioHolding
from openlia_server.db.models.departments import MbUserConfig
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id,
             password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_build_uses_defaults_when_no_config(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    builder = MbRequestBuilderImpl()
    req: ReportRequest = builder.build(session=db_session, user_id="u_1",
                                       schedule_id="s_1")
    assert req.mode == "morning_briefing"
    # 7 default sections enabled.
    assert len(req.enabled_sections) == 7
    # Default length "normal" -> "standard".
    assert req.length == "standard"
    assert req.custom_sections == []


def test_build_maps_length_vocab(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="concise",
        enabled_section_ids=["executive_summary"],
        section_topics={}, custom_sections=[],
        reference_portfolio=False,
    ))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.length == "brief"


def test_build_passes_enabled_sections_and_customs(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="elaborative",
        enabled_section_ids=["executive_summary", "global_macro"],
        section_topics={"global_macro": [{"topic": "War", "notes": "Ukraine"}]},
        custom_sections=[{"id": "abc", "title": "My Focus",
                          "description": "FX desk view"}],
        reference_portfolio=False,
    ))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert req.enabled_sections == ["executive_summary", "global_macro"]
    assert req.length == "long"
    # Custom sections are forwarded as-is for Plan 5.
    assert any(cs["title"] == "My Focus" for cs in req.custom_sections)


def test_build_injects_reference_portfolio_when_enabled(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="normal",
        enabled_section_ids=["upcoming_preview"],
        section_topics={}, custom_sections=[],
        reference_portfolio=True,
    ))
    db_session.add(PortfolioHolding(
        id="h1", user_id="u_1", ticker="AAPL", name="Apple Inc.",
    ))
    db_session.add(PortfolioHolding(
        id="h2", user_id="u_1", ticker="NVDA", name="NVIDIA",
    ))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    # Request body includes the ticker list somewhere the prompt can reach it.
    assert "AAPL" in req.user_input
    assert "NVDA" in req.user_input


def test_build_skips_reference_portfolio_when_toggle_off(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="normal",
        enabled_section_ids=["upcoming_preview"],
        section_topics={}, custom_sections=[],
        reference_portfolio=False,
    ))
    db_session.add(PortfolioHolding(
        id="h1", user_id="u_1", ticker="AAPL", name="Apple Inc.",
    ))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert "AAPL" not in req.user_input


def test_build_reference_portfolio_gracefully_absent(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="normal",
        enabled_section_ids=["upcoming_preview"],
        section_topics={}, custom_sections=[],
        reference_portfolio=True,
    ))
    db_session.commit()
    # Toggle on, but the user has no holdings.
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    # No AAPL/NVDA etc. to inject; no crash.
    assert req.mode == "morning_briefing"


def test_build_user_scoped_portfolio(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="normal",
        enabled_section_ids=["upcoming_preview"],
        section_topics={}, custom_sections=[],
        reference_portfolio=True,
    ))
    db_session.add(PortfolioHolding(id="h1", user_id="u_2", ticker="TSLA", name="Tesla"))
    db_session.commit()
    builder = MbRequestBuilderImpl()
    req = builder.build(session=db_session, user_id="u_1", schedule_id="s_1")
    assert "TSLA" not in req.user_input
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_mb_request_builder.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the builder**

```python
# packages/server/src/openlia_server/services/mb_request_builder.py
"""MBRequestBuilder implementation — fulfills the Plan 6 Protocol.

Reads the user's MB config + (optional) portfolio holdings and composes
the ReportRequest. The scheduler's `MBBriefingExecutor` passes this
through to `ReportRunner`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.content import PortfolioHolding
from openlia_server.services import mb_config as mb_config_svc


_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


def _portfolio_available(session: Session, *, user_id: str) -> list[dict]:
    rows = (
        session.query(PortfolioHolding)
        .filter_by(user_id=user_id)
        .order_by(PortfolioHolding.ticker.asc())
        .all()
    )
    return [{"ticker": r.ticker, "name": r.name} for r in rows]


@dataclass
class MbRequestBuilderImpl:
    """Implements `MBRequestBuilder` from `scheduler.payloads`."""

    def build(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
    ) -> ReportRequest:
        cfg = mb_config_svc.get_config(session, user_id=user_id)

        reference_portfolio: list[dict] | None = None
        if cfg.reference_portfolio:
            holdings = _portfolio_available(session, user_id=user_id)
            if holdings:
                reference_portfolio = holdings

        # The prompt consumes enabled_sections, section_topics, custom_sections,
        # and reference_portfolio directly. Plan 5's ReportRequest carries:
        #   mode, user_input, enabled_sections, custom_sections, length
        # Section topics and reference_portfolio ride inside `user_input` as
        # a JSON block the template can parse (no retroactive extension of
        # ReportRequest). Ancillary fields are serialized deterministically
        # so the prompt render matches regardless of dict ordering.
        extras = {
            "section_topics": cfg.section_topics,
            "reference_portfolio": reference_portfolio,
        }
        user_input = (
            "Generate today's Morning Briefing using the user's coverage list "
            "and configured topics.\n\n"
            + "MB_EXTRAS_JSON:\n"
            + json.dumps(extras, sort_keys=True)
        )

        return ReportRequest(
            mode="morning_briefing",
            user_input=user_input,
            enabled_sections=list(cfg.enabled_section_ids),
            custom_sections=list(cfg.custom_sections),
            length=_LENGTH_MAP.get(cfg.report_length, "standard"),
        )
```

> **Prompt-side adapter:** The prompt template renders `section_topics` and `reference_portfolio` by parsing the `MB_EXTRAS_JSON:` block out of `user_input` in the `ReportRunner`'s prompt context. This is intentionally simple — we avoid changing Plan 5's `ReportRequest` shape and keep all coupling inside the department.

- [ ] **Step 4: Update prompt rendering to accept `MB_EXTRAS_JSON` pass-through**

The prompt Task 2 rewrite already expects `section_topics` and `reference_portfolio` as render-context inputs. The bridge between `ReportRequest.user_input` and those inputs lives in the `ReportRunner` prompt-context hook for the `morning_briefing` department. If the hook is not yet a generic facility, add one narrow adapter at `packages/server/src/openlia_server/services/mb_runner.py` (next task) that splits `MB_EXTRAS_JSON` off `user_input` before invoking `ReportRunner.run()` and passes the extras through the runner's `extra_context` keyword — ship whichever mechanism Plan 5 already exposes for per-department render variables. The test at Task 8 asserts this contract end-to-end.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_mb_request_builder.py -v`
Expected: PASS (7 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/mb_request_builder.py \
        packages/server/tests/services/test_mb_request_builder.py
git commit -m "feat(server): add MbRequestBuilderImpl fulfilling Plan 6 MBRequestBuilder Protocol"
```

---

### Task 8: Server — `mb_runner` on-demand orchestrator

Thin wrapper: builds the request via `MbRequestBuilderImpl`, calls `ReportRunner.run()`, forwards every SSE event to the caller. Persists the report to `report_store.create_report` on `ReportComplete` and yields a synthetic `report.saved` event with the stored id per README pattern #3.

**Files:**
- Create: `packages/server/src/openlia_server/services/mb_runner.py`
- Test: `packages/server/tests/services/test_mb_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_mb_runner.py
from dataclasses import dataclass, field
from typing import AsyncIterator

import pytest
from sqlalchemy.orm import Session

from openlia.llm.runtime.events import (
    ReportComplete, ReportDelta, ReportStart, SseEvent,
)
from openlia.llm.runtime.messages import ReportRequest

from openlia_server.db.models.auth import User
from openlia_server.services.mb_runner import run_on_demand, ReportSavedEvent


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id,
             password_hash="x", is_admin=False)
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

    def create_report(self, *, user_id: str, department: str, report_type: str,
                      title: str, content_markdown: str, content_structured: dict,
                      model_ref: str | None = None) -> str:
        rid = f"r_{len(self.saved) + 1}"
        self.saved.append({
            "user_id": user_id, "report_id": rid, "department": department,
            "report_type": report_type, "title": title,
        })
        return rid


@pytest.mark.asyncio
async def test_on_demand_forwards_events_and_persists(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    complete = ReportComplete(report_id="pending_r",
                              schema={"title": "Morning Briefing 2026-04-23",
                                      "sections": []})
    runner = ScriptedRunner(events=[
        ReportStart(report_id="pending_r", department="morning_briefing",
                    mode="morning_briefing",
                    section_titles=["Executive Summary"]),
        ReportDelta(report_id="pending_r", section_id="executive_summary",
                    delta="Risk-off overnight..."),
        complete,
    ])
    store = FakeReportStore()

    collected: list[SseEvent] = []
    async for ev in run_on_demand(
        session=db_session, user_id="u_1",
        report_runner=runner, report_store=store,
    ):
        collected.append(ev)

    kinds = [type(e).__name__ for e in collected]
    # Stream includes ReportStart + ReportDelta + ReportComplete + ReportSavedEvent.
    assert kinds == ["ReportStart", "ReportDelta", "ReportComplete", "ReportSavedEvent"]
    assert isinstance(collected[-1], ReportSavedEvent)
    assert collected[-1].report_id == "r_1"
    assert runner.received[0][0] == "morning_briefing"
    assert runner.received[0][2].mode == "morning_briefing"
    assert store.saved[0]["department"] == "morning_briefing"
    assert store.saved[0]["report_type"] == "morning_briefing"


@pytest.mark.asyncio
async def test_on_demand_reads_config(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.departments import MbUserConfig
    _mk_user(db_session)
    db_session.add(MbUserConfig(
        id="c1", user_id="u_1", report_length="elaborative",
        enabled_section_ids=["executive_summary"],
        section_topics={}, custom_sections=[],
        reference_portfolio=False,
    ))
    db_session.commit()
    complete = ReportComplete(report_id="pending",
                              schema={"title": "x", "sections": []})
    runner = ScriptedRunner(events=[complete])
    store = FakeReportStore()
    async for _ in run_on_demand(
        session=db_session, user_id="u_1",
        report_runner=runner, report_store=store,
    ):
        pass
    req = runner.received[0][2]
    assert req.length == "long"
    assert req.enabled_sections == ["executive_summary"]
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_mb_runner.py -v`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Write the orchestrator**

```python
# packages/server/src/openlia_server/services/mb_runner.py
"""On-demand Morning Briefing report orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Protocol

from sqlalchemy.orm import Session

from openlia.llm.runtime.events import ReportComplete, SseEvent
from openlia.llm.runtime.messages import ReportRequest

from openlia_server.services.mb_request_builder import MbRequestBuilderImpl


@dataclass(frozen=True)
class ReportSavedEvent(SseEvent):
    """Terminal event emitted after the report is persisted by report_store.

    Mirrors README pattern #3: `report.saved {report_id}`.
    """

    report_id: str

    @property
    def event_type(self) -> str:
        return "report.saved"


class ReportRunnerLike(Protocol):
    async def run(
        self, *, department_id: str, user_id: str, request: ReportRequest,
    ) -> AsyncIterator[SseEvent]: ...


class ReportStoreLike(Protocol):
    def create_report(
        self, *, user_id: str, department: str, report_type: str,
        title: str, content_markdown: str, content_structured: dict,
        model_ref: str | None = None,
    ) -> str: ...


async def run_on_demand(
    *,
    session: Session,
    user_id: str,
    report_runner: ReportRunnerLike,
    report_store: ReportStoreLike,
) -> AsyncIterator[SseEvent]:
    builder = MbRequestBuilderImpl()
    request = builder.build(session=session, user_id=user_id, schedule_id="on_demand")

    last_schema: dict | None = None
    async for event in report_runner.run(
        department_id="morning_briefing", user_id=user_id, request=request,
    ):
        yield event
        if isinstance(event, ReportComplete):
            last_schema = event.schema

    if last_schema is None:
        return

    title = last_schema.get("title") or "Morning Briefing"
    # Rendering markdown from the schema is Plan 13's ReportRenderer job; if
    # `content_markdown` is not yet produced at this layer, pass an empty
    # string — Plan 13's report_store will render on read. See Plan 13 for the
    # canonical creation flow and swap to its shipped signature if different.
    rid = report_store.create_report(
        user_id=user_id,
        department="morning_briefing",
        report_type="morning_briefing",
        title=title,
        content_markdown="",
        content_structured=last_schema,
    )
    yield ReportSavedEvent(report_id=rid)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/services/test_mb_runner.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/mb_runner.py \
        packages/server/tests/services/test_mb_runner.py
git commit -m "feat(server): add mb_runner on-demand orchestrator with report.saved terminal event"
```

---

### Task 9: Server — `/departments/morning-briefing/config` routes

Two endpoints: `GET /config`, `PUT /config`. Mirror the Plan 15 config pattern. All in a single router factory at `packages/server/src/openlia_server/routes/departments/morning_briefing.py` (the other routes ride the same factory in Tasks 10-12 — they share `require_auth` + `session_dep`).

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/routes/departments/test_morning_briefing_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_morning_briefing_config.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def logged_in_client(app_client_factory, db_session):
    return app_client_factory(user_id="u_1")


def test_get_config_returns_defaults(logged_in_client) -> None:
    r = logged_in_client.get("/departments/morning-briefing/config")
    assert r.status_code == 200
    body = r.json()
    assert body["report_length"] == "normal"
    assert len(body["enabled_section_ids"]) == 7
    assert body["reference_portfolio"] is False
    assert body["section_topics"] == {}
    assert body["custom_sections"] == []


def test_put_config_persists(logged_in_client) -> None:
    payload = {
        "report_length": "concise",
        "enabled_section_ids": ["executive_summary", "global_macro"],
        "section_topics": {"global_macro": [{"topic": "War", "notes": "Ukraine"}]},
        "custom_sections": [
            {"id": "c1", "title": "My Focus", "description": "FX desk"},
        ],
        "reference_portfolio": True,
    }
    r = logged_in_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 200
    assert r.json()["report_length"] == "concise"

    r2 = logged_in_client.get("/departments/morning-briefing/config")
    body = r2.json()
    assert body["enabled_section_ids"] == ["executive_summary", "global_macro"]
    assert body["reference_portfolio"] is True
    assert body["section_topics"]["global_macro"][0]["topic"] == "War"


def test_put_config_rejects_invalid_length(logged_in_client) -> None:
    payload = {
        "report_length": "tiny",
        "enabled_section_ids": [], "section_topics": {},
        "custom_sections": [], "reference_portfolio": False,
    }
    r = logged_in_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 422


def test_put_config_rejects_unknown_section(logged_in_client) -> None:
    payload = {
        "report_length": "normal",
        "enabled_section_ids": ["not_a_section"],
        "section_topics": {}, "custom_sections": [],
        "reference_portfolio": False,
    }
    r = logged_in_client.put("/departments/morning-briefing/config", json=payload)
    assert r.status_code == 422


def test_routes_require_auth(unauth_client) -> None:
    r = unauth_client.get("/departments/morning-briefing/config")
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_config.py -v`
Expected: FAIL — router not yet mounted.

- [ ] **Step 3: Write the router factory skeleton + config endpoints**

```python
# packages/server/src/openlia_server/routes/departments/morning_briefing.py
"""Morning Briefing HTTP routes."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from openlia.llm.runtime.events import to_wire

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatSession
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import mb_config as config_svc
from openlia_server.services import mb_runner
from openlia_server.services import mb_schedules as schedules_svc


def _scheduler_dep(request: Request):
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "scheduler not initialized")
    return scheduler


def _report_runner_dep(request: Request):
    runner = getattr(request.app.state, "report_runner", None)
    if runner is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "report runner not initialized")
    return runner


def _report_store_dep(request: Request):
    store = getattr(request.app.state, "report_store", None)
    if store is None:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR,
                            "report store not initialized")
    return store


class _TopicIn(BaseModel):
    topic: str = Field(min_length=1, max_length=128)
    notes: str = Field(default="", max_length=2000)


class _CustomSectionIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)


class _ConfigIn(BaseModel):
    report_length: Literal["concise", "normal", "elaborative"]
    enabled_section_ids: list[str]
    section_topics: dict[str, list[_TopicIn]]
    custom_sections: list[_CustomSectionIn]
    reference_portfolio: bool = False


class _ConfigOut(BaseModel):
    report_length: str
    enabled_section_ids: list[str]
    section_topics: dict[str, list[dict]]
    custom_sections: list[dict]
    reference_portfolio: bool


class _ScheduleIn(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
    days_of_week: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(min_length=1)
    label: str = Field(default="", max_length=64)


class _ScheduleOut(BaseModel):
    id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class _ChatSessionOut(BaseModel):
    session_id: str


def build_morning_briefing_router(*, db_session_factory, mode: str) -> APIRouter:
    router = APIRouter(prefix="/departments/morning-briefing",
                       tags=["morning-briefing"])
    require_auth = build_require_auth(db_session_factory=db_session_factory,
                                      mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    @router.get("/config", response_model=_ConfigOut)
    def get_config(
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
    ) -> _ConfigOut:
        cfg = config_svc.get_config(db, user_id=user.id)
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            section_topics=dict(cfg.section_topics),
            custom_sections=list(cfg.custom_sections),
            reference_portfolio=bool(cfg.reference_portfolio),
        )

    @router.put("/config", response_model=_ConfigOut)
    def put_config(
        payload: _ConfigIn,
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
    ) -> _ConfigOut:
        try:
            cfg = config_svc.update_config(
                db,
                user_id=user.id,
                report_length=payload.report_length,
                enabled_section_ids=list(payload.enabled_section_ids),
                section_topics={
                    sid: [t.model_dump() for t in topics]
                    for sid, topics in payload.section_topics.items()
                },
                custom_sections=[cs.model_dump() for cs in payload.custom_sections],
                reference_portfolio=payload.reference_portfolio,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            section_topics=dict(cfg.section_topics),
            custom_sections=list(cfg.custom_sections),
            reference_portfolio=bool(cfg.reference_portfolio),
        )

    # Task 10, 11, 12 add /schedule, /report, /chat/session inside this router.
    return router
```

- [ ] **Step 4: Register the router in `app.py`**

In `packages/server/src/openlia_server/app.py`:

```python
from openlia_server.routes.departments.morning_briefing import (
    build_morning_briefing_router,
)

app.include_router(
    build_morning_briefing_router(db_session_factory=factory, mode=mode)
)
```

- [ ] **Step 5: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_config.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/morning_briefing.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/routes/departments/test_morning_briefing_config.py
git commit -m "feat(server): add /departments/morning-briefing/config routes"
```

---

### Task 10: Server — `/departments/morning-briefing/schedule` routes

Three endpoints: `GET /schedule` (returns the single schedule or `null`), `PUT /schedule` (upsert), `DELETE /schedule` (remove).

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/routes/departments/test_morning_briefing_schedule.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_morning_briefing_schedule.py
import pytest


@pytest.fixture
def logged_in_client(app_client_factory):
    return app_client_factory(user_id="u_1")


def test_get_schedule_returns_null_when_missing(logged_in_client) -> None:
    r = logged_in_client.get("/departments/morning-briefing/schedule")
    assert r.status_code == 200
    assert r.json() == {"schedule": None}


def test_put_schedule_creates_and_modifies(logged_in_client) -> None:
    payload = {
        "time": "07:00",
        "timezone": "America/New_York",
        "days_of_week": ["mon", "tue", "wed", "thu", "fri"],
        "label": "Pre-Market",
    }
    r = logged_in_client.put("/departments/morning-briefing/schedule", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["time"] == "07:00"
    assert body["label"] == "Pre-Market"
    assert body["days_of_week"] == ["mon", "tue", "wed", "thu", "fri"]

    # Second PUT modifies in place.
    payload2 = {**payload, "time": "08:00", "label": "Updated"}
    r2 = logged_in_client.put("/departments/morning-briefing/schedule",
                              json=payload2)
    assert r2.status_code == 200
    assert r2.json()["time"] == "08:00"
    assert r2.json()["label"] == "Updated"

    # GET reflects modification.
    r3 = logged_in_client.get("/departments/morning-briefing/schedule")
    assert r3.json()["schedule"]["time"] == "08:00"


def test_put_schedule_rejects_invalid_time(logged_in_client) -> None:
    r = logged_in_client.put(
        "/departments/morning-briefing/schedule",
        json={"time": "25:99", "timezone": "America/New_York",
              "days_of_week": ["mon"], "label": "bad"},
    )
    assert r.status_code == 422


def test_put_schedule_rejects_invalid_timezone(logged_in_client) -> None:
    r = logged_in_client.put(
        "/departments/morning-briefing/schedule",
        json={"time": "07:00", "timezone": "Mars/Phobos",
              "days_of_week": ["mon"], "label": "bad"},
    )
    assert r.status_code == 422


def test_delete_schedule_removes(logged_in_client) -> None:
    logged_in_client.put(
        "/departments/morning-briefing/schedule",
        json={"time": "07:00", "timezone": "America/New_York",
              "days_of_week": ["mon"], "label": "a"},
    )
    r = logged_in_client.delete("/departments/morning-briefing/schedule")
    assert r.status_code == 204
    r2 = logged_in_client.get("/departments/morning-briefing/schedule")
    assert r2.json() == {"schedule": None}


def test_schedule_is_user_scoped(app_client_factory) -> None:
    c1 = app_client_factory(user_id="u_1")
    c2 = app_client_factory(user_id="u_2")
    c1.put("/departments/morning-briefing/schedule",
           json={"time": "07:00", "timezone": "America/New_York",
                 "days_of_week": ["mon"], "label": "a"})
    r = c2.get("/departments/morning-briefing/schedule")
    assert r.json() == {"schedule": None}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_schedule.py -v`
Expected: FAIL.

- [ ] **Step 3: Add schedule endpoints to the router factory**

Inside `build_morning_briefing_router`, append:

```python
    @router.get("/schedule")
    def get_schedule(
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
    ):
        dto = schedules_svc.get_schedule(db, user_id=user.id)
        if dto is None:
            return {"schedule": None}
        return {"schedule": _ScheduleOut(**dto.__dict__).model_dump()}

    @router.put("/schedule", response_model=_ScheduleOut)
    async def put_schedule(
        payload: _ScheduleIn,
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
        scheduler=Depends(_scheduler_dep),
    ) -> _ScheduleOut:
        try:
            dto = await schedules_svc.upsert_schedule(
                db,
                user_id=user.id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                scheduler=scheduler,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                str(exc)) from exc
        return _ScheduleOut(**dto.__dict__)

    @router.delete("/schedule", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
        scheduler=Depends(_scheduler_dep),
    ) -> None:
        await schedules_svc.delete_schedule(db, user_id=user.id,
                                            scheduler=scheduler)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_schedule.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/morning_briefing.py \
        packages/server/tests/routes/departments/test_morning_briefing_schedule.py
git commit -m "feat(server): add /departments/morning-briefing/schedule routes"
```

---

### Task 11: Server — `/departments/morning-briefing/report` SSE route

Named-event SSE framing (README pattern #1 and #3): `event: <type>\ndata: <json>\n\n` frames terminating in `report.saved {report_id}`.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/routes/departments/test_morning_briefing_report.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_morning_briefing_report.py
import pytest


@pytest.fixture
def logged_in_client(app_client_factory, scripted_report_runner, fake_report_store):
    # Fixture wires app.state.report_runner + app.state.report_store to fakes.
    return app_client_factory(user_id="u_1")


def test_report_endpoint_streams_named_events(logged_in_client) -> None:
    r = logged_in_client.post("/departments/morning-briefing/report",
                              json={}, headers={"Accept": "text/event-stream"})
    assert r.status_code == 200
    body = r.text
    # Named-event SSE framing.
    assert "event: report.start" in body
    assert "event: report.delta" in body
    assert "event: report.complete" in body
    assert "event: report.saved" in body
    # Each frame has a matching data line.
    for line in body.splitlines():
        if line.startswith("event: "):
            # next non-blank line must start with "data: "
            assert True


def test_report_endpoint_requires_auth(unauth_client) -> None:
    r = unauth_client.post("/departments/morning-briefing/report", json={})
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_report.py -v`
Expected: FAIL — endpoint doesn't exist yet.

- [ ] **Step 3: Add the report endpoint**

Inside `build_morning_briefing_router`, append:

```python
    @router.post("/report")
    async def generate_report(
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
        runner=Depends(_report_runner_dep),
        store=Depends(_report_store_dep),
    ) -> StreamingResponse:
        async def gen():
            async for event in mb_runner.run_on_demand(
                session=db,
                user_id=user.id,
                report_runner=runner,
                report_store=store,
            ):
                payload = to_wire(event)
                event_name = (
                    payload.get("type")
                    if isinstance(payload, dict)
                    else event.event_type
                )
                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")
```

> `to_wire(event)` returns a dict that already carries a `type` key per Plan 5's SSE taxonomy. The `event: <name>` framing line is what `EventSource.addEventListener` / `useReportStream` dispatch on (README pattern #1). `ReportSavedEvent` (Task 8) exposes `event_type == "report.saved"` via its property — `to_wire` output matches if the runtime's serializer is generic, or the route falls back to `event.event_type`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_report.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/morning_briefing.py \
        packages/server/tests/routes/departments/test_morning_briefing_report.py
git commit -m "feat(server): add /departments/morning-briefing/report named-event SSE route"
```

---

### Task 12: Server — `/departments/morning-briefing/chat/session` route

The shared chat stream endpoint `GET /api/chat/sessions/{session_id}/stream?q=...` (Plan 12 + README pattern #2) is session-bound. Departments don't ship bespoke `POST /chat` routes; instead they expose a small helper that **resolves-or-creates** a chat session whose `department` column equals `"morning_briefing"`. The frontend calls this once, caches the session id, and routes chat messages through the shared stream endpoint.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/morning_briefing.py`
- Test: `packages/server/tests/routes/departments/test_morning_briefing_chat_session.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_morning_briefing_chat_session.py
import pytest


@pytest.fixture
def logged_in_client(app_client_factory):
    return app_client_factory(user_id="u_1")


def test_resolves_or_creates_session(logged_in_client) -> None:
    r = logged_in_client.post("/departments/morning-briefing/chat/session")
    assert r.status_code == 200
    body = r.json()
    sid = body["session_id"]
    assert len(sid) == 36

    # Second call returns the same session id.
    r2 = logged_in_client.post("/departments/morning-briefing/chat/session")
    assert r2.json()["session_id"] == sid


def test_session_is_user_scoped(app_client_factory) -> None:
    c1 = app_client_factory(user_id="u_1")
    c2 = app_client_factory(user_id="u_2")
    sid_1 = c1.post("/departments/morning-briefing/chat/session").json()["session_id"]
    sid_2 = c2.post("/departments/morning-briefing/chat/session").json()["session_id"]
    assert sid_1 \!= sid_2


def test_session_department_is_morning_briefing(logged_in_client, db_session) -> None:
    from openlia_server.db.models.content import ChatSession
    sid = logged_in_client.post(
        "/departments/morning-briefing/chat/session"
    ).json()["session_id"]
    row = db_session.query(ChatSession).filter_by(id=sid).one()
    assert row.department == "morning_briefing"


def test_session_requires_auth(unauth_client) -> None:
    r = unauth_client.post("/departments/morning-briefing/chat/session")
    assert r.status_code in (401, 403)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_chat_session.py -v`
Expected: FAIL.

- [ ] **Step 3: Add the chat-session endpoint**

Inside `build_morning_briefing_router`, append:

```python
    @router.post("/chat/session", response_model=_ChatSessionOut)
    def get_or_create_chat_session(
        user: User = Depends(require_auth),
        db: Session = Depends(session_dep),
    ) -> _ChatSessionOut:
        import uuid

        existing = (
            db.query(ChatSession)
            .filter_by(user_id=user.id, department="morning_briefing",
                       is_archived=False)
            .order_by(ChatSession.created_at.desc())
            .first()
        )
        if existing is not None:
            return _ChatSessionOut(session_id=existing.id)

        sid = str(uuid.uuid4())
        row = ChatSession(
            id=sid,
            user_id=user.id,
            department="morning_briefing",
            title="Morning Briefing",
            is_pinned=False,
            is_archived=False,
            context=None,
        )
        db.add(row)
        db.commit()
        return _ChatSessionOut(session_id=sid)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/routes/departments/test_morning_briefing_chat_session.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/morning_briefing.py \
        packages/server/tests/routes/departments/test_morning_briefing_chat_session.py
git commit -m "feat(server): add /departments/morning-briefing/chat/session resolver"
```

---

### Task 13: Server — Wire real `MbRequestBuilderImpl` into `build_scheduler_service`

Plan 6 ships `StubMBRequestBuilder` by default (raises `DepartmentPayloadBuilderNotWired`). Plan 16 replaces it with the real implementation at app startup.

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py` (default `mb_builder` stays `StubMBRequestBuilder()` — no change here if the kwarg is already plumbed; only the app startup changes).
- Modify: `packages/server/src/openlia_server/app.py` (pass the real builder into `build_scheduler_service`).
- Test: `packages/server/tests/scheduler/test_wiring_mb_builder.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/scheduler/test_wiring_mb_builder.py
from dataclasses import dataclass, field

from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl


@dataclass
class _StubRunner:
    async def run(self, **kwargs):
        if False:
            yield


@dataclass
class _StubStore:
    saved: list[dict] = field(default_factory=list)

    def save(self, **kwargs):
        self.saved.append(kwargs)
        return "r_x"


def test_wiring_accepts_real_mb_builder(session_factory) -> None:
    builder = MbRequestBuilderImpl()
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        report_runner=_StubRunner(),
        report_store=_StubStore(),
        mb_builder=builder,
    )
    assert svc is not None
```

- [ ] **Step 2: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/scheduler/test_wiring_mb_builder.py -v`
Expected: PASS — Plan 6 already accepts `mb_builder`. This test is a regression guard that proves `MbRequestBuilderImpl` is structurally compatible with the wiring Protocol.

- [ ] **Step 3: Update `app.py` to inject the real builder at startup**

In `packages/server/src/openlia_server/app.py`, inside the `lifespan` block that builds the scheduler:

```python
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl

mb_builder = MbRequestBuilderImpl()
app.state.scheduler = build_scheduler_service(
    session_factory=app.state.session_factory,
    settings=scheduler_settings,
    report_runner=app.state.report_runner,
    report_store=app.state.report_store,
    mb_builder=mb_builder,
    # ... other builders (eu_planner, etc.)
)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/scheduler/test_wiring_mb_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/app.py \
        packages/server/tests/scheduler/test_wiring_mb_builder.py
git commit -m "feat(server): wire MbRequestBuilderImpl into scheduler at app startup"
```

---

### Task 14: Frontend — `api/morning-briefing.ts` typed client

All MB HTTP calls. Report generation uses the shipped `useReportStream` hook; this file exposes only the non-stream endpoints + the `chat/session` resolver.

**Files:**
- Create: `frontend/src/api/morning-briefing.ts`
- Test: `frontend/src/api/__tests__/morning-briefing.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/api/__tests__/morning-briefing.test.ts
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
  fetchConfig,
  updateConfig,
  fetchSchedule,
  upsertSchedule,
  deleteSchedule,
  resolveChatSession,
  fetchReports,
} from "../morning-briefing";

beforeEach(() => vi.restoreAllMocks());

describe("morning-briefing api client", () => {
  it("fetchConfig GETs /config", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        report_length: "normal", enabled_section_ids: [],
        section_topics: {}, custom_sections: [], reference_portfolio: false,
      }), { status: 200 }),
    );
    const r = await fetchConfig();
    expect(r.report_length).toBe("normal");
    expect(spy.mock.calls[0][0]).toBe("/api/departments/morning-briefing/config");
  });

  it("updateConfig PUTs full body", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        report_length: "concise", enabled_section_ids: ["executive_summary"],
        section_topics: {}, custom_sections: [], reference_portfolio: true,
      }), { status: 200 }),
    );
    await updateConfig({
      report_length: "concise",
      enabled_section_ids: ["executive_summary"],
      section_topics: {},
      custom_sections: [],
      reference_portfolio: true,
    });
    expect(spy.mock.calls[0][1]?.method).toBe("PUT");
    const body = JSON.parse((spy.mock.calls[0][1] as RequestInit).body as string);
    expect(body.reference_portfolio).toBe(true);
  });

  it("fetchSchedule GETs /schedule", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ schedule: null }), { status: 200 }),
    );
    const r = await fetchSchedule();
    expect(r.schedule).toBeNull();
  });

  it("upsertSchedule PUTs /schedule", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({
        id: "s_1", time: "07:00", timezone: "America/New_York",
        days_of_week: ["mon"], label: "Pre-Market", is_enabled: true,
      }), { status: 200 }),
    );
    const r = await upsertSchedule({
      time: "07:00", timezone: "America/New_York",
      days_of_week: ["mon"], label: "Pre-Market",
    });
    expect(r.id).toBe("s_1");
  });

  it("deleteSchedule DELETEs /schedule", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(null, { status: 204 }),
    );
    await deleteSchedule();
    expect(spy.mock.calls[0][1]?.method).toBe("DELETE");
  });

  it("resolveChatSession POSTs /chat/session", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ session_id: "s_chat_1" }), { status: 200 }),
    );
    const r = await resolveChatSession();
    expect(r.session_id).toBe("s_chat_1");
  });

  it("fetchReports hits shared /reports with department filter", async () => {
    const spy = vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ reports: [] }), { status: 200 }),
    );
    await fetchReports();
    expect(spy.mock.calls[0][0]).toBe("/api/reports?department=morning_briefing");
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/api/__tests__/morning-briefing.test.ts`
Expected: FAIL (`Cannot find module '../morning-briefing'`).

- [ ] **Step 3: Write the client**

```ts
// frontend/src/api/morning-briefing.ts
export type ReportLength = "concise" | "normal" | "elaborative";

export interface TopicEntry {
  topic: string;
  notes: string;
}

export interface CustomSection {
  id: string;
  title: string;
  description: string;
}

export interface MbConfig {
  report_length: ReportLength;
  enabled_section_ids: string[];
  section_topics: Record<string, TopicEntry[]>;
  custom_sections: CustomSection[];
  reference_portfolio: boolean;
}

export interface MbSchedule {
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
  report_type: string;
  created_at: string;
}

export class HttpError extends Error {
  constructor(public status: number, public body: string) {
    super(`HTTP ${status}: ${body}`);
  }
}

async function json<T>(input: RequestInfo, init?: RequestInit): Promise<T> {
  const r = await fetch(input, init);
  if (\!r.ok) throw new HttpError(r.status, await r.text());
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

const BASE = "/api/departments/morning-briefing";

export const fetchConfig = () => json<MbConfig>(`${BASE}/config`);

export const updateConfig = (cfg: MbConfig) =>
  json<MbConfig>(`${BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cfg),
  });

export const fetchSchedule = () =>
  json<{ schedule: MbSchedule | null }>(`${BASE}/schedule`);

export const upsertSchedule = (payload: Omit<MbSchedule, "id" | "is_enabled">) =>
  json<MbSchedule>(`${BASE}/schedule`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

export const deleteSchedule = () =>
  json<void>(`${BASE}/schedule`, { method: "DELETE" });

export const resolveChatSession = () =>
  json<{ session_id: string }>(`${BASE}/chat/session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });

export const fetchReports = () =>
  json<{ reports: RecentReport[] }>(
    `/api/reports?department=morning_briefing`,
  );
```

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/api/__tests__/morning-briefing.test.ts`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/morning-briefing.ts \
        frontend/src/api/__tests__/morning-briefing.test.ts
git commit -m "feat(frontend): add morning-briefing typed api client"
```

---

### Task 15: Frontend — Section catalog + hooks

- `lib/morning-briefing/section-catalog.ts` — 7 default section ids with titles + hint text (for the Settings View topic-row hints).
- `hooks/useMbConfig.ts` — SWR-style fetch + save + optimistic update.
- `hooks/useMbSchedule.ts` — SWR-style fetch + upsert + delete.
- `hooks/useMbReports.ts` — wrapper over `fetchReports` with refresh.
- `hooks/useMbChatSession.ts` — resolves-or-creates the MB chat session id once per mount.

**Files:**
- Create: `frontend/src/lib/morning-briefing/section-catalog.ts`
- Create: `frontend/src/hooks/useMbConfig.ts`
- Create: `frontend/src/hooks/useMbSchedule.ts`
- Create: `frontend/src/hooks/useMbReports.ts`
- Create: `frontend/src/hooks/useMbChatSession.ts`
- Test: `frontend/src/lib/morning-briefing/__tests__/section-catalog.test.ts`
- Test: `frontend/src/hooks/__tests__/useMbConfig.test.tsx`
- Test: `frontend/src/hooks/__tests__/useMbChatSession.test.tsx`

- [ ] **Step 1: Write the failing catalog test**

```ts
// frontend/src/lib/morning-briefing/__tests__/section-catalog.test.ts
import { describe, expect, it } from "vitest";

import { MB_SECTION_CATALOG, DEFAULT_MB_SECTIONS } from "../section-catalog";

describe("MB section catalog", () => {
  it("exposes 7 default sections", () => {
    expect(DEFAULT_MB_SECTIONS.length).toBe(7);
  });

  it("has catalog entries for every default id", () => {
    for (const id of DEFAULT_MB_SECTIONS) {
      const entry = MB_SECTION_CATALOG[id];
      expect(entry).toBeDefined();
      expect(entry.title.length).toBeGreaterThan(0);
    }
  });

  it("catalog ids match framework JSON order", () => {
    expect(DEFAULT_MB_SECTIONS).toEqual([
      "executive_summary", "global_macro", "country_news",
      "market_news", "sector_news", "stock_news", "upcoming_preview",
    ]);
  });

  it("Executive Summary has no topic-input hint (toggle only)", () => {
    expect(MB_SECTION_CATALOG.executive_summary.hasTopics).toBe(false);
  });

  it("Upcoming Preview exposes reference-portfolio toggle", () => {
    expect(MB_SECTION_CATALOG.upcoming_preview.hasReferencePortfolioToggle).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/lib/morning-briefing/__tests__/section-catalog.test.ts`
Expected: FAIL.

- [ ] **Step 3: Write the catalog**

```ts
// frontend/src/lib/morning-briefing/section-catalog.ts
export interface SectionCatalogEntry {
  title: string;
  hint: string;
  topicPlaceholder: string;
  hasTopics: boolean;
  hasReferencePortfolioToggle?: boolean;
}

export const MB_SECTION_CATALOG: Record<string, SectionCatalogEntry> = {
  executive_summary: {
    title: "Executive Summary",
    hint: "Always included as a summary of the full briefing.",
    topicPlaceholder: "",
    hasTopics: false,
  },
  global_macro: {
    title: "Global Macro News",
    hint: "Add macro topics to cover (e.g., War, Politics, Energy).",
    topicPlaceholder: "Add topic",
    hasTopics: true,
  },
  country_news: {
    title: "Country News",
    hint: "Add countries to cover (e.g., US, Taiwan, Japan).",
    topicPlaceholder: "Add country",
    hasTopics: true,
  },
  market_news: {
    title: "Market News",
    hint: "Add markets to cover (e.g., Bonds, Gold, Oil).",
    topicPlaceholder: "Add market",
    hasTopics: true,
  },
  sector_news: {
    title: "Sector News",
    hint: "Add sectors or industries to cover.",
    topicPlaceholder: "Add sector",
    hasTopics: true,
  },
  stock_news: {
    title: "Stock News",
    hint: "Add tickers to cover (e.g., AAPL, TSLA).",
    topicPlaceholder: "Add stock",
    hasTopics: true,
  },
  upcoming_preview: {
    title: "Upcoming Preview",
    hint: "Covers major upcoming events for the next few sessions.",
    topicPlaceholder: "Add topic",
    hasTopics: true,
    hasReferencePortfolioToggle: true,
  },
};

export const DEFAULT_MB_SECTIONS: readonly string[] = [
  "executive_summary",
  "global_macro",
  "country_news",
  "market_news",
  "sector_news",
  "stock_news",
  "upcoming_preview",
];
```

- [ ] **Step 4: Write the failing config-hook test**

```tsx
// frontend/src/hooks/__tests__/useMbConfig.test.tsx
import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../api/morning-briefing";
import { useMbConfig } from "../useMbConfig";

describe("useMbConfig", () => {
  it("loads config on mount", async () => {
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal", enabled_section_ids: ["executive_summary"],
      section_topics: {}, custom_sections: [], reference_portfolio: false,
    });
    const { result } = renderHook(() => useMbConfig());
    await waitFor(() => expect(result.current.config).not.toBeNull());
    expect(result.current.config?.report_length).toBe("normal");
  });

  it("save updates config via api", async () => {
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal", enabled_section_ids: [],
      section_topics: {}, custom_sections: [], reference_portfolio: false,
    });
    const updateSpy = vi.spyOn(api, "updateConfig").mockResolvedValue({
      report_length: "concise", enabled_section_ids: ["global_macro"],
      section_topics: {}, custom_sections: [], reference_portfolio: true,
    });
    const { result } = renderHook(() => useMbConfig());
    await waitFor(() => expect(result.current.config).not.toBeNull());
    await act(async () => {
      await result.current.save({
        report_length: "concise",
        enabled_section_ids: ["global_macro"],
        section_topics: {},
        custom_sections: [],
        reference_portfolio: true,
      });
    });
    expect(updateSpy).toHaveBeenCalled();
    expect(result.current.config?.reference_portfolio).toBe(true);
  });
});
```

- [ ] **Step 5: Write the config hook**

```ts
// frontend/src/hooks/useMbConfig.ts
import { useCallback, useEffect, useState } from "react";

import { fetchConfig, updateConfig, type MbConfig } from "../api/morning-briefing";

export function useMbConfig() {
  const [config, setConfig] = useState<MbConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchConfig()
      .then((c) => {
        if (\!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (\!cancelled) setError(e as Error);
      })
      .finally(() => {
        if (\!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(async (next: MbConfig) => {
    const updated = await updateConfig(next);
    setConfig(updated);
    return updated;
  }, []);

  return { config, loading, error, save };
}
```

- [ ] **Step 6: Write the schedule hook**

```ts
// frontend/src/hooks/useMbSchedule.ts
import { useCallback, useEffect, useState } from "react";

import {
  deleteSchedule,
  fetchSchedule,
  upsertSchedule,
  type MbSchedule,
} from "../api/morning-briefing";

export function useMbSchedule() {
  const [schedule, setSchedule] = useState<MbSchedule | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchSchedule()
      .then(({ schedule }) => {
        if (\!cancelled) setSchedule(schedule);
      })
      .finally(() => {
        if (\!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const upsert = useCallback(async (payload: Omit<MbSchedule, "id" | "is_enabled">) => {
    const next = await upsertSchedule(payload);
    setSchedule(next);
    return next;
  }, []);

  const remove = useCallback(async () => {
    await deleteSchedule();
    setSchedule(null);
  }, []);

  return { schedule, loading, upsert, remove };
}
```

- [ ] **Step 7: Write the reports hook**

```ts
// frontend/src/hooks/useMbReports.ts
import { useCallback, useEffect, useState } from "react";

import { fetchReports, type RecentReport } from "../api/morning-briefing";

export function useMbReports() {
  const [reports, setReports] = useState<RecentReport[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const { reports } = await fetchReports();
    setReports(reports);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchReports()
      .then(({ reports }) => {
        if (\!cancelled) setReports(reports);
      })
      .finally(() => {
        if (\!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { reports, loading, refresh };
}
```

- [ ] **Step 8: Write the failing chat-session hook test**

```tsx
// frontend/src/hooks/__tests__/useMbChatSession.test.tsx
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../api/morning-briefing";
import { useMbChatSession } from "../useMbChatSession";

describe("useMbChatSession", () => {
  it("resolves the session id once on mount", async () => {
    const spy = vi.spyOn(api, "resolveChatSession").mockResolvedValue({
      session_id: "s_1",
    });
    const { result } = renderHook(() => useMbChatSession());
    await waitFor(() => expect(result.current.sessionId).toBe("s_1"));
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 9: Write the chat-session hook**

```ts
// frontend/src/hooks/useMbChatSession.ts
import { useEffect, useState } from "react";

import { resolveChatSession } from "../api/morning-briefing";

export function useMbChatSession() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    resolveChatSession()
      .then(({ session_id }) => {
        if (\!cancelled) setSessionId(session_id);
      })
      .finally(() => {
        if (\!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { sessionId, loading };
}
```

- [ ] **Step 10: Run the hook tests**

```bash
cd frontend && npx vitest run src/lib/morning-briefing/ src/hooks/__tests__/useMbConfig.test.tsx src/hooks/__tests__/useMbChatSession.test.tsx
```

Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/lib/morning-briefing \
        frontend/src/hooks/useMbConfig.ts \
        frontend/src/hooks/useMbSchedule.ts \
        frontend/src/hooks/useMbReports.ts \
        frontend/src/hooks/useMbChatSession.ts \
        frontend/src/hooks/__tests__/useMbConfig.test.tsx \
        frontend/src/hooks/__tests__/useMbChatSession.test.tsx
git commit -m "feat(frontend): add MB section catalog + config/schedule/reports/chat-session hooks"
```

---

### Task 16: Frontend — `MBReportCard` + `MBArchiveView`

Date-grouped grid of report cards with Open + Download actions.

**Files:**
- Create: `frontend/src/components/morning-briefing/MBReportCard.tsx`
- Create: `frontend/src/components/morning-briefing/MBArchiveView.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/MBArchiveView.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/morning-briefing/__tests__/MBArchiveView.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { RecentReport } from "../../../api/morning-briefing";
import { MBArchiveView } from "../MBArchiveView";

function fixedDate(y: number, m: number, d: number): string {
  return new Date(Date.UTC(y, m - 1, d, 12, 0, 0)).toISOString();
}

describe("MBArchiveView", () => {
  it("renders empty state when no reports", () => {
    render(
      <MBArchiveView reports={[]}
                     onOpen={() => {}} onDownload={() => {}}
                     onGoToSettings={() => {}} />,
    );
    expect(screen.getByText(/No reports yet/i)).toBeInTheDocument();
  });

  it("groups reports by calendar date (most recent first)", () => {
    const reports: RecentReport[] = [
      { id: "r1", title: "MB April 9", report_type: "morning_briefing",
        created_at: fixedDate(2026, 4, 9) },
      { id: "r2", title: "MB April 8 PM", report_type: "morning_briefing",
        created_at: fixedDate(2026, 4, 8) },
      { id: "r3", title: "MB April 8 AM", report_type: "morning_briefing",
        created_at: fixedDate(2026, 4, 8) },
    ];
    render(
      <MBArchiveView reports={reports}
                     onOpen={() => {}} onDownload={() => {}}
                     onGoToSettings={() => {}} />,
    );
    // There should be exactly 2 date groups.
    expect(screen.getAllByRole("heading", { level: 2 })).toHaveLength(2);
    expect(screen.getByText(/April 9/)).toBeInTheDocument();
    expect(screen.getByText(/April 8/)).toBeInTheDocument();
  });

  it("fires onOpen when a card is clicked", () => {
    const onOpen = vi.fn();
    const reports: RecentReport[] = [
      { id: "r1", title: "MB", report_type: "morning_briefing",
        created_at: fixedDate(2026, 4, 9) },
    ];
    render(
      <MBArchiveView reports={reports}
                     onOpen={onOpen} onDownload={() => {}}
                     onGoToSettings={() => {}} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /open/i }));
    expect(onOpen).toHaveBeenCalledWith("r1");
  });

  it("empty state CTA fires onGoToSettings", () => {
    const onGoToSettings = vi.fn();
    render(
      <MBArchiveView reports={[]}
                     onOpen={() => {}} onDownload={() => {}}
                     onGoToSettings={onGoToSettings} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /settings/i }));
    expect(onGoToSettings).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MBArchiveView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write `MBReportCard`**

```tsx
// frontend/src/components/morning-briefing/MBReportCard.tsx
import { Download } from "lucide-react";

import type { RecentReport } from "../../api/morning-briefing";

interface Props {
  report: RecentReport;
  onOpen: (id: string) => void;
  onDownload: (id: string) => void;
}

export function MBReportCard({ report, onOpen, onDownload }: Props) {
  const d = new Date(report.created_at);
  const dateLabel = d.toLocaleDateString(undefined, {
    year: "numeric", month: "long", day: "numeric",
  });
  const timeLabel = d.toLocaleTimeString(undefined, {
    hour: "numeric", minute: "2-digit",
  });

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(report.id)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onOpen(report.id);
      }}
      className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4 flex flex-col gap-2 hover:border-[--color-border-secondary] hover:shadow-sm cursor-pointer"
    >
      <div className="text-sm font-medium text-[--color-text-secondary]">
        {timeLabel}
      </div>
      <div className="text-base font-semibold text-[--color-text-primary]">
        {report.title || "Morning Briefing"}
      </div>
      <div className="text-sm text-[--color-text-secondary]">{dateLabel}</div>
      <div className="flex items-center gap-2 mt-1">
        <button
          type="button"
          aria-label={`Open ${report.title}`}
          onClick={(e) => {
            e.stopPropagation();
            onOpen(report.id);
          }}
          className="text-sm bg-[--color-accent-primary] text-white h-7 px-3 rounded-[--radius-md]"
        >
          Open
        </button>
        <button
          type="button"
          aria-label={`Download ${report.title}`}
          onClick={(e) => {
            e.stopPropagation();
            onDownload(report.id);
          }}
          className="text-sm border border-[--color-border-secondary] text-[--color-text-secondary] h-7 px-3 rounded-[--radius-md] flex items-center gap-1"
        >
          <Download size={14} />
          Download
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `MBArchiveView`**

```tsx
// frontend/src/components/morning-briefing/MBArchiveView.tsx
import { Settings as SettingsIcon, Sun } from "lucide-react";

import type { RecentReport } from "../../api/morning-briefing";
import { MBReportCard } from "./MBReportCard";

interface Props {
  reports: RecentReport[];
  onOpen: (id: string) => void;
  onDownload: (id: string) => void;
  onGoToSettings: () => void;
}

function groupByDate(reports: RecentReport[]): Record<string, RecentReport[]> {
  const groups: Record<string, RecentReport[]> = {};
  for (const r of reports) {
    const d = new Date(r.created_at);
    const key = `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
    (groups[key] ||= []).push(r);
  }
  return groups;
}

function dateHeading(isoLike: string): string {
  const [y, m, d] = isoLike.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const today = new Date();
  const yesterday = new Date(); yesterday.setDate(today.getDate() - 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate();
  if (sameDay(dt, today)) {
    return `Today — ${dt.toLocaleDateString(undefined, {
      weekday: "long", year: "numeric", month: "long", day: "numeric",
    })}`;
  }
  if (sameDay(dt, yesterday)) {
    return `Yesterday — ${dt.toLocaleDateString(undefined, {
      weekday: "long", month: "long", day: "numeric",
    })}`;
  }
  return dt.toLocaleDateString(undefined, { month: "long", day: "numeric" });
}

export function MBArchiveView({
  reports, onOpen, onDownload, onGoToSettings,
}: Props) {
  if (reports.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center">
          <Sun size={40} className="mx-auto text-[--color-text-tertiary]" />
          <p className="mt-4 text-[--color-text-primary] font-medium">
            No reports yet.
          </p>
          <p className="mt-1 text-sm text-[--color-text-secondary] max-w-sm">
            Configure a schedule in Settings to start receiving your morning
            briefings automatically.
          </p>
          <button
            type="button"
            onClick={onGoToSettings}
            className="mt-4 flex items-center gap-1 mx-auto bg-[--color-accent-primary] text-white text-sm h-8 px-3 rounded-[--radius-md]"
          >
            <SettingsIcon size={16} /> Go to Settings
          </button>
        </div>
      </div>
    );
  }

  const groups = groupByDate(reports);
  const sortedKeys = Object.keys(groups).sort((a, b) => {
    const [ay, am, ad] = a.split("-").map(Number);
    const [by, bm, bd] = b.split("-").map(Number);
    return new Date(by, bm - 1, bd).getTime() - new Date(ay, am - 1, ad).getTime();
  });

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5">
      {sortedKeys.map((key) => (
        <section key={key} className="mb-5">
          <h2 className="text-sm font-medium text-[--color-text-secondary] mb-3">
            {dateHeading(key)}
          </h2>
          <div className="grid gap-3 grid-cols-1 sm:grid-cols-2">
            {groups[key].map((r) => (
              <MBReportCard
                key={r.id}
                report={r}
                onOpen={onOpen}
                onDownload={onDownload}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MBArchiveView.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/morning-briefing/MBReportCard.tsx \
        frontend/src/components/morning-briefing/MBArchiveView.tsx \
        frontend/src/components/morning-briefing/__tests__/MBArchiveView.test.tsx
git commit -m "feat(frontend): add MBReportCard + MBArchiveView with date grouping"
```

---

### Task 17: Frontend — `SectionRow` + `TopicChip` + `NotesPopover`

One section row per standard section id, listing topic chips (with notes popover) + an inline "Add topic" input chip.

**Files:**
- Create: `frontend/src/components/morning-briefing/SectionRow.tsx`
- Create: `frontend/src/components/morning-briefing/TopicChip.tsx`
- Create: `frontend/src/components/morning-briefing/NotesPopover.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/SectionRow.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/morning-briefing/__tests__/SectionRow.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TopicEntry } from "../../../api/morning-briefing";
import { SectionRow } from "../SectionRow";

describe("SectionRow", () => {
  it("renders title + topics", () => {
    const topics: TopicEntry[] = [
      { topic: "War", notes: "" }, { topic: "Energy", notes: "" },
    ];
    render(
      <SectionRow
        sectionId="global_macro"
        enabled={true}
        topics={topics}
        referencePortfolio={false}
        onToggleEnabled={() => {}}
        onTopicsChange={() => {}}
        onReferencePortfolioChange={() => {}}
      />,
    );
    expect(screen.getByText(/Global Macro News/i)).toBeInTheDocument();
    expect(screen.getByText("War")).toBeInTheDocument();
    expect(screen.getByText("Energy")).toBeInTheDocument();
  });

  it("toggles the checkbox through onToggleEnabled", () => {
    const onToggle = vi.fn();
    render(
      <SectionRow
        sectionId="global_macro"
        enabled={true}
        topics={[]}
        referencePortfolio={false}
        onToggleEnabled={onToggle}
        onTopicsChange={() => {}}
        onReferencePortfolioChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /global macro/i }));
    expect(onToggle).toHaveBeenCalledWith(false);
  });

  it("executive_summary has no topic input", () => {
    render(
      <SectionRow
        sectionId="executive_summary"
        enabled={true}
        topics={[]}
        referencePortfolio={false}
        onToggleEnabled={() => {}}
        onTopicsChange={() => {}}
        onReferencePortfolioChange={() => {}}
      />,
    );
    expect(screen.queryByPlaceholderText(/Add/i)).not.toBeInTheDocument();
  });

  it("upcoming_preview shows a Reference Portfolio toggle", () => {
    const onRef = vi.fn();
    render(
      <SectionRow
        sectionId="upcoming_preview"
        enabled={true}
        topics={[]}
        referencePortfolio={false}
        onToggleEnabled={() => {}}
        onTopicsChange={() => {}}
        onReferencePortfolioChange={onRef}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /Reference Portfolio/i }));
    expect(onRef).toHaveBeenCalledWith(true);
  });

  it("adding a new topic fires onTopicsChange", () => {
    const onTopicsChange = vi.fn();
    render(
      <SectionRow
        sectionId="country_news"
        enabled={true}
        topics={[]}
        referencePortfolio={false}
        onToggleEnabled={() => {}}
        onTopicsChange={onTopicsChange}
        onReferencePortfolioChange={() => {}}
      />,
    );
    const input = screen.getByPlaceholderText(/Add country/i);
    fireEvent.change(input, { target: { value: "US" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onTopicsChange).toHaveBeenCalledWith([{ topic: "US", notes: "" }]);
  });

  it("removing a topic via × fires onTopicsChange", () => {
    const onTopicsChange = vi.fn();
    render(
      <SectionRow
        sectionId="country_news"
        enabled={true}
        topics={[{ topic: "US", notes: "" }]}
        referencePortfolio={false}
        onToggleEnabled={() => {}}
        onTopicsChange={onTopicsChange}
        onReferencePortfolioChange={() => {}}
      />,
    );
    fireEvent.click(screen.getByLabelText(/Remove US/));
    expect(onTopicsChange).toHaveBeenCalledWith([]);
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/SectionRow.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write `NotesPopover`**

```tsx
// frontend/src/components/morning-briefing/NotesPopover.tsx
import * as Popover from "@radix-ui/react-popover";
import { useState } from "react";

interface Props {
  topic: string;
  notes: string;
  onSave: (notes: string) => void;
  children: React.ReactNode;
}

export function NotesPopover({ topic, notes, onSave, children }: Props) {
  const [draft, setDraft] = useState(notes);

  return (
    <Popover.Root>
      <Popover.Trigger asChild>{children}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md p-4 w-[280px]"
        >
          <div className="text-base font-semibold text-[--color-text-primary]">
            {topic}
          </div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add sub-topics or focus areas..."
            rows={3}
            className="w-full mt-2 text-sm bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] px-3 py-2 resize-none"
          />
          <div className="flex justify-end mt-2">
            <Popover.Close asChild>
              <button
                type="button"
                onClick={() => onSave(draft)}
                className="text-sm bg-[--color-accent-primary] text-white h-7 px-3 rounded-[--radius-md]"
              >
                Done
              </button>
            </Popover.Close>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
```

- [ ] **Step 4: Write `TopicChip`**

```tsx
// frontend/src/components/morning-briefing/TopicChip.tsx
import { X } from "lucide-react";

import type { TopicEntry } from "../../api/morning-briefing";
import { NotesPopover } from "./NotesPopover";

interface Props {
  entry: TopicEntry;
  onRemove: () => void;
  onNotesChange: (notes: string) => void;
}

export function TopicChip({ entry, onRemove, onNotesChange }: Props) {
  return (
    <NotesPopover
      topic={entry.topic}
      notes={entry.notes}
      onSave={onNotesChange}
    >
      <span
        role="button"
        tabIndex={0}
        className="relative inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[--color-surface-active] text-sm text-[--color-text-primary] cursor-pointer"
      >
        {entry.topic}
        <button
          type="button"
          aria-label={`Remove ${entry.topic}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
          className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
        >
          <X size={12} />
        </button>
        {entry.notes ? (
          <span className="absolute top-0 right-0 w-1 h-1 rounded-full bg-[--color-accent-primary]" />
        ) : null}
      </span>
    </NotesPopover>
  );
}
```

- [ ] **Step 5: Write `SectionRow`**

```tsx
// frontend/src/components/morning-briefing/SectionRow.tsx
import { useState } from "react";

import type { TopicEntry } from "../../api/morning-briefing";
import { MB_SECTION_CATALOG } from "../../lib/morning-briefing/section-catalog";
import { TopicChip } from "./TopicChip";

interface Props {
  sectionId: string;
  enabled: boolean;
  topics: TopicEntry[];
  referencePortfolio: boolean;
  onToggleEnabled: (next: boolean) => void;
  onTopicsChange: (next: TopicEntry[]) => void;
  onReferencePortfolioChange: (next: boolean) => void;
}

export function SectionRow({
  sectionId,
  enabled,
  topics,
  referencePortfolio,
  onToggleEnabled,
  onTopicsChange,
  onReferencePortfolioChange,
}: Props) {
  const entry = MB_SECTION_CATALOG[sectionId];
  const [draft, setDraft] = useState("");

  function addTopic(): void {
    const v = draft.trim();
    if (\!v) return;
    if (topics.some((t) => t.topic.toLowerCase() === v.toLowerCase())) {
      setDraft("");
      return;
    }
    onTopicsChange([...topics, { topic: v, notes: "" }]);
    setDraft("");
  }

  function removeTopic(topic: string): void {
    onTopicsChange(topics.filter((t) => t.topic \!== topic));
  }

  function updateNotes(topic: string, notes: string): void {
    onTopicsChange(topics.map((t) => (t.topic === topic ? { ...t, notes } : t)));
  }

  return (
    <div className="flex items-start gap-3 p-4">
      <input
        type="checkbox"
        aria-label={entry.title}
        checked={enabled}
        onChange={(e) => onToggleEnabled(e.target.checked)}
        className="mt-1"
      />
      <div className="flex-1">
        <div className={enabled
          ? "text-base font-medium text-[--color-text-primary]"
          : "text-base font-medium text-[--color-text-tertiary]"}>
          {entry.title}
        </div>
        <div className="text-xs text-[--color-text-tertiary] mt-0.5">
          {entry.hint}
        </div>

        {enabled && entry.hasTopics ? (
          <div className="flex flex-wrap gap-2 mt-2">
            {topics.map((t) => (
              <TopicChip
                key={t.topic}
                entry={t}
                onRemove={() => removeTopic(t.topic)}
                onNotesChange={(n) => updateNotes(t.topic, n)}
              />
            ))}
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full border border-dashed border-[--color-border-secondary]">
              <input
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === ",") {
                    e.preventDefault();
                    addTopic();
                  }
                }}
                placeholder={entry.topicPlaceholder}
                className="bg-transparent text-sm text-[--color-text-primary] outline-none w-28"
              />
            </span>
          </div>
        ) : null}

        {enabled && entry.hasReferencePortfolioToggle ? (
          <label className="mt-3 flex items-center gap-2 text-sm text-[--color-text-primary]">
            <input
              type="checkbox"
              aria-label="Reference Portfolio"
              checked={referencePortfolio}
              onChange={(e) => onReferencePortfolioChange(e.target.checked)}
            />
            Reference Portfolio
          </label>
        ) : null}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: Run the test**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/SectionRow.test.tsx`
Expected: PASS (6 tests).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/morning-briefing/SectionRow.tsx \
        frontend/src/components/morning-briefing/TopicChip.tsx \
        frontend/src/components/morning-briefing/NotesPopover.tsx \
        frontend/src/components/morning-briefing/__tests__/SectionRow.test.tsx
git commit -m "feat(frontend): add MB SectionRow + TopicChip + NotesPopover"
```

---

### Task 18: Frontend — `CustomSectionRow`

Inline card for a custom section: editable name + description + remove.

**Files:**
- Create: `frontend/src/components/morning-briefing/CustomSectionRow.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/CustomSectionRow.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/morning-briefing/__tests__/CustomSectionRow.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CustomSectionRow } from "../CustomSectionRow";

describe("CustomSectionRow", () => {
  it("renders title and description inputs", () => {
    render(
      <CustomSectionRow
        value={{ id: "abc", title: "My Focus", description: "FX desk" }}
        onChange={() => {}}
        onRemove={() => {}}
      />,
    );
    expect(screen.getByDisplayValue("My Focus")).toBeInTheDocument();
    expect(screen.getByDisplayValue("FX desk")).toBeInTheDocument();
  });

  it("onChange fires when title is edited", () => {
    const onChange = vi.fn();
    render(
      <CustomSectionRow
        value={{ id: "abc", title: "My Focus", description: "" }}
        onChange={onChange}
        onRemove={() => {}}
      />,
    );
    fireEvent.change(screen.getByDisplayValue("My Focus"), {
      target: { value: "Updated" },
    });
    expect(onChange).toHaveBeenCalledWith({
      id: "abc", title: "Updated", description: "",
    });
  });

  it("onRemove fires when × clicked", () => {
    const onRemove = vi.fn();
    render(
      <CustomSectionRow
        value={{ id: "abc", title: "x", description: "" }}
        onChange={() => {}}
        onRemove={onRemove}
      />,
    );
    fireEvent.click(screen.getByLabelText(/Remove custom section/i));
    expect(onRemove).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/CustomSectionRow.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/morning-briefing/CustomSectionRow.tsx
import { X } from "lucide-react";

import type { CustomSection } from "../../api/morning-briefing";

interface Props {
  value: CustomSection;
  onChange: (next: CustomSection) => void;
  onRemove: () => void;
}

export function CustomSectionRow({ value, onChange, onRemove }: Props) {
  return (
    <div className="border border-[--color-border-subtle] rounded-[--radius-lg] p-4 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={value.title}
          onChange={(e) => onChange({ ...value, title: e.target.value })}
          placeholder="Custom section title"
          className="flex-1 text-base font-medium bg-transparent border-b border-[--color-border-subtle] py-1"
        />
        <button
          type="button"
          aria-label="Remove custom section"
          onClick={onRemove}
          className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
        >
          <X size={16} />
        </button>
      </div>
      <textarea
        value={value.description}
        onChange={(e) => onChange({ ...value, description: e.target.value })}
        placeholder="Describe what this section should cover..."
        rows={3}
        className="w-full text-sm bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] px-3 py-2 resize-none"
      />
    </div>
  );
}
```

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/CustomSectionRow.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/CustomSectionRow.tsx \
        frontend/src/components/morning-briefing/__tests__/CustomSectionRow.test.tsx
git commit -m "feat(frontend): add MB CustomSectionRow"
```

---

### Task 19: Frontend — `ScheduleRow` + `AddScheduleModal`

One schedule row display + modal for time/timezone/days/label. V1 ships one row at most per user (README pattern #8); if a row exists the "Add Schedule" button becomes "Edit".

**Files:**
- Create: `frontend/src/components/morning-briefing/ScheduleRow.tsx`
- Create: `frontend/src/components/morning-briefing/AddScheduleModal.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/AddScheduleModal.test.tsx`

- [ ] **Step 1: Write the failing modal test**

```tsx
// frontend/src/components/morning-briefing/__tests__/AddScheduleModal.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AddScheduleModal } from "../AddScheduleModal";

describe("AddScheduleModal", () => {
  it("submits with selected values", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AddScheduleModal
        open
        initial={null}
        onClose={() => {}}
        onSubmit={onSubmit}
      />,
    );
    fireEvent.change(screen.getByLabelText(/Time/i), {
      target: { value: "07:00" },
    });
    fireEvent.change(screen.getByLabelText(/Timezone/i), {
      target: { value: "America/New_York" },
    });
    fireEvent.click(screen.getByLabelText(/Mon/));
    fireEvent.change(screen.getByLabelText(/Label/i), {
      target: { value: "Pre-Market" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Add Schedule/i }));
    expect(onSubmit).toHaveBeenCalledWith({
      time: "07:00", timezone: "America/New_York",
      days_of_week: ["mon"], label: "Pre-Market",
    });
  });

  it("disables submit when no day is selected", () => {
    render(
      <AddScheduleModal
        open
        initial={null}
        onClose={() => {}}
        onSubmit={() => Promise.resolve()}
      />,
    );
    const btn = screen.getByRole("button", { name: /Add Schedule/i });
    expect(btn).toBeDisabled();
  });

  it("prefills from initial when editing", () => {
    render(
      <AddScheduleModal
        open
        initial={{
          time: "08:30", timezone: "America/New_York",
          days_of_week: ["mon", "tue"], label: "Pre",
        }}
        onClose={() => {}}
        onSubmit={() => Promise.resolve()}
      />,
    );
    expect(screen.getByDisplayValue("08:30")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Pre")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/AddScheduleModal.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write `ScheduleRow`**

```tsx
// frontend/src/components/morning-briefing/ScheduleRow.tsx
import { X } from "lucide-react";

import type { MbSchedule } from "../../api/morning-briefing";

const DAY_LABELS: Record<string, string> = {
  mon: "Mon", tue: "Tue", wed: "Wed", thu: "Thu",
  fri: "Fri", sat: "Sat", sun: "Sun",
};

function formatDays(days: string[]): string {
  if (days.length === 7) return "Every day";
  if (days.length === 5 &&
      ["mon", "tue", "wed", "thu", "fri"].every((d) => days.includes(d))) {
    return "Mon-Fri";
  }
  return days.map((d) => DAY_LABELS[d] ?? d).join(", ");
}

interface Props {
  schedule: MbSchedule;
  onEdit: () => void;
  onRemove: () => void;
}

export function ScheduleRow({ schedule, onEdit, onRemove }: Props) {
  return (
    <div className="flex items-center justify-between px-4 py-3 border-b border-[--color-border-subtle] last:border-0">
      <div className="flex items-baseline gap-2">
        <span className="text-base font-medium text-[--color-text-primary]">
          {schedule.time}
        </span>
        <span className="text-sm text-[--color-text-secondary]">
          {schedule.timezone} · {formatDays(schedule.days_of_week)}
          {schedule.label ? ` · ${schedule.label}` : ""}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onEdit}
          className="text-sm text-[--color-text-secondary]"
        >
          Edit
        </button>
        <button
          type="button"
          aria-label="Remove schedule"
          onClick={onRemove}
          className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
        >
          <X size={16} />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write `AddScheduleModal`**

```tsx
// frontend/src/components/morning-briefing/AddScheduleModal.tsx
import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";

const DAYS: { id: string; label: string }[] = [
  { id: "mon", label: "Mon" }, { id: "tue", label: "Tue" },
  { id: "wed", label: "Wed" }, { id: "thu", label: "Thu" },
  { id: "fri", label: "Fri" }, { id: "sat", label: "Sat" },
  { id: "sun", label: "Sun" },
];

export interface ScheduleFormValue {
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
}

interface Props {
  open: boolean;
  initial: ScheduleFormValue | null;
  onClose: () => void;
  onSubmit: (v: ScheduleFormValue) => Promise<void>;
}

export function AddScheduleModal({ open, initial, onClose, onSubmit }: Props) {
  const [time, setTime] = useState(initial?.time ?? "07:00");
  const [timezone, setTimezone] = useState(
    initial?.timezone ?? "America/New_York",
  );
  const [days, setDays] = useState<string[]>(initial?.days_of_week ?? []);
  const [label, setLabel] = useState(initial?.label ?? "");
  const [submitting, setSubmitting] = useState(false);

  function toggleDay(id: string): void {
    setDays((prev) =>
      prev.includes(id) ? prev.filter((d) => d \!== id) : [...prev, id]);
  }

  async function handleSubmit(): Promise<void> {
    if (days.length === 0) return;
    setSubmitting(true);
    try {
      await onSubmit({ time, timezone, days_of_week: days, label });
      onClose();
    } finally {
      setSubmitting(false);
    }
  }

  const submitDisabled = submitting || days.length === 0;
  const submitLabel = initial ? "Save" : "Add Schedule";

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (\!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content
          className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-5 w-[440px]"
        >
          <Dialog.Title className="text-base font-semibold">
            {initial ? "Edit Schedule" : "Add Schedule"}
          </Dialog.Title>

          <div className="mt-4 flex flex-col gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-sm text-[--color-text-secondary]">Time</span>
              <input
                aria-label="Time"
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
                className="h-8 px-2 border border-[--color-border-subtle] rounded-[--radius-md]"
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-sm text-[--color-text-secondary]">Timezone</span>
              <input
                aria-label="Timezone"
                type="text"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="h-8 px-2 border border-[--color-border-subtle] rounded-[--radius-md]"
              />
            </label>

            <div className="flex flex-col gap-1">
              <span className="text-sm text-[--color-text-secondary]">Days</span>
              <div className="flex flex-wrap gap-2">
                {DAYS.map((d) => (
                  <label key={d.id} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      aria-label={d.label}
                      checked={days.includes(d.id)}
                      onChange={() => toggleDay(d.id)}
                    />
                    {d.label}
                  </label>
                ))}
              </div>
            </div>

            <label className="flex flex-col gap-1">
              <span className="text-sm text-[--color-text-secondary]">Label (optional)</span>
              <input
                aria-label="Label"
                type="text"
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Pre-Market"
                className="h-8 px-2 border border-[--color-border-subtle] rounded-[--radius-md]"
              />
            </label>
          </div>

          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] h-8 px-3 rounded-[--radius-md]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={submitDisabled}
              onClick={() => void handleSubmit()}
              className="text-sm bg-[--color-accent-primary] text-white h-8 px-3 rounded-[--radius-md] disabled:opacity-50"
            >
              {submitLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 5: Run the tests**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/AddScheduleModal.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/morning-briefing/ScheduleRow.tsx \
        frontend/src/components/morning-briefing/AddScheduleModal.tsx \
        frontend/src/components/morning-briefing/__tests__/AddScheduleModal.test.tsx
git commit -m "feat(frontend): add MB ScheduleRow + AddScheduleModal"
```

---

### Task 20: Frontend — `MBSettingsView`

Top-level Settings View: wraps section rows, custom sections list, schedule row + modal. Saves via `useMbConfig`.

**Files:**
- Create: `frontend/src/components/morning-briefing/MBSettingsView.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/MBSettingsView.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/morning-briefing/__tests__/MBSettingsView.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MbConfig, MbSchedule } from "../../../api/morning-briefing";
import { MBSettingsView } from "../MBSettingsView";

const baseConfig: MbConfig = {
  report_length: "normal",
  enabled_section_ids: [
    "executive_summary", "global_macro", "country_news",
    "market_news", "sector_news", "stock_news", "upcoming_preview",
  ],
  section_topics: {},
  custom_sections: [],
  reference_portfolio: false,
};

describe("MBSettingsView", () => {
  it("renders all 7 standard section rows", () => {
    render(
      <MBSettingsView
        config={baseConfig}
        schedule={null}
        onSaveConfig={() => Promise.resolve()}
        onUpsertSchedule={() => Promise.resolve({} as MbSchedule)}
        onDeleteSchedule={() => Promise.resolve()}
        onBack={() => {}}
      />,
    );
    expect(screen.getByText(/Executive Summary/)).toBeInTheDocument();
    expect(screen.getByText(/Global Macro News/)).toBeInTheDocument();
    expect(screen.getByText(/Upcoming Preview/)).toBeInTheDocument();
  });

  it("toggling a section fires onSaveConfig with updated state", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    render(
      <MBSettingsView
        config={baseConfig}
        schedule={null}
        onSaveConfig={onSave}
        onUpsertSchedule={() => Promise.resolve({} as MbSchedule)}
        onDeleteSchedule={() => Promise.resolve()}
        onBack={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: /Stock News/i }));
    await waitFor(() => {
      expect(onSave).toHaveBeenCalled();
    });
    const callArg = onSave.mock.calls[0][0];
    expect(callArg.enabled_section_ids.includes("stock_news")).toBe(false);
  });

  it("Back button fires onBack", () => {
    const onBack = vi.fn();
    render(
      <MBSettingsView
        config={baseConfig}
        schedule={null}
        onSaveConfig={() => Promise.resolve()}
        onUpsertSchedule={() => Promise.resolve({} as MbSchedule)}
        onDeleteSchedule={() => Promise.resolve()}
        onBack={onBack}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Back to Reports/i }));
    expect(onBack).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MBSettingsView.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write `MBSettingsView`**

```tsx
// frontend/src/components/morning-briefing/MBSettingsView.tsx
import { ChevronLeft, Plus } from "lucide-react";
import { useState } from "react";

import type {
  CustomSection,
  MbConfig,
  MbSchedule,
  TopicEntry,
} from "../../api/morning-briefing";
import { DEFAULT_MB_SECTIONS } from "../../lib/morning-briefing/section-catalog";
import { AddScheduleModal, type ScheduleFormValue } from "./AddScheduleModal";
import { CustomSectionRow } from "./CustomSectionRow";
import { ScheduleRow } from "./ScheduleRow";
import { SectionRow } from "./SectionRow";

interface Props {
  config: MbConfig;
  schedule: MbSchedule | null;
  onSaveConfig: (next: MbConfig) => Promise<void>;
  onUpsertSchedule: (payload: Omit<MbSchedule, "id" | "is_enabled">) => Promise<MbSchedule>;
  onDeleteSchedule: () => Promise<void>;
  onBack: () => void;
}

function cryptoRandomId(): string {
  const c = (globalThis as { crypto?: Crypto }).crypto;
  return c && "randomUUID" in c ? c.randomUUID() : Math.random().toString(36).slice(2);
}

export function MBSettingsView({
  config, schedule, onSaveConfig, onUpsertSchedule, onDeleteSchedule, onBack,
}: Props) {
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);

  function persist(patch: Partial<MbConfig>): void {
    const next: MbConfig = { ...config, ...patch };
    void onSaveConfig(next);
  }

  function toggleSection(sectionId: string, enabled: boolean): void {
    const current = new Set(config.enabled_section_ids);
    if (enabled) current.add(sectionId);
    else current.delete(sectionId);
    persist({
      enabled_section_ids: DEFAULT_MB_SECTIONS.filter((id) => current.has(id)),
    });
  }

  function setTopicsFor(sectionId: string, topics: TopicEntry[]): void {
    const next = { ...config.section_topics, [sectionId]: topics };
    persist({ section_topics: next });
  }

  function setReferencePortfolio(next: boolean): void {
    persist({ reference_portfolio: next });
  }

  function addCustom(): void {
    const newCs: CustomSection = {
      id: cryptoRandomId(), title: "", description: "",
    };
    persist({ custom_sections: [...config.custom_sections, newCs] });
  }

  function updateCustom(idx: number, next: CustomSection): void {
    persist({
      custom_sections: config.custom_sections.map((c, i) => (i === idx ? next : c)),
    });
  }

  function removeCustom(idx: number): void {
    persist({
      custom_sections: config.custom_sections.filter((_, i) => i \!== idx),
    });
  }

  async function handleScheduleSubmit(v: ScheduleFormValue): Promise<void> {
    await onUpsertSchedule(v);
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex items-center justify-between border-b border-[--color-border-subtle] px-6 flex-shrink-0">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <ChevronLeft size={14} /> Back to Reports
        </button>
        <div className="text-base font-medium">Morning Briefings Settings</div>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-5">
        <h3 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em] mb-2">
          Report Sections
        </h3>
        <div className="border border-[--color-border-subtle] rounded-[--radius-lg] divide-y divide-[--color-border-subtle]">
          {DEFAULT_MB_SECTIONS.map((sid) => (
            <SectionRow
              key={sid}
              sectionId={sid}
              enabled={config.enabled_section_ids.includes(sid)}
              topics={config.section_topics[sid] ?? []}
              referencePortfolio={config.reference_portfolio}
              onToggleEnabled={(enabled) => toggleSection(sid, enabled)}
              onTopicsChange={(t) => setTopicsFor(sid, t)}
              onReferencePortfolioChange={setReferencePortfolio}
            />
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between mb-2">
          <h3 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em]">
            Custom Sections
          </h3>
          <button
            type="button"
            onClick={addCustom}
            className="flex items-center gap-1 text-sm text-[--color-accent-primary]"
          >
            <Plus size={14} /> Add Section
          </button>
        </div>
        <div className="flex flex-col gap-2">
          {config.custom_sections.length === 0 ? (
            <div className="text-sm text-[--color-text-tertiary]">
              No custom sections yet
            </div>
          ) : (
            config.custom_sections.map((cs, idx) => (
              <CustomSectionRow
                key={cs.id}
                value={cs}
                onChange={(next) => updateCustom(idx, next)}
                onRemove={() => removeCustom(idx)}
              />
            ))
          )}
        </div>

        <div className="mt-6 flex items-center justify-between mb-2">
          <h3 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em]">
            Schedule
          </h3>
          <button
            type="button"
            onClick={() => setScheduleModalOpen(true)}
            className="flex items-center gap-1 text-sm text-[--color-accent-primary]"
          >
            <Plus size={14} /> {schedule ? "Edit Schedule" : "Add Schedule"}
          </button>
        </div>
        <div className="border border-[--color-border-subtle] rounded-[--radius-lg]">
          {schedule ? (
            <ScheduleRow
              schedule={schedule}
              onEdit={() => setScheduleModalOpen(true)}
              onRemove={() => void onDeleteSchedule()}
            />
          ) : (
            <div className="p-4 text-sm text-[--color-text-tertiary]">
              No schedule configured. Reports will not be generated automatically.
            </div>
          )}
        </div>
      </div>

      <AddScheduleModal
        open={scheduleModalOpen}
        initial={schedule
          ? {
              time: schedule.time,
              timezone: schedule.timezone,
              days_of_week: schedule.days_of_week,
              label: schedule.label,
            }
          : null}
        onClose={() => setScheduleModalOpen(false)}
        onSubmit={handleScheduleSubmit}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/MBSettingsView.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/MBSettingsView.tsx \
        frontend/src/components/morning-briefing/__tests__/MBSettingsView.test.tsx
git commit -m "feat(frontend): add MB MBSettingsView composition"
```

---

### Task 21: Frontend — `OnDemandBriefingButton`

Uses the shipped `useReportStream` hook (README pattern #4). Starts the POST-based SSE, shows progress, opens the FileViewer on `report.saved`.

**Files:**
- Create: `frontend/src/components/morning-briefing/OnDemandBriefingButton.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/OnDemandBriefingButton.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/morning-briefing/__tests__/OnDemandBriefingButton.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnDemandBriefingButton } from "../OnDemandBriefingButton";

vi.mock("../../../components/report/useReportStream", () => ({
  useReportStream: () => ({
    state: { status: "idle", events: [] },
    start: vi.fn().mockImplementation(async () => {
      fakeOnSaved?.("r_42");
    }),
    reset: vi.fn(),
  }),
}));

let fakeOnSaved: ((id: string) => void) | null = null;

describe("OnDemandBriefingButton", () => {
  it("renders a Generate button", () => {
    render(<OnDemandBriefingButton onReportSaved={() => {}} />);
    expect(screen.getByRole("button", { name: /Generate Briefing/i })).toBeInTheDocument();
  });

  it("calls onReportSaved when the stream completes", async () => {
    const onReportSaved = vi.fn();
    fakeOnSaved = onReportSaved;
    render(<OnDemandBriefingButton onReportSaved={onReportSaved} />);
    fireEvent.click(screen.getByRole("button", { name: /Generate Briefing/i }));
    await waitFor(() => expect(onReportSaved).toHaveBeenCalledWith("r_42"));
  });
});
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/OnDemandBriefingButton.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/morning-briefing/OnDemandBriefingButton.tsx
import { Play } from "lucide-react";
import { useEffect } from "react";

import { useReportStream } from "../../components/report/useReportStream";

interface Props {
  onReportSaved: (reportId: string) => void;
}

export function OnDemandBriefingButton({ onReportSaved }: Props) {
  const { state, start, reset } = useReportStream();

  useEffect(() => {
    const savedEvent = state.events.find((e) => e.type === "report.saved");
    if (savedEvent && "report_id" in savedEvent.data) {
      onReportSaved(String(savedEvent.data.report_id));
      reset();
    }
  }, [state.events, onReportSaved, reset]);

  async function handleClick(): Promise<void> {
    await start({
      url: "/api/departments/morning-briefing/report",
      body: {},
    });
  }

  const busy = state.status === "streaming";

  return (
    <button
      type="button"
      onClick={() => void handleClick()}
      disabled={busy}
      className="flex items-center gap-1 bg-[--color-accent-primary] text-white text-sm h-8 px-3 rounded-[--radius-md] disabled:opacity-50"
    >
      <Play size={14} />
      {busy ? "Generating..." : "Generate Briefing"}
    </button>
  );
}
```

> **Contract:** `useReportStream.start({url, body})` is the shipped Plan 13 signature. If the actual shipped signature is different (e.g., `start({endpoint, payload})`), use the real field names; never invent new ones. Confirm via `grep useReportStream frontend/src/pages/departments/EquityResearch.tsx` before finalizing.

- [ ] **Step 4: Run the test**

Run: `cd frontend && npx vitest run src/components/morning-briefing/__tests__/OnDemandBriefingButton.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/OnDemandBriefingButton.tsx \
        frontend/src/components/morning-briefing/__tests__/OnDemandBriefingButton.test.tsx
git commit -m "feat(frontend): add MB OnDemandBriefingButton using useReportStream"
```

---

### Task 22: Frontend — `pages/departments/MorningBriefing.tsx` composition

Full page composition: header toggles between Archive and Settings views. Chat panel (shipped `ChatInterface`) bound to the MB chat session id from `useMbChatSession`. `OnDemandBriefingButton` lives in the header of the Archive View.

**Files:**
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx`
- Modify: `frontend/src/routes.tsx` (confirm `/morning-briefing` route renders the new composition; the placeholder route likely already exists).
- Test: `frontend/src/pages/departments/__tests__/MorningBriefing.test.tsx`

- [ ] **Step 1: Write the failing page test**

```tsx
// frontend/src/pages/departments/__tests__/MorningBriefing.test.tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import MorningBriefing from "../MorningBriefing";

vi.mock("../../../components/chat/ChatInterface", () => ({
  ChatInterface: ({ sessionId }: { sessionId: string }) => (
    <div data-testid="chat">chat:{sessionId}</div>
  ),
}));

vi.mock("../../../components/report/useReportStream", () => ({
  useReportStream: () => ({ state: { status: "idle", events: [] }, start: vi.fn(), reset: vi.fn() }),
}));

describe("MorningBriefing page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "fetchConfig").mockResolvedValue({
      report_length: "normal",
      enabled_section_ids: [
        "executive_summary", "global_macro", "country_news",
        "market_news", "sector_news", "stock_news", "upcoming_preview",
      ],
      section_topics: {}, custom_sections: [], reference_portfolio: false,
    });
    vi.spyOn(api, "fetchSchedule").mockResolvedValue({ schedule: null });
    vi.spyOn(api, "fetchReports").mockResolvedValue({ reports: [] });
    vi.spyOn(api, "resolveChatSession").mockResolvedValue({ session_id: "chat_1" });
  });

  it("renders header + archive view + chat", async () => {
    render(<MorningBriefing />);
    expect(screen.getByText(/Morning Briefings/i)).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("chat")).toHaveTextContent("chat:chat_1");
    });
  });

  it("switches to Settings View when Settings clicked", async () => {
    render(<MorningBriefing />);
    fireEvent.click(await screen.findByRole("button", { name: /Settings/i }));
    await waitFor(() => {
      expect(screen.getByText(/Morning Briefings Settings/i)).toBeInTheDocument();
    });
  });

  it("Back button in Settings returns to Archive", async () => {
    render(<MorningBriefing />);
    fireEvent.click(await screen.findByRole("button", { name: /Settings/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Back to Reports/i }));
    await waitFor(() => {
      expect(screen.queryByText(/Morning Briefings Settings/i)).not.toBeInTheDocument();
    });
  });
});
```

- [ ] **Step 2: Write the page**

```tsx
// frontend/src/pages/departments/MorningBriefing.tsx
import { Settings as SettingsIcon } from "lucide-react";
import { useState } from "react";

import { ChatInterface } from "../../components/chat/ChatInterface";
import { MBArchiveView } from "../../components/morning-briefing/MBArchiveView";
import { MBSettingsView } from "../../components/morning-briefing/MBSettingsView";
import { OnDemandBriefingButton } from "../../components/morning-briefing/OnDemandBriefingButton";
import { useFileViewer } from "../../components/FileViewer/FileViewerContext";
import { useMbChatSession } from "../../hooks/useMbChatSession";
import { useMbConfig } from "../../hooks/useMbConfig";
import { useMbReports } from "../../hooks/useMbReports";
import { useMbSchedule } from "../../hooks/useMbSchedule";

type View = "archive" | "settings";

export default function MorningBriefing(): JSX.Element {
  const [view, setView] = useState<View>("archive");
  const { config, save: saveConfig } = useMbConfig();
  const { schedule, upsert: upsertSchedule, remove: removeSchedule } = useMbSchedule();
  const { reports, refresh: refreshReports } = useMbReports();
  const { sessionId } = useMbChatSession();
  const fv = useFileViewer();

  function openReport(id: string): void {
    fv.openReport(id);
  }

  function downloadReport(id: string): void {
    fv.downloadReport(id);
  }

  if (view === "settings") {
    if (config === null) {
      return <div className="p-6 text-sm text-[--color-text-secondary]">Loading...</div>;
    }
    return (
      <MBSettingsView
        config={config}
        schedule={schedule}
        onSaveConfig={saveConfig}
        onUpsertSchedule={upsertSchedule}
        onDeleteSchedule={removeSchedule}
        onBack={() => setView("archive")}
      />
    );
  }

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex items-center justify-between border-b border-[--color-border-subtle] px-6 flex-shrink-0">
        <h1 className="text-xl font-semibold">Morning Briefings</h1>
        <div className="flex items-center gap-2">
          <OnDemandBriefingButton
            onReportSaved={(id) => {
              void refreshReports();
              openReport(id);
            }}
          />
          <button
            type="button"
            onClick={() => setView("settings")}
            className="flex items-center gap-1 border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-8 hover:bg-[--color-surface-hover]"
          >
            <SettingsIcon size={16} /> Settings
          </button>
        </div>
      </header>

      <div className="flex-1 flex min-h-0">
        <div className="flex-1 min-w-0">
          <MBArchiveView
            reports={reports}
            onOpen={openReport}
            onDownload={downloadReport}
            onGoToSettings={() => setView("settings")}
          />
        </div>
        <div className="w-[420px] border-l border-[--color-border-subtle] flex-shrink-0">
          {sessionId ? (
            <ChatInterface sessionId={sessionId} />
          ) : (
            <div className="p-6 text-sm text-[--color-text-secondary]">
              Loading chat...
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Register the route**

In `frontend/src/routes.tsx`, confirm the MB route points at `./pages/departments/MorningBriefing`. The placeholder export was a default function `MorningBriefing`, so the route entry does not need structural changes — just re-verify the import path.

- [ ] **Step 4: Run the tests**

Run: `cd frontend && npx vitest run src/pages/departments/__tests__/MorningBriefing.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/MorningBriefing.tsx \
        frontend/src/pages/departments/__tests__/MorningBriefing.test.tsx \
        frontend/src/routes.tsx
git commit -m "feat(frontend): MorningBriefing page composition + chat + archive/settings toggle"
```

---

### Task 23: Manual smoke test + README + matrices

- [ ] **Step 1: Apply the migration**

```bash
uv run alembic -c packages/server/alembic.ini upgrade head
```

Expected: no errors.

- [ ] **Step 2: Run the full aggregate suite + lint/format**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Expected: all pass. Fix any incidental regressions before proceeding.

- [ ] **Step 3: Run the server**

```bash
uv run openlia serve
```

- [ ] **Step 4: Run the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 5: Manual checks**

1. Navigate to `/morning-briefing`. The Archive View loads with the empty state and the chat pane on the right.
2. Click Settings. Verify all 7 section rows render with checkboxes. Uncheck "Stock News"; verify a toast (or inline save indicator) confirms persistence. Reload — the checkbox is still unchecked.
3. On "Global Macro News", add topics `War`, `Politics`, `Energy` via the "Add topic" chip (Enter + comma both work). Click the `War` chip; enter notes `Russia-Ukraine`. Verify the notes dot appears on the chip.
4. On "Upcoming Preview", check "Reference Portfolio". Verify a toast confirms save.
5. Click Add Section under Custom Sections. Enter title "My Macro Focus", description "Focus on EUR/JPY crosses". Verify persistence.
6. Click "Add Schedule". Enter 07:00 America/New_York Mon-Fri, label "Pre-Market". Verify the row appears and `fetchSchedule` returns it.
7. Re-click "Edit Schedule", change time to 08:00, label "Late Pre-Market". Verify modify path.
8. Click Back to Reports. Click Generate Briefing. Verify the SSE stream emits `report.start -> report.delta -> report.complete -> report.saved`; the FileViewer opens automatically with the new report.
9. In the chat pane on the right, ask "Summarize today's macro pillar." Verify `/api/chat/sessions/{sessionId}/stream?q=...` is called, tokens stream in, and the assistant response persists after reload.
10. Delete the schedule (× icon). Verify the scheduler unregisters (check `uv run openlia jobs status` or the server logs).
11. Trigger the scheduled briefing manually via CLI (`openlia jobs run --type mb_briefing --user me` if shipped, else wait for the cron fire). Verify a new report lands in the archive, a notification dot appears on the sidebar, and the chat session re-renders without a page refresh after the archive refetches.

- [ ] **Step 6: Update README status + matrices**

Edit `planning/implementation-plans/README.md` — change the Plan 16 row from `Not started | —` to:

```
| 16 | 5 | Morning Briefing department + briefing scheduling | Draft | `2026-04-23-phase-16-morning-briefing.md` |
```

Add rows for the new endpoints in `planning/implementation-plans/endpoint-contract-matrix.md`:

- `GET /departments/morning-briefing/config`
- `PUT /departments/morning-briefing/config`
- `GET /departments/morning-briefing/schedule`
- `PUT /departments/morning-briefing/schedule`
- `DELETE /departments/morning-briefing/schedule`
- `POST /departments/morning-briefing/report`
- `POST /departments/morning-briefing/chat/session`

Add the matching rows in `planning/implementation-plans/route-authorization-matrix.md` (all authenticated; owner-scoped; mount in both personal and company modes).

- [ ] **Step 7: Commit**

```bash
git add planning/implementation-plans/README.md \
        planning/implementation-plans/endpoint-contract-matrix.md \
        planning/implementation-plans/route-authorization-matrix.md
git commit -m "docs: mark Plan 16 (Morning Briefing) Draft + add endpoint/auth matrix rows"
```

---

## Non-goals / follow-up work

1. **Multiple schedules per user.** The README lock "one schedule per (job_type, user_id)" forces a v1 design where users get exactly one MB schedule. To support pre-market + post-market in the same day, a follow-up plan extends `SchedulerService` to key on `(job_type, user_id, schedule_id)` and teaches the executor to carry slot-specific label context. Out of scope for Plan 16.
2. **Reference Portfolio full wiring.** If Plan 21 (Portfolio page) hasn't shipped at the time this plan runs, `PortfolioHolding` rows can only be seeded manually (admin CLI, or via API tests). MB handles both states — toggle on with zero holdings is a no-op at prompt-rendering time. When Plan 21 ships, no MB code change is required; the request builder already reads `PortfolioHolding` rows defensively.
3. **Email notifications on report completion.** The spec mentions email; this plan does not ship an email transport. `user_notifications` rows are produced by Plan 6's executor and consumed by Plan 8's `NotificationBadge`. An email-transport layer is a separate plan.
4. **Archive View "New" badge + sidebar notification dot.** Both ride on top of the notifications plumbing owned by Plan 6 + Plan 8. This plan writes no new code there.
5. **PDF export of a briefing.** Uses the shipped `POST /reports/{id}/export/pdf` from Plan 13 (README pattern #6). No MB-specific PDF wiring needed.

---

## Self-Review

### Spec coverage mapping

| Spec section | Owning task(s) |
|---|---|
| Archive View header + Settings button | 22 |
| Archive View — empty state + "Go to Settings" CTA | 16, 22 |
| Archive View — date groups + report cards + Open/Download | 16 |
| Settings View header + Back to Reports | 20, 22 |
| Report Sections list (7 standard) + checkboxes | 17, 20 |
| Topic chips + inline "Add topic" + Notes popover | 17 |
| Executive Summary (toggle-only, no topic input) | 15 (catalog `hasTopics: false`), 17 |
| Upcoming Preview — Reference Portfolio checkbox | 17, 20 |
| Custom Sections list + Add/Edit/Remove + description textarea | 18, 20 |
| Schedule list + Add/Edit/Remove | 19, 20 |
| Add Schedule modal (time + tz + days + label) | 19 |
| Toast on save success/failure | Existing toast primitive in Plan 8 shell; `onSaveConfig` resolves -> toast on success, rejects -> toast on failure. Wired in Task 20 implementation and verified in Task 23 manual checks. |
| Responsive behavior (2-col > 1-col) | 16 (grid uses `grid-cols-1 sm:grid-cols-2`) |
| Section transition animation | Out of scope (cosmetic; a follow-up can add Framer Motion slide). |
| Scheduled briefing generation | 6, 7, 13 + Plan 6's `MBBriefingExecutor` |
| On-demand briefing generation | 8, 11, 21 |
| Follow-up chat on generated briefing | 12, 15 (`useMbChatSession`), 22 |
| Report framework + style guide | Read-only — shipped in Plan 13. Prompt consumes them. |

### Contract compliance checklist

- Named-event SSE: Task 11 emits `event: <type>\ndata: <json>\n\n`. (README #1)
- Chat stream shape: Task 12 creates a session; the frontend uses the shipped `/api/chat/sessions/{id}/stream`. No MB-specific chat route. (README #2)
- Report stream shape: Task 11 is `POST /api/departments/morning-briefing/report`; terminates with `report.saved` (Task 8). (README #3)
- `useReportStream` is the only SSE reader on the frontend. (README #4 — Task 21)
- `ChatReportThumbnail` wire shape `{message_id, report_id, filename}` is consumed by `useChatStream` (Plan 12) — MB doesn't re-implement. (README #5)
- `/reports` listing is the shared endpoint with `?department=morning_briefing` filter (Task 14). (README #6)
- `suggest_redirect` structured-tool contract: MB does not ship extra tools (`extra_tools=()` in Task 1). Secretary's existing `suggest_redirect` already routes to MB via `get_department("morning_briefing")`. (README #7)
- Scheduler one-per-(job_type, user_id): Task 6 enforces upsert + single row per user. Task 10 exposes only `GET`/`PUT`/`DELETE` — no plural routes. (README #8)
- `String(36)` UUIDs with `str(uuid.uuid4())`: Tasks 5 (`MbUserConfig.id`), 6 (`MbSchedule.id`), 12 (`ChatSession.id`). No prefixed short-hex ids. (README #9)
- Length-branching prompt uses mapped values (`brief`/`standard`/`long`): Task 2 (prompt), Tasks 7+8 (mapping layer). (Ancillary lock)

### Placeholder scan

Every step has runnable code, exact file paths, and concrete assertions. No `TODO`, `TBD`, `fill in`, or `implement later`. Two consult-first notes are explicit:

- Task 7 Step 4 — the `MB_EXTRAS_JSON` pass-through mechanism depends on Plan 5's prompt-context hook surface. If that hook takes a different keyword name, adapt the adapter; do not extend `ReportRequest`.
- Task 21 Step 3 — confirm the `useReportStream.start` signature by grepping `pages/departments/EquityResearch.tsx` before committing.

Both are pointers to existing code, not deferred implementation work.

### Type consistency

- `MorningBriefingMode = Literal["morning_briefing"]` (core, Task 1) <-> `request.mode == "morning_briefing"` (Tasks 7/8).
- `report_length` vocab `{concise, normal, elaborative}` (Python DB column, Python config DTO, Pydantic `_ConfigIn`, TS `ReportLength`) <-> `ReportRequest.length ∈ {brief, standard, long}` mapped at call-site (Tasks 7, 8).
- `TopicEntry` `{topic, notes}` is identical in: DB `section_topics` JSON value, Python config DTO, Pydantic `_TopicIn`, TS `TopicEntry`.
- `CustomSection` `{id, title, description}` is identical across core prompt input, Python DB JSON, Pydantic `_CustomSectionIn`, TS `CustomSection`. `id` is `str(uuid.uuid4())` (Task 20 `cryptoRandomId()` on the frontend; Python side uses `str(uuid.uuid4())` when the server originates ids).
- `MbSchedule` fields `{id, time, timezone, days_of_week, label, is_enabled}` match across Plan 1B's SQLAlchemy model, Python DTO, Pydantic `_ScheduleOut`, and TS `MbSchedule`.
- `reference_portfolio: bool` is identical across DB column, Python config DTO, Pydantic, TS.

### Cross-plan consistency

- `DEPARTMENT_DEFAULT_TIERS["morning_briefing"] = EVERYDAY` (Plan 4) matches `MorningBriefingDepartment.tier_for()` (Task 1).
- `mb_schedules` is owned by Plan 1B; this plan writes to it but does not redefine it.
- `MBRequestBuilder` Protocol signature `build(session, user_id, schedule_id) -> ReportRequest` (Plan 6) is implemented in Task 7.
- `ReportRequest` fields (mode, user_input, enabled_sections, custom_sections, length) are the ones Plan 5 ships; no retroactive edits.
- `report_store.create_report(user_id, department, report_type, title, content_markdown, content_structured, model_ref=None)` matches Plan 13's shipped API (Task 8).
- Framework `morning_briefing.json` + `morning_briefing_style_guide.md` already live at `packages/core/src/openlia/reports/frameworks/` (Plan 13).
- Chat session model (`ChatSession` with `department`, `is_pinned`, `is_archived`, `context`) matches the current backend contract (Task 12).
