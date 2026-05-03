# Skills MVP (Prompt-Only) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Each task follows TDD red-green-refactor — see the `tdd` skill.

**Goal:** Ship the prompt-only half (Q1 shape "A") of the OpenLIA skills system end-to-end: users can install a SKILL.md-format skill from a folder, git URL, or zip upload, the skill appears in the Settings UI, and the LLM discovers it through a system-prompt menu and pulls its body via a `load_skill` meta-tool.

**Architecture:** A new `openlia.skills` core module owns parsing, storage, and the registry. Storage is a `SkillStore` Protocol with two implementations: `FilesystemSkillStore` (default) and `DatabaseSkillStore` (used for company-mode user-scope installs); `LayeredSkillStore` composes them. A new shared Jinja partial `shared/skills_menu.yaml.j2` is included from every department's chat and report system slots, populated from the registry by the existing `PromptLoader`. The existing tool dispatcher gains a `load_skill` meta-tool. Audit events extend the existing `lia_guardrail_events` table via an Alembic migration that relaxes a few NOT NULLs and adds a `payload_json` column. Frontend gains `/settings/skills` (everyone) and `/settings/admin/skills` (admin) routes.

**Tech Stack:** Python 3.12 (FastAPI, SQLAlchemy 2.x, Pydantic v2, Jinja2, PyYAML, Alembic, pytest), React 18 + TypeScript + Vite + react-router-dom. No new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-05-03-skills-system-design.md`

**Out of this plan (Plan 2):** MCP tool dispatcher, secrets vault, npm `@openlia/skill-installer` helper, `SkillToolInvoked` SSE event, first-party primitives carve-out (`openlia.repo.*`, `openlia.connector.query`). Plan 2 layers on top of this one.

---

## File Structure

**New (core):**
- `packages/core/src/openlia/skills/__init__.py` — public surface (`SkillManifest`, `InstalledSkill`, `parse_skill_md`, `SkillStore`, `LayeredSkillStore`, `SkillRegistry`).
- `packages/core/src/openlia/skills/types.py` — `SkillManifest` Pydantic model + `InstalledSkill` dataclass.
- `packages/core/src/openlia/skills/parser.py` — `parse_skill_md(text) -> tuple[SkillManifest, str]` and `serialize_skill_md(manifest, body) -> str`.
- `packages/core/src/openlia/skills/store.py` — `SkillStore` Protocol + `LayeredSkillStore`.
- `packages/core/src/openlia/skills/filesystem_store.py` — `FilesystemSkillStore`.
- `packages/core/src/openlia/skills/registry.py` — `SkillRegistry` (in-memory cache, dept/user filtering).
- `packages/core/src/openlia/prompts/shared/skills_menu.yaml.j2` — Jinja partial.

**New (server):**
- `packages/server/src/openlia_server/db/models/skills.py` — `Skill`, `SkillUserOverride` ORM models; extends `LiaGuardrailEvent` payload column.
- `packages/server/src/openlia_server/skills/database_store.py` — `DatabaseSkillStore`.
- `packages/server/src/openlia_server/services/skill_installer.py` — git-clone, zip-extract, folder-copy install paths.
- `packages/server/src/openlia_server/services/skill_audit.py` — writes skill events into `lia_guardrail_events`.
- `packages/server/src/openlia_server/routes/skills.py` — user-facing routes.
- `packages/server/src/openlia_server/routes/admin_skills.py` — admin routes.
- `packages/server/alembic/versions/<rev>_skills_tables.py` — migration.

**New (frontend):**
- `frontend/src/api/skills.ts` — typed API client.
- `frontend/src/components/settings/sections/SkillsSection.tsx` — `/settings/skills`.
- `frontend/src/components/settings/sections/AdminSkillsSection.tsx` — `/settings/admin/skills`.
- `frontend/src/components/settings/skills/SkillRow.tsx` — per-skill list row.
- `frontend/src/components/settings/skills/SkillDetailPanel.tsx` — body viewer + metadata.
- `frontend/src/components/settings/skills/InstallSkillModal.tsx` — git URL / zip / folder rescan tabs.
- `frontend/src/components/chat/SkillLoadedCard.tsx` — inline event card.

**Modified:**
- `packages/core/src/openlia/llm/runtime/events.py` — add `ChatSkillLoaded` dataclass.
- `packages/core/src/openlia/llm/runtime/prompts.py` — `render()` accepts and threads `skills_menu` context.
- `packages/core/src/openlia/llm/runtime/tools.py` — register `load_skill` meta-tool; dispatcher protocol extended.
- `packages/core/src/openlia/llm/runtime/chat.py` — pull menu from registry, pass to renderer; emit `ChatSkillLoaded`.
- `packages/core/src/openlia/llm/runtime/report.py` — same menu wiring for report flows (no event emission needed).
- `packages/core/src/openlia/prompts/{secretary,equity_research,earnings_update,morning_briefing,macro_research,retail_sentiment,retail_sentiment_insights,panic_thermometer}.yaml` — `{% include "shared/skills_menu.yaml.j2" %}` added to chat and report slots.
- `packages/server/src/openlia_server/app.py` — wire `LayeredSkillStore` + `SkillRegistry` at startup; mount new routers.
- `packages/server/src/openlia_server/db/models/safety.py` — add `payload_json` Mapped column to `LiaGuardrailEvent`; relax NOT NULLs on `session_id`, `department_id`, `category`, `user_input_hash`, `response_excerpt`.
- `packages/server/src/openlia_server/db/models/register_all.py` — import the new `skills` module so its tables register on `Base.metadata`.
- `frontend/src/pages/SettingsPage.tsx` — add `<Route path="skills">` (everyone) and `<Route path="admin/skills">` (admin).

---

## Phase 1 — Skill format and storage

### Task 1: Skill manifest model + frontmatter parser

**Files:**
- Create: `packages/core/src/openlia/skills/types.py`
- Create: `packages/core/src/openlia/skills/parser.py`
- Create: `packages/core/src/openlia/skills/__init__.py`
- Create: `packages/core/tests/test_skills/__init__.py`
- Create: `packages/core/tests/test_skills/test_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_skills/test_parser.py
import pytest

from openlia.skills import SkillManifest, parse_skill_md, serialize_skill_md


VALID_SKILL_MD = """---
name: equity-toolkit
display_name: Equity Toolkit
description: A small DCF playbook.
version: "1.0.0"
departments: [equity_research]
author: Acme
---

# How to use

Body content here.
"""


def test_parse_minimal_skill_md():
    manifest, body = parse_skill_md(VALID_SKILL_MD)
    assert manifest.name == "equity-toolkit"
    assert manifest.display_name == "Equity Toolkit"
    assert manifest.description == "A small DCF playbook."
    assert manifest.version == "1.0.0"
    assert manifest.departments == ["equity_research"]
    assert manifest.author == "Acme"
    assert body.lstrip().startswith("# How to use")


def test_parse_rejects_invalid_skill_id():
    bad = VALID_SKILL_MD.replace("equity-toolkit", "Equity Toolkit!")
    with pytest.raises(ValueError, match="invalid skill id"):
        parse_skill_md(bad)


def test_parse_rejects_missing_departments():
    bad = VALID_SKILL_MD.replace("departments: [equity_research]\n", "")
    with pytest.raises(ValueError, match="departments"):
        parse_skill_md(bad)


def test_parse_accepts_wildcard_departments():
    text = VALID_SKILL_MD.replace("[equity_research]", '["*"]')
    manifest, _ = parse_skill_md(text)
    assert manifest.departments == ["*"]


def test_serialize_round_trips():
    manifest, body = parse_skill_md(VALID_SKILL_MD)
    text = serialize_skill_md(manifest, body)
    manifest2, body2 = parse_skill_md(text)
    assert manifest2.model_dump() == manifest.model_dump()
    assert body2.strip() == body.strip()


def test_parse_rejects_no_frontmatter():
    with pytest.raises(ValueError, match="frontmatter"):
        parse_skill_md("just a body, no frontmatter\n")
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_parser.py -v`
Expected: FAIL — `ImportError: cannot import name 'SkillManifest' from 'openlia.skills'`.

- [ ] **Step 3: Implement minimum**

```python
# packages/core/src/openlia/skills/types.py
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

SKILL_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class SkillManifest(BaseModel):
    """Parsed SKILL.md frontmatter."""

    name: str
    display_name: str | None = None
    description: str
    version: str = "0.0.0"
    departments: list[str]  # dept ids, or ["*"] for global
    author: str | None = None
    # Plan 2 fields (parsed but unused in Plan 1):
    mcp: dict | None = None
    tools: list[dict] | None = None
    requires_secrets: list[dict] | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        if not SKILL_ID_RE.match(v):
            raise ValueError(f"invalid skill id: {v!r}")
        return v

    @field_validator("departments")
    @classmethod
    def _validate_departments(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("departments must be non-empty (or ['*'] for global)")
        return v


@dataclass(frozen=True)
class InstalledSkill:
    """A skill as it lives in the registry/store."""

    manifest: SkillManifest
    body: str
    scope: Literal["system", "user"]
    user_id: str | None  # None for system scope
    enabled: bool
    installed_at: datetime
    source: str  # "folder", "git:<url>", "zip", "npx:<pkg>"
```

```python
# packages/core/src/openlia/skills/parser.py
from __future__ import annotations

import yaml

from openlia.skills.types import SkillManifest


_FRONTMATTER_RE_OPEN = "---\n"
_FRONTMATTER_RE_CLOSE = "\n---\n"


def parse_skill_md(text: str) -> tuple[SkillManifest, str]:
    """Split a SKILL.md document into (manifest, body)."""
    if not text.startswith(_FRONTMATTER_RE_OPEN):
        raise ValueError("SKILL.md must start with '---' frontmatter")
    rest = text[len(_FRONTMATTER_RE_OPEN):]
    end = rest.find(_FRONTMATTER_RE_CLOSE)
    if end == -1:
        raise ValueError("SKILL.md frontmatter not closed with '---'")
    raw = rest[:end]
    body = rest[end + len(_FRONTMATTER_RE_CLOSE):]
    data = yaml.safe_load(raw) or {}
    if not isinstance(data, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    manifest = SkillManifest(**data)
    return manifest, body


def serialize_skill_md(manifest: SkillManifest, body: str) -> str:
    """Inverse of parse_skill_md."""
    fm = manifest.model_dump(exclude_none=True)
    raw = yaml.safe_dump(fm, sort_keys=False).rstrip() + "\n"
    return f"---\n{raw}---\n{body}"
```

```python
# packages/core/src/openlia/skills/__init__.py
from openlia.skills.parser import parse_skill_md, serialize_skill_md
from openlia.skills.types import SKILL_ID_RE, InstalledSkill, SkillManifest

__all__ = [
    "SKILL_ID_RE",
    "InstalledSkill",
    "SkillManifest",
    "parse_skill_md",
    "serialize_skill_md",
]
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_parser.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills packages/core/tests/test_skills
git commit -m "feat(skills): SkillManifest model + SKILL.md frontmatter parser"
```

---

### Task 2: SkillStore protocol and InstalledSkill helpers

**Files:**
- Create: `packages/core/src/openlia/skills/store.py`
- Modify: `packages/core/src/openlia/skills/__init__.py`
- Create: `packages/core/tests/test_skills/test_store_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_skills/test_store_protocol.py
from openlia.skills import SkillStore, LayeredSkillStore


def test_protocol_is_runtime_checkable():
    class Dummy:
        async def list(self, *, scope, user_id): return []
        async def get(self, skill_id, *, scope, user_id): return None
        async def install(self, source, *, scope, user_id, body, manifest): ...
        async def uninstall(self, skill_id, *, scope, user_id): ...
        async def set_enabled(self, skill_id, enabled, *, scope, user_id): ...
    assert isinstance(Dummy(), SkillStore)


def test_layered_store_constructs():
    class Empty:
        async def list(self, *, scope, user_id): return []
        async def get(self, skill_id, *, scope, user_id): return None
        async def install(self, source, *, scope, user_id, body, manifest): ...
        async def uninstall(self, skill_id, *, scope, user_id): ...
        async def set_enabled(self, skill_id, enabled, *, scope, user_id): ...
    layered = LayeredSkillStore(system=Empty(), user=Empty())
    assert layered.system is not None
    assert layered.user is not None
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_store_protocol.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement minimum**

```python
# packages/core/src/openlia/skills/store.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from openlia.skills.types import InstalledSkill, SkillManifest

Scope = Literal["system", "user"]


@runtime_checkable
class SkillStore(Protocol):
    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]: ...
    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None: ...
    async def install(
        self,
        source: str,
        *,
        scope: Scope,
        user_id: str | None,
        body: str,
        manifest: SkillManifest,
    ) -> InstalledSkill: ...
    async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None: ...
    async def set_enabled(
        self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
    ) -> None: ...


@dataclass
class LayeredSkillStore:
    """Routes by scope: system reads/writes go to `system`, user to `user`."""

    system: SkillStore
    user: SkillStore

    def for_scope(self, scope: Scope) -> SkillStore:
        return self.system if scope == "system" else self.user

    async def list_visible(
        self, *, user_id: str | None, scope_filter: Scope | None = None
    ) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        if scope_filter in (None, "system"):
            out.extend(await self.system.list(scope="system", user_id=None))
        if scope_filter in (None, "user"):
            out.extend(await self.user.list(scope="user", user_id=user_id))
        return out
```

```python
# packages/core/src/openlia/skills/__init__.py  (append)
from openlia.skills.store import LayeredSkillStore, Scope, SkillStore

__all__ += ["LayeredSkillStore", "Scope", "SkillStore"]
```

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_store_protocol.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills/store.py packages/core/src/openlia/skills/__init__.py packages/core/tests/test_skills/test_store_protocol.py
git commit -m "feat(skills): SkillStore protocol + LayeredSkillStore"
```

---

### Task 3: FilesystemSkillStore — read paths

**Files:**
- Create: `packages/core/src/openlia/skills/filesystem_store.py`
- Modify: `packages/core/src/openlia/skills/__init__.py`
- Create: `packages/core/tests/test_skills/test_filesystem_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_skills/test_filesystem_store.py
import pytest

from openlia.skills import FilesystemSkillStore, parse_skill_md, serialize_skill_md


SAMPLE = """---
name: alpha
display_name: Alpha
description: A test skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


@pytest.fixture
def tmp_root(tmp_path):
    (tmp_path / "system").mkdir()
    (tmp_path / "user").mkdir()
    return tmp_path


@pytest.fixture
def installed_alpha(tmp_root):
    skill_dir = tmp_root / "user" / "alpha"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(SAMPLE)
    return skill_dir


@pytest.mark.asyncio
async def test_list_user_scope_finds_installed(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    skills = await store.list(scope="user", user_id="any")
    assert len(skills) == 1
    assert skills[0].manifest.name == "alpha"
    assert skills[0].body.strip() == "Body."
    assert skills[0].enabled is True


@pytest.mark.asyncio
async def test_get_returns_none_for_missing(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    assert await store.get("nope", scope="user", user_id="any") is None


@pytest.mark.asyncio
async def test_disabled_marker_flips_enabled(tmp_root, installed_alpha):
    (installed_alpha / ".disabled").touch()
    store = FilesystemSkillStore(root=tmp_root)
    skills = await store.list(scope="user", user_id="any")
    assert skills[0].enabled is False
```

- [ ] **Step 2: Run test, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'FilesystemSkillStore'`.

- [ ] **Step 3: Implement minimum**

```python
# packages/core/src/openlia/skills/filesystem_store.py
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from openlia.skills.parser import parse_skill_md, serialize_skill_md
from openlia.skills.store import Scope
from openlia.skills.types import InstalledSkill, SkillManifest


class FilesystemSkillStore:
    """Backs `<root>/{system,user}/<skill_id>/SKILL.md`. Per-user scoping
    in personal mode collapses to a single user dir; company-mode user
    scope uses DatabaseSkillStore instead."""

    def __init__(self, *, root: Path) -> None:
        self._root = root

    def _scope_dir(self, scope: Scope) -> Path:
        d = self._root / scope
        d.mkdir(parents=True, exist_ok=True)
        return d

    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        for sub in sorted(self._scope_dir(scope).iterdir()):
            if not sub.is_dir():
                continue
            md = sub / "SKILL.md"
            if not md.exists():
                continue
            try:
                manifest, body = parse_skill_md(md.read_text())
            except Exception:
                continue
            stat = md.stat()
            out.append(
                InstalledSkill(
                    manifest=manifest,
                    body=body,
                    scope=scope,
                    user_id=user_id if scope == "user" else None,
                    enabled=not (sub / ".disabled").exists(),
                    installed_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    source=(sub / ".source").read_text().strip()
                    if (sub / ".source").exists() else "folder",
                )
            )
        return out

    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None:
        for s in await self.list(scope=scope, user_id=user_id):
            if s.manifest.name == skill_id:
                return s
        return None

    # Write paths land in Task 4-5.
    async def install(self, source, *, scope, user_id, body, manifest):  # noqa: ANN001
        raise NotImplementedError  # Task 4

    async def uninstall(self, skill_id, *, scope, user_id):  # noqa: ANN001
        raise NotImplementedError  # Task 5

    async def set_enabled(self, skill_id, enabled, *, scope, user_id):  # noqa: ANN001
        raise NotImplementedError  # Task 5
```

```python
# packages/core/src/openlia/skills/__init__.py  (append)
from openlia.skills.filesystem_store import FilesystemSkillStore

__all__ += ["FilesystemSkillStore"]
```

Add `pytest-asyncio` config if not already present in `pyproject.toml` (`asyncio_mode = "auto"` for the `[tool.pytest.ini_options]` table) — verify with: `grep asyncio_mode pyproject.toml`. If absent, add it.

- [ ] **Step 4: Run test, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills packages/core/tests/test_skills/test_filesystem_store.py
git commit -m "feat(skills): FilesystemSkillStore read paths (list/get)"
```

---

### Task 4: FilesystemSkillStore — install path

**Files:**
- Modify: `packages/core/src/openlia/skills/filesystem_store.py`
- Modify: `packages/core/tests/test_skills/test_filesystem_store.py`

- [ ] **Step 1: Append failing test**

```python
# packages/core/tests/test_skills/test_filesystem_store.py  (append)
@pytest.mark.asyncio
async def test_install_writes_skill_md(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    manifest, body = parse_skill_md(SAMPLE)
    installed = await store.install(
        source="folder", scope="user", user_id="u", body=body, manifest=manifest
    )
    assert installed.manifest.name == "alpha"
    assert (tmp_root / "user" / "alpha" / "SKILL.md").exists()


@pytest.mark.asyncio
async def test_install_rejects_duplicate(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    manifest, body = parse_skill_md(SAMPLE)
    with pytest.raises(FileExistsError):
        await store.install(
            source="folder", scope="user", user_id="u", body=body, manifest=manifest
        )
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py::test_install_writes_skill_md -v`
Expected: FAIL — `NotImplementedError`.

- [ ] **Step 3: Implement install**

```python
# packages/core/src/openlia/skills/filesystem_store.py  (replace install method)
async def install(
    self,
    source: str,
    *,
    scope: Scope,
    user_id: str | None,
    body: str,
    manifest: SkillManifest,
) -> InstalledSkill:
    target = self._scope_dir(scope) / manifest.name
    if target.exists():
        raise FileExistsError(
            f"Skill '{manifest.name}' already installed in scope '{scope}'"
        )
    target.mkdir(parents=True)
    (target / "SKILL.md").write_text(serialize_skill_md(manifest, body))
    (target / ".source").write_text(source + "\n")
    got = await self.get(manifest.name, scope=scope, user_id=user_id)
    if got is None:
        raise RuntimeError(
            f"install succeeded but get('{manifest.name}') returned None"
        )
    return got
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills/filesystem_store.py packages/core/tests/test_skills/test_filesystem_store.py
git commit -m "feat(skills): FilesystemSkillStore.install writes SKILL.md + source pin"
```

---

### Task 5: FilesystemSkillStore — uninstall and set_enabled

**Files:**
- Modify: `packages/core/src/openlia/skills/filesystem_store.py`
- Modify: `packages/core/tests/test_skills/test_filesystem_store.py`

- [ ] **Step 1: Append failing tests**

```python
# packages/core/tests/test_skills/test_filesystem_store.py  (append)
@pytest.mark.asyncio
async def test_uninstall_removes_directory(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    await store.uninstall("alpha", scope="user", user_id="u")
    assert not installed_alpha.exists()


@pytest.mark.asyncio
async def test_uninstall_missing_raises(tmp_root):
    store = FilesystemSkillStore(root=tmp_root)
    with pytest.raises(FileNotFoundError):
        await store.uninstall("ghost", scope="user", user_id="u")


@pytest.mark.asyncio
async def test_set_enabled_toggles_marker(tmp_root, installed_alpha):
    store = FilesystemSkillStore(root=tmp_root)
    await store.set_enabled("alpha", False, scope="user", user_id="u")
    assert (installed_alpha / ".disabled").exists()
    await store.set_enabled("alpha", True, scope="user", user_id="u")
    assert not (installed_alpha / ".disabled").exists()
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py -v`
Expected: 3 new tests FAIL.

- [ ] **Step 3: Implement**

```python
# packages/core/src/openlia/skills/filesystem_store.py  (replace stubs)
import shutil

async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None:
    target = self._scope_dir(scope) / skill_id
    if not target.exists():
        raise FileNotFoundError(f"Skill '{skill_id}' not installed in scope '{scope}'")
    shutil.rmtree(target)

async def set_enabled(
    self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
) -> None:
    target = self._scope_dir(scope) / skill_id
    if not target.exists():
        raise FileNotFoundError(f"Skill '{skill_id}' not installed in scope '{scope}'")
    marker = target / ".disabled"
    if enabled and marker.exists():
        marker.unlink()
    elif not enabled and not marker.exists():
        marker.touch()
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_filesystem_store.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills/filesystem_store.py packages/core/tests/test_skills/test_filesystem_store.py
git commit -m "feat(skills): FilesystemSkillStore.uninstall + set_enabled"
```

---

### Task 6: Alembic migration — `skills`, `skill_user_overrides`, extend `lia_guardrail_events`

**Files:**
- Create: `packages/server/src/openlia_server/db/models/skills.py`
- Modify: `packages/server/src/openlia_server/db/models/safety.py`
- Modify: `packages/server/src/openlia_server/db/models/register_all.py`
- Create: `packages/server/alembic/versions/<rev>_skills_tables.py` (use `uv run alembic revision --autogenerate -m "skills_tables"` then hand-edit to match below)
- Create: `packages/server/tests/db/test_skills_migration.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_skills_migration.py
from openlia_server.db.models import register_all  # noqa: F401
from openlia_server.db.base import Base


def test_skills_tables_registered():
    names = {t.name for t in Base.metadata.tables.values()}
    assert "skills" in names
    assert "skill_user_overrides" in names


def test_guardrail_event_has_payload_json():
    table = Base.metadata.tables["lia_guardrail_events"]
    assert "payload_json" in table.columns


def test_guardrail_event_session_id_nullable():
    table = Base.metadata.tables["lia_guardrail_events"]
    assert table.columns["session_id"].nullable is True
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/db/test_skills_migration.py -v`
Expected: 3 FAIL.

- [ ] **Step 3: Implement model + migration**

```python
# packages/server/src/openlia_server/db/models/skills.py
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from openlia_server.db.base import Base


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('system', 'user')",
            name="scope_enum",  # naming convention expands to ck_skills_scope_enum
        ),
        Index("idx_skills_scope_skill_id", "scope", "skill_id", unique=False),
        Index("idx_skills_user_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    frontmatter: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(256), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="0.0.0", nullable=False)


class SkillUserOverride(Base):
    __tablename__ = "skill_user_overrides"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    skill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
```

```python
# packages/server/src/openlia_server/db/models/safety.py  (modify LiaGuardrailEvent)
# 1) add JSON import
from sqlalchemy import CheckConstraint, DateTime, Index, JSON, String, Text, func

# 2) replace event_type CheckConstraint
CheckConstraint(
    "event_type IN ('persona_refusal', 'tripwire_flag', 'skill_installed', "
    "'skill_uninstalled', 'skill_enabled', 'skill_disabled', 'skill_loaded')",
    name="ck_lia_guardrail_events_event_type",
),

# 3) relax NOT NULLs and add payload_json
session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
department_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
category: Mapped[str | None] = mapped_column(String(64), nullable=True)
user_input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
response_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
```

```python
# packages/server/src/openlia_server/db/models/register_all.py  (append import)
from openlia_server.db.models import skills  # noqa: F401
```

Generate the migration:

```bash
uv run alembic -c packages/server/alembic.ini revision --autogenerate -m "skills_tables"
```

Then hand-edit the generated file to ensure:
- `skills` and `skill_user_overrides` are created.
- The `event_type` CHECK is dropped + recreated with the new tuple.
- The five columns (`session_id`, `department_id`, `category`, `user_input_hash`, `response_excerpt`) are altered to `nullable=True`.
- A `payload_json` column is added.
- `downgrade()` reverses each step.

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/db/test_skills_migration.py -v`
Expected: 3 PASS. Then sanity-check Alembic upgrade on a fresh SQLite DB:

Run: `OPENLIA_MODE=personal uv run alembic -c packages/server/alembic.ini upgrade head`
Expected: clean upgrade, no errors.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/skills.py packages/server/src/openlia_server/db/models/safety.py packages/server/src/openlia_server/db/models/register_all.py packages/server/alembic/versions packages/server/tests/db/test_skills_migration.py
git commit -m "feat(skills): db tables + extend lia_guardrail_events for skill events"
```

---

### Task 7: DatabaseSkillStore

**Files:**
- Create: `packages/server/src/openlia_server/skills/__init__.py` (empty)
- Create: `packages/server/src/openlia_server/skills/database_store.py`
- Create: `packages/server/tests/test_skills/__init__.py` (empty)
- Create: `packages/server/tests/test_skills/test_database_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_skills/test_database_store.py
import pytest

from openlia.skills import parse_skill_md
from openlia_server.skills.database_store import DatabaseSkillStore


SAMPLE = """---
name: beta
description: Beta skill.
version: "0.1.0"
departments: [secretary]
---

Body.
"""


@pytest.mark.asyncio
async def test_install_then_get(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(
        source="zip", scope="user", user_id="u1", body=body, manifest=manifest
    )
    got = await store.get("beta", scope="user", user_id="u1")
    assert got is not None
    assert got.manifest.name == "beta"
    assert got.body.strip() == "Body."


@pytest.mark.asyncio
async def test_install_then_uninstall(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(
        source="zip", scope="user", user_id="u1", body=body, manifest=manifest
    )
    await store.uninstall("beta", scope="user", user_id="u1")
    assert await store.get("beta", scope="user", user_id="u1") is None


@pytest.mark.asyncio
async def test_set_enabled_persists(db_session_factory):
    store = DatabaseSkillStore(session_factory=db_session_factory)
    manifest, body = parse_skill_md(SAMPLE)
    await store.install(
        source="zip", scope="user", user_id="u1", body=body, manifest=manifest
    )
    await store.set_enabled("beta", False, scope="user", user_id="u1")
    got = await store.get("beta", scope="user", user_id="u1")
    assert got is not None
    assert got.enabled is False
```

`db_session_factory` is the existing fixture from `packages/server/tests/conftest.py` (verify path with `grep -n db_session_factory packages/server/tests/conftest.py`). If it returns a context manager, adapt accordingly.

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/test_skills/test_database_store.py -v`
Expected: FAIL — `ModuleNotFoundError: openlia_server.skills.database_store`.

- [ ] **Step 3: Implement**

```python
# packages/server/src/openlia_server/skills/database_store.py
from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import and_, delete, select
from sqlalchemy.orm import Session as DBSession

from openlia.skills.store import Scope
from openlia.skills.types import InstalledSkill, SkillManifest
from openlia_server.db.models.skills import Skill, SkillUserOverride


class DatabaseSkillStore:
    """User-scope store for company mode (no shell access for users)."""

    def __init__(self, *, session_factory: Callable[[], DBSession]) -> None:
        self._sf = session_factory

    async def list(self, *, scope: Scope, user_id: str | None) -> list[InstalledSkill]:
        with self._sf() as db:
            stmt = select(Skill).where(Skill.scope == scope)
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            rows = db.execute(stmt).scalars().all()
            return [self._to_installed(r) for r in rows]

    async def get(
        self, skill_id: str, *, scope: Scope, user_id: str | None
    ) -> InstalledSkill | None:
        with self._sf() as db:
            stmt = select(Skill).where(
                and_(Skill.scope == scope, Skill.skill_id == skill_id)
            )
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            row = db.execute(stmt).scalar_one_or_none()
            return self._to_installed(row) if row else None

    async def install(
        self,
        source: str,
        *,
        scope: Scope,
        user_id: str | None,
        body: str,
        manifest: SkillManifest,
    ) -> InstalledSkill:
        with self._sf() as db:
            existing = db.execute(
                select(Skill).where(
                    and_(
                        Skill.scope == scope,
                        Skill.skill_id == manifest.name,
                        Skill.user_id == (user_id if scope == "user" else None),
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                raise FileExistsError(
                    f"Skill '{manifest.name}' already installed in scope '{scope}'"
                )
            row = Skill(
                id=str(uuid.uuid4()),
                skill_id=manifest.name,
                scope=scope,
                user_id=user_id if scope == "user" else None,
                frontmatter=manifest.model_dump(exclude_none=True),
                body=body,
                enabled=True,
                source=source,
                version=manifest.version,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_installed(row)

    async def uninstall(self, skill_id: str, *, scope: Scope, user_id: str | None) -> None:
        with self._sf() as db:
            stmt = delete(Skill).where(
                and_(Skill.scope == scope, Skill.skill_id == skill_id)
            )
            if scope == "user":
                stmt = stmt.where(Skill.user_id == user_id)
            res = db.execute(stmt)
            if res.rowcount == 0:
                raise FileNotFoundError(
                    f"Skill '{skill_id}' not installed in scope '{scope}'"
                )
            db.commit()

    async def set_enabled(
        self, skill_id: str, enabled: bool, *, scope: Scope, user_id: str | None
    ) -> None:
        with self._sf() as db:
            if scope == "system":
                # System scope: write a per-user override.
                if user_id is None:
                    raise ValueError("user_id required to override a system skill")
                ov = db.execute(
                    select(SkillUserOverride).where(
                        and_(
                            SkillUserOverride.user_id == user_id,
                            SkillUserOverride.skill_id == skill_id,
                        )
                    )
                ).scalar_one_or_none()
                if ov is None:
                    ov = SkillUserOverride(
                        user_id=user_id, skill_id=skill_id, enabled=enabled
                    )
                    db.add(ov)
                else:
                    ov.enabled = enabled
                db.commit()
                return
            row = db.execute(
                select(Skill).where(
                    and_(
                        Skill.scope == "user",
                        Skill.skill_id == skill_id,
                        Skill.user_id == user_id,
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise FileNotFoundError(skill_id)
            row.enabled = enabled
            db.commit()

    @staticmethod
    def _to_installed(row: Skill) -> InstalledSkill:
        manifest = SkillManifest(**row.frontmatter)
        return InstalledSkill(
            manifest=manifest,
            body=row.body,
            scope=row.scope,  # type: ignore[arg-type]
            user_id=row.user_id,
            enabled=row.enabled,
            installed_at=row.installed_at or datetime.now(UTC),
            source=row.source,
        )
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/test_skills/test_database_store.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/skills packages/server/tests/test_skills
git commit -m "feat(skills): DatabaseSkillStore (company-mode user scope)"
```

---

## Phase 2 — Registry

### Task 8: SkillRegistry — load + filter

**Files:**
- Create: `packages/core/src/openlia/skills/registry.py`
- Modify: `packages/core/src/openlia/skills/__init__.py`
- Create: `packages/core/tests/test_skills/test_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_skills/test_registry.py
import pytest

from openlia.skills import (
    FilesystemSkillStore,
    LayeredSkillStore,
    SkillRegistry,
    parse_skill_md,
)


SECRETARY_SKILL = """---
name: greet-skill
description: Says hi.
version: "1.0.0"
departments: [secretary]
---
Body.
"""

GLOBAL_SKILL = """---
name: tone
description: Plain English voice.
version: "1.0.0"
departments: ["*"]
---
Body.
"""


@pytest.fixture
def populated_root(tmp_path):
    (tmp_path / "user" / "greet-skill").mkdir(parents=True)
    (tmp_path / "user" / "greet-skill" / "SKILL.md").write_text(SECRETARY_SKILL)
    (tmp_path / "system" / "tone").mkdir(parents=True)
    (tmp_path / "system" / "tone" / "SKILL.md").write_text(GLOBAL_SKILL)
    return tmp_path


@pytest.mark.asyncio
async def test_visible_for_secretary_user(populated_root):
    fs = FilesystemSkillStore(root=populated_root)
    layered = LayeredSkillStore(system=fs, user=fs)
    reg = SkillRegistry(store=layered)
    await reg.refresh()
    visible = reg.visible(department_id="secretary", user_id="u1")
    names = [s.manifest.name for s in visible]
    assert "greet-skill" in names
    assert "tone" in names


@pytest.mark.asyncio
async def test_filtered_by_department(populated_root):
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh()
    visible = reg.visible(department_id="equity_research", user_id="u1")
    names = [s.manifest.name for s in visible]
    assert "greet-skill" not in names
    assert "tone" in names  # global


@pytest.mark.asyncio
async def test_disabled_skill_hidden(populated_root):
    (populated_root / "user" / "greet-skill" / ".disabled").touch()
    fs = FilesystemSkillStore(root=populated_root)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh()
    names = [s.manifest.name for s in reg.visible(department_id="secretary", user_id="u1")]
    assert "greet-skill" not in names
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_skills/test_registry.py -v`
Expected: 3 FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# packages/core/src/openlia/skills/registry.py
from __future__ import annotations

from openlia.skills.store import LayeredSkillStore
from openlia.skills.types import InstalledSkill


class SkillRegistry:
    """In-memory cache of installed skills with department + user filtering.

    Call `refresh()` after install/uninstall/toggle to rebuild the cache.
    `visible(...)` returns the subset for a given (department, user).
    """

    def __init__(self, *, store: LayeredSkillStore) -> None:
        self._store = store
        self._system: list[InstalledSkill] = []
        self._user: dict[str | None, list[InstalledSkill]] = {}

    async def refresh(self, *, user_ids: list[str | None] | None = None) -> None:
        self._system = await self._store.system.list(scope="system", user_id=None)
        self._user = {}
        for uid in user_ids or [None]:
            self._user[uid] = await self._store.user.list(scope="user", user_id=uid)

    async def refresh_user(self, user_id: str | None) -> None:
        self._user[user_id] = await self._store.user.list(
            scope="user", user_id=user_id
        )

    def visible(
        self, *, department_id: str, user_id: str | None
    ) -> list[InstalledSkill]:
        out: list[InstalledSkill] = []
        for s in self._system + self._user.get(user_id, []):
            if not s.enabled:
                continue
            depts = s.manifest.departments
            if "*" in depts or department_id in depts:
                out.append(s)
        return out

    def get(self, skill_id: str, *, user_id: str | None) -> InstalledSkill | None:
        for s in self._system + self._user.get(user_id, []):
            if s.manifest.name == skill_id:
                return s
        return None
```

```python
# packages/core/src/openlia/skills/__init__.py  (append)
from openlia.skills.registry import SkillRegistry

__all__ += ["SkillRegistry"]
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_skills/test_registry.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/skills/registry.py packages/core/src/openlia/skills/__init__.py packages/core/tests/test_skills/test_registry.py
git commit -m "feat(skills): SkillRegistry with dept + user filtering"
```

---

## Phase 3 — Prompt slot integration

### Task 9: `skills_menu.yaml.j2` partial

**Files:**
- Create: `packages/core/src/openlia/prompts/shared/skills_menu.yaml.j2`
- Create: `packages/core/tests/test_llm/test_runtime/test_skills_menu_partial.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_skills_menu_partial.py
from openlia.llm.runtime.prompts import PromptLoader


def test_menu_renders_when_skills_present(tmp_path):
    loader = PromptLoader()
    rendered = loader._env.get_template("shared/skills_menu.yaml.j2").render(
        skills_menu=[
            {"id": "alpha", "description": "Alpha skill.", "tools": []},
            {"id": "beta", "description": "Beta skill.", "tools": ["beta_tool"]},
        ]
    )
    assert "alpha" in rendered
    assert "Alpha skill." in rendered
    assert "beta_tool" in rendered


def test_menu_empty_when_no_skills():
    loader = PromptLoader()
    rendered = loader._env.get_template("shared/skills_menu.yaml.j2").render(
        skills_menu=[]
    )
    assert rendered.strip() == ""
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_skills_menu_partial.py -v`
Expected: 2 FAIL — `TemplateNotFound: shared/skills_menu.yaml.j2`.

- [ ] **Step 3: Create the partial**

```jinja
{# packages/core/src/openlia/prompts/shared/skills_menu.yaml.j2 #}
{%- if skills_menu and skills_menu|length > 0 -%}
## Skills available

The following installed skills are scoped to your current desk. Each line is `id: description`. Call `load_skill(skill_id)` to fetch the full playbook before relying on a skill's guidance; tools listed are always callable.

{% for s in skills_menu -%}
- **{{ s.id }}**: {{ s.description }}{% if s.tools %} *Tools:* {{ s.tools | join(', ') }}.{% endif %}
{% endfor %}
{%- endif -%}
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_skills_menu_partial.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/shared/skills_menu.yaml.j2 packages/core/tests/test_llm/test_runtime/test_skills_menu_partial.py
git commit -m "feat(skills): shared skills_menu.yaml.j2 prompt partial"
```

---

### Task 10: Include the partial in every department's chat + report slots

**Files:**
- Modify: each of `packages/core/src/openlia/prompts/{secretary,equity_research,earnings_update,morning_briefing,macro_research,retail_sentiment,retail_sentiment_insights,panic_thermometer}.yaml`
- Modify: `packages/core/src/openlia/llm/runtime/prompts.py` (auto-default `skills_menu=[]` when caller omits it, so existing render() callers don't break)
- Create: `packages/core/tests/test_llm/test_runtime/test_skills_menu_in_dept_prompts.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_skills_menu_in_dept_prompts.py
import pytest

from openlia.llm.runtime.prompts import PromptLoader


CHAT_DEPTS = ["secretary"]  # Plan 1 wires Secretary's chat slot; reports below.


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_chat_system_renders_with_no_skills(dept):
    loader = PromptLoader()
    rendered = loader.render(dept, "chat.system", skills_menu=[])
    assert "Skills available" not in rendered  # empty branch


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_chat_system_renders_with_skills(dept):
    loader = PromptLoader()
    rendered = loader.render(
        dept, "chat.system",
        skills_menu=[{"id": "alpha", "description": "X.", "tools": []}],
    )
    assert "Skills available" in rendered
    assert "alpha" in rendered


def test_existing_render_calls_still_work_without_skills_menu():
    loader = PromptLoader()
    # No skills_menu kwarg — must not raise StrictUndefined.
    rendered = loader.render("secretary", "chat.system")
    assert isinstance(rendered, str)
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_skills_menu_in_dept_prompts.py -v`
Expected: tests FAIL — `UndefinedError: 'skills_menu' is undefined` or include statements not present.

- [ ] **Step 3: Implement — partial includes + render default**

In every department YAML, add the include line right before the `output_discipline` include in each system slot. Example for `secretary.yaml`:

```yaml
chat:
  system: |
    {% include "shared/lia_identity.yaml.j2" %}

    ## Your desk right now
    ...

    {% include "shared/skills_menu.yaml.j2" %}

    {% include "shared/output_discipline.yaml.j2" %}
```

For department files that have report slots (`report.<kind>.system`), add the same include in the same position. For the four report-only departments (`equity_research`, `earnings_update`, `morning_briefing`, `macro_research`, `retail_sentiment`, `panic_thermometer`), include in each `report.*.system` slot.

In `prompts.py`, default `skills_menu` to `[]` when not provided:

```python
# packages/core/src/openlia/llm/runtime/prompts.py  (modify render)
merged = {
    "current_desk": DEPARTMENT_LABELS.get(department_id, department_id),
    "skills_menu": [],  # default; callers override
    **context,
}
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/ -v`
Expected: all green, including the new file plus existing prompt tests.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/*.yaml packages/core/src/openlia/llm/runtime/prompts.py packages/core/tests/test_llm/test_runtime/test_skills_menu_in_dept_prompts.py
git commit -m "feat(skills): include skills_menu partial in all dept chat + report slots"
```

---

## Phase 4 — `load_skill` meta-tool

### Task 11: `ChatSkillLoaded` SSE event + `load_skill` schema

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/events.py`
- Modify: `packages/core/src/openlia/llm/runtime/tools.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_load_skill_tool.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_load_skill_tool.py
from openlia.llm.runtime.events import ChatSkillLoaded
from openlia.llm.runtime.tools import LOAD_SKILL_SCHEMA


def test_chat_skill_loaded_to_wire():
    e = ChatSkillLoaded(message_id="m1", skill_id="alpha", display_name="Alpha")
    wire = {"type": e.TYPE, **{k: v for k, v in vars(e).items()}}
    assert wire["type"] == "chat.skill_loaded"
    assert wire["skill_id"] == "alpha"


def test_load_skill_schema_shape():
    assert LOAD_SKILL_SCHEMA.name == "load_skill"
    assert "skill_id" in LOAD_SKILL_SCHEMA.parameters["properties"]
    assert LOAD_SKILL_SCHEMA.parameters["required"] == ["skill_id"]
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_load_skill_tool.py -v`
Expected: FAIL — `ImportError: cannot import name 'ChatSkillLoaded'`.

- [ ] **Step 3: Implement**

```python
# packages/core/src/openlia/llm/runtime/events.py  (append)
@dataclass(frozen=True)
class ChatSkillLoaded:
    TYPE = "chat.skill_loaded"
    message_id: str
    skill_id: str
    display_name: str
```

```python
# packages/core/src/openlia/llm/runtime/tools.py  (append, near _FIND_MORE_DATA_SCHEMA)
LOAD_SKILL_SCHEMA = ToolSchema(
    name="load_skill",
    description=(
        "Load the full instructions/playbook for an installed skill. Returns the "
        "skill's markdown body. Call this when the user's question matches a skill "
        "from the menu and you want its detailed guidance before answering."
    ),
    parameters={
        "type": "object",
        "properties": {
            "skill_id": {"type": "string", "description": "Id from the skill menu."}
        },
        "required": ["skill_id"],
        "additionalProperties": False,
    },
)
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_load_skill_tool.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/events.py packages/core/src/openlia/llm/runtime/tools.py packages/core/tests/test_llm/test_runtime/test_load_skill_tool.py
git commit -m "feat(skills): ChatSkillLoaded event + load_skill ToolSchema"
```

---

### Task 12: Wire `load_skill` into the chat dispatcher

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/chat.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_load_skill_dispatch.py`

Read `chat.py` and `tools.py` first to find the existing dispatch site (look for the `dispatch` or `dispatch_many` method that already routes `find_more_data`). The `load_skill` handler is added next to it. The chat runtime needs a `SkillRegistry` injected at construction; thread it via the existing chat-runtime config dataclass.

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_load_skill_dispatch.py
import pytest

from openlia.llm.runtime.tools import dispatch_load_skill
from openlia.skills import (
    FilesystemSkillStore,
    LayeredSkillStore,
    SkillRegistry,
)


SAMPLE = """---
name: alpha
description: A.
version: "1.0.0"
departments: [secretary]
---

Skill body content.
"""


@pytest.mark.asyncio
async def test_dispatch_returns_body(tmp_path):
    (tmp_path / "user" / "alpha").mkdir(parents=True)
    (tmp_path / "user" / "alpha" / "SKILL.md").write_text(SAMPLE)
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    result = await dispatch_load_skill(reg, user_id="u1", skill_id="alpha", call_id="c1")
    assert result.ok
    assert "Skill body content" in result.payload["body"]


@pytest.mark.asyncio
async def test_dispatch_unknown_skill_returns_error(tmp_path):
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    result = await dispatch_load_skill(reg, user_id="u1", skill_id="ghost", call_id="c1")
    assert not result.ok
    assert "ghost" in result.summary
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_load_skill_dispatch.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# packages/core/src/openlia/llm/runtime/tools.py  (append)
async def dispatch_load_skill(
    registry,  # type: SkillRegistry — typed via TYPE_CHECKING to avoid circular import
    *,
    user_id: str | None,
    skill_id: str,
    call_id: str,
) -> ToolCallResult:
    skill = registry.get(skill_id, user_id=user_id)
    if skill is None:
        return ToolCallResult(
            call_id=call_id,
            ok=False,
            summary=f"Unknown skill: {skill_id}",
            payload={"error": f"Unknown skill: {skill_id}"},
        )
    return ToolCallResult(
        call_id=call_id,
        ok=True,
        summary=f"Loaded skill: {skill.manifest.display_name or skill.manifest.name}",
        payload={"body": skill.body, "skill_id": skill.manifest.name},
        structured={
            "skill_id": skill.manifest.name,
            "display_name": skill.manifest.display_name or skill.manifest.name,
        },
    )
```

In `chat.py`, identify the tool-dispatch function (search for `find_more_data` and `dispatch_many`). Add a branch for `load_skill`:

```python
# packages/core/src/openlia/llm/runtime/chat.py  (in the dispatch loop)
if call.name == "load_skill":
    args = json.loads(call.arguments) if isinstance(call.arguments, str) else call.arguments
    result = await dispatch_load_skill(
        config.skill_registry,
        user_id=config.user_id,
        skill_id=args["skill_id"],
        call_id=call.call_id,
    )
    if result.ok and result.structured:
        await emit(ChatSkillLoaded(
            message_id=message_id,
            skill_id=result.structured["skill_id"],
            display_name=result.structured["display_name"],
        ))
    yield result
    continue
```

The chat config dataclass must gain a `skill_registry: SkillRegistry` field — set to `None` is **not** acceptable (fail-fast principle); construct one in tests with an empty filesystem root.

The chat tool array is built in `chat.py` near where `_WEB_SEARCH_SCHEMA` and `_FIND_MORE_DATA_SCHEMA` are appended — add `LOAD_SKILL_SCHEMA` only when `len(skill_registry.visible(...)) > 0` (else it would be a no-op tool the LLM might call with garbage).

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/ -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime packages/core/tests/test_llm/test_runtime/test_load_skill_dispatch.py
git commit -m "feat(skills): wire load_skill into chat dispatcher; emit ChatSkillLoaded"
```

---

### Task 13: Pass `skills_menu` context into chat + report renderers

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/chat.py`
- Modify: `packages/core/src/openlia/llm/runtime/report.py`
- Create: `packages/core/tests/test_llm/test_runtime/test_skills_menu_threading.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/test_llm/test_runtime/test_skills_menu_threading.py
import pytest

from openlia.llm.runtime.chat import build_chat_system_prompt
from openlia.skills import (
    FilesystemSkillStore,
    LayeredSkillStore,
    SkillRegistry,
)


SAMPLE = """---
name: alpha
description: Alpha skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


@pytest.mark.asyncio
async def test_secretary_prompt_includes_alpha(tmp_path):
    (tmp_path / "user" / "alpha").mkdir(parents=True)
    (tmp_path / "user" / "alpha" / "SKILL.md").write_text(SAMPLE)
    fs = FilesystemSkillStore(root=tmp_path)
    reg = SkillRegistry(store=LayeredSkillStore(system=fs, user=fs))
    await reg.refresh(user_ids=["u1"])
    prompt = build_chat_system_prompt(
        department_id="secretary", user_id="u1", registry=reg
    )
    assert "alpha" in prompt
    assert "Alpha skill." in prompt
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/test_skills_menu_threading.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_chat_system_prompt'` (or whatever the existing function is named — read `chat.py` to confirm; if a function already exists for assembling the system prompt, modify that one and update the test import accordingly).

- [ ] **Step 3: Implement**

Locate the chat-runtime entry point that calls `PromptLoader.render(department_id, "chat.system", ...)`. Modify it to take a `registry: SkillRegistry` and `user_id` and pass `skills_menu=...`:

```python
# packages/core/src/openlia/llm/runtime/chat.py  (modify the prompt-build site)
def build_chat_system_prompt(
    *,
    department_id: str,
    user_id: str | None,
    registry,  # SkillRegistry
    loader: PromptLoader | None = None,
) -> str:
    loader = loader or PromptLoader()
    visible = registry.visible(department_id=department_id, user_id=user_id)
    skills_menu = [
        {
            "id": s.manifest.name,
            "description": s.manifest.description,
            "tools": [
                f"skill__{s.manifest.name.replace('-', '_')}__{t['name']}"
                for t in (s.manifest.tools or [])
            ],
        }
        for s in visible
    ]
    return loader.render(department_id, "chat.system", skills_menu=skills_menu)
```

Same wiring in `report.py` for the report system slot, but no event-emission needed (reports don't have an SSE stream that surfaces tool-style cards).

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/core/tests/test_llm/test_runtime/ -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/llm/runtime/chat.py packages/core/src/openlia/llm/runtime/report.py packages/core/tests/test_llm/test_runtime/test_skills_menu_threading.py
git commit -m "feat(skills): thread skills_menu context into chat + report renderers"
```

---

## Phase 5 — Audit logging

### Task 14: Skill audit writer

**Files:**
- Create: `packages/server/src/openlia_server/services/skill_audit.py`
- Create: `packages/server/tests/test_skills/test_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_skills/test_audit.py
import pytest

from sqlalchemy import select

from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.services.skill_audit import (
    record_skill_installed,
    record_skill_loaded,
    record_skill_uninstalled,
    record_skill_toggled,
)


@pytest.mark.asyncio
async def test_record_install_writes_event(db_session_factory):
    record_skill_installed(
        db_session_factory,
        skill_id="alpha", scope="user", user_id="u1",
        source="folder", version="1.0.0",
    )
    with db_session_factory() as db:
        rows = db.execute(select(LiaGuardrailEvent)).scalars().all()
        assert len(rows) == 1
        assert rows[0].event_type == "skill_installed"
        assert rows[0].payload_json["skill_id"] == "alpha"


@pytest.mark.asyncio
async def test_record_load_writes_event(db_session_factory):
    record_skill_loaded(
        db_session_factory,
        skill_id="alpha", session_id="s1", user_id="u1", department_id="secretary",
    )
    with db_session_factory() as db:
        rows = db.execute(select(LiaGuardrailEvent)).scalars().all()
        assert rows[0].event_type == "skill_loaded"
        assert rows[0].session_id == "s1"
        assert rows[0].department_id == "secretary"
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/test_skills/test_audit.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# packages/server/src/openlia_server/services/skill_audit.py
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.safety import LiaGuardrailEvent


def _write(
    sf: Callable[[], DBSession], *, event_type: str,
    session_id: str | None = None,
    user_id: str | None = None,
    department_id: str | None = None,
    payload: dict[str, Any],
) -> None:
    with sf() as db:
        db.add(LiaGuardrailEvent(
            id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            department_id=department_id,
            event_type=event_type,
            category=payload.get("skill_id", "unknown"),
            action_taken="logged",
            user_input_hash=None,
            response_excerpt=None,
            payload_json=payload,
        ))
        db.commit()


def record_skill_installed(sf, *, skill_id, scope, user_id, source, version):
    _write(sf, event_type="skill_installed", user_id=user_id,
           payload={"skill_id": skill_id, "scope": scope, "source": source, "version": version})


def record_skill_uninstalled(sf, *, skill_id, scope, user_id):
    _write(sf, event_type="skill_uninstalled", user_id=user_id,
           payload={"skill_id": skill_id, "scope": scope})


def record_skill_toggled(sf, *, skill_id, scope, user_id, enabled):
    et = "skill_enabled" if enabled else "skill_disabled"
    _write(sf, event_type=et, user_id=user_id,
           payload={"skill_id": skill_id, "scope": scope})


def record_skill_loaded(sf, *, skill_id, session_id, user_id, department_id):
    _write(sf, event_type="skill_loaded",
           session_id=session_id, user_id=user_id, department_id=department_id,
           payload={"skill_id": skill_id})
```

The existing `LiaGuardrailEvent.action_taken` CHECK still constrains values to `('replaced', 'warned', 'logged')`; for skill events we use `'logged'`.

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/test_skills/test_audit.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/skill_audit.py packages/server/tests/test_skills/test_audit.py
git commit -m "feat(skills): audit writers reusing lia_guardrail_events"
```

---

## Phase 6 — Backend routes

### Task 15: Skill installer service (folder rescan + git URL + zip upload)

**Files:**
- Create: `packages/server/src/openlia_server/services/skill_installer.py`
- Create: `packages/server/tests/test_skills/test_installer.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_skills/test_installer.py
import io
import zipfile

import pytest

from openlia_server.services.skill_installer import (
    install_from_zip,
    install_from_folder,
)


SAMPLE = """---
name: zipped
description: Zip skill.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


def _make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("zipped/SKILL.md", SAMPLE)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_install_from_zip_writes_skill(tmp_path):
    fs_store, _ = _make_stores(tmp_path)
    installed = await install_from_zip(
        fs_store, scope="user", user_id="u1", zip_bytes=_make_zip()
    )
    assert installed.manifest.name == "zipped"
    got = await fs_store.get("zipped", scope="user", user_id="u1")
    assert got is not None


@pytest.mark.asyncio
async def test_install_from_folder_path(tmp_path):
    src = tmp_path / "src" / "alpha"
    src.mkdir(parents=True)
    (src / "SKILL.md").write_text(SAMPLE.replace("zipped", "alpha"))
    fs_store, _ = _make_stores(tmp_path)
    installed = await install_from_folder(
        fs_store, scope="user", user_id="u1", folder_path=src
    )
    assert installed.manifest.name == "alpha"


def _make_stores(tmp_path):
    from openlia.skills import FilesystemSkillStore
    return FilesystemSkillStore(root=tmp_path / "store"), tmp_path
```

(Git-URL install is exercised via integration test in Task 16; here we keep the unit test scope to zip + folder.)

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/test_skills/test_installer.py -v`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implement**

```python
# packages/server/src/openlia_server/services/skill_installer.py
from __future__ import annotations

import asyncio
import io
import shutil
import tempfile
import zipfile
from pathlib import Path

from openlia.skills import (
    FilesystemSkillStore,
    InstalledSkill,
    SkillStore,
    parse_skill_md,
)


_MAX_ZIP_BYTES = 5 * 1024 * 1024


async def install_from_folder(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    folder_path: Path,
) -> InstalledSkill:
    md_path = folder_path / "SKILL.md"
    if not md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {folder_path}")
    manifest, body = parse_skill_md(md_path.read_text())
    return await store.install(
        source=f"folder:{folder_path}",
        scope=scope, user_id=user_id, body=body, manifest=manifest,
    )


async def install_from_zip(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    zip_bytes: bytes,
) -> InstalledSkill:
    if len(zip_bytes) > _MAX_ZIP_BYTES:
        raise ValueError("zip exceeds 5 MB cap")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            z.extractall(tmp_path)
        # Find a SKILL.md anywhere in the archive.
        md = next(tmp_path.rglob("SKILL.md"), None)
        if md is None:
            raise FileNotFoundError("zip contains no SKILL.md")
        return await install_from_folder(
            store, scope=scope, user_id=user_id, folder_path=md.parent
        )


async def install_from_git(
    store: SkillStore,
    *,
    scope: str,
    user_id: str | None,
    git_url: str,
    ref: str | None = None,
) -> InstalledSkill:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "clone"
        cmd = ["git", "clone", "--depth", "1"]
        if ref:
            cmd += ["--branch", ref]
        cmd += [git_url, str(tmp_path)]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(
                f"git clone failed (exit {proc.returncode}): {stderr.decode().strip()}"
            )
        md = next(tmp_path.rglob("SKILL.md"), None)
        if md is None:
            raise FileNotFoundError(f"{git_url} contains no SKILL.md")
        manifest, body = parse_skill_md(md.read_text())
        return await store.install(
            source=f"git:{git_url}" + (f"#{ref}" if ref else ""),
            scope=scope, user_id=user_id, body=body, manifest=manifest,
        )
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/test_skills/test_installer.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/skill_installer.py packages/server/tests/test_skills/test_installer.py
git commit -m "feat(skills): installer service (folder, zip, git)"
```

---

### Task 16: User-facing skills router

**Files:**
- Create: `packages/server/src/openlia_server/routes/skills.py`
- Modify: `packages/server/src/openlia_server/app.py` — mount router; construct `LayeredSkillStore` + `SkillRegistry` and pass through DI
- Create: `packages/server/tests/test_skills/test_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_skills/test_routes.py
import io
import zipfile

import pytest


SAMPLE = """---
name: viaapi
description: Installed via API.
version: "1.0.0"
departments: [secretary]
---

Body.
"""


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("viaapi/SKILL.md", SAMPLE)
    return buf.getvalue()


def test_install_zip_lists_and_disables(client_authed):
    # Install
    files = {"file": ("viaapi.zip", _zip(), "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200, r.text
    assert r.json()["skill_id"] == "viaapi"

    # List
    r = client_authed.get("/api/skills")
    assert r.status_code == 200
    assert any(s["skill_id"] == "viaapi" for s in r.json()["items"])

    # Toggle off
    r = client_authed.patch("/api/skills/viaapi", json={"enabled": False})
    assert r.status_code == 200
    listing = client_authed.get("/api/skills").json()["items"]
    assert next(s for s in listing if s["skill_id"] == "viaapi")["enabled"] is False

    # Body
    r = client_authed.get("/api/skills/viaapi/body")
    assert r.status_code == 200
    assert "Body." in r.json()["body"]

    # Uninstall
    r = client_authed.delete("/api/skills/viaapi")
    assert r.status_code == 204


def test_install_rejects_bad_skill_md(client_authed):
    files = {"file": ("bad.zip", b"not a zip", "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 400
```

`client_authed` is the existing test client fixture (verify path with `grep -rn 'client_authed\|TestClient' packages/server/tests/conftest.py`). If the fixture name differs, adapt.

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/test_skills/test_routes.py -v`
Expected: FAIL — `404 Not Found` on `/api/skills`.

- [ ] **Step 3: Implement**

```python
# packages/server/src/openlia_server/routes/skills.py
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry
from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.skill_audit import (
    record_skill_installed,
    record_skill_uninstalled,
    record_skill_toggled,
)
from openlia_server.services.skill_installer import (
    install_from_folder,
    install_from_git,
    install_from_zip,
)


class TogglePatch(BaseModel):
    enabled: bool


def build_skills_router(
    *,
    db_session_factory: Callable[[], DBSession],
    store: LayeredSkillStore,
    registry: SkillRegistry,
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/skills", tags=["skills"])

    @router.get("")
    async def list_skills(user: User = require_auth):
        sys_skills = await store.system.list(scope="system", user_id=None)
        usr_skills = await store.user.list(scope="user", user_id=user.id)
        return {
            "items": [
                {
                    "skill_id": s.manifest.name,
                    "display_name": s.manifest.display_name or s.manifest.name,
                    "description": s.manifest.description,
                    "version": s.manifest.version,
                    "departments": s.manifest.departments,
                    "scope": s.scope,
                    "enabled": s.enabled,
                    "source": s.source,
                    "installed_at": s.installed_at.isoformat(),
                }
                for s in [*sys_skills, *usr_skills]
            ]
        }

    @router.post("/install")
    async def install(
        scope: str = Form("user"),
        source_type: str = Form(...),
        git_url: str | None = Form(None),
        ref: str | None = Form(None),
        folder_path: str | None = Form(None),
        file: UploadFile | None = File(None),
        user: User = require_auth,
    ):
        if scope == "system" and not getattr(user, "is_admin", False):
            raise HTTPException(403, "system-scope install requires admin")
        target = store.for_scope(scope)  # type: ignore[arg-type]
        try:
            if source_type == "zip":
                if file is None:
                    raise HTTPException(400, "missing zip file")
                installed = await install_from_zip(
                    target, scope=scope, user_id=user.id, zip_bytes=await file.read()
                )
            elif source_type == "git":
                if not git_url:
                    raise HTTPException(400, "missing git_url")
                installed = await install_from_git(
                    target, scope=scope, user_id=user.id, git_url=git_url, ref=ref
                )
            elif source_type == "folder":
                from pathlib import Path
                if not folder_path:
                    raise HTTPException(400, "missing folder_path")
                installed = await install_from_folder(
                    target, scope=scope, user_id=user.id, folder_path=Path(folder_path)
                )
            else:
                raise HTTPException(400, f"unknown source_type: {source_type}")
        except (ValueError, FileNotFoundError, RuntimeError) as e:
            raise HTTPException(400, str(e)) from None
        record_skill_installed(
            db_session_factory,
            skill_id=installed.manifest.name,
            scope=scope, user_id=user.id,
            source=installed.source, version=installed.manifest.version,
        )
        await registry.refresh_user(user.id)
        return {"skill_id": installed.manifest.name, "scope": scope}

    @router.delete("/{skill_id}", status_code=204)
    async def uninstall(skill_id: str, user: User = require_auth):
        target = store.user
        try:
            await target.uninstall(skill_id, scope="user", user_id=user.id)
        except FileNotFoundError:
            raise HTTPException(404, "skill not installed") from None
        record_skill_uninstalled(
            db_session_factory, skill_id=skill_id, scope="user", user_id=user.id
        )
        await registry.refresh_user(user.id)
        return None

    @router.patch("/{skill_id}")
    async def toggle(skill_id: str, body: TogglePatch, user: User = require_auth):
        # Try user scope first, fall back to system override.
        try:
            await store.user.set_enabled(
                skill_id, body.enabled, scope="user", user_id=user.id
            )
            scope = "user"
        except FileNotFoundError:
            await store.system.set_enabled(
                skill_id, body.enabled, scope="system", user_id=user.id
            )
            scope = "system"
        record_skill_toggled(
            db_session_factory, skill_id=skill_id, scope=scope, user_id=user.id,
            enabled=body.enabled,
        )
        await registry.refresh_user(user.id)
        return {"skill_id": skill_id, "enabled": body.enabled, "scope": scope}

    @router.get("/{skill_id}/body")
    async def body_for(skill_id: str, user: User = require_auth):
        sys_s = await store.system.get(skill_id, scope="system", user_id=None)
        usr_s = await store.user.get(skill_id, scope="user", user_id=user.id)
        s = usr_s or sys_s
        if s is None:
            raise HTTPException(404, "skill not found")
        return {"skill_id": skill_id, "body": s.body}

    return router
```

In `app.py`, instantiate stores+registry once at startup and inject into the router builder. Use the existing config-derived skills root (e.g. `<config_dir>/skills/`) for the system store and the FS store in personal mode; use `DatabaseSkillStore` for user scope in company mode.

```python
# packages/server/src/openlia_server/app.py  (sketch — adapt to actual factory)
from pathlib import Path
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry
from openlia_server.skills.database_store import DatabaseSkillStore
from openlia_server.routes.skills import build_skills_router

skills_root = Path(config.config_dir) / "skills"
skills_root.mkdir(parents=True, exist_ok=True)
fs_store = FilesystemSkillStore(root=skills_root)
user_store = (
    fs_store if mode == "personal"
    else DatabaseSkillStore(session_factory=db_session_factory)
)
skills_layered = LayeredSkillStore(system=fs_store, user=user_store)
skills_registry = SkillRegistry(store=skills_layered)
await skills_registry.refresh()  # NOTE: app startup is async-friendly via lifespan
app.include_router(
    build_skills_router(
        db_session_factory=db_session_factory,
        store=skills_layered,
        registry=skills_registry,
        mode=mode,
    ),
    prefix="/api",
)
```

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/test_skills/test_routes.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/skills.py packages/server/src/openlia_server/app.py packages/server/tests/test_skills/test_routes.py
git commit -m "feat(skills): /api/skills router (list/install/delete/toggle/body)"
```

---

### Task 17: Admin skills router

**Files:**
- Create: `packages/server/src/openlia_server/routes/admin_skills.py`
- Modify: `packages/server/src/openlia_server/app.py`
- Create: `packages/server/tests/test_skills/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/test_skills/test_admin_routes.py
def test_admin_lists_all_skills(admin_client):
    r = admin_client.get("/api/admin/skills")
    assert r.status_code == 200
    assert "items" in r.json()


def test_non_admin_blocked(client_authed):
    r = client_authed.get("/api/admin/skills")
    assert r.status_code == 403


def test_admin_audit_log_filter(admin_client):
    r = admin_client.get("/api/admin/skills/audit?since_days=7")
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)
```

- [ ] **Step 2: Run, verify failure**

Run: `uv run pytest packages/server/tests/test_skills/test_admin_routes.py -v`
Expected: FAIL — `404`.

- [ ] **Step 3: Implement**

```python
# packages/server/src/openlia_server/routes/admin_skills.py
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia.skills import LayeredSkillStore, SkillRegistry
from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.middleware.auth import build_require_auth


_SKILL_EVENT_TYPES = (
    "skill_installed", "skill_uninstalled", "skill_enabled",
    "skill_disabled", "skill_loaded",
)


def build_admin_skills_router(
    *,
    db_session_factory: Callable[[], DBSession],
    store: LayeredSkillStore,
    registry: SkillRegistry,
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/admin/skills", tags=["skills-admin"])

    def _admin_only(user: User) -> User:
        if not getattr(user, "is_admin", False):
            raise HTTPException(403, "admin only")
        return user

    @router.get("")
    async def list_all(user: User = require_auth):
        _admin_only(user)
        sys_skills = await store.system.list(scope="system", user_id=None)
        return {
            "items": [
                {
                    "skill_id": s.manifest.name,
                    "scope": s.scope,
                    "user_id": s.user_id,
                    "version": s.manifest.version,
                    "enabled": s.enabled,
                    "installed_at": s.installed_at.isoformat(),
                }
                for s in sys_skills
            ]
        }

    @router.get("/audit")
    def audit(
        since_days: int = Query(7, ge=1, le=365),
        skill_id: str | None = None,
        limit: int = Query(200, ge=1, le=1000),
        offset: int = Query(0, ge=0),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ):
        _admin_only(user)
        cutoff = datetime.now(UTC) - timedelta(days=since_days)
        stmt = (
            select(LiaGuardrailEvent)
            .where(LiaGuardrailEvent.event_type.in_(_SKILL_EVENT_TYPES))
            .where(LiaGuardrailEvent.created_at >= cutoff)
            .order_by(LiaGuardrailEvent.created_at.desc())
            .limit(limit).offset(offset)
        )
        if skill_id:
            stmt = stmt.where(LiaGuardrailEvent.category == skill_id)
        rows = db.execute(stmt).scalars().all()
        return {
            "items": [
                {
                    "id": r.id,
                    "created_at": r.created_at.isoformat(),
                    "user_id": r.user_id,
                    "session_id": r.session_id,
                    "department_id": r.department_id,
                    "event_type": r.event_type,
                    "skill_id": r.category,
                    "payload": r.payload_json,
                }
                for r in rows
            ]
        }

    return router
```

Mount the router in `app.py` at prefix `/api`.

- [ ] **Step 4: Run, verify pass**

Run: `uv run pytest packages/server/tests/test_skills/test_admin_routes.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/routes/admin_skills.py packages/server/src/openlia_server/app.py packages/server/tests/test_skills/test_admin_routes.py
git commit -m "feat(skills): /api/admin/skills router (list + audit)"
```

---

## Phase 7 — Frontend

### Task 18: Skills API client

**Files:**
- Create: `frontend/src/api/skills.ts`
- Create: `frontend/src/api/__tests__/skills.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/src/api/__tests__/skills.test.ts
import { describe, expect, it, vi } from 'vitest';
import { listSkills, toggleSkill } from '../skills';

describe('skills api', () => {
  it('listSkills hits GET /api/skills', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    await listSkills();
    expect(fetch).toHaveBeenCalledWith('/api/skills', expect.any(Object));
  });

  it('toggleSkill PATCHes with enabled flag', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    await toggleSkill('alpha', false);
    const call = fetch.mock.calls[0];
    expect(call[0]).toBe('/api/skills/alpha');
    expect(call[1].method).toBe('PATCH');
    expect(JSON.parse(call[1].body)).toEqual({ enabled: false });
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `cd frontend && npm test -- src/api/__tests__/skills.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```typescript
// frontend/src/api/skills.ts
export interface SkillSummary {
  skill_id: string;
  display_name: string;
  description: string;
  version: string;
  departments: string[];
  scope: 'system' | 'user';
  enabled: boolean;
  source: string;
  installed_at: string;
}

export async function listSkills(): Promise<SkillSummary[]> {
  const res = await fetch('/api/skills', { credentials: 'include' });
  if (!res.ok) throw new Error(`listSkills: ${res.status}`);
  const json = await res.json();
  return json.items as SkillSummary[];
}

export async function toggleSkill(skillId: string, enabled: boolean) {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: 'PATCH',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error(`toggleSkill: ${res.status}`);
  return res.json();
}

export async function uninstallSkill(skillId: string) {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!res.ok && res.status !== 204) throw new Error(`uninstallSkill: ${res.status}`);
}

export async function fetchSkillBody(skillId: string): Promise<string> {
  const res = await fetch(`/api/skills/${encodeURIComponent(skillId)}/body`, {
    credentials: 'include',
  });
  if (!res.ok) throw new Error(`fetchSkillBody: ${res.status}`);
  const json = await res.json();
  return json.body as string;
}

export async function installSkillFromGit(gitUrl: string, ref?: string) {
  const fd = new FormData();
  fd.append('source_type', 'git');
  fd.append('scope', 'user');
  fd.append('git_url', gitUrl);
  if (ref) fd.append('ref', ref);
  const res = await fetch('/api/skills/install', {
    method: 'POST', credentials: 'include', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function installSkillFromZip(file: File) {
  const fd = new FormData();
  fd.append('source_type', 'zip');
  fd.append('scope', 'user');
  fd.append('file', file);
  const res = await fetch('/api/skills/install', {
    method: 'POST', credentials: 'include', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test -- src/api/__tests__/skills.test.ts`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/skills.ts frontend/src/api/__tests__/skills.test.ts
git commit -m "feat(skills/fe): typed API client"
```

---

### Task 19: `SkillsSection` and `SkillRow` components

**Files:**
- Create: `frontend/src/components/settings/sections/SkillsSection.tsx`
- Create: `frontend/src/components/settings/skills/SkillRow.tsx`
- Create: `frontend/src/components/settings/skills/__tests__/SkillsSection.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/skills/__tests__/SkillsSection.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { SkillsSection } from '../../sections/SkillsSection';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
    new Response(JSON.stringify({
      items: [{
        skill_id: 'alpha', display_name: 'Alpha', description: 'd',
        version: '1', departments: ['secretary'], scope: 'user',
        enabled: true, source: 'folder', installed_at: '2026-05-03T00:00:00Z',
      }],
    }), { status: 200 }),
  ));
});

describe('SkillsSection', () => {
  it('renders installed skills', async () => {
    render(<SkillsSection />);
    await waitFor(() => expect(screen.getByText('Alpha')).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `cd frontend && npm test -- src/components/settings/skills/__tests__/SkillsSection.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/settings/sections/SkillsSection.tsx
import { useEffect, useState } from 'react';
import { listSkills, type SkillSummary } from '../../../api/skills';
import { SkillRow } from '../skills/SkillRow';
import { InstallSkillModal } from '../skills/InstallSkillModal';

export function SkillsSection(): JSX.Element {
  const [items, setItems] = useState<SkillSummary[] | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const refresh = () => listSkills().then(setItems);
  useEffect(() => { void refresh(); }, []);
  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Skills</h2>
        <button
          className="px-3 py-1 bg-accent text-white rounded"
          onClick={() => setShowInstall(true)}
        >
          Install skill
        </button>
      </div>
      {items === null ? <p>Loading…</p>
        : items.length === 0
          ? <p className="text-text-secondary">No skills installed.</p>
          : <ul className="divide-y">
              {items.map(s => (
                <SkillRow key={`${s.scope}:${s.skill_id}`} skill={s} onChange={refresh} />
              ))}
            </ul>}
      {showInstall && (
        <InstallSkillModal
          onClose={() => setShowInstall(false)}
          onInstalled={() => { setShowInstall(false); void refresh(); }}
        />
      )}
    </div>
  );
}
```

```tsx
// frontend/src/components/settings/skills/SkillRow.tsx
import { useState } from 'react';
import { toggleSkill, uninstallSkill, type SkillSummary } from '../../../api/skills';
import { SkillDetailPanel } from './SkillDetailPanel';

export function SkillRow({
  skill, onChange,
}: { skill: SkillSummary; onChange: () => void }): JSX.Element {
  const [open, setOpen] = useState(false);
  const onToggle = async () => {
    await toggleSkill(skill.skill_id, !skill.enabled);
    onChange();
  };
  const onUninstall = async () => {
    if (!confirm(`Uninstall "${skill.display_name}"?`)) return;
    await uninstallSkill(skill.skill_id);
    onChange();
  };
  return (
    <li className="py-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-medium">{skill.display_name}</div>
          <div className="text-sm text-text-secondary">{skill.description}</div>
          <div className="text-xs text-text-tertiary mt-1">
            v{skill.version} · {skill.scope} · {skill.departments.join(', ')}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={skill.enabled} onChange={onToggle} />
            Enabled
          </label>
          <button onClick={() => setOpen(o => !o)} className="text-sm underline">
            {open ? 'Hide' : 'Details'}
          </button>
          {skill.scope === 'user' && (
            <button onClick={onUninstall} className="text-sm text-red-600 underline">
              Uninstall
            </button>
          )}
        </div>
      </div>
      {open && <SkillDetailPanel skillId={skill.skill_id} />}
    </li>
  );
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test -- src/components/settings/skills/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/SkillsSection.tsx frontend/src/components/settings/skills/SkillRow.tsx frontend/src/components/settings/skills/__tests__/SkillsSection.test.tsx
git commit -m "feat(skills/fe): SkillsSection + SkillRow components"
```

---

### Task 20: `SkillDetailPanel` and `InstallSkillModal`

**Files:**
- Create: `frontend/src/components/settings/skills/SkillDetailPanel.tsx`
- Create: `frontend/src/components/settings/skills/InstallSkillModal.tsx`
- Create: `frontend/src/components/settings/skills/__tests__/InstallSkillModal.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/skills/__tests__/InstallSkillModal.test.tsx
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { InstallSkillModal } from '../InstallSkillModal';

describe('InstallSkillModal', () => {
  it('submits a git URL', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ skill_id: 'fromgit' }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    const onInstalled = vi.fn();
    render(<InstallSkillModal onClose={() => {}} onInstalled={onInstalled} />);
    fireEvent.change(screen.getByLabelText(/git url/i), {
      target: { value: 'https://example.com/skill.git' },
    });
    fireEvent.click(screen.getByRole('button', { name: /install/i }));
    await waitFor(() => expect(onInstalled).toHaveBeenCalled());
    expect(fetch).toHaveBeenCalledWith('/api/skills/install', expect.any(Object));
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `cd frontend && npm test -- src/components/settings/skills/__tests__/InstallSkillModal.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/settings/skills/SkillDetailPanel.tsx
import { useEffect, useState } from 'react';
import { fetchSkillBody } from '../../../api/skills';

export function SkillDetailPanel({ skillId }: { skillId: string }): JSX.Element {
  const [body, setBody] = useState<string | null>(null);
  useEffect(() => { void fetchSkillBody(skillId).then(setBody); }, [skillId]);
  return (
    <div className="mt-3 p-3 bg-bg-tertiary rounded">
      {body === null ? <p>Loading body…</p>
        : <pre className="whitespace-pre-wrap text-sm">{body}</pre>}
    </div>
  );
}
```

```tsx
// frontend/src/components/settings/skills/InstallSkillModal.tsx
import { useState } from 'react';
import { installSkillFromGit, installSkillFromZip } from '../../../api/skills';

type Tab = 'git' | 'zip';

export function InstallSkillModal({
  onClose, onInstalled,
}: { onClose: () => void; onInstalled: () => void }): JSX.Element {
  const [tab, setTab] = useState<Tab>('git');
  const [gitUrl, setGitUrl] = useState('');
  const [ref, setRef] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const submit = async () => {
    setErr(null);
    try {
      if (tab === 'git') await installSkillFromGit(gitUrl, ref || undefined);
      else if (file) await installSkillFromZip(file);
      else throw new Error('select a file');
      onInstalled();
    } catch (e) { setErr(String(e)); }
  };
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div className="bg-bg-primary p-6 rounded shadow w-[480px]">
        <h3 className="text-lg font-semibold mb-3">Install skill</h3>
        <div className="flex gap-2 mb-3">
          {(['git', 'zip'] as Tab[]).map(t => (
            <button key={t}
              className={`px-3 py-1 rounded ${tab === t ? 'bg-accent text-white' : 'bg-bg-tertiary'}`}
              onClick={() => setTab(t)}
            >
              {t === 'git' ? 'Git URL' : 'Upload zip'}
            </button>
          ))}
        </div>
        {tab === 'git' && (
          <div className="space-y-2">
            <label className="block text-sm">Git URL
              <input value={gitUrl} onChange={e => setGitUrl(e.target.value)}
                className="w-full border rounded p-1" />
            </label>
            <label className="block text-sm">Branch / tag (optional)
              <input value={ref} onChange={e => setRef(e.target.value)}
                className="w-full border rounded p-1" />
            </label>
          </div>
        )}
        {tab === 'zip' && (
          <div>
            <input type="file" accept=".zip"
              onChange={e => setFile(e.target.files?.[0] ?? null)} />
          </div>
        )}
        {err && <p className="text-red-600 text-sm mt-2">{err}</p>}
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose} className="px-3 py-1">Cancel</button>
          <button onClick={submit} className="px-3 py-1 bg-accent text-white rounded">
            Install
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test -- src/components/settings/skills/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/skills/SkillDetailPanel.tsx frontend/src/components/settings/skills/InstallSkillModal.tsx frontend/src/components/settings/skills/__tests__/InstallSkillModal.test.tsx
git commit -m "feat(skills/fe): SkillDetailPanel + InstallSkillModal"
```

---

### Task 21: Admin skills section + route wiring

**Files:**
- Create: `frontend/src/components/settings/sections/AdminSkillsSection.tsx`
- Modify: `frontend/src/pages/SettingsPage.tsx` — add `<Route path="skills">` and `<Route path="admin/skills">`.
- Modify: `frontend/src/components/settings/SettingsShell.tsx` — add nav links for Skills (everyone) and Skill Activity (admin).
- Create: `frontend/src/components/settings/sections/__tests__/AdminSkillsSection.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/settings/sections/__tests__/AdminSkillsSection.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { AdminSkillsSection } from '../AdminSkillsSection';

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn().mockImplementation((url: string) => {
    if (url.includes('/audit')) {
      return Promise.resolve(new Response(JSON.stringify({
        items: [{
          id: '1', created_at: '2026-05-03T00:00:00Z', user_id: 'u',
          session_id: 's', department_id: 'secretary',
          event_type: 'skill_loaded', skill_id: 'alpha', payload: {},
        }],
      }), { status: 200 }));
    }
    return Promise.resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
  }));
});

describe('AdminSkillsSection', () => {
  it('renders system skills + audit log tabs', async () => {
    render(<AdminSkillsSection />);
    await waitFor(() => expect(screen.getByText(/skill_loaded/i)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `cd frontend && npm test -- src/components/settings/sections/__tests__/AdminSkillsSection.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/settings/sections/AdminSkillsSection.tsx
import { useEffect, useState } from 'react';

interface AuditEntry {
  id: string; created_at: string; user_id: string | null;
  session_id: string | null; department_id: string | null;
  event_type: string; skill_id: string; payload: Record<string, unknown>;
}

export function AdminSkillsSection(): JSX.Element {
  const [audit, setAudit] = useState<AuditEntry[] | null>(null);
  useEffect(() => {
    fetch('/api/admin/skills/audit?since_days=30', { credentials: 'include' })
      .then(r => r.json())
      .then(j => setAudit(j.items));
  }, []);
  return (
    <div className="p-6 space-y-4">
      <h2 className="text-xl font-semibold">Skill Activity (admin)</h2>
      {audit === null ? <p>Loading…</p>
        : audit.length === 0 ? <p>No skill events.</p>
        : <table className="w-full text-sm">
            <thead>
              <tr><th>When</th><th>User</th><th>Event</th><th>Skill</th><th>Department</th></tr>
            </thead>
            <tbody>
              {audit.map(r => (
                <tr key={r.id}>
                  <td>{r.created_at}</td>
                  <td>{r.user_id ?? '—'}</td>
                  <td>{r.event_type}</td>
                  <td>{r.skill_id}</td>
                  <td>{r.department_id ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>}
    </div>
  );
}
```

```tsx
// frontend/src/pages/SettingsPage.tsx  (add inside <Routes>)
<Route path="skills" element={<SkillsSection />} />
{isAdmin && <Route path="admin/skills" element={<AdminSkillsSection />} />}
```

Add nav links in `SettingsShell.tsx` (locate the existing nav and add a `Skills` entry visible to all, plus `Skill Activity` under the admin sub-nav).

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/settings/sections/AdminSkillsSection.tsx frontend/src/pages/SettingsPage.tsx frontend/src/components/settings/SettingsShell.tsx frontend/src/components/settings/sections/__tests__/AdminSkillsSection.test.tsx
git commit -m "feat(skills/fe): AdminSkillsSection + Settings routes/nav"
```

---

### Task 22: Inline `SkillLoadedCard` in chat stream

**Files:**
- Create: `frontend/src/components/chat/SkillLoadedCard.tsx`
- Modify: `frontend/src/components/chat/ChatInterface.tsx` (or whichever component renders SSE event cards) — add a branch for `chat.skill_loaded`
- Modify: `frontend/src/api/chatStream.ts` — extend the event type union with `chat.skill_loaded`
- Create: `frontend/src/components/chat/__tests__/SkillLoadedCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/chat/__tests__/SkillLoadedCard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { SkillLoadedCard } from '../SkillLoadedCard';

describe('SkillLoadedCard', () => {
  it('renders skill display name', () => {
    render(<SkillLoadedCard skillId="alpha" displayName="Alpha Skill" />);
    expect(screen.getByText(/Alpha Skill/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run, verify failure**

Run: `cd frontend && npm test -- src/components/chat/__tests__/SkillLoadedCard.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement**

```tsx
// frontend/src/components/chat/SkillLoadedCard.tsx
export function SkillLoadedCard({
  skillId, displayName,
}: { skillId: string; displayName: string }): JSX.Element {
  return (
    <div className="my-2 px-3 py-2 bg-bg-tertiary rounded text-sm border-l-2 border-accent">
      <span className="text-text-secondary">Loaded skill:</span>{' '}
      <code>{displayName}</code>
      <span className="text-text-tertiary ml-2">({skillId})</span>
    </div>
  );
}
```

In the chat-stream type union (`frontend/src/api/chatStream.ts` or equivalent — search with `grep -rn "chat.tool_call" frontend/src/api`), add:

```typescript
| { type: 'chat.skill_loaded'; message_id: string; skill_id: string; display_name: string }
```

In the chat renderer, add the branch:

```tsx
case 'chat.skill_loaded':
  return <SkillLoadedCard skillId={ev.skill_id} displayName={ev.display_name} />;
```

The server already emits `ChatSkillLoaded` from Task 12; the SSE wire mapping happens in the existing `_event_source` (search `packages/server/src/openlia_server/routes/chat_stream.py` for `ChatToolCallResult` to find the handoff point) — verify the new dataclass is included in the `to_wire` switch.

- [ ] **Step 4: Run, verify pass**

Run: `cd frontend && npm test`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/SkillLoadedCard.tsx frontend/src/components/chat/ChatInterface.tsx frontend/src/api/chatStream.ts frontend/src/components/chat/__tests__/SkillLoadedCard.test.tsx packages/server/src/openlia_server/routes/chat_stream.py
git commit -m "feat(skills/fe): inline SkillLoadedCard for chat.skill_loaded events"
```

---

## Phase 8 — End-to-end verification

### Task 23: Full-stack smoke test

**Files:**
- Create: `packages/server/tests/e2e/test_skills_e2e.py`

- [ ] **Step 1: Write the test**

```python
# packages/server/tests/e2e/test_skills_e2e.py
import io
import zipfile

import pytest


SAMPLE = """---
name: e2e-skill
display_name: E2E Skill
description: Smoke test skill.
version: "1.0.0"
departments: [secretary]
---

E2E body content.
"""


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("e2e-skill/SKILL.md", SAMPLE)
    return buf.getvalue()


def test_install_then_appears_in_secretary_chat_prompt(
    client_authed, app_state
):
    """Install a skill, then verify the secretary chat-system prompt
    rendered for this user contains the skill in its menu."""
    files = {"file": ("e2e.zip", _zip(), "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200

    # Force registry refresh (in case startup-only refresh missed it).
    user_id = app_state.current_user_id
    import asyncio
    asyncio.get_event_loop().run_until_complete(
        app_state.skills_registry.refresh_user(user_id)
    )

    from openlia.llm.runtime.chat import build_chat_system_prompt
    prompt = build_chat_system_prompt(
        department_id="secretary", user_id=user_id,
        registry=app_state.skills_registry,
    )
    assert "e2e-skill" in prompt
    assert "Smoke test skill." in prompt


def test_audit_log_records_install(client_authed, admin_client):
    files = {"file": ("e2e.zip", _zip().replace(b"e2e-skill", b"audited"), "application/zip")}
    r = client_authed.post(
        "/api/skills/install",
        data={"scope": "user", "source_type": "zip"},
        files=files,
    )
    assert r.status_code == 200
    audit = admin_client.get("/api/admin/skills/audit").json()["items"]
    assert any(e["event_type"] == "skill_installed" and e["skill_id"] == "audited"
               for e in audit)
```

`app_state` is whatever fixture exposes the running app's resolved dependencies (registry, current user). If absent, add it to `conftest.py` exposing the app's lifespan-built objects.

- [ ] **Step 2: Run, verify pass**

Run: `uv run pytest packages/server/tests/e2e/test_skills_e2e.py -v`
Expected: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add packages/server/tests/e2e/test_skills_e2e.py
git commit -m "test(skills): full-stack smoke (install -> prompt -> audit)"
```

---

### Task 24: Browser smoke (manual)

This is a final-pass manual verification, not a TDD task.

- [ ] Start dev stack: `uv run openlia serve` (in one shell), `cd frontend && npm run dev` (in another).
- [ ] Open `http://localhost:5173` in a browser, log in.
- [ ] Navigate to `Settings → Skills`. List should be empty.
- [ ] Click "Install skill". Choose "Git URL" tab. Paste a known SKILL.md-bearing repo URL (or use the bundled fixture under `packages/server/tests/fixtures/skills/`). Install.
- [ ] Confirm the skill appears with version, scope=user, enabled toggle.
- [ ] Open the Secretary chat. Send: "Use my [skill] to <question>". Confirm an inline `SkillLoadedCard` renders with the skill's display name.
- [ ] Toggle the skill off in Settings. Refresh chat. Confirm next turn's prompt no longer includes the skill (verify by sending a message that previously triggered it; check audit log for `skill_disabled`).
- [ ] As admin, navigate to `Settings → (Admin) → Skill Activity`. Confirm `skill_installed`, `skill_loaded`, `skill_disabled` rows are present.
- [ ] Uninstall the skill. Confirm it disappears from the list and an audit entry exists.

---

## Self-Review Checklist

Spec coverage:

- Component 1 (Skill format) → Tasks 1, 9
- Component 2 (Storage / SkillStore) → Tasks 2-7
- Component 3 (Install sources) → Tasks 15-16 (folder/git/zip; **npx deferred to Plan 2**)
- Component 4.1-4.2, 4.4, 4.6 (activation, slot eligibility, prompt slot) → Tasks 9-13
- Component 4.3, 4.5 (skill-declared tools, MCP lifecycle) → **deferred to Plan 2**
- Component 5 (SSE events: SkillLoaded only; SkillToolInvoked → Plan 2) → Tasks 11, 22
- Component 6 (Audit logging) → Tasks 6, 14
- Component 7 (Secrets vault) → **deferred to Plan 2** (no MCP servers in Plan 1, no env-injection need)
- Component 8 (Settings UI) → Tasks 18-21 (no secrets form yet — Plan 2)
- Component 9 (Backend routes) → Tasks 16-17 (no `/api/skills/{id}/secrets` — Plan 2)

Confirmed: every Plan 1-scoped section has a task. The MCP/secrets/npx surface is consistently labeled as Plan 2 in this plan and the linked spec.

Type/name consistency check:

- `SkillManifest`, `InstalledSkill` — used identically across all Python tasks.
- `parse_skill_md`, `serialize_skill_md` — identical signatures from Task 1 onward.
- Tool name namespacing pattern `skill__<id_with_underscores>__<tool>` — used in Task 13 (menu rendering); Plan 2 will introduce dispatch.
- `SkillRegistry.refresh()` vs `refresh_user()` — both used; consistent in routes (Tasks 16-17).
- Frontend types: `SkillSummary` defined in Task 18, consumed in 19-21.

No placeholders remain. Every step has concrete code or concrete commands.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-03-skills-mvp-prompt-only.md`. Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
