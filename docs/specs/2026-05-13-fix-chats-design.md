# fix-chats — chat response quality and continuity

**Branch:** `fix-chats`
**Date:** 2026-05-13
**Status:** design approved, exemplar content TBD (drilled per-file at implementation time)

## 1. Problem

Secretary chat exhibits three reproducible failures and one quality bar miss:

1. **Unprompted self-introduction.** Lia opens replies with "I'm Lia — short for Little Investor Assistant." every turn, even after she has already introduced herself or the user has not asked.
2. **Asks for ticker basket on general market questions.** Prompts like "give me a market snapshot," "what are today's main movers," "what's the market doing" sometimes work, but often Lia replies asking the user to specify "anchor tickers." Behavior is non-deterministic across runs.
3. **Loses thread on follow-ups.** User replies like "reformat this into a clean premarket snapshot" cause Lia to ask for the source content — even when the content is her own prior assistant turn in the same session.
4. **Quality bar.** Responses feel inconsistent in tone, vocabulary, and structure. Some are sharp and expert-shaped; others are bland or generic.

## 2. Root cause

Pure prompt-side. Server-side history persistence and message passing are correct: `packages/server/src/openlia_server/routes/chat_stream.py:103-104` already loads the full session history and passes it as `RuntimeChatMessage` to the runtime. The model receives the conversation; it just doesn't act on it reliably under the current system prompt.

Confirmed by:
- Same-session reproduction with full message history flowing.
- Cross-model reproduction (multiple GPT-class models exhibit the same behaviors), so the fix targets the prompt surface, not a single provider.

The current `lia_identity.yaml.j2:9` rule is the explicit source of issue #1:

> "When the user asks who you are **or you have not been introduced yet** in this conversation, introduce yourself..."

The bolded clause is interpreted at every turn because the model has no reliable way to confirm whether the introduction has already happened.

## 3. Scope

- **Primary target:** Secretary chat (`packages/core/src/openlia/prompts/secretary.yaml`).
- **Secondary:** the 6 other chat departments — spot-check and port matching changes (lia_identity edits apply to all 7 by inclusion).
- **Out of scope:** any change to the chat history plumbing, session model, or message persistence.

## 4. Architecture

Five workstreams, each independently mergeable.

### 4.A. `lia_identity.yaml.j2` — two rule edits

Affects all 7 departments via shared include.

- **Self-intro rule.** Tighten to: introduce only when explicitly asked ("who are you?", "what is Lia?", "what's your name?"). Drop the "or you have not been introduced yet" branch. The UI `welcome` message and the OpenLIA brand handle the first impression.
- **Continuity rule.** New paragraph: "You are in an ongoing conversation. When the user says 'this', 'that', 'it', 'redo', 'reformat', 'summarize', 'expand', etc., they are referring to your most recent assistant message in this thread. Never ask the user to re-paste content that already appears above in the conversation." Followed by one short worked example: a user follow-up referencing prior assistant content, the wrong response (asking for source), and the right response (acting on the content above).

### 4.B. New Secretary-side shared partials

Four new files under `packages/core/src/openlia/prompts/shared/`:

- **`market_conventions.yaml.j2`** — compact desk cheat sheet. Risk-on/off pairings (SPY/QQQ + HYG strength + TLT/GLD soft = risk-on; flip = risk-off). 11 SPDR sector ETFs (XLK / XLF / XLE / XLV / XLP / XLY / XLU / XLI / XLB / XLRE / XLC). Duration semantics (TLT long-duration; SHY short-duration; long-end yields move inverse to TLT). Credit (HYG vs LQD ratio for credit risk-on/off). Dollar (DXY up → headwind for gold, oil, EM, US multinationals). Vol regime (VIX < 15 calm, 15-20 normal, > 25 stressed; term-structure inversion = acute fear).
- **`snapshot_format.yaml.j2`** — locked structure Lia renders for "market snapshot" requests:

  ```
  **Tape**       — SPY / QQQ / DIA / IWM
  **Risk**       — VIX, HYG, TLT
  **Macro**      — DXY, GLD, USO
  **Crypto**     — BTC
  **Top movers** — top-2 + bottom-2 of the 11 SPDR sectors by % change
  **Read-through** — 1-3 short bullets, what the tape says
  **Watch next** — one line, what would confirm or break the read
  ```

- **`autonomous_defaults.yaml.j2`** — "decide, don't ask." Explicit triggers:
  - "market snapshot" / "tape" / "what's the market doing" / "movers" / "what's leading" → use default basket, render snapshot format, never ask.
  - Named tickers → answer directly, no clarification.
  - Ask only when the request is genuinely ambiguous AND a sensible default would mislead.

- **`finance_voice.yaml.j2`** — four sub-blocks:
  - **Persona tightening (without faking credentials).** "You think like a 20-year multi-asset sell-side strategist briefing a portfolio manager in 90 seconds. You're fluent across equities, rates, FX, and credit." No real-firm name (compliance / off-brand / fabrication risk).
  - **Audience model.** "User is an experienced retail investor — knows tickers, sectors, and basic macro concepts. Define technical jargon briefly inline when used (per existing voice rule 4); skip 101-level explanations of things like 'what a stock is' or 'how an ETF works.'"
  - **Vocabulary anchors.**
    - **Use:** tape, read-through, risk-on/off, duration, setup, frame, re-rate, multiple compression, spread tightening, basis points (bps), term structure.
    - **Avoid:** "great question," "I hope this helps," "let me know if," "as an AI," "in conclusion," "delve into," "moreover," "furthermore."
  - **Framework priming.** "Default answer shape: (1) the read — what's happening, (2) the why — what's driving it, (3) what to watch."

### 4.C. Exemplar library + deterministic conditional injection

New directory: `packages/core/src/openlia/prompts/shared/exemplars/`

Files at launch:

- `general.yaml.j2` — always-on baseline. One well-formed answer to a generic market question.
- `snapshot.yaml.j2` — triggers: `snapshot`, `tape`, `movers`, `what's the market doing`, `what's leading`.
- `single_stock.yaml.j2` — triggers: ticker regex (`\$?[A-Z]{1,5}\b` plus context cues), "read on X", "thoughts on $X".
- `continuation.yaml.j2` — triggers: `reformat`, `redo`, `do that`, `expand`, `tighten`, `shorten`, `same thing for`. Directly addresses Issue #3.

New module: `packages/server/src/openlia_server/services/exemplar_selector.py`.
- Pure-Python regex/keyword classifier. No LLM call.
- Input: latest user message (the `q` parameter).
- Output: list of exemplar names (e.g., `["general", "snapshot"]`).
- Pattern mirrors `openlia_server.services.graph_retrieval.retrieve_memory_block` exactly: same call-site shape, same near-zero overhead when no match.

Wiring in `chat_stream.py`:
- After `memory_block` is computed (line 112), compute `selected_exemplars`.
- Pass to `_event_source` as a new kwarg alongside `memory_block`.
- Render in prompt at a fixed dynamic position (see Section 5).

**Important: exemplar *content* is intentionally TBD in this spec.** Content will be drilled one file at a time during implementation. Each exemplar must demonstrate: snapshot-format adherence, voice anchors used (not just listed), framework structure, expert audience-model tone.

### 4.D. User-editable default market basket

**DB.** New `default_market_basket` JSON column on `user_prefs` table (Alembic migration). Seed value per user:

```json
{
  "tape":   ["SPY", "QQQ", "DIA", "IWM"],
  "risk":   ["VIX", "HYG", "TLT"],
  "macro":  ["DXY", "GLD", "USO"],
  "crypto": ["BTC"]
}
```

**Server.** New REST surface under existing settings router:
- `GET /api/settings/preferences/market-basket` — returns user's basket (creates seeded default on first read).
- `PUT /api/settings/preferences/market-basket` — writes user's basket. Validates: each section is a list of strings, ticker count per section ≤ 12, ticker regex `^[A-Z0-9.^-]{1,10}$`.

**Frontend.** Settings → Preferences → new "Market Snapshot Basket" panel. Four rows (Tape / Risk / Macro / Crypto), each a comma-separated input (UI shape per Q10:B). Save button. Optimistic update + toast on success.

**Render.** Basket injected into Secretary system prompt at request time, same flow as `memory_block` — passed as render variable, rendered as a small Markdown table in the dynamic prompt section.

**Note: sector ETFs for "Top movers" stay hardcoded** in `snapshot_format.yaml.j2` (the 11 SPDR sectors are a universal taxonomy — not user-editable).

### 4.E. Prompt cache wiring

Add a static/dynamic boundary so providers that support prefix caching can amortize the static prompt cost.

- **Anthropic adapter:** insert `cache_control: {"type": "ephemeral"}` on the last static block (the one just before `memory_block` renders).
- **OpenAI adapter:** prefix-stable ordering already enables automatic caching; verify by inspecting `prompt_tokens_details.cached_tokens` in response usage.
- **OpenRouter / Ollama:** best-effort; cache is no-op where provider doesn't support it.

## 5. Prompt order

Order matters for both cache stability and readability. After this change, the Secretary system prompt renders in this fixed order:

```
STATIC (cacheable):
  1.  lia_identity                  (shared)
  2.  desk description              (Secretary-specific)
  3.  market_conventions            (new, Secretary)
  4.  snapshot_format               (new, Secretary)
  5.  autonomous_defaults           (new, Secretary)
  6.  finance_voice                 (new, Secretary)
  7.  exemplars/general             (new, always-on)
  8.  skills_menu                   (existing)
  9.  attachments_inline            (existing)
  10. response_length               (existing)
  11. output_discipline             (existing)
  12. chat_rich_blocks              (existing)
  13. chat_formatting               (existing, from PR #107)
  --- CACHE BREAKPOINT ---
DYNAMIC (per-request):
  14. memory_block                  (existing — graph_retrieval)
  15. matched exemplar(s)           (new — exemplar_selector)
  16. user.default_market_basket    (new — rendered as table)
  17. conversation history          (existing)
  18. user_input (latest, wrapped)  (existing)
```

## 6. Testing

- **Python sanity tests** (mirror `packages/core/tests/test_llm/test_runtime/test_chat_formatting_in_dept_prompts.py`):
  - Each new partial loads cleanly across the departments where it's wired.
  - Exemplar files all parse as Jinja templates.
- **Exemplar selector unit tests** (`packages/server/tests/services/test_exemplar_selector.py`):
  - Each trigger pattern returns the expected exemplar.
  - Unmatched messages return `["general"]` as the fallback baseline.
  - Multiple matches merge correctly (e.g., snapshot + continuation when user says "redo the snapshot").
- **Server tests** for basket route: GET seeds default, PUT validates and persists, malformed input is rejected.
- **Frontend tests** for basket Settings panel: existing settings-test patterns.
- **Manual browser smoke** after merge:
  1. New chat → first message "what's the market doing today" → snapshot rendered without asking.
  2. Same chat → "reformat that without Top movers" → succeeds without asking for source.
  3. Same chat → second turn "what's the read on TLT" → no self-intro prefix.
  4. Settings → edit basket → reload chat → new basket reflected in response.

## 7. Commit slicing

Seven commits, each independently mergeable. Commit 1 alone fixes issues #1 and #3 — it's worth shipping first even if the rest takes more time.

1. **`fix(prompts): tighten lia_identity intro + continuity rules`** — smallest, biggest immediate impact (fixes #1, #3).
2. **`feat(prompts): market_conventions + snapshot_format + autonomous_defaults`** — fixes #2 with hardcoded basket.
3. **`feat(prompts): finance_voice partial + general exemplar`** — addresses quality bar.
4. **`feat(chat): exemplar library + deterministic selector + chat_stream wiring`** — scales tone control across question types.
5. **`feat(prefs): default_market_basket — schema, migration, route, Settings UI`** — user pref persistence.
6. **`feat(llm): prompt cache breakpoint`** — cost + latency.
7. **`chore(prompts): port + spot-check across 6 other chat departments`** — propagation.

## 8. Out of scope (deferred / not in this branch)

- **Skill-bundled exemplars.** Each skill carrying its own exemplar field is a larger refactor; the standalone library covers the gap for now.
- **LLM-based intent classifier.** Two-stage prompting (classify → respond) is slower and more expensive than deterministic regex routing; revisit only if regex coverage proves insufficient.
- **Per-department market baskets.** All chat departments share the user's single basket. Splitting per-desk is a follow-up if real demand emerges.
- **Multi-language.** English only for now (matches existing project memory).
- **Top-movers single-name expansion.** Stays at SPDR sector ETFs; single-name leaders are a future enhancement.

## 9. Open items for implementation

These are deliberately left unresolved in the spec; each one is drilled at implementation time, one at a time:

- **Exemplar content for all four files** (`general`, `snapshot`, `single_stock`, `continuation`). Quality of few-shot exemplars is the single biggest tone lever — each one gets written, reviewed, and approved before commit.
- **Exact regex/keyword triggers** in `exemplar_selector.py`. First-pass triggers are listed in Section 4.C; final patterns drilled during commit 4.
- **Worked example text** inside the `lia_identity` continuity rule (commit 1). Short, in-voice, mirrors the real failure mode the user reported.
- **Vocabulary "avoid" list refinement** in `finance_voice.yaml.j2`. Section 4.B has the starter list; expansion happens after a real-output review.
