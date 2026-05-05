# Connector Tool Enum Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode EODHD `financial_news.t` standard topic vocabulary as a JSON Schema `enum` in the connector tool override so the model picks valid tags on the first call and Anthropic's tool-use validator structurally rejects hallucinated values like `"general"`.

**Architecture:** Extend the existing `tool_overrides` mechanism on `BuiltInTemplate` (no infra change). Add the 53-tag enum to `_FINANCIAL_NEWS_OVERRIDE` in `eodhd.py`, augment the description with a steering hint pointing broad-market queries to `s` with index tickers, then trigger connector revalidation so the live `cached_tools` row in the DB carries the new schema.

**Tech Stack:** Python 3.13, FastAPI, SQLite (`openlia-v2.db`), pytest, ruff. uv package manager. Anthropic schema validator (consumed by OpenRouter adapter). No new dependencies.

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `packages/core/src/openlia/connectors/builtins/eodhd.py` | EODHD built-in template + per-tool overrides | Modify: add `_FINANCIAL_NEWS_STANDARD_TAGS` constant; replace `_FINANCIAL_NEWS_OVERRIDE` schema with enum + steering description |
| `packages/core/tests/connectors/builtins/test_eodhd.py` | Snapshot the EODHD template's invariants | Modify: add tests asserting `enum` present, length 53, lowercase, no duplicates; assert steering hint in description |

No new files. No production-code changes outside `eodhd.py`. The override application path (`_apply_tool_overrides`), dispatcher constraint enforcement (`require_one_of`), and chat runtime are all untouched — they already work and will pick up the richer schema automatically once `cached_tools` is refreshed.

---

## Task 1: Define standard-tag constant

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/eodhd.py` (insert above `_FINANCIAL_NEWS_OVERRIDE` block, after line 134)
- Test: `packages/core/tests/connectors/builtins/test_eodhd.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/connectors/builtins/test_eodhd.py`:

```python
from openlia.connectors.builtins.eodhd import _FINANCIAL_NEWS_STANDARD_TAGS


def test_financial_news_standard_tags_constant() -> None:
    """The standard-tag list is the source of truth for the financial_news
    `t` enum. Lock its size, casing, and uniqueness so a careless edit
    doesn't quietly drop a valid value."""
    assert len(_FINANCIAL_NEWS_STANDARD_TAGS) == 53
    assert len(set(_FINANCIAL_NEWS_STANDARD_TAGS)) == 53, "duplicate tags"
    assert all(tag == tag.lower() for tag in _FINANCIAL_NEWS_STANDARD_TAGS), (
        "all tags must be lowercase to match EODHD API"
    )
    # Spot-check anchors from the EODHD docs.
    for anchor in ("earnings results", "price target", "initial public offering", "zacks rank"):
        assert anchor in _FINANCIAL_NEWS_STANDARD_TAGS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py::test_financial_news_standard_tags_constant -v`
Expected: FAIL with `ImportError: cannot import name '_FINANCIAL_NEWS_STANDARD_TAGS'`

- [ ] **Step 3: Add the constant**

Insert into `packages/core/src/openlia/connectors/builtins/eodhd.py` immediately above the existing `_FINANCIAL_NEWS_OVERRIDE` block (around line 137, before the comment that begins with `# EODHD's financial_news SDK signature...`):

```python
# EODHD's documented standard topic-tag vocabulary for the financial_news
# endpoint. Source: https://eodhd.com/financial-apis/stock-market-financial-news-api
# Anthropic's tool validator can enforce these as a schema enum so the
# model can't hallucinate an unsupported tag (e.g. "general") that the
# upstream API rejects with "Incorrect value was fullfiled for s or t".
# EODHD also returns AI-auto-detected tags beyond this list, but those
# are an open vocabulary, not a guaranteed contract — intentionally
# excluded from the enum.
_FINANCIAL_NEWS_STANDARD_TAGS: tuple[str, ...] = (
    "balance sheet",
    "capital employed",
    "class action",
    "company announcement",
    "consensus eps estimate",
    "consensus estimate",
    "credit rating",
    "discounted cash flow",
    "dividend payments",
    "earnings estimate",
    "earnings growth",
    "earnings per share",
    "earnings release",
    "earnings report",
    "earnings results",
    "earnings surprise",
    "estimate revisions",
    "european regulatory news",
    "financial results",
    "fourth quarter",
    "free cash flow",
    "future cash flows",
    "growth rate",
    "initial public offering",
    "insider ownership",
    "insider transactions",
    "institutional investors",
    "institutional ownership",
    "intrinsic value",
    "market research reports",
    "net income",
    "operating income",
    "present value",
    "press releases",
    "price target",
    "quarterly earnings",
    "quarterly results",
    "ratings",
    "research analysis and reports",
    "return on equity",
    "revenue estimates",
    "revenue growth",
    "roce",
    "roe",
    "share price",
    "shareholder",
    "shareholder rights",
    "shares outstanding",
    "split",
    "strong buy",
    "total revenue",
    "zacks investment research",
    "zacks rank",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py::test_financial_news_standard_tags_constant -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py
git commit -m "feat(eodhd): add standard topic-tag vocabulary constant for financial_news"
```

---

## Task 2: Wire the enum into the financial_news override

**Files:**
- Modify: `packages/core/src/openlia/connectors/builtins/eodhd.py` (lines 142-174 — the `_FINANCIAL_NEWS_OVERRIDE` block)
- Test: `packages/core/tests/connectors/builtins/test_eodhd.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/core/tests/connectors/builtins/test_eodhd.py`:

```python
def test_financial_news_override_has_topic_enum() -> None:
    """The `t` parameter must declare its full standard-tag enum so the
    Anthropic tool validator rejects hallucinated topics before the SDK
    round-trip. Without this, the model picks plausible-sounding values
    like "general" and EODHD returns "Incorrect value was fullfiled for
    s or t", killing the chat turn."""
    overrides = dict(EODHD_TEMPLATE.tool_overrides)
    schema = overrides["financial_news"]["input_schema"]
    t_prop = schema["properties"]["t"]
    assert t_prop["type"] == "string"
    assert "enum" in t_prop, "`t` must declare an enum of valid topic tags"
    assert tuple(t_prop["enum"]) == _FINANCIAL_NEWS_STANDARD_TAGS


def test_financial_news_override_steers_broad_queries_to_tickers() -> None:
    """The original failure mode: model picks `t="general"` for "what
    happened in the market today". Even with the enum locking out
    invalid values, a broad query has no good topic match. The tool's
    top-level description must steer such queries toward `s` with
    index tickers instead of guessing a topic."""
    overrides = dict(EODHD_TEMPLATE.tool_overrides)
    description = overrides["financial_news"]["description"].lower()
    assert "broad" in description or "market-wide" in description, (
        "description should explicitly address broad-market queries"
    )
    assert "spy" in description or "index" in description, (
        "description should point at index tickers as the alternative to topic guessing"
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py::test_financial_news_override_has_topic_enum packages/core/tests/connectors/builtins/test_eodhd.py::test_financial_news_override_steers_broad_queries_to_tickers -v`
Expected: BOTH FAIL — `KeyError: 'enum'` on the first; the second fails because current description has neither "broad" nor "spy".

- [ ] **Step 3: Replace the override block**

In `packages/core/src/openlia/connectors/builtins/eodhd.py`, replace the existing `_FINANCIAL_NEWS_OVERRIDE` definition (lines ~142-174 — the entire dict literal currently assigned) with:

```python
_FINANCIAL_NEWS_OVERRIDE: dict = {
    "description": (
        "Fetch financial news from EODHD. REQUIRED: provide EITHER `s` "
        "(comma-separated ticker codes, e.g. 'AAPL.US') OR `t` (a topic "
        "tag from the enum). Calling without one will fail. "
        "For broad market-wide news (e.g. 'what moved the market today'), "
        "set `s` to major index tickers like 'SPY.US,QQQ.US,DIA.US,IWM.US' "
        "rather than guessing a topic tag — `t` is for topic-specific "
        "filtering. Optional: `from_date`/`to_date` (YYYY-MM-DD), "
        "`limit` (1-1000, default 50), `offset` (default 0)."
    ),
    # Note: Anthropic's tool `input_schema` validator doesn't accept
    # JSON-Schema combinators like `anyOf`/`oneOf` — only the basic
    # `{type, properties, required}` triple plus `enum` on individual
    # properties. The s-OR-t requirement stays in the description and
    # is also enforced server-side by the dispatcher's `require_one_of`
    # argument constraint. The `enum` on `t` lets the validator reject
    # hallucinated tags before the SDK round-trip.
    "input_schema": {
        "type": "object",
        "properties": {
            "s": {
                "type": "string",
                "description": (
                    "Ticker code(s), comma-separated (e.g. 'AAPL.US' or "
                    "'SPY.US,QQQ.US'). Required if `t` is empty. Use this "
                    "for broad market queries with index tickers."
                ),
            },
            "t": {
                "type": "string",
                "enum": list(_FINANCIAL_NEWS_STANDARD_TAGS),
                "description": (
                    "Topic tag for filtered news. Choose ONE value from "
                    "the enum. Common picks: 'earnings results' / "
                    "'quarterly earnings' for results, 'price target' / "
                    "'ratings' for analyst calls, 'initial public offering' "
                    "for IPOs, 'insider transactions' for insider activity, "
                    "'press releases' for company announcements. Required "
                    "if `s` is empty."
                ),
            },
            "from_date": {"type": "string", "description": "Start date YYYY-MM-DD."},
            "to_date": {"type": "string", "description": "End date YYYY-MM-DD."},
            "limit": {"type": "integer", "description": "1-1000, default 50."},
            "offset": {"type": "integer", "description": "Default 0."},
        },
    },
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py -v`
Expected: ALL PASS — including the pre-existing `test_eodhd_tool_overrides_use_anthropic_compatible_schema` (we did not introduce `anyOf`/`oneOf`/`allOf`/`not`).

- [ ] **Step 5: Lint and format**

Run: `uv run ruff check packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py && uv run ruff format packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py`
Expected: no errors, files reformatted if needed.

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/connectors/builtins/eodhd.py packages/core/tests/connectors/builtins/test_eodhd.py
git commit -m "feat(eodhd): enum-restrict financial_news topic tags + steer broad queries to s"
```

---

## Task 3: Verify override propagates through the apply_tool_overrides plumbing

**Files:**
- Test: `packages/server/tests/services/test_tool_overrides.py`

This task pins the cross-layer contract: when an override carries an `enum`, the plumbing preserves it end-to-end. The plumbing already works (it does a shallow `dict.update`), but a regression test catches future refactors that might lose the field.

- [ ] **Step 1: Write the test**

Append to `packages/server/tests/services/test_tool_overrides.py`:

```python
def test_apply_tool_overrides_preserves_property_enum() -> None:
    """Overrides may declare per-property enums so the Anthropic
    validator can lock the model to a fixed vocabulary (e.g. EODHD
    financial_news topic tags). The shallow merge in
    `_apply_tool_overrides` must carry the `enum` through unchanged."""
    tools = [
        {
            "name": "financial_news",
            "description": "auto",
            "input_schema": {"type": "object", "properties": {"t": {"type": "string"}}},
        }
    ]
    overrides = {
        "financial_news": {
            "input_schema": {
                "type": "object",
                "properties": {
                    "t": {"type": "string", "enum": ["earnings", "ratings"]},
                },
            },
        }
    }
    out = _apply_tool_overrides(tools, overrides)
    assert out[0]["input_schema"]["properties"]["t"]["enum"] == ["earnings", "ratings"]
```

- [ ] **Step 2: Run test to verify it passes (no impl change needed)**

Run: `uv run pytest packages/server/tests/services/test_tool_overrides.py::test_apply_tool_overrides_preserves_property_enum -v`
Expected: PASS — the existing shallow merge already preserves nested fields.

- [ ] **Step 3: Lint**

Run: `uv run ruff check packages/server/tests/services/test_tool_overrides.py`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add packages/server/tests/services/test_tool_overrides.py
git commit -m "test(connectors): pin override plumbing preserves per-property enum"
```

---

## Task 4: Run the full targeted test suite

**Files:** none modified.

- [ ] **Step 1: Run core + server eodhd-adjacent tests**

Run: `uv run pytest packages/core/tests/connectors/builtins/test_eodhd.py packages/server/tests/services/test_tool_overrides.py -v`
Expected: ALL PASS.

- [ ] **Step 2: Run the full core + server suite**

Run: `uv run pytest packages/core/tests/ packages/server/tests/`
Expected: PASS (or only pre-existing failures unrelated to eodhd / overrides — flag any new failures introduced by this branch).

If new failures appear, they are this PR's responsibility — fix them before continuing.

---

## Task 5: Refresh cached_tools for the live eodhd connector

The dispatcher reads tool schemas from the `connectors.cached_tools` JSON column, populated when the connector is validated. Editing the override changes the source code but does not rewrite the cached row. After deploying the code change, hit the existing revalidate endpoint to refresh the cache so the chat path sees the new enum.

**Files:** none modified. This is an operational step against the running dev server.

- [ ] **Step 1: Confirm the dev server is running on the new code**

The dev server must be restarted so the import-time `_FINANCIAL_NEWS_OVERRIDE` mutation is in effect. Check it's serving on `:8000`:

Run: `lsof -iTCP:8000 -sTCP:LISTEN`
Expected: a `python` process listed.

If the server was running before Task 2's code change, restart it:

Run: `pkill -f "openlia serve" && sleep 1 && nohup uv run openlia serve > /private/tmp/openlia-server.log 2>&1 &`
Expected: new PID; first few log lines show `Uvicorn running on http://127.0.0.1:8000`.

- [ ] **Step 2: Trigger revalidation for the eodhd connector**

The eodhd connector ID in the live DB (per session memory): `6692e543-b20b-4bae-8c65-a9b066c164e6`.

Run: `curl -sS -X POST http://127.0.0.1:8000/api/connectors/6692e543-b20b-4bae-8c65-a9b066c164e6/validate | head -c 400`
Expected: JSON response with `"status":"validated"` (the endpoint re-runs `list_tools()` against the live SDK and reapplies overrides via `_apply_tool_overrides`).

- [ ] **Step 3: Verify the cached schema now carries the enum**

Run:

```bash
sqlite3 "$HOME/.openlia/openlia-v2.db" \
  "SELECT json_extract(value, '$.input_schema.properties.t.enum') \
   FROM connectors c, json_each(c.cached_tools) \
   WHERE c.id='6692e543-b20b-4bae-8c65-a9b066c164e6' \
     AND json_extract(value, '$.name')='financial_news';"
```

Expected output: a JSON array containing all 53 standard tags, e.g. `["balance sheet","capital employed","class action",...,"zacks rank"]`.

If the column is empty or `null`, revalidation didn't fire — re-check that the server is running the updated code, then retry Step 2.

---

## Task 6: Browser smoke test

**Files:** none modified.

- [ ] **Step 1: Trigger the original failure in the browser**

Open the OpenLIA frontend at `http://127.0.0.1:8000/secretary` (the same URL the failing conversations used). Send the prompt:

> what were the major events that happened today that affected the market

Watch the dev events panel (or the network tab) for the assistant's tool calls.

- [ ] **Step 2: Confirm `eodhd__financial_news` is no longer called with a hallucinated topic**

Two acceptance criteria:

1. **Either** the model calls `eodhd__financial_news` with `s="SPY.US,QQQ.US,DIA.US,IWM.US"` (or a similar index basket) — i.e. it took the steering hint;
2. **Or** the model calls with `t=<a value from the enum>` and the call succeeds.

The error tool result `eodhd__financial_news failed: Incorrect value was fullfiled for s or t` must NOT appear.

- [ ] **Step 3: If the failure recurs, capture the exact arguments and report**

If `eodhd__financial_news` still fails, run:

```bash
sqlite3 "$HOME/.openlia/openlia-v2.db" \
  "SELECT m.created_at, m.tool_calls FROM chat_messages m \
   WHERE m.tool_calls LIKE '%financial_news%' \
   ORDER BY m.created_at DESC LIMIT 1;"
```

Inspect the `args_preview` on the failing call. Likely cause: model sent an empty or invalid `t` despite the enum (which would mean the override didn't actually reach the model — Task 5 didn't refresh the cache). Re-run Task 5 Step 3 to verify the cached row.

---

## Task 7: Final commit and branch hygiene

- [ ] **Step 1: Check branch state**

Run: `git status && git log --oneline main..HEAD`
Expected: branch ahead of `main` by 4 commits (spec + 3 task commits from this plan). Working tree clean.

- [ ] **Step 2: Push branch (do not open PR yet — wait for explicit user request)**

Run: `git push -u origin fix/news-fetch-eodhd-firecrawl`
Expected: branch published.

The Firecrawl `SearchData` JSON serialization bug is tracked separately (also surfaced in the same dev session) and is out of scope for this plan — handle in its own PR.
