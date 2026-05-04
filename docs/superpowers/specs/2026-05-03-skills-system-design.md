# OpenLIA Skills System — Design

**Date:** 2026-05-03
**Status:** Draft, awaiting user review
**Related:** Builds on `2026-05-02-lia-persona-design.md` (prompt slot conventions) and `2026-05-02-lia-safety-and-compliance-guardrails-design.md` (audit log table reused for skill events).

## Problem

OpenLIA today ships seven fixed-purpose departments (Secretary, Equity Research, Earnings Update, Morning Briefing, Retail Sentiment, Macro Research, Panic Thermometer). Their prompts and tool sets are hard-coded in the repo. Users who want to extend Lia — bring a new playbook, add a custom data source, wire in a third-party MCP server — have no path to do so without forking.

This spec defines a *skills system*: a user-facing extensibility surface that lets either an admin or a user install a self-contained "skill" bundle, after which the LLM can discover and invoke it from inside ordinary chat or report flows.

A skill is one of two shapes (or both at once):

- **Prompt-only skill** — a markdown body of instructions / playbooks / checklists the LLM can pull into context on demand.
- **Tool-providing skill** — declares one or more callable tools whose handlers run as MCP servers (stdio subprocess or HTTP/SSE endpoint).

The system is designed to be **Claude-Code-skill-format-compatible**: an existing Claude Code skill (a folder with a `SKILL.md` carrying YAML frontmatter) is portable into OpenLIA with at most a `departments:` field added.

## Scope: in vs. out

**In:**
- Skill format (frontmatter + body), storage layout, install sources (folder drop, git URL, **npm/npx primary**, zip upload).
- Two-phase activation (menu in system prompt, body fetched via `load_skill` meta-tool).
- MCP tool dispatcher (stdio + HTTP/SSE) with lazy-start / idle-shutdown lifecycle.
- Per-department scoping (`departments: [...]` or `["*"]`) and per-user enable/disable toggle.
- System-scope (admin-installed, all users see) and user-scope (per-user installs) layered storage.
- Audit logging via the existing `lia_guardrail_events` table.
- Per-skill secret vault with env-var fallback.
- Two settings surfaces: `/settings/skills` (personal) and `/settings/admin/skills` (admin-only).
- Inline `skill_loaded` and `skill_tool_invoked` SSE events surfaced in the chat stream.

**Out (deferred to named follow-on specs):**
- *Capability sandboxing* — declared `network: true` / `filesystem: write` style permission flags **and their enforcement**. This spec leans on a trust-the-user model; sandboxing is the natural next bucket once threat data exists.
- *Skill marketplace / registry* — named lookup (`openlia skill install equity-toolkit`) backed by a curated index. Out of scope until skills proliferate enough to need discovery infrastructure.
- *Author tooling* — `openlia skill validate <path>` linter, scaffolding generator, MCP server templates. Authors get docs only this round.
- *Per-conversation skill toggles* — only per-user (Settings) toggles ship in this spec.
- *Heuristic skill preselection* — embedding/classifier-based menu pruning. Always-show-menu is fine until N grows.
- *Skill versioning beyond a manifest field* — no auto-update, no version pinning at the install command, no rollback. `version:` is informational.

## Architecture overview

```
┌────────────────────────────────────────────────────────────────┐
│ Frontend                                                       │
│  /settings/skills            /settings/admin/skills            │
│  install (npx/git/zip), toggle, uninstall                      │
└──────┬─────────────────────────────────────────────────────────┘
       │ REST
┌──────▼─────────────────────────────────────────────────────────┐
│ openlia_server                                                 │
│  routes/skills.py           (install, list, toggle, uninstall) │
│  routes/admin_skills.py     (system-scope ops, audit query)    │
│  services/skill_installer.py (run npx/git, write to store)     │
└──────┬─────────────────────────────────────────────────────────┘
       │
┌──────▼─────────────────────────────────────────────────────────┐
│ openlia.skills                  (NEW core module)              │
│  store.py        SkillStore protocol; FS + DB impls            │
│  loader.py       Manifest parser, frontmatter splitter         │
│  registry.py     In-memory cache; (dept, user) → list[Skill]   │
│  mcp/                                                          │
│    dispatcher.py MCPToolDispatcher; lazy lifecycle pool        │
│    transport_stdio.py   subprocess + JSON-RPC                  │
│    transport_http.py    HTTP/SSE client                        │
│  audit.py        Wraps guardrail-event writer for skill events │
│  vault.py        Per-user / system secrets, AES at rest        │
└──────┬─────────────────────────────────────────────────────────┘
       │
┌──────▼─────────────────────────────────────────────────────────┐
│ openlia.llm.runtime                                            │
│  prompts.py      + render context: skills_menu                 │
│  tools.py        + load_skill meta-tool; merge skill tools     │
│  events.py       + SkillLoaded, SkillToolInvoked SSE events    │
└────────────────────────────────────────────────────────────────┘
```

Boundary rules: `openlia.skills` is core (no FastAPI). The MCP dispatcher conforms to the existing `DataProviderDispatcher`-shaped Protocol so the runtime treats it as just another tool source.

---

## Component 1 — Skill format

### 1.1 — On-disk shape

A skill is a folder. The required file is `SKILL.md`. The frontmatter is the manifest; the body below is the prompt.

```
~/.openlia/skills/{system,user}/<skill_id>/
  SKILL.md            # frontmatter + body, REQUIRED
  mcp.json            # OPTIONAL: MCP server config (can also live in frontmatter)
  resources/          # OPTIONAL: assets the skill body references
```

`<skill_id>` is `[a-z0-9][a-z0-9_-]{0,63}` and globally unique within its scope.

### 1.2 — Frontmatter schema

```yaml
---
name: equity-research-toolkit
display_name: "Equity Research Toolkit"
description: "DCF templates, peer comp checklist, and a Bloomberg quote tool."
version: "1.2.0"
departments: [equity_research, earnings_update]   # or ["*"] for global
author: "Acme Capital"

# Optional. Present iff this is a tool-providing skill.
mcp:
  transport: stdio
  command: npx
  args: ["-y", "@acme/equity-mcp@latest"]
  # OR for HTTP/SSE:
  # transport: http
  # url: "https://mcp.example.com/equity"

# Optional. Tools the skill exposes from its MCP server.
# If omitted, OpenLIA discovers via MCP `list_tools` at first start.
tools:
  - name: dcf
    description: "Run a DCF on a ticker."
  - name: peer_comp
    description: "Pull peer comparables."

# Optional. Secrets the MCP server expects in env at launch.
requires_secrets:
  - name: ACME_API_KEY
    description: "Acme platform API key."
    scope: user           # user | system
---

# How to use this skill

The body is markdown. The LLM receives it verbatim as a tool result when
it calls `load_skill("equity-research-toolkit")`. Document playbooks,
heuristics, and tool usage examples here.
```

`departments` is required (no implicit global default — authors must opt in to `["*"]`). All other fields are optional.

### 1.3 — First-party primitives carve-out

Skills can declare a tool whose `name` matches a first-party primitive (e.g. `openlia.repo.search`, `openlia.connector.query`). In that case `mcp:` and `tools:` are not used; the runtime maps the name to the in-process handler directly. This handles "I just want my skill to expose `read_repo` to the LLM" without forcing every author to write an MCP server.

The first-party primitives shipped in v1 are:
- `openlia.repo.search` — query the user's report repository.
- `openlia.repo.read` — read a saved report by id.
- `openlia.connector.query` — invoke a configured connector by id (subject to existing connector permissions).

---

## Component 2 — Storage and `SkillStore` protocol

### 2.1 — `SkillStore` protocol

```python
class SkillStore(Protocol):
    async def list(self, *, scope: Literal["system", "user"], user_id: str | None) -> list[InstalledSkill]: ...
    async def get(self, skill_id: str, *, scope, user_id) -> InstalledSkill | None: ...
    async def install(self, source: SkillSource, *, scope, user_id) -> InstalledSkill: ...
    async def uninstall(self, skill_id: str, *, scope, user_id) -> None: ...
    async def set_enabled(self, skill_id: str, enabled: bool, *, scope, user_id) -> None: ...
```

Two implementations:

- **`FilesystemSkillStore`** — backs `~/.openlia/skills/{system,user}/`. The default in personal mode for both scopes; the default in company mode for system scope.
- **`DatabaseSkillStore`** — used in company mode for *user* scope (where users have no shell access). Skill files are persisted as rows in a `skills` table; the loader reads body+frontmatter from the row, treating it identically to a file.

A `LayeredSkillStore` composes the two (system reads always go to FS; user reads in personal mode go to FS, in company mode go to DB).

### 2.2 — Database schema (company-mode user scope)

New table `skills`:

| Column | Type | Notes |
|---|---|---|
| `id` | uuid PK | |
| `skill_id` | text | The `[a-z0-9_-]` id; unique per (scope, user_id) |
| `scope` | enum('system','user') | |
| `user_id` | uuid nullable | NULL when scope='system' |
| `frontmatter` | jsonb | Parsed manifest |
| `body` | text | The markdown body |
| `enabled` | bool default true | Per-user toggle. For system skills, per-user override row in `skill_user_overrides` |
| `installed_at` | timestamptz | |
| `version` | text | Mirrors frontmatter.version for query convenience |

`skill_user_overrides`: `(user_id, skill_id, enabled)` lets a user disable a system-installed skill for themselves only.

Alembic migration adds both tables.

---

## Component 3 — Install sources

The user-facing CLI is `openlia skill install <SOURCE>`. The same logic backs the Settings UI install button.

### 3.1 — npm/npx (primary)

The expected shape, modeled on `npx -y firecrawl-cli@latest init`:

```bash
npx -y @acme/equity-toolkit@latest init
```

Skill authors publish an npm package whose `init` subcommand:

1. Detects the OpenLIA installation. Personal mode: writes to `~/.openlia/skills/user/<skill_id>/`. Company mode: POSTs the SKILL.md body + frontmatter to `POST /api/skills/install` with the user's auth token (read from `~/.openlia/auth.json` or prompted).
2. Optionally accepts `--system` to target system scope (admin only; the API rejects non-admins).
3. Optionally accepts `--scope`, `--server-url` to override defaults.

OpenLIA ships a tiny npm helper, **`@openlia/skill-installer`**, exporting:

```ts
installSkill({
  skillId, frontmatter, body, mode?: 'auto'|'personal'|'company',
  serverUrl?, authToken?, scope?: 'user'|'system'
}): Promise<{installed: true, path?: string, id?: string}>
```

Skill authors call this from their `init` script — they don't reimplement detection/auth logic.

### 3.2 — Git URL

```bash
openlia skill install https://github.com/foo/bar-skill.git[#ref]
```

Server (or local CLI) `git clone`s into a temp dir, validates the SKILL.md exists, parses frontmatter, copies into the target store path.

### 3.3 — Folder drop

User puts a folder under `~/.openlia/skills/user/<id>/`. The registry rescans on app boot or on explicit `openlia skill rescan`. Personal-mode developer workflow.

### 3.4 — Zip upload

UI dropzone for company-mode users without shell access. Server unzips into the DB-backed user store. Hard cap: 5 MB.

### 3.5 — Versioning

`version:` is a frontmatter field. Updates are manual: re-run install. The CLI reports old → new version; the UI shows version and last-installed-at. No auto-pull, no rollback.

---

## Component 4 — Activation and the LLM runtime

### 4.1 — Two-phase activation

Phase 1 (always): a **skill menu** is rendered into the system prompt. For each skill scoped to the current department and enabled for the current user:

```
- equity-research-toolkit: DCF templates, peer comp checklist, and a Bloomberg quote tool. Tools: skill__equity_research_toolkit__dcf, skill__equity_research_toolkit__peer_comp.
```

Phase 2 (on demand): the LLM calls **`load_skill(skill_id)`**. The dispatcher reads the body from the store, returns it as the tool result. The body lives in conversation history like any other tool result. If compacted out, the LLM can call `load_skill` again. No server-side caching beyond store-level reads.

### 4.2 — `load_skill` schema

```python
_LOAD_SKILL_SCHEMA = ToolSchema(
    name="load_skill",
    description=(
        "Load the full instructions/playbook for a skill from the menu above. "
        "Returns the skill's markdown body. Use when the user's question matches "
        "a skill's stated purpose and you want its detailed guidance."
    ),
    parameters={
        "type": "object",
        "properties": {
            "skill_id": {"type": "string", "description": "Id from the skill menu."}
        },
        "required": ["skill_id"],
    },
)
```

### 4.3 — Skill-declared tools

For every B-skill scoped to the current department and enabled for the current user, OpenLIA appends its tools to the tool array. Tool names are namespaced:

```
skill__<skill_id_with_dashes_replaced_by_underscores>__<tool_name>
```

A skill `equity-research-toolkit` declaring tool `dcf` becomes `skill__equity_research_toolkit__dcf`.

The dispatcher routes any name starting with `skill__` to the `MCPToolDispatcher`, which:

1. Parses the namespaced name back to `(skill_id, tool_name)`.
2. Looks up the skill's MCP transport config from the registry.
3. Ensures the MCP server is running (lazy-start, see 4.5).
4. Calls `tools/call` over the transport.
5. Returns the response as a `ToolCallResult` (matching the existing dispatcher contract).

Skill tools are **always callable**, with or without a preceding `load_skill`. The body is informational, not a gate.

### 4.4 — Slot eligibility

Skills inject into **all slots** — both `chat.system` and `report.*.system`. Reports become technically non-bit-reproducible if the user's installed skills change between generations, but report regeneration is already user-initiated and the diff is auditable via the skill audit log. Authors of regulated outputs can opt their report flows out by not including `shared/skills_menu.yaml.j2` in those slots.

### 4.5 — MCP server lifecycle

Lazy-start with idle shutdown.

- Pool is keyed by `skill_id`. Pool size: 1 per skill.
- First call to a skill's tool spawns the server.
  - **stdio:** `subprocess.create_subprocess_exec(command, *args, env=injected_env, stdin/stdout=PIPE)`.
  - **http:** open a persistent HTTP/SSE client.
- Idle timeout: 5 minutes (configurable via `OPENLIA_MCP_IDLE_TIMEOUT_S`). On timeout, terminate stdio subprocess / close HTTP client. Restart on next call.
- On app shutdown, all running MCP servers are terminated cleanly (SIGTERM with 5s timeout, then SIGKILL).
- Crash recovery: if the subprocess exits unexpectedly mid-call, the dispatcher returns `ok=False` with `summary="Skill server crashed"`. Next call re-spawns. No retry inside a single call.

### 4.6 — Prompt slot integration

A new shared partial **`packages/core/src/openlia/prompts/shared/skills_menu.yaml.j2`**:

```jinja
{% if skills_menu %}
## Skills available

The following skills are installed and ready. Each line is `id: description`.
Call `load_skill(skill_id)` to read the full playbook before using; tools
listed are always callable.

{% for s in skills_menu %}
- **{{ s.id }}**: {{ s.description }}{% if s.tools %} *Tools:* {{ s.tools | join(', ') }}.{% endif %}
{% endfor %}
{% endif %}
```

Each department's chat and report system slots include this partial:

```jinja
{% include "shared/lia_identity.yaml.j2" %}
...
{% include "shared/skills_menu.yaml.j2" %}
{% include "shared/output_discipline.yaml.j2" %}
```

The runtime (chat assembly + report assembly) populates the `skills_menu` context variable. When the list is empty, the partial renders to nothing and the prompt is unchanged.

---

## Component 5 — SSE events

Two new events join the existing `SseEvent` union in `openlia.llm.runtime.events`:

```python
class SkillLoaded(BaseModel):
    type: Literal["skill_loaded"] = "skill_loaded"
    skill_id: str
    display_name: str

class SkillToolInvoked(BaseModel):
    type: Literal["skill_tool_invoked"] = "skill_tool_invoked"
    skill_id: str
    tool_name: str
    ok: bool
    summary: str
```

Frontend renders both as tool-call-style cards in the chat stream.

---

## Component 6 — Audit logging

Extend `lia_guardrail_events` rather than create a new table. Add the following `event_type` enum values (Alembic migration):

- `skill_installed` — payload: `{skill_id, scope, source, version}`
- `skill_uninstalled` — payload: `{skill_id, scope}`
- `skill_enabled` / `skill_disabled` — payload: `{skill_id, scope}`
- `skill_loaded` — payload: `{skill_id, session_id, department}`
- `skill_tool_invoked` — payload: `{skill_id, tool_name, ok, latency_ms}`

The retention job (registered with the existing `MaintenanceExecutor`) trims skill events on the same schedule as other guardrail events.

The Settings → Guardrail Activity UI gains a *Skills* filter. The admin Settings page gains a *Skill Activity* sub-section that defaults to all-users skill events.

---

## Component 7 — Secrets vault

### 7.1 — Storage

A new table `skill_secrets`:

| Column | Type |
|---|---|
| `id` | uuid PK |
| `skill_id` | text |
| `scope` | enum('system','user') |
| `user_id` | uuid nullable |
| `secret_name` | text |
| `secret_value_encrypted` | bytea |
| `created_at` | timestamptz |

Encryption: AES-256-GCM with a key from `OPENLIA_SECRET_KEY` env var. If the env var is missing, OpenLIA refuses to start in company mode and warns in personal mode (with a one-time generated key written to `~/.openlia/secret.key` chmod 600).

### 7.2 — Injection at MCP launch

When the MCP dispatcher spawns a skill's stdio subprocess (or initializes an HTTP transport), it composes the env:

1. Start with the OpenLIA process env, **filtered** to a small allowlist (`PATH`, `HOME`, `LANG`, `TZ`, plus any keys named in the skill's `requires_secrets`).
2. Add OpenLIA-set entries (`OPENLIA_SKILL_ID`, `OPENLIA_USER_ID` for telemetry).
3. For each entry in the skill's `requires_secrets`:
   - First check `skill_secrets` for `(skill_id, scope, user_id, secret_name)`. If present, decrypt and inject.
   - Else fall back to the OpenLIA process env (admin-set fallback).
   - Else: refuse to start the server, return `ok=False` summary `"missing required secret: <name>"`.

### 7.3 — UI

Settings → Skills → per-skill detail page. If `requires_secrets` is non-empty, a section lists each secret name + description with a write-only input (existing values shown as `••••••`, never returned in API responses). Save POSTs to `/api/skills/{id}/secrets` which encrypts and upserts.

---

## Component 8 — Frontend (settings)

### 8.1 — `/settings/skills` (everyone)

Lists installed skills (system + user merged) with badges showing scope. Per-skill row:

- Toggle (enable/disable for this user). Disabling a system skill writes a row to `skill_user_overrides`.
- "Details" — opens a panel showing frontmatter, body preview, secrets form (if applicable), version, install source, last-loaded timestamp.
- "Uninstall" — only available on user-scoped skills (system-scoped uninstall is admin-only).
- "Install" button — modal accepts an `npx` command, a git URL, or a zip drop. One-click install (no preview/confirmation step). Result toast.

### 8.2 — `/settings/admin/skills` (admin only)

System-scope management:
- Install/uninstall system skills.
- View per-skill installation across all users (filterable user list).
- Skill activity audit log (filtered view of `lia_guardrail_events` to skill events).

### 8.3 — Chat-stream rendering

`SkillLoaded` and `SkillToolInvoked` events render as small inline cards in the existing chat stream component, sharing the visual treatment of tool-call cards.

---

## Component 9 — Backend routes

```
GET    /api/skills                          List skills visible to current user
POST   /api/skills/install                  Install (multipart: source_type + source)
DELETE /api/skills/{id}                     Uninstall (user scope or admin+system)
PATCH  /api/skills/{id}                     {enabled: bool}
GET    /api/skills/{id}/body                Read SKILL.md body for the panel preview
POST   /api/skills/{id}/secrets             {name, value}
GET    /api/admin/skills                    Admin-only: all installs across users
GET    /api/admin/skills/audit              Admin-only: filtered guardrail-event view
```

Auth/middleware: existing auth middleware applies. `/api/admin/*` requires admin role. `POST /api/skills/install` with `scope=system` requires admin role.

---

## Out of scope (named follow-on specs)

These get their own specs after this MVP ships:

1. **Capability declaration & sandbox enforcement** — `network`, `filesystem`, `secrets` flags in frontmatter, plus actual containment (subprocess sandboxing, seccomp, namespace-isolation, or container runtime). Today: trust-the-user model.
2. **Skill marketplace** — named install (`openlia skill install equity-toolkit`) backed by a curated index, ratings, signed manifests.
3. **Skill author tooling** — `openlia skill validate <path>`, `openlia skill scaffold`, MCP server templates, lint rules.
4. **Heuristic skill preselection** — embedding/classifier-based menu pruning when N grows large.
5. **Per-conversation skill toggles** — UI for picking active skills per chat session.
6. **Auto-update for git/npm-installed skills** — version-watching, "update available" notifications, optional auto-pull.

---

## Token cost estimate

Skill menu entries are ~25-40 tokens each (id + description + tool list). At 50 installed-and-enabled skills per user, the menu adds ~1.5-2K tokens to every system prompt — bounded and acceptable. The `load_skill` body is paid only when called, scoped to that turn's conversation. Skill-declared tools add ~30-60 tokens each to the tool array.

## Testing

- **Unit:** `SkillStore` impls (FS + DB), frontmatter parser, namespacing round-trip, secrets encryption/decryption, MCP dispatcher (with a fake transport).
- **Integration:** install → list → load → invoke flow end-to-end with a fake stdio MCP server. Department scoping (skill scoped to `equity_research` does not appear in `secretary` menus). Per-user toggle hides skill from menu and from tool array. Audit events written for each transition.
- **Browser smoke:** install via UI dropzone, skill appears in `/settings/skills`, chat with Secretary triggers `skill_loaded` event card, MCP tool invocation succeeds and renders `skill_tool_invoked` card.
- **Negative:** missing secret returns `ok=False` summary; crashed MCP server returns `ok=False` and re-spawns on next call; uninstall mid-conversation removes the skill from subsequent turns.

## Companion implementation plan

To be written next via the `superpowers:writing-plans` skill once this design is approved.
