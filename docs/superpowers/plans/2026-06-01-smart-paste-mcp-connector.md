# Smart-paste MCP connector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user add a remote or local (stdio) MCP connector by pasting a single URL or command, auto-extracting the embedded API key into the connector's secret bag, and validating the server is actually usable.

**Architecture:** Three new pure frontend modules (classify paste → detect secret chips → build the connector payload) drive a thin new React component, `SmartPasteMcpForm`. The only backend change extends the existing `{NAME}` secret-substitution to `cli_mcp` argv tokens (so a key placed as a positional CLI arg resolves at launch) and tightens validation to require at least one tool for MCP sources. No schema changes; reuses the existing `connectors` table, transports, and `POST /connectors` route.

**Tech Stack:** Python 3.13 (FastAPI server, SQLAlchemy), pytest. React 18 + TypeScript + Vite, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-06-01-smart-paste-mcp-connector-design.md`

---

## File Structure

Backend (only one behavior change + one validation tightening):
- Modify `packages/server/src/openlia_server/services/dispatcher_factory.py` — substitute `{NAME}` in `cli_mcp` argv (cli branch of `_build_transport`).
- Modify `packages/server/src/openlia_server/services/connectors_service.py` — in `_validate_launch`, require >= 1 tool for `cli_mcp` / `remote_mcp`.
- Test `packages/server/tests/test_services/test_dispatcher_factory_substitutions.py` — argv substitution cases (append).
- Test `packages/server/tests/services/test_connectors_service.py` — zero-tool validation cases (append).

Frontend (three pure modules, one component, one wording fix):
- Create `frontend/src/setup/steps/parseMcpInput.ts` — classify + structurally parse pasted text.
- Create `frontend/src/setup/steps/detectSecrets.ts` — pre-select secret chips over the parsed structure.
- Create `frontend/src/setup/steps/buildMcpLaunch.ts` — turn parsed + chips + values into `{ mode, secrets }`.
- Create `frontend/src/setup/steps/SmartPasteMcpForm.tsx` — the paste UI.
- Modify `frontend/src/setup/steps/AddConnectorForm.tsx` — soften the false "encrypted" secrets wording.
- Tests: `frontend/src/setup/steps/__tests__/parseMcpInput.test.ts`, `detectSecrets.test.ts`, `buildMcpLaunch.test.ts`, `SmartPasteMcpForm.test.tsx`.

Each pure module has one responsibility and no I/O, so it is unit-testable in isolation. The component composes them and performs the single network call.

---

## Task 1: Backend — substitute `{NAME}` into `cli_mcp` argv

**Files:**
- Modify: `packages/server/src/openlia_server/services/dispatcher_factory.py:113-119` (the `cli_mcp` branch of `_build_transport`)
- Test: `packages/server/tests/test_services/test_dispatcher_factory_substitutions.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/test_services/test_dispatcher_factory_substitutions.py`:

```python
def test_build_transport_substitutes_placeholder_in_cli_argv() -> None:
    """A key placed as a positional CLI arg (e.g. `uvx marketdata-mcp-server {KEY}`)
    must resolve from secrets at launch, the same way remote URLs do."""
    mode = {
        "kind": "cli_mcp",
        "argv": ["uvx", "marketdata-mcp-server", "{MARKETDATA_KEY}"],
        "env_keys": [],
    }
    secrets = {"MARKETDATA_KEY": "md-secret-123"}
    t = _build_transport("c1", mode, secrets)
    assert t._mode.argv == [  # type: ignore[attr-defined]
        "uvx",
        "marketdata-mcp-server",
        "md-secret-123",
    ]


def test_build_transport_leaves_unknown_argv_placeholder_unchanged() -> None:
    """Missing secret -> placeholder stays literal so the failure is obvious."""
    mode = {
        "kind": "cli_mcp",
        "argv": ["uvx", "srv", "{MISSING}"],
        "env_keys": [],
    }
    t = _build_transport("c1", mode, {})
    assert t._mode.argv == ["uvx", "srv", "{MISSING}"]  # type: ignore[attr-defined]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_services/test_dispatcher_factory_substitutions.py::test_build_transport_substitutes_placeholder_in_cli_argv -v`
Expected: FAIL — argv contains the literal `{MARKETDATA_KEY}` instead of the resolved secret.

- [ ] **Step 3: Write minimal implementation**

In `dispatcher_factory.py`, replace the `cli_mcp` branch of `_build_transport` (currently):

```python
    if kind == "cli_mcp":
        cli_mode = CliMcpMode(
            kind="cli_mcp",
            argv=list(mode.get("argv") or []),
            env_keys=list(mode.get("env_keys") or []),
        )
        return CliMcpTransport(mode=cli_mode, secrets=secrets)
```

with:

```python
    if kind == "cli_mcp":
        # Substitute `{NAME}` placeholders in argv tokens from secrets, mirroring
        # the remote_mcp URL/header substitution below. This lets an API key be
        # supplied as a positional CLI arg (e.g. `uvx marketdata-mcp-server {KEY}`)
        # without persisting the raw key in launch JSON. Unmatched placeholders
        # stay literal so a missing secret surfaces as an obvious failure.
        argv = [
            _substitute_secrets(tok, secrets) if isinstance(tok, str) else tok
            for tok in (mode.get("argv") or [])
        ]
        cli_mode = CliMcpMode(
            kind="cli_mcp",
            argv=argv,
            env_keys=list(mode.get("env_keys") or []),
        )
        return CliMcpTransport(mode=cli_mode, secrets=secrets)
```

(`_substitute_secrets` and `_PLACEHOLDER_RE` already exist in this module — no new import.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_dispatcher_factory_substitutions.py -v`
Expected: PASS (all cases, including the two new ones).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/dispatcher_factory.py packages/server/tests/test_services/test_dispatcher_factory_substitutions.py
git commit -m "feat(connectors): substitute secret placeholders in cli_mcp argv"
```

---

## Task 2: Backend — require >= 1 tool when validating MCP connectors

**Files:**
- Modify: `packages/server/src/openlia_server/services/connectors_service.py:214-253` (inside `_validate_launch`, after the tool list is built)
- Test: `packages/server/tests/services/test_connectors_service.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/services/test_connectors_service.py`:

```python
import pytest

from openlia_server.services import connectors_service as cs


class _FakeTransport:
    def __init__(self, tools: list[dict]) -> None:
        self._tools = tools

    async def list_tools(self) -> list[dict]:
        return self._tools

    async def aclose(self) -> None:
        return None


@pytest.mark.anyio
async def test_validate_launch_fails_when_remote_mcp_returns_no_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        cs, "_build_transport", lambda connector_id, mode, secrets: _FakeTransport([])
    )
    launch = {"modes": [{"kind": "remote_mcp", "url": "https://x/mcp", "headers": {}}]}
    result = await cs._validate_launch(launch, {})
    assert isinstance(result, cs.ValidationFailure)
    assert "no tools" in result.error.lower()


@pytest.mark.anyio
async def test_validate_launch_passes_when_cli_mcp_returns_a_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tool = {"name": "quote", "description": "", "input_schema": {}}
    monkeypatch.setattr(
        cs, "_build_transport", lambda connector_id, mode, secrets: _FakeTransport([tool])
    )
    launch = {"modes": [{"kind": "cli_mcp", "argv": ["uvx", "srv"], "env_keys": []}]}
    result = await cs._validate_launch(launch, {})
    assert isinstance(result, cs.ValidationOk)
    assert result.tools == [tool]
```

Note: this repo's async tests use `anyio` (the existing suite already marks coroutine tests). If a nearby test in this file uses a different marker (e.g. `@pytest.mark.asyncio`), match that marker instead — check the top of the file before running.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/services/test_connectors_service.py::test_validate_launch_fails_when_remote_mcp_returns_no_tools -v`
Expected: FAIL — current `_validate_launch` returns `ValidationOk` with an empty tool list.

- [ ] **Step 3: Write minimal implementation**

In `connectors_service.py`, inside `_validate_launch`, immediately AFTER the `for entry in raw_tools or []:` loop that builds `tools` (and before the `python_callables` block), insert:

```python
        if selected_mode.get("kind") in ("cli_mcp", "remote_mcp") and not tools:
            return ValidationFailure(
                error=(
                    "Connected to the MCP server but it returned no tools. "
                    "The server may be unauthorized (check the API key) or may "
                    "expose nothing usable."
                ),
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/services/test_connectors_service.py -v`
Expected: PASS (existing tests unaffected — they stub `_validate_launch` wholesale; the new tests exercise the real function).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/connectors_service.py packages/server/tests/services/test_connectors_service.py
git commit -m "feat(connectors): require at least one tool to validate an MCP connector"
```

---

## Task 3: Frontend — `parseMcpInput` (classify + structural parse)

**Files:**
- Create: `frontend/src/setup/steps/parseMcpInput.ts`
- Test: `frontend/src/setup/steps/__tests__/parseMcpInput.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/setup/steps/__tests__/parseMcpInput.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { parseMcpInput } from "../parseMcpInput";

describe("parseMcpInput", () => {
  it("classifies an https URL as remote and splits query params", () => {
    const r = parseMcpInput("https://mcp.alphavantage.co/mcp?apikey=AV12345");
    expect(r.kind).toBe("remote");
    if (r.kind === "remote") {
      expect(r.baseUrl).toBe("https://mcp.alphavantage.co/mcp");
      expect(r.queryParams).toEqual([{ name: "apikey", value: "AV12345" }]);
      expect(r.headers).toEqual([]);
    }
  });

  it("classifies a uvx command as cli and finds the server token index", () => {
    const r = parseMcpInput("uvx marketdata-mcp-server MD_KEY_789");
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["uvx", "marketdata-mcp-server", "MD_KEY_789"]);
      expect(r.serverIndex).toBe(1);
    }
  });

  it("classifies a bare npx command as cli", () => {
    const r = parseMcpInput("npx -y newsapi-mcp");
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["npx", "-y", "newsapi-mcp"]);
      expect(r.serverIndex).toBe(2);
    }
  });

  it("parses an mcpServers JSON blob into cli argv", () => {
    const json = JSON.stringify({
      mcpServers: { foo: { command: "npx", args: ["-y", "foo-mcp"] } },
    });
    const r = parseMcpInput(json);
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["npx", "-y", "foo-mcp"]);
    }
  });

  it("returns an error for empty input", () => {
    const r = parseMcpInput("   ");
    expect(r.kind).toBe("error");
  });

  it("returns an error for a malformed URL", () => {
    const r = parseMcpInput("https://");
    expect(r.kind).toBe("error");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/parseMcpInput.test.ts`
Expected: FAIL — module `../parseMcpInput` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/setup/steps/parseMcpInput.ts`:

```ts
/**
 * Classify a pasted MCP connection string and parse it into a structure the
 * smart-paste add flow can render as editable chips.
 *
 * Accepts:
 *   - A remote URL:   https://mcp.example.com/mcp?apikey=KEY
 *   - A CLI command:  uvx some-mcp-server KEY   |   npx -y some-mcp
 *   - An mcpServers JSON blob (delegated to parseMcpConfig for argv)
 */
import { parseMcpConfig } from "./parseMcpConfig";

export interface RemoteParsed {
  kind: "remote";
  baseUrl: string;
  queryParams: { name: string; value: string }[];
  headers: { name: string; value: string }[];
}

export interface CliParsed {
  kind: "cli";
  argv: string[];
  /** index in argv of the resolved server/package token (-1 if none found) */
  serverIndex: number;
}

export type ParseMcpInputResult =
  | RemoteParsed
  | CliParsed
  | { kind: "error"; error: string };

// Command runners that wrap the actual server package/binary.
const RUNNERS = new Set([
  "npx",
  "uvx",
  "uv",
  "bunx",
  "pnpm",
  "node",
  "python",
  "python3",
  "deno",
]);

function tokenize(text: string): string[] {
  return text
    .trim()
    .replace(/^['"]|['"]$/g, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function findServerIndex(argv: string[]): number {
  let i = 0;
  // Skip a leading runner and its sub-command (e.g. `uv run`).
  if (argv.length > 0 && RUNNERS.has(argv[0])) {
    i = 1;
    if (argv[0] === "uv" && argv[1] === "run") i = 2;
  }
  for (; i < argv.length; i++) {
    if (!argv[i].startsWith("-")) return i;
  }
  return -1;
}

export function parseMcpInput(text: string): ParseMcpInputResult {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { kind: "error", error: "Paste a URL or a command." };
  }

  if (/^https?:\/\//i.test(trimmed)) {
    let url: URL;
    try {
      url = new URL(trimmed);
    } catch {
      return { kind: "error", error: "That does not look like a valid URL." };
    }
    if (!url.hostname) {
      return { kind: "error", error: "That does not look like a valid URL." };
    }
    const queryParams = [...url.searchParams.entries()].map(([name, value]) => ({
      name,
      value,
    }));
    return {
      kind: "remote",
      baseUrl: `${url.origin}${url.pathname}`,
      queryParams,
      headers: [],
    };
  }

  if (trimmed.startsWith("{")) {
    const cfg = parseMcpConfig(trimmed);
    if (!cfg.ok) {
      return { kind: "error", error: cfg.error };
    }
    return { kind: "cli", argv: cfg.argv, serverIndex: findServerIndex(cfg.argv) };
  }

  const argv = tokenize(trimmed);
  if (argv.length === 0) {
    return { kind: "error", error: "Paste a URL or a command." };
  }
  return { kind: "cli", argv, serverIndex: findServerIndex(argv) };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/parseMcpInput.test.ts`
Expected: PASS (all 6 cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/parseMcpInput.ts frontend/src/setup/steps/__tests__/parseMcpInput.test.ts
git commit -m "feat(connectors): add parseMcpInput classifier for smart-paste"
```

---

## Task 4: Frontend — `detectSecrets` (pre-select secret chips)

**Files:**
- Create: `frontend/src/setup/steps/detectSecrets.ts`
- Test: `frontend/src/setup/steps/__tests__/detectSecrets.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/setup/steps/__tests__/detectSecrets.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { detectSecrets } from "../detectSecrets";
import type { RemoteParsed, CliParsed } from "../parseMcpInput";

describe("detectSecrets", () => {
  it("pre-selects an apikey query param and suggests a key name", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://mcp.alphavantage.co/mcp",
      queryParams: [{ name: "apikey", value: "AV12345" }],
      headers: [],
    };
    const chips = detectSecrets(parsed, "alphavantage");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toMatchObject({
      locator: { kind: "query", name: "apikey" },
      rawValue: "AV12345",
      preselected: true,
      suggestedKey: "ALPHAVANTAGE_APIKEY",
    });
  });

  it("does not pre-select a non-credential query param", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [{ name: "region", value: "us" }],
      headers: [],
    };
    const chips = detectSecrets(parsed, "x");
    expect(chips[0].preselected).toBe(false);
  });

  it("pre-selects an Authorization header", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [],
      headers: [{ name: "Authorization", value: "Bearer abc" }],
    };
    const chips = detectSecrets(parsed, "x");
    expect(chips[0]).toMatchObject({
      locator: { kind: "header", name: "Authorization" },
      preselected: true,
    });
  });

  it("pre-selects a credential-looking cli arg after the server token", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["uvx", "marketdata-mcp-server", "MD_KEY_789"],
      serverIndex: 1,
    };
    const chips = detectSecrets(parsed, "marketdata");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toMatchObject({
      locator: { kind: "arg", index: 2 },
      rawValue: "MD_KEY_789",
      preselected: true,
      suggestedKey: "MARKETDATA_ARG2",
    });
  });

  it("ignores flag tokens and the server token itself in cli", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["npx", "-y", "newsapi-mcp"],
      serverIndex: 2,
    };
    const chips = detectSecrets(parsed, "newsapi");
    expect(chips).toEqual([]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/detectSecrets.test.ts`
Expected: FAIL — module `../detectSecrets` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/setup/steps/detectSecrets.ts`:

```ts
/**
 * Detect which parts of a parsed MCP connection string are likely secrets,
 * pre-selecting credential-looking values. The result drives editable chips;
 * the user can toggle any chip on or off before saving.
 */
import type { CliParsed, RemoteParsed } from "./parseMcpInput";

export type SecretLocator =
  | { kind: "query"; name: string }
  | { kind: "header"; name: string }
  | { kind: "arg"; index: number };

export interface SecretChip {
  locator: SecretLocator;
  /** Human label, e.g. "apikey", "Authorization", "arg #2". */
  label: string;
  /** Current literal value as pasted. */
  rawValue: string;
  /** Whether the detector thinks this is a secret. */
  preselected: boolean;
  /** Suggested env-var-style key name for the secret bag. */
  suggestedKey: string;
}

const SECRET_NAME_RE =
  /(api[_-]?key|apikey|api[_-]?token|access[_-]?token|token|secret|key)/i;

function sanitizeKey(s: string): string {
  return s.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").toUpperCase();
}

function looksLikeCredential(token: string): boolean {
  // Placeholder-shaped: YOUR_API_KEY, <KEY>, {KEY}
  if (/^(your[_-]|<|\{)/i.test(token)) return true;
  // ALLCAPS_WITH_UNDERSCORES of reasonable length
  if (/^[A-Z0-9_]{6,}$/.test(token)) return true;
  // High-entropy: long, mixed letters + digits, no path/flag punctuation
  if (token.length >= 12 && /[A-Za-z]/.test(token) && /[0-9]/.test(token)) {
    return true;
  }
  return false;
}

export function detectSecrets(
  parsed: RemoteParsed | CliParsed,
  providerId: string,
): SecretChip[] {
  const prefix = sanitizeKey(providerId) || "CONNECTOR";

  if (parsed.kind === "remote") {
    const chips: SecretChip[] = [];
    for (const p of parsed.queryParams) {
      chips.push({
        locator: { kind: "query", name: p.name },
        label: p.name,
        rawValue: p.value,
        preselected: SECRET_NAME_RE.test(p.name),
        suggestedKey: `${prefix}_${sanitizeKey(p.name)}`,
      });
    }
    for (const h of parsed.headers) {
      const isAuth = h.name.toLowerCase() === "authorization";
      chips.push({
        locator: { kind: "header", name: h.name },
        label: h.name,
        rawValue: h.value,
        preselected: isAuth || SECRET_NAME_RE.test(h.name),
        suggestedKey: `${prefix}_${sanitizeKey(h.name)}`,
      });
    }
    return chips;
  }

  // cli: candidate = non-flag tokens after the server token.
  const chips: SecretChip[] = [];
  for (let i = 0; i < parsed.argv.length; i++) {
    if (i <= parsed.serverIndex) continue;
    const tok = parsed.argv[i];
    if (tok.startsWith("-")) continue;
    chips.push({
      locator: { kind: "arg", index: i },
      label: `arg #${i}`,
      rawValue: tok,
      preselected: looksLikeCredential(tok),
      suggestedKey: `${prefix}_ARG${i}`,
    });
  }
  return chips;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/detectSecrets.test.ts`
Expected: PASS (all 5 cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/detectSecrets.ts frontend/src/setup/steps/__tests__/detectSecrets.test.ts
git commit -m "feat(connectors): add detectSecrets for smart-paste chips"
```

---

## Task 5: Frontend — `buildMcpLaunch` (parsed + chips → payload)

**Files:**
- Create: `frontend/src/setup/steps/buildMcpLaunch.ts`
- Test: `frontend/src/setup/steps/__tests__/buildMcpLaunch.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/setup/steps/__tests__/buildMcpLaunch.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { buildMcpLaunch } from "../buildMcpLaunch";
import type { SecretChip } from "../detectSecrets";
import type { RemoteParsed, CliParsed } from "../parseMcpInput";

describe("buildMcpLaunch", () => {
  it("replaces a selected query secret with a placeholder and extracts it", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://mcp.alphavantage.co/mcp",
      queryParams: [{ name: "apikey", value: "AV12345" }],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "AV12345",
        preselected: true,
        suggestedKey: "ALPHAVANTAGE_APIKEY",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode).toEqual({
      kind: "remote_mcp",
      url: "https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_APIKEY}",
      headers: {},
    });
    expect(built.secrets).toEqual({ ALPHAVANTAGE_APIKEY: "AV12345" });
  });

  it("uses the typed value over the raw value when provided", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [{ name: "apikey", value: "YOUR_API_KEY" }],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "YOUR_API_KEY",
        preselected: true,
        suggestedKey: "X_APIKEY",
      },
    ];
    const built = buildMcpLaunch({
      parsed,
      selected: chips,
      values: { X_APIKEY: "real-key-123" },
    });
    expect(built.secrets).toEqual({ X_APIKEY: "real-key-123" });
    expect(built.mode.url).toBe("https://x/mcp?apikey={X_APIKEY}");
  });

  it("keeps non-selected query params literal", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [
        { name: "apikey", value: "AV1" },
        { name: "region", value: "us" },
      ],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "AV1",
        preselected: true,
        suggestedKey: "X_APIKEY",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode.url).toBe("https://x/mcp?apikey={X_APIKEY}&region=us");
  });

  it("replaces a selected cli arg with a placeholder and clears env_keys", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["uvx", "marketdata-mcp-server", "MD_KEY_789"],
      serverIndex: 1,
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "arg", index: 2 },
        label: "arg #2",
        rawValue: "MD_KEY_789",
        preselected: true,
        suggestedKey: "MARKETDATA_ARG2",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode).toEqual({
      kind: "cli_mcp",
      argv: ["uvx", "marketdata-mcp-server", "{MARKETDATA_ARG2}"],
      env_keys: [],
    });
    expect(built.secrets).toEqual({ MARKETDATA_ARG2: "MD_KEY_789" });
  });

  it("embeds the placeholder inside a Bearer header value", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [],
      headers: [{ name: "Authorization", value: "Bearer abc123" }],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "header", name: "Authorization" },
        label: "Authorization",
        rawValue: "Bearer abc123",
        preselected: true,
        suggestedKey: "X_AUTHORIZATION",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode.headers).toEqual({
      Authorization: "Bearer {X_AUTHORIZATION}",
    });
    expect(built.secrets).toEqual({ X_AUTHORIZATION: "abc123" });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/buildMcpLaunch.test.ts`
Expected: FAIL — module `../buildMcpLaunch` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/setup/steps/buildMcpLaunch.ts`:

```ts
/**
 * Turn a parsed MCP input plus the user's confirmed secret selections into a
 * connector launch mode + an extracted secret bag. Selected secrets are
 * replaced in the launch by `{KEY}` placeholders; their values move into the
 * secret bag so the raw key never persists in launch JSON.
 */
import type { ModeIn } from "../../api/connectors";
import type { SecretChip } from "./detectSecrets";
import type { CliParsed, RemoteParsed } from "./parseMcpInput";

export interface BuildMcpLaunchInput {
  parsed: RemoteParsed | CliParsed;
  /** The chips the user confirmed as secrets. */
  selected: SecretChip[];
  /** Optional typed-in secret values, keyed by suggestedKey. */
  values: Record<string, string>;
}

export interface BuiltMcpLaunch {
  mode: ModeIn;
  secrets: Record<string, string>;
}

/** Replace the trailing whitespace-delimited token, or the whole string. */
function placeholderInHeader(value: string, key: string): string {
  if (/\s/.test(value)) {
    return value.replace(/(\S+)\s*$/, `{${key}}`);
  }
  return `{${key}}`;
}

export function buildMcpLaunch(input: BuildMcpLaunchInput): BuiltMcpLaunch {
  const { parsed, selected, values } = input;
  const secrets: Record<string, string> = {};

  const secretValueOf = (chip: SecretChip, extracted: string): void => {
    secrets[chip.suggestedKey] = values[chip.suggestedKey] ?? extracted;
  };

  if (parsed.kind === "remote") {
    const queryByName = new Map<string, SecretChip>();
    const headerByName = new Map<string, SecretChip>();
    for (const c of selected) {
      if (c.locator.kind === "query") queryByName.set(c.locator.name, c);
      if (c.locator.kind === "header") headerByName.set(c.locator.name, c);
    }

    const queryParts = parsed.queryParams.map((p) => {
      const chip = queryByName.get(p.name);
      if (chip) {
        secretValueOf(chip, p.value);
        return `${p.name}={${chip.suggestedKey}}`;
      }
      return `${p.name}=${p.value}`;
    });
    const url =
      queryParts.length > 0
        ? `${parsed.baseUrl}?${queryParts.join("&")}`
        : parsed.baseUrl;

    const headers: Record<string, string> = {};
    for (const h of parsed.headers) {
      const chip = headerByName.get(h.name);
      if (chip) {
        // Extracted value = the credential token (last whitespace segment).
        const token = /\s/.test(h.value)
          ? h.value.trim().split(/\s+/).pop() ?? h.value
          : h.value;
        secretValueOf(chip, token);
        headers[h.name] = placeholderInHeader(h.value, chip.suggestedKey);
      } else {
        headers[h.name] = h.value;
      }
    }

    return { mode: { kind: "remote_mcp", url, headers }, secrets };
  }

  // cli
  const argByIndex = new Map<number, SecretChip>();
  for (const c of selected) {
    if (c.locator.kind === "arg") argByIndex.set(c.locator.index, c);
  }
  const argv = parsed.argv.map((tok, i) => {
    const chip = argByIndex.get(i);
    if (chip) {
      secretValueOf(chip, tok);
      return `{${chip.suggestedKey}}`;
    }
    return tok;
  });

  return { mode: { kind: "cli_mcp", argv, env_keys: [] }, secrets };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/buildMcpLaunch.test.ts`
Expected: PASS (all 5 cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/buildMcpLaunch.ts frontend/src/setup/steps/__tests__/buildMcpLaunch.test.ts
git commit -m "feat(connectors): add buildMcpLaunch payload builder for smart-paste"
```

---

## Task 6: Frontend — `SmartPasteMcpForm` component

**Files:**
- Create: `frontend/src/setup/steps/SmartPasteMcpForm.tsx`
- Test: `frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`

This component composes the three pure modules and performs the single `createConnector` call. It derives `provider_id` from the parse (hostname for remote, server token for cli), lets the user edit it and pick a category, renders the detected chips with per-chip enable + value inputs, and submits.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { SmartPasteMcpForm } from "../SmartPasteMcpForm";
import * as api from "../../../api/connectors";

describe("SmartPasteMcpForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("parses a pasted URL, extracts the apikey as a secret, and submits", async () => {
    const created = vi.fn();
    const row: api.ConnectorRow = {
      id: "c1",
      provider_id: "alphavantage",
      display_name: "alphavantage",
      source: "remote_mcp",
      category: "financial",
      status: "validated",
      last_error: null,
      cached_tools_count: 3,
    };
    const spy = vi
      .spyOn(api, "createConnector")
      .mockResolvedValue(row);

    render(<SmartPasteMcpForm onCancel={() => {}} onCreated={created} />);

    fireEvent.change(screen.getByLabelText(/paste a url or command/i), {
      target: { value: "https://mcp.alphavantage.co/mcp?apikey=AV12345" },
    });

    // Detected secret value is pre-filled from the pasted key.
    expect(await screen.findByDisplayValue("AV12345")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /validate & add/i }));

    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    const payload = spy.mock.calls[0][0];
    expect(payload.source).toBe("remote_mcp");
    expect(payload.launch.modes[0]).toMatchObject({
      kind: "remote_mcp",
      url: "https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_APIKEY}",
    });
    expect(payload.secrets).toEqual({ ALPHAVANTAGE_APIKEY: "AV12345" });
    expect(created).toHaveBeenCalledWith(row);
  });

  it("shows an error and does not submit when input is unclassifiable", () => {
    const spy = vi.spyOn(api, "createConnector");
    render(<SmartPasteMcpForm onCancel={() => {}} onCreated={() => {}} />);
    fireEvent.change(screen.getByLabelText(/paste a url or command/i), {
      target: { value: "https://" },
    });
    expect(screen.getByRole("button", { name: /validate & add/i })).toBeDisabled();
    expect(spy).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`
Expected: FAIL — module `../SmartPasteMcpForm` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `frontend/src/setup/steps/SmartPasteMcpForm.tsx`:

```tsx
import { useMemo, useState, type FormEvent } from "react";
import {
  createConnector,
  type Category,
  type ConnectorRow,
  type CreateConnectorInput,
} from "../../api/connectors";
import { ApiError } from "../../api/client";
import { parseMcpInput } from "./parseMcpInput";
import { detectSecrets, type SecretChip } from "./detectSecrets";
import { buildMcpLaunch } from "./buildMcpLaunch";

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "financial", label: "Financial" },
  { value: "news", label: "News" },
  { value: "social", label: "Social" },
  { value: "web_search", label: "Web search" },
];

interface Props {
  onCancel: () => void;
  onCreated: (row: ConnectorRow) => void;
}

function deriveProviderId(text: string): string {
  const parsed = parseMcpInput(text);
  if (parsed.kind === "remote") {
    try {
      return new URL(parsed.baseUrl).hostname.split(".").slice(-2, -1)[0] ?? "";
    } catch {
      return "";
    }
  }
  if (parsed.kind === "cli" && parsed.serverIndex >= 0) {
    const tok = parsed.argv[parsed.serverIndex] ?? "";
    const base = tok.includes("/") ? tok.slice(tok.lastIndexOf("/") + 1) : tok;
    return base.replace(/-mcp$|^server-/g, "");
  }
  return "";
}

export function SmartPasteMcpForm({ onCancel, onCreated }: Props) {
  const [text, setText] = useState("");
  const [providerId, setProviderId] = useState("");
  const [providerEdited, setProviderEdited] = useState(false);
  const [category, setCategory] = useState<Category>("financial");
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = useMemo(() => parseMcpInput(text), [text]);
  const effectiveProvider = providerEdited
    ? providerId
    : deriveProviderId(text);

  const chips: SecretChip[] = useMemo(() => {
    if (parsed.kind === "error") return [];
    return detectSecrets(parsed, effectiveProvider || "connector");
  }, [parsed, effectiveProvider]);

  // Initialize enable/value state for newly-seen chips (pre-selected + raw value).
  const chipState = useMemo(() => {
    const en: Record<string, boolean> = {};
    const va: Record<string, string> = {};
    for (const c of chips) {
      en[c.suggestedKey] = enabled[c.suggestedKey] ?? c.preselected;
      const isPlaceholder = /^(your[_-]|<|\{)/i.test(c.rawValue);
      va[c.suggestedKey] =
        values[c.suggestedKey] ?? (isPlaceholder ? "" : c.rawValue);
    }
    return { en, va };
  }, [chips, enabled, values]);

  const canSubmit =
    parsed.kind !== "error" && text.trim().length > 0 && !submitting;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (parsed.kind === "error") return;
    setError(null);
    setSubmitting(true);
    try {
      const selected = chips.filter((c) => chipState.en[c.suggestedKey]);
      const built = buildMcpLaunch({
        parsed,
        selected,
        values: chipState.va,
      });
      const payload: CreateConnectorInput = {
        provider_id: (effectiveProvider || "connector").trim(),
        display_name: (effectiveProvider || "connector").trim(),
        source: parsed.kind === "remote" ? "remote_mcp" : "cli_mcp",
        category,
        launch: { modes: [built.mode] },
        secrets: built.secrets,
      };
      const row = await createConnector(payload);
      onCreated(row);
    } catch (err) {
      let msg = "Failed to add connector.";
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        msg = body?.detail ?? err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      aria-label="Add MCP connector"
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <label className="block text-xs text-text-secondary">
        Paste a URL or command
        <textarea
          aria-label="paste a url or command"
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="https://mcp.example.com/mcp?apikey=YOUR_KEY   —or—   uvx some-mcp-server YOUR_KEY"
          className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
        />
      </label>

      {parsed.kind === "error" && text.trim().length > 0 ? (
        <p role="alert" className="text-xs text-feedback-error">
          {parsed.error}
        </p>
      ) : null}

      {parsed.kind !== "error" && text.trim().length > 0 ? (
        <p data-testid="detected-kind" className="text-[10px] text-text-secondary">
          Detected: {parsed.kind === "remote" ? "Remote MCP server" : "Local MCP server"}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-text-secondary">
          Provider id
          <input
            type="text"
            aria-label="provider id"
            value={effectiveProvider}
            onChange={(e) => {
              setProviderEdited(true);
              setProviderId(e.target.value);
            }}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <label className="text-xs text-text-secondary">
          Category
          <select
            aria-label="category"
            value={category}
            onChange={(e) => setCategory(e.target.value as Category)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {chips.length > 0 ? (
        <fieldset className="space-y-1">
          <legend className="text-xs text-text-secondary">Detected secrets</legend>
          <p className="text-[10px] text-text-secondary">
            Stored on the server, never sent to the LLM. Toggle off anything that
            is not a secret.
          </p>
          {chips.map((c) => (
            <div key={c.suggestedKey} className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`treat ${c.label} as secret`}
                checked={chipState.en[c.suggestedKey]}
                onChange={(e) =>
                  setEnabled((prev) => ({
                    ...prev,
                    [c.suggestedKey]: e.target.checked,
                  }))
                }
              />
              <span className="w-20 shrink-0 text-[10px] text-text-secondary">
                {c.label}
              </span>
              <input
                type="password"
                aria-label={`secret value ${c.label}`}
                value={chipState.va[c.suggestedKey]}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [c.suggestedKey]: e.target.value,
                  }))
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </div>
          ))}
        </fieldset>
      ) : null}

      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={!canSubmit}
          className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Validating..." : "Validate & add"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`
Expected: PASS (both cases).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/setup/steps/SmartPasteMcpForm.tsx frontend/src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx
git commit -m "feat(connectors): add SmartPasteMcpForm component"
```

---

## Task 7: Frontend — mount the smart-paste form + soften the "encrypted" wording

**Files:**
- Modify: `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` (add a "Add MCP connector" entry that renders `SmartPasteMcpForm`; keep the existing `AddConnectorForm` reachable as "Advanced")
- Modify: `frontend/src/setup/steps/AddConnectorForm.tsx:786-789` (the secrets fieldset help text)

- [ ] **Step 1: Soften the false "encrypted" claim**

In `AddConnectorForm.tsx`, change the secrets help text:

Replace:

```tsx
        <p className="text-[10px] text-text-secondary">
          Stored encrypted on the server. Never sent to the LLM. Key is the env var
          name; value is the actual secret.
        </p>
```

with:

```tsx
        <p className="text-[10px] text-text-secondary">
          Stored on the server, never sent to the LLM. Key is the env var
          name; value is the actual secret.
        </p>
```

- [ ] **Step 2: Wire SmartPasteMcpForm into the admin panel**

Read `frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx` first to match its existing add-flow state pattern (it already toggles `AddConnectorForm`). Add a sibling entry point — a button labeled "Add MCP connector" that renders `SmartPasteMcpForm` with the same `onCreated` (refresh the connector list) and `onCancel` (close) handlers the panel already uses for `AddConnectorForm`. Keep the existing "Add connector (advanced)" entry pointing at `AddConnectorForm` so `python_lib` and manual editing remain available.

Import at the top of the file:

```tsx
import { SmartPasteMcpForm } from "../../../setup/steps/SmartPasteMcpForm";
```

Exact JSX placement follows the panel's existing add-form conditional; reuse the same `onCreated`/`onCancel` callbacks already defined there. Do not duplicate list-refresh logic — call the same handler.

- [ ] **Step 3: Verify the admin panel still type-checks and renders**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/components/settings/admin`
Expected: PASS (no type errors; existing admin-panel tests still green).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/settings/admin/ConnectorsAdminPanel.tsx frontend/src/setup/steps/AddConnectorForm.tsx
git commit -m "feat(connectors): mount smart-paste MCP add; correct secrets wording"
```

---

## Task 8: Integration verification

**Files:** none (verification only)

- [ ] **Step 1: Backend — full connector + dispatcher suites**

Run: `uv run pytest packages/server/tests/services/test_connectors_service.py packages/server/tests/test_services/test_dispatcher_factory_substitutions.py packages/core/tests/connectors -v`
Expected: PASS.

- [ ] **Step 2: Backend — lint/format**

Run: `uv run ruff check packages/server/src/openlia_server/services/dispatcher_factory.py packages/server/src/openlia_server/services/connectors_service.py`
Expected: no errors.

- [ ] **Step 3: Frontend — new module + component tests**

Run: `cd frontend && npx vitest run src/setup/steps/__tests__/parseMcpInput.test.ts src/setup/steps/__tests__/detectSecrets.test.ts src/setup/steps/__tests__/buildMcpLaunch.test.ts src/setup/steps/__tests__/SmartPasteMcpForm.test.tsx`
Expected: PASS.

- [ ] **Step 4: Frontend — typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: clean typecheck, successful build.

- [ ] **Step 5: Manual smoke (document only — requires a real server)**

Not automated. When a server is available, verify end to end:
- Paste `https://mcp.alphavantage.co/mcp?apikey=<real key>` → detected Remote, apikey pre-filled → Validate & add → row shows `validated` with tools > 0.
- Paste `uvx marketdata-mcp-server <real key>` → detected Local, arg pre-selected → Validate & add → `validated`.
- Paste a key-less or bad-key server → `failed` with the "no tools" or connect-error message.
- Confirm the stored connector detail shows `{NAME}` placeholders in launch, the secret key in `secret_keys`, and the raw key absent from `launch`.

- [ ] **Step 6: Commit (if any lint/format fixups were needed)**

```bash
git add -A
git commit -m "chore(connectors): smart-paste MCP integration verification fixups"
```

---

## Self-Review notes

- **Spec coverage:** one paste box (T6), classify remote/local (T3), extract key from URL query / CLI arg / header into secrets with `{NAME}` placeholder (T4/T5), argv substitution backend gap (T1), validation connect + list_tools >= 1 (T2), soften encrypted wording (T7). All spec sections map to a task.
- **python_lib untouched:** no task modifies the python_lib branch; `AddConnectorForm` stays as Advanced (T7).
- **Type consistency:** `ModeIn` reused from `api/connectors`; `SecretChip` / `SecretLocator` defined in T4 and consumed unchanged in T5/T6; `RemoteParsed`/`CliParsed`/`parseMcpInput` defined in T3 and consumed in T4/T5/T6; `buildMcpLaunch({ parsed, selected, values })` signature identical across T5 test and T6 caller.
```
