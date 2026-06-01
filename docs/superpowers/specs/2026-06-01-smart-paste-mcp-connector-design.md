# Smart-paste MCP connector add — design

Date: 2026-06-01
Status: Approved (brainstorming), pending implementation plan
Scope owner: connector subsystem (v2)

## Problem

Adding a custom MCP connector today is awkward and the secret model is too narrow:

- The add form (`frontend/src/setup/steps/AddConnectorForm.tsx`) requires the user to
  pick a mode and hand-fill mode-specific fields.
- An MCP API key can only flow in as an **env var** (`cli_mcp` injects `secrets[k]`
  for each `k` in `env_keys`; `remote_mcp` substitutes `{NAME}` in URL/headers).
- Real-world MCP servers put the key elsewhere:
  - `https://mcp.alphavantage.co/mcp?apikey=YOUR_API_KEY` — key in a URL **query param**.
  - `uvx marketdata-mcp-server YOUR_API_KEY` — key as a positional **CLI argument**.
- The CLI-arg-as-secret case is **unsupported**: there is no argv substitution, so the
  user must store the raw key in plaintext `launch` JSON.
- "Validated" overpromises: custom connectors are validated with `list_tools()` only,
  so a wrong key can pass green and only fail at runtime.
- The form claims secrets are "Stored encrypted on the server" — the `secrets` column is
  plain JSON, so that claim is false.

These examples are illustrative. The design must not hard-code those specific URLs or
commands.

## Goals

1. One paste box that accepts a remote URL **or** a local command and figures out the rest.
2. Get the API key out of plaintext `launch` JSON into the connector secret bag, wherever
   the provider places it (URL query param, CLI arg, header).
3. Validation that proves the server is reachable and usable (connect + `list_tools`,
   require >= 1 tool).
4. No false claims about secret encryption.

## Non-goals

- `python_lib` connectors. Left exactly as-is; their branch of the existing
  `AddConnectorForm` stays available as an "Advanced" option.
- OAuth-authenticated MCP servers (still unsupported; out of scope).
- Encrypting the `secrets` column at rest (tracked separately; see "Secrets at rest").
- Changes to runtime dispatch, the Earnings Update per-user toggle model, the
  `connectors` table schema, or multi-mode failover.

## Scope

New streamlined add path for **`remote_mcp` + `cli_mcp` only**. Reuses the existing
`launch` / `secrets` / `cached_tools` columns and the existing transports. One backend
behavior change (argv substitution); everything else is new parsing/UX plus a validation
tightening for these two sources.

## User flow

1. A single textarea: "Paste a URL or command."
2. On input, **classify** the pasted text:
   - Starts with `http://` or `https://` -> `remote_mcp`.
   - Looks like `{ "mcpServers": ... }` JSON, or starts with `npx ` -> `cli_mcp`
     (reuse existing `parseMcpConfig` / `parseNpxCommand` parsers).
   - Otherwise tokenize as a shell command -> `cli_mcp` (handles
     `uvx marketdata-mcp-server KEY`, `npx ...`, `uv run ...`, etc.).
3. **Parse to a structure** and render its parts as labeled chips:
   - remote: the base URL plus one chip per query param; one chip per header value.
   - cli: one chip per argv token (the resolved server/package name marked as non-secret).
   Each "value-ish" chip is selectable as a secret. Best-guess secrets are pre-selected
   (see "Secret detection").
4. The user confirms or adjusts which chips are secrets, types the secret value(s) if the
   pasted string used a placeholder rather than a real key, and edits the auto-suggested
   `provider_id` and `category`.
5. **Validate & add** -> connect + `list_tools` -> require >= 1 tool -> `validated`.

The detection is a *suggestion*. The user can always toggle any chip on/off as a secret.
Nothing is auto-committed without the confirm step.

## Secret detection (with manual override)

- **Remote URL:** a query param is pre-selected as a secret when its name matches
  `(?i)api[_-]?key|apikey|api[_-]?token|access[_-]?token|token|secret|key`.
  (AlphaVantage `apikey` -> pre-selected.) Header values are selectable but not
  auto-selected unless the header name matches the same pattern or is `Authorization`.
- **CLI argv:** every token after the resolved server/package name is a candidate.
  Pre-select a token that looks like a credential: placeholder-shaped (`YOUR_*`,
  ALLCAPS_WITH_UNDERSCORES) or high-entropy (long, mixed-case/digits, no spaces).
  (`uvx marketdata-mcp-server KEY` -> arg #2 pre-selected.)
- For each selected secret:
  - Extract the value into `secrets` under an auto-generated key
    `<PROVIDER>_<PARAM>` uppercased (e.g. `ALPHAVANTAGE_APIKEY`,
    `MARKETDATA_ARG2`). The key name is editable.
  - Replace the value in the stored `launch` with a `{NAME}` placeholder token.
  - The raw key never persists in `launch` JSON; it lives only in `secrets`.

If the pasted string already contains a placeholder (`YOUR_API_KEY`, `{API_KEY}`), the
chip is pre-selected and its value field starts empty for the user to fill.

## Backend change (the one real gap)

**Extend `{NAME}` substitution to `cli_mcp` argv.**

- Today `dispatcher_factory._build_transport` substitutes `{NAME}` from secrets into the
  `remote_mcp` URL and headers, but the `cli_mcp` branch passes argv through untouched and
  only projects `env_keys` into the child env.
- Change: in the `cli_mcp` branch, substitute `{NAME}` placeholders in each argv token
  from `secrets` (same `_substitute_secrets` helper already used for URLs). A token with no
  matching secret is left literal so a missing key surfaces as an obvious failure.
- Because both validation (`_validate_launch`) and runtime (`_prepare_connector`) build
  transports through `_build_transport`, this single change covers both paths.
- No schema change. `cli_mcp` mode keeps `argv` + `env_keys`; argv tokens may now contain
  `{NAME}` placeholders. Env-var-based secrets continue to work unchanged.

## Validation & errors

For `remote_mcp` / `cli_mcp` connectors added through this path:

- `_validate_launch` opens the session and calls `list_tools()`.
- Require **>= 1 tool**; zero tools -> `failed`.
- Persist discovered tools to `cached_tools`, set `status = validated`, on success.
- Surface the distinct failure shapes with actionable messages:
  - classify-failed (could not tell a URL from a command) — caught client-side before submit.
  - connect/initialize failed — likely a bad key, wrong endpoint, or (cli) a missing host
    binary; include the underlying error.
  - zero tools returned — server reachable but exposed nothing; the key may be unauthorized.

This matches the agreed validation rigor: connect + `list_tools`, require >= 1 tool. No
tool is actually invoked (we cannot know which tool is side-effect-free on an arbitrary
server).

## Secrets at rest

The current form text "Stored encrypted on the server" is false — `Connector.secrets` is a
plain JSON column. For this increment, **soften the wording** to a truthful statement, e.g.
"Stored on the server, never sent to the LLM." Actually encrypting the column is a separate,
larger piece of work and is out of scope here.

## Architecture / components

New, focused units:

- `frontend/src/setup/steps/parseMcpInput.ts` (new) — pure classifier + structural parser.
  Input: pasted text. Output: a discriminated union
  `{ kind: "remote", baseUrl, queryParams[], headers[] } | { kind: "cli", argv[] } | { error }`.
  Reuses `parseMcpConfig` / `parseNpxCommand`; adds bare-shell-command tokenization.
- `frontend/src/setup/steps/detectSecrets.ts` (new) — pure secret-candidate detector over
  the parsed structure; returns chips with a `preselected` flag and a suggested key name.
- A new "Add MCP connector (smart paste)" UI — either a new component or a new top branch
  inside `AddConnectorForm`, with the existing per-mode fields demoted under "Advanced".
  Decision deferred to the implementation plan; preference is a small new component so the
  existing form stays intact for `python_lib`.
- `dispatcher_factory._build_transport` — argv substitution in the `cli_mcp` branch.
- `connectors_service._validate_launch` — the >= 1 tool requirement for these sources.

Each pure unit (parse, detect, substitute) is independently testable with no I/O.

## Data flow

paste text
  -> parseMcpInput (classify + structure)
  -> detectSecrets (preselect candidates)
  -> user confirms chips + names + provider_id + category
  -> build LaunchIn: secrets extracted to `secrets`, placeholders left in `launch`
  -> POST /connectors (create) -> _validate_launch (connect + list_tools >= 1)
  -> validated row with cached_tools
  -> runtime: _build_transport substitutes {NAME} into URL/headers/argv from secrets

## Testing

- `parseMcpInput`: remote URL with `?apikey=`, `uvx pkg KEY`, `npx -y pkg`, mcpServers JSON,
  bare command with flags, unclassifiable input.
- `detectSecrets`: URL apikey preselected, header Authorization preselected, cli credential
  token preselected, no-secret case, multi-secret case, placeholder-shaped tokens.
- Backend: argv `{NAME}` substitution resolves from secrets and leaves unmatched tokens
  literal; both `remote` and `cli` validation green-path with a fake session returning
  >= 1 tool, red-path on zero tools and on connect error.
- Frontend: one flow test for classify -> chip-confirm -> submit payload shape.

## Open questions

- New component vs new branch in `AddConnectorForm` — settle in the implementation plan.
- Auto-suggested `provider_id` source: hostname for remote, package name for cli. Editable
  either way; exact derivation is an implementation detail.
</content>
</invoke>
