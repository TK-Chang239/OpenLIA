# Connector Tool Enum Metadata — Design

**Status:** Draft for review
**Author:** TK + Lia
**Date:** 2026-05-04
**Branch:** `fix/news-fetch-eodhd-firecrawl`

## Problem

EODHD's `financial_news` tool exposes a `t` (topic tag) parameter whose
upstream API accepts only a fixed vocabulary (~53 standard tags). The
current cached schema declares `t` as a free-form string with no
enumeration. Result: the chat LLM hallucinates plausible-sounding values
like `"general"` for broad queries ("what happened in the market today"),
EODHD rejects them, and the user sees:

```
eodhd__financial_news failed: Incorrect value was fullfiled for s or t
```

Same failure shape will recur on every connector tool whose parameter
has a fixed vocabulary the LLM can't infer (FMP filters, NewsAPI
categories, etc.). We need a structural fix, not per-tool steering text.

## Goal

For any connector tool parameter with a fixed vocabulary, encode that
vocabulary in the tool's `input_schema` as a JSON-Schema `enum`, with
per-value description text in the property's `description`. Two effects:

1. Anthropic's tool-use validator structurally **rejects out-of-vocab
   values before the call** — no SDK round-trip, no failed turn.
2. The model sees every legal value with brief context at decision time
   and **picks correctly on the first call**.

Apply concretely to EODHD `financial_news.t` first; the mechanism
generalizes to any builtin via existing `tool_overrides`.

## Approach

### Mechanism

`BuiltInTemplate.tool_overrides` already accepts an arbitrary
`input_schema` dict that supersedes the auto-introspected one. JSON
Schema's `enum` keyword is supported by Anthropic's validator.
Therefore: no infrastructure change. We just write richer override
schemas per builtin.

### EODHD `financial_news.t` — concrete schema

Source: <https://eodhd.com/financial-apis/stock-market-financial-news-api>

The standard tag list (52 values, lowercase, exact strings the API
accepts):

```
balance sheet, capital employed, class action, company announcement,
consensus eps estimate, consensus estimate, credit rating,
discounted cash flow, dividend payments, earnings estimate,
earnings growth, earnings per share, earnings release, earnings report,
earnings results, earnings surprise, estimate revisions,
european regulatory news, financial results, fourth quarter,
free cash flow, future cash flows, growth rate, initial public offering,
insider ownership, insider transactions, institutional investors,
institutional ownership, intrinsic value, market research reports,
net income, operating income, present value, press releases,
price target, quarterly earnings, quarterly results, ratings,
research analysis and reports, return on equity, revenue estimates,
revenue growth, roce, roe, share price, shareholder, shareholder rights,
shares outstanding, split, strong buy, total revenue,
zacks investment research, zacks rank
```

EODHD also documents AI-auto-detected tags beyond the standard list
(e.g. "ARTIFICIAL INTELLIGENCE", "MERGERS AND ACQUISITIONS"). We
**deliberately exclude** auto-detected tags from the enum: they're an
open vocabulary, not a contract. The standard 53 cover all common
finance topics; for domain-specific niches the model can use `s` with
relevant tickers.

Schema fragment:

```python
"t": {
    "type": "string",
    "enum": [<53 standard tags, lowercase>],
    "description": (
        "Topic tag. Choose ONE value from the enum. Common picks: "
        "'earnings results' / 'quarterly earnings' for results, "
        "'price target' / 'ratings' for analyst calls, "
        "'initial public offering' for IPOs, "
        "'insider transactions' for insider activity, "
        "'press releases' for company announcements."
    ),
}
```

### Steering hint for broad-market queries

The original failure was the model picking `t="general"` for "what
happened in the market today". Even with the enum in place, the model
might pick a poorly-fitting standard tag for the same query. Add to the
tool's top-level `description`:

> For broad market news without a specific topic, set `s` to major index
> tickers (e.g. `SPY.US,QQQ.US,DIA.US,IWM.US`) instead of guessing a
> topic tag. The `t` parameter is for topic-specific filtering.

## Touch points

1. **`packages/core/src/openlia/connectors/builtins/eodhd.py`**
   Replace `_FINANCIAL_NEWS_OVERRIDE` with the enum-equipped schema and
   updated description (steering hint).

2. **DB cache refresh.** `Dispatcher.list_tools` / cached_tools is read
   from the DB row, not regenerated per request. After the override
   change, the eodhd connector's `cached_tools` row needs re-validation
   so the new schema reaches live dispatch. Reuse the existing
   re-validation flow (`POST /api/connectors/{id}/revalidate` or
   equivalent service call). No new endpoint.

3. **Tests**
   - Unit: snapshot `_FINANCIAL_NEWS_OVERRIDE` shape — confirm `enum`
     contains the expected 53 values, no duplicates, all lowercase.
   - Unit: `tool_overrides` round-trip through `apply_tool_overrides`
     (or wherever the override merges into auto-introspected schema)
     preserves `enum`.
   - Integration: build a fresh dispatcher with the eodhd template,
     assert the cached schema for `financial_news` carries `enum` and
     that `dispatch_tool_use(..., t="general")` is rejected by the
     dispatcher's argument-constraint check OR by Anthropic's schema
     validator (whichever fires first in the live path — clarify in
     plan).

4. **No changes to `dispatch.py`.** The existing `require_one_of(s, t)`
   constraint stays; it's complementary (catches both-empty case before
   schema validation runs).

## Out of scope

- FMP filters, NewsAPI categories, etc. — same pattern, future PRs.
- Generic helper like `with_enum(...)` — premature; eodhd is the
  only concrete use today. Extract when a second builtin needs it.
- Auto-detected tags (open vocabulary) — explicitly excluded above.
- Live `list_tools()` on every chat turn — out of scope; cache refresh
  on connector revalidation is enough for static enums.

## Risks and mitigations

- **EODHD changes the standard tag list.** Standard tags are stable per
  vendor docs. If they change, our cached schema is stale, model picks
  a value EODHD now rejects, surfaces as the same SDK error, we update
  the list. Acceptable maintenance burden.
- **Model picks an oddly-fitting tag for vague queries.** Mitigated by
  the steering hint nudging broad-market queries toward `s` with index
  tickers.
- **Anthropic validator rejection silently retries.** The chat runtime
  already surfaces `MissingRequiredArgumentError` to the model with a
  hint; verify the validator path produces a similarly recoverable
  error, not a hard 400 that kills the turn. This is a plan-time
  verification step, not a design-time blocker.

## Open question

Do we want a follow-up issue to apply the same pattern to FMP and
NewsAPI tools today, or wait until concrete failures surface? Default:
wait. Single-purpose PR for eodhd first; pattern is set for whoever
hits the next incident.
