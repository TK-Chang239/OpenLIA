# Formula Engine DSL — Design Spec

A shared, deterministic formula engine used by Panic Thermometer (PT) and Macro Research T1/T2 (MR) to evaluate user-defined threshold conditions against live and historical financial data. Replaces hardcoded thresholds with user-editable rule sets that map live values to status levels (green / amber / red / dark_red).

Referenced by:
- `planning/specs/pages/departments/PanicThermometerPageSpec.md`
- `planning/specs/systems/macro-research-dalio-dashboards-design.md`
- `planning/GAPS.md` (Formula engine not yet shared)


## Goals

1. **Zero hardcoded thresholds.** Every trigger condition is a user-defined formula evaluated against live and historical data. Ship sensible defaults as editable presets.
2. **Determinism and consistency.** Every computation (MAs, ATR, slope, percentile, streak backtest) has exactly one implementation. Two panels evaluating the same formula against the same data produce identical results, guaranteed.
3. **Safe evaluation.** No `eval()`, no `exec`, no `new Function()`. Formulas are parsed into an AST and walked by a sandboxed evaluator. User-authored formulas cannot execute arbitrary code.
4. **Cross-provider portability.** The engine does not depend on any particular data provider's pre-computed indicators. All math is computed locally from raw OHLC bars so results stay identical across EODHD, FMP, Finnhub, etc.
5. **Shared across departments.** One module in `packages/core/`. PT and MR T1/T2 both import it.
6. **Transparent debugging.** Users can see parse errors inline, test formulas against live data, and preview which status level a candidate rule set would produce.


## Scope and Non-Goals

**In scope:**
- Parsing and evaluating boolean/arithmetic formula expressions over a data context.
- Computing standard derived indicators (MAs, ATR, stddev, 52w extremes, price ratios, streaks) from raw bar history.
- Evaluating ordered rule sets (first-match-wins) and returning a status + interpolated label.
- Parse-only validation API for the frontend rule editor.
- Preset libraries shipped per department.

**Out of scope:**
- String manipulation (concat, substring, regex). Keyword matching for Fed Language Tracker and Diplomatic Progress is pre-computed by the panel's data-fetching layer, which injects boolean flags into the context.
- Date arithmetic beyond `days_since`. Callers inject `days_elapsed`, `days_remaining`, etc. as scalars.
- Loops, conditionals, variable assignment. Rule sets provide conditional dispatch via ordering; formulas are pure expressions.
- User-defined functions. The built-in function set is closed for v1.
- LLM-based threshold suggestion (that's Smart Mode in MR, which manipulates `params` values in-place — orthogonal to the engine).


## Module Placement

The engine lives in `packages/core/` as a pure Python module with no HTTP, FastAPI, or web dependencies. Respects the core-boundary rule in `CLAUDE.md`.

```
packages/core/src/openlia/formula/
├── __init__.py           # Public API re-exports
├── tokenizer.py          # Tokenize formula string → tokens
├── parser.py             # Tokens → AST
├── ast_nodes.py          # AST node types (Literal, Identifier, BinOp, FnCall, ...)
├── evaluator.py          # Walk AST against context/history, return value
├── functions.py          # The 9 built-in functions
├── derived.py            # Reserved-scalar computation (ma20/50/200, atr_14, streak_days, ...)
├── rules.py              # Rule set evaluation (top-to-bottom, first-match, label interp)
├── exceptions.py         # ParseError, UnknownIdentifierError, TypeMismatchError, ...
└── types.py              # Pydantic models for Rule, RuleSet, PanelResult, FormulaResult
```

Consumer departments build their data contexts and delegate to the engine:

```
packages/core/src/openlia/departments/panic_thermometer/
├── __init__.py
├── panels/               # One module per panel — fetches data, builds context, calls engine
│   ├── oil.py
│   ├── inflation.py
│   ├── fed_language.py
│   ├── wage_growth.py
│   └── diplomacy.py
└── presets.py            # Report defaults, MA-relative, Volatility-adjusted libraries

packages/core/src/openlia/departments/macro_research/
├── __init__.py
├── formula_config.py     # T1/T2 indicator configurations
└── presets.py            # Dalio defaults, Conservative, Relaxed
```


## Data Model

The engine takes three separate inputs when evaluating a rule set or formula:

| Input | Shape | Purpose |
|---|---|---|
| `raw_series` | `dict[str, list[float]]` | Named arrays of historical bar data, chronologically ordered (oldest first). Keys are identifier names (e.g., `"price"`, `"high"`, `"low"`). |
| `scalars` | `dict[str, Any]` | Panel-specific scalar values the engine cannot derive — e.g., `michigan_5y`, `days_elapsed`, `crisis_keyword_detected`, `manual_override`. |
| `params` | `dict[str, float \| int \| str]` | User-tunable thresholds (e.g., `price_threshold`, `streak_red`, `wage_threshold_amber`). |

Identifier resolution order when the evaluator encounters an identifier:

1. **Reserved derived scalars** (computed by the engine from `raw_series`) — `ma20`, `ma200`, `atr_14`, `streak_days`, etc. See "Reserved scalars" below.
2. **`scalars` dict** — caller-provided scalars.
3. **`params` dict** — user-tunable values from the rule set.

Time-series function arguments (e.g., the `field` argument of `avg(field, 20)`) resolve against `raw_series`. If the identifier is not found in `raw_series`, the function call raises `UnknownIdentifierError`.

**Rationale for keeping `raw_series` separate from `scalars`:**

- Explicit contract: the engine knows unambiguously which identifiers are time series and which are scalars.
- Validation is straightforward: before evaluation, the engine can check "formula references `avg(price, 20)` — does `raw_series` have a `price` key with ≥ 20 entries?"
- The engine owns all derived-indicator computation. The caller's job is reduced to "fetch raw bars, extract primitive series, pass them in." No per-panel math means no per-panel drift.


## Reserved Scalars (Engine-Computed)

When present in `raw_series`, the engine auto-populates these into the evaluation context from a single pass over history:

| Name | Formula | Source series |
|---|---|---|
| `price` | Latest value | `raw_series["price"]` |
| `prev_close` | Second-to-last value | `raw_series["price"]` |
| `change_pct` | `(price - prev_close) / prev_close * 100` | derived |
| `ma20`, `ma50`, `ma100`, `ma200` | Simple moving average over N bars | `raw_series["price"]` |
| `atr_14` | Average true range over 14 bars | requires `high`, `low`, `price` |
| `std_20` | Standard deviation of daily returns over 20 bars | `raw_series["price"]` |
| `high_52w`, `low_52w` | Max / min of last 252 bars | `raw_series["price"]` |
| `pct_from_high` | `(price - high_52w) / high_52w * 100` (negative %) | derived |
| `pct_from_low` | `(price - low_52w) / low_52w * 100` (positive %) | derived |
| `price_vs_ma200` | `price / ma200` (ratio, >1 = above) | derived |
| `ma50_vs_ma200` | `ma50 / ma200` (ratio, >1 = golden) | derived |
| `streak_days` | Consecutive bars at the tail where `streak_condition` is true | see "Streak computation" |

**Semantics:**

- Derived scalars are computed lazily only when referenced by a formula. Unreferenced derived scalars are not computed.
- For `cross_above(ma50, ma200)` and similar paired time-series access, the engine also pre-computes and caches each MA as a full time series (not just its latest value). This allows the function to compare today's and yesterday's MA values without recomputation.
- If insufficient history exists for a derived scalar (e.g., `ma200` with only 150 bars), the scalar is `null` and any comparison against it evaluates to `false` per null semantics below. A warning is emitted in `PanelResult.warnings`.

**Reserved scalars compute from `raw_series["price"]` by convention.** Panels using a different primary series (e.g., the wage panel uses `value` from economic events) must either (a) place that series under the `price` key in `raw_series` so reserved scalars work, or (b) use explicit time-series functions like `avg(value, 200)` in their formulas and not reference reserved scalars. This keeps the engine's reserved-name contract simple and avoids per-panel naming conventions like `ma200_of_value`.

**Simple vs. exponential MA:** v1 uses simple moving average only. If EMA is needed later, add `ema20`, `ema50`, ... as distinct reserved names rather than changing `ma20` semantics.

**Standard deviation:** sample stddev (divisor `n - 1`), computed over daily log returns. Not annualized.

**ATR:** Wilder's smoothing is not used for v1 — plain average of true range over the lookback. Document this explicitly; users who expect Wilder's ATR will see small differences vs. TradingView.


## Language Specification

### Operators (precedence, tightest → loosest)

| Precedence | Operator | Kind | Notes |
|---|---|---|---|
| 1 | `(` `)` | Grouping | |
| 2 | Unary `-`, `NOT` | Unary | `NOT` is an uppercase keyword, not `!` |
| 3 | `*`, `/` | Arithmetic | |
| 4 | `+`, `-` | Arithmetic | Binary |
| 5 | `>`, `<`, `>=`, `<=`, `==`, `!=` | Comparison | |
| 6 | `AND` | Boolean | Short-circuit |
| 7 | `OR` | Boolean | Short-circuit |

No modulo, no exponentiation, no bitwise operators. `AND`, `OR`, `NOT` are uppercase keywords matching the spec's example formulas.

### Literals

| Kind | Examples |
|---|---|
| Number | `85`, `3.14`, `-0.5`, `1.2e-3` |
| String | `">"`, `"Average Hourly Earnings"` (double quotes only) |
| Boolean | `true`, `false` (lowercase) |
| Null | `null` (lowercase) |

### Identifiers

Pattern: `[a-zA-Z_][a-zA-Z0-9_]*`. Resolved per "Identifier resolution order" above.

### Built-in Functions (closed set)

| Function | Signature | Description |
|---|---|---|
| `cross_above(fast, slow)` | `(series, series) → bool` | True if `fast[-2] <= slow[-2]` and `fast[-1] > slow[-1]` |
| `cross_below(fast, slow)` | `(series, series) → bool` | True if `fast[-2] >= slow[-2]` and `fast[-1] < slow[-1]` |
| `consecutive(field, op, value)` | `(series, string, number) → int` | Count of consecutive tail bars where `field[i] <op> value` is true. `op` is one of `">"`, `"<"`, `">="`, `"<="`, `"=="`, `"!="`. |
| `pct_change(field, n_days)` | `(series, int) → number` | `(field[-1] - field[-1-n]) / field[-1-n] * 100` |
| `avg(field, n_days)` | `(series, int) → number` | Simple arithmetic mean of last `n` bars |
| `max(field, n_days)` | `(series, int) → number` | Max of last `n` bars |
| `min(field, n_days)` | `(series, int) → number` | Min of last `n` bars |
| `slope(field, n_days)` | `(series, int) → number` | Linear regression slope of last `n` bars vs. bar index (units: value per bar) |
| `percentile(field, lookback, pct)` | `(series, int, number) → number` | The value at the given percentile rank within the trailing `lookback` bars. `pct` in [0, 100]. Linear interpolation between ranks. |
| `days_since(event_type)` | `(string) → int` | Trading days since the last occurrence of an economic event matching `event_type`. Requires an `events` side-channel on the context. |

**Fixed, not extensible for v1.** Rationale: a closed set is exhaustively testable, enables parse-time call validation, and avoids user-contributed-code security questions. Adding a function is a targeted engine PR.

### Type Discipline (Strict)

- No implicit type coercion. `"3" > 2` raises `TypeMismatchError` at evaluation time.
- Strings compare only with `==` and `!=`. No ordering on strings.
- Arithmetic operators require number operands on both sides. `null + 3` raises per null semantics below.

### Null Semantics (Propagation)

- `null > x`, `null < x`, `null >= x`, `null <= x` (for any non-null `x`) evaluate to `false`.
- `null == null` → `true`.
- `null != null` → `false`.
- `null == x` (non-null `x`) → `false`. `null != x` → `true`.
- Arithmetic on `null`: any operand is `null` → result is `null`. Comparisons involving a `null` arithmetic result follow the rules above.
- Function calls with `null` arguments where a number is required (e.g., `avg(field, null)`) raise `TypeMismatchError`.

**Why silent propagation of `null` through comparisons:**
Rules can be written naturally (`michigan_5y >= level_red`) without crashing when the survey hasn't released yet. That rule simply doesn't match, falling through to the next. Users who want to branch on missing data write `michigan_5y == null AND ...`.

### Short-Circuit Evaluation

- `AND`: right operand is not evaluated if the left evaluates to `false`.
- `OR`: right operand is not evaluated if the left evaluates to `true`.

Enables null-guarded access: `michigan_5y != null AND michigan_5y > 3.0` is safe.

### Error Model

| Category | Behavior | Surfaced as |
|---|---|---|
| Parse error (bad syntax) | Rule cannot be saved | Inline error in rule editor with position offset |
| Unknown identifier | Rule cannot be saved | Inline error with list of valid names |
| Type mismatch | Rule cannot be saved (caught on test) or evaluates to `false` at runtime with warning | Inline error / warning bar |
| Insufficient history (e.g., `avg(price, 200)` with 50 bars) | Function returns `null`; containing rule evaluates to `false` via null propagation | `PanelResult.warnings` |
| Division by zero | Returns `null` | `PanelResult.warnings` |
| Unknown function name | Parse error | Inline |

Errors are subclasses of `openlia.formula.exceptions.FormulaError`, each with structured fields (`position`, `identifier`, `type_`, etc.) for frontend consumption.


## Public API

```python
from openlia.formula import (
    parse_formula,        # formula: str → AST  (or raises ParseError)
    evaluate_formula,     # formula + context → FormulaResult
    evaluate_ruleset,     # RuleSet + context → PanelResult
    RuleSet, Rule,
    PanelResult, FormulaResult,
    FormulaError, ParseError, UnknownIdentifierError, TypeMismatchError,
)
```

### `RuleSet` schema

```python
class Rule(BaseModel):
    status: Literal["green", "amber", "red", "dark_red"]
    formula: str
    label: str   # template with {identifier} placeholders

class RuleSet(BaseModel):
    rules: list[Rule]
    params: dict[str, float | int | str]
    streak_condition: str | None = None
```

### `PanelResult` (returned by `evaluate_ruleset`)

```python
class PanelResult(BaseModel):
    status: Literal["green", "amber", "red", "dark_red"]
    matched_rule_index: int | None       # None if no rule matched
    label: str                           # label with {var} substitutions resolved
    resolved_values: dict[str, Any]      # every identifier in the matched rule
    derived_scalars: dict[str, float | None]  # engine-computed scalars for UI charts
    warnings: list[str]
```

### `FormulaResult` (returned by `evaluate_formula`)

```python
class FormulaResult(BaseModel):
    value: bool | float | str | None
    resolved_values: dict[str, Any]
    errors: list[FormulaError]
    warnings: list[str]
```

### Rule-set evaluation semantics

1. Compute all derived scalars (single pass over `raw_series`).
2. If any rule's formula references `streak_days`, run streak backtest (see below) to populate `streak_days`.
3. Merge identifier namespaces in precedence order (highest first): **reserved derived scalars > `scalars` dict > `params` dict**. Reserved names cannot be shadowed — if a caller passes `scalars["ma200"]` or `params["ma200"]`, the engine raises `ValidationError` at rule-set load. This matches the resolution order stated in "Data Model" above.
4. Evaluate `rules[0].formula` against the merged namespace. If `true`, return that status + label (with `{var}` placeholders filled from resolved values).
5. Otherwise continue to `rules[1]`, etc.
6. If no rule matches, return `status="green"`, `matched_rule_index=None`, `label="No rule matched"`.

**Label interpolation:** uses Python's `str.format_map`. Missing keys fall back to the literal placeholder (e.g., `"{unknown}"` stays as `{unknown}`) — not an error.


## Streak Computation

Documented in detail for cross-checking. `streak_days` is the most complex derived scalar.

### What it represents

The number of consecutive most-recent bars where a user-defined condition (`streak_condition`) evaluates to `true`. The walk stops at the first bar where the condition is `false`.

### Why it can't be pre-computed statically

`streak_condition` can reference derived scalars like `ma200` or `percentile(price, 252, 90)`. These values differ at every historical bar. Computing a streak therefore requires evaluating the condition against *each* historical bar with the derived scalars *recomputed as of that bar*, not the current value everywhere.

Example: "price above MA200 × 1.15" at today's MA200 might be `$90`, but at a bar 60 days ago the MA200 was `$85` → the threshold was `$97.75` back then. The streak walk must evaluate against the historical threshold, not today's.

### Algorithm

Given:
- `raw_series`: dict of full history arrays (oldest → newest)
- `streak_condition`: a parsed formula AST
- `scalars`, `params`: same as top-level evaluation

Precondition: if any rule references `streak_days`, `streak_condition` must be non-null and parseable. Else raise `ValidationError` at rule-set load time.

```
FUNCTION compute_streak(raw_series, streak_condition_ast, scalars, params) -> int:

    n = length(raw_series["price"])    # assume all arrays have equal length
    count = 0

    # Pre-compute full derived series once (not recomputed per iteration)
    derived_full = precompute_derived_series(raw_series)
    # derived_full is a dict like:
    #   {"ma200": [None, None, ..., 78.3, 78.1, 78.2, ...],
    #    "atr_14": [None, ..., 2.1, 2.0, ...],
    #    ...}
    # where None indicates insufficient history at that bar index.

    FOR i FROM n - 1 DOWNTO 0:
        # Build a synthetic "as-of bar i" context
        bar_context = {}
        FOR each key in raw_series:
            bar_context[key] = raw_series[key][i]           # scalar at bar i
        FOR each key in derived_full:
            bar_context[key] = derived_full[key][i]          # derived scalar at bar i
        bar_context = bar_context | scalars | params

        # Build a sliced raw_series for time-series function calls
        bar_series = {}
        FOR each key in raw_series:
            bar_series[key] = raw_series[key][0..i]          # trailing window ending at bar i

        # Evaluate the condition against this synthetic view
        result = evaluate_ast(streak_condition_ast, bar_context, bar_series)

        IF result == true:
            count = count + 1
        ELSE:
            BREAK

    RETURN count
```

### Worked example

Setup:
- `raw_series["price"]` = `[..., 79.0, 82.5, 87.1, 91.2, 92.4]` (last 5 bars shown; full history has 252 bars)
- `streak_condition` = `"price > price_threshold"`
- `params["price_threshold"]` = `85`

Walk (from `i = n-1` downward):
| Bar index | `price[i]` | `price > 85` | Action |
|---|---|---|---|
| n-1 | 92.4 | true | count = 1, continue |
| n-2 | 91.2 | true | count = 2, continue |
| n-3 | 87.1 | true | count = 3, continue |
| n-4 | 82.5 | false | break |

Result: `streak_days = 3`.

### Worked example with MA-relative condition

Setup:
- `streak_condition` = `"price > ma200 * 1.15"`
- `raw_series["price"]` = 252 bars of history ending at today.

Walk:
| Bar index | `price[i]` | `ma200[i]` (recomputed at bar i) | `ma200[i] * 1.15` | `price > threshold` | Count |
|---|---|---|---|---|---|
| n-1 | 92.4 | 78.3 | 90.05 | true | 1 |
| n-2 | 91.2 | 78.1 | 89.82 | true | 2 |
| ... | ... | ... | ... | ... | ... |
| n-k | 82.5 | 77.2 | 88.78 | false | break |

Result: `streak_days = k - 1`.

### Cost and optimization

- Naive cost: at each of `k` backward steps, recomputing MA200 over the trailing 200-bar window costs `O(200)`. Total `O(k × 200)`.
- Optimized cost: pre-compute the full derived series (`ma20`, `ma50`, `ma200`, `atr_14`, `std_20`) in one pass at engine entry — `O(n × w_max)` where `n` is history length and `w_max` is the longest derived window. Subsequent streak evaluation is `O(k)` lookups.
- Pre-computation happens once per `evaluate_ruleset` call and is cached for subsequent time-series function evaluations within the same call. Not cached across calls (each engine call assumes fresh data).

### Edge cases

| Case | Behavior |
|---|---|
| `streak_condition` is `None` but a rule references `streak_days` | Raise `ValidationError` at rule-set load |
| `streak_condition` is literal `true` | `streak_days = n` (full history length) |
| `streak_condition` is literal `false` | `streak_days = 0` |
| Insufficient history to evaluate condition at bar `i` (e.g., MA200 needed but only 150 bars precede) | Stop walk at bar `i`, return current count; emit warning |
| `streak_condition` raises type/unknown-id error at any bar | Fail rule-set validation at load (condition must be evaluable with current data) |
| User changes `streak_condition` | Next `evaluate_ruleset` call recomputes from scratch; no persisted state |

### Testability

Streak tests live in `packages/core/tests/formula/test_streak.py`. Test fixtures include:
- Fixed-threshold streaks of known length (3, 30, 90 bars).
- MA-relative streaks where the threshold line crosses the price at a known bar.
- Empty / all-false / all-true conditions.
- Insufficient-history truncation.


## Preset Libraries

Each department ships preset rule sets per panel. Presets are plain Python data in `packages/core/src/openlia/departments/<dept>/presets.py`. Read-only — the user edits their live config, not the preset source.

### Shape

```python
PT_PRESETS: dict[str, dict[str, RuleSet]] = {
    "oil": {
        "report_defaults": RuleSet(...),
        "ma_relative": RuleSet(...),
        "volatility_adjusted": RuleSet(...),
    },
    "inflation": { ... },
    "fed_language": { ... },
    "wage_growth": { ... },
    "diplomacy": { ... },
}

MR_PRESETS: dict[str, dict[str, RuleSet]] = {
    "debt_cycle": { ... },
    "four_seasons": { ... },
}
```

### Loading semantics

- Loading a preset fully replaces that panel's `rules`, `params`, and `streak_condition`. No merging with existing user edits.
- Other panels are untouched.
- Preset identity is not retained in the user's config — once loaded, it's just data. We can't show "your config differs from Report defaults" without extra metadata; skipped for v1.

### Validation at ship time

CI runs a test that parses every formula in every preset and validates every identifier against the panel's known context. Catches broken presets before deployment.


## Validation and Debugging (Frontend Integration)

Three REST endpoints on the server back the rule editor UI. All three delegate to the same core engine primitives.

### `POST /api/panic-thermometer/formula/parse`

Used for inline syntax checking as the user types (debounced ~200ms).

Request:
```json
{
  "formula": "price > ma200 * 1.15",
  "panel": "oil"
}
```

Response (ok):
```json
{
  "ok": true,
  "identifiers": ["price", "ma200"],
  "unknown_identifiers": [],
  "warnings": []
}
```

Response (error):
```json
{
  "ok": false,
  "errors": [
    {"type": "parse", "message": "Unexpected token '*'", "position": 15}
  ]
}
```

### `POST /api/panic-thermometer/formula/test`

Used when the user clicks "Test" on a formula.

Request:
```json
{
  "formula": "streak_days >= streak_red AND price > price_threshold",
  "panel": "oil",
  "params": {"price_threshold": 85, "streak_red": 30}
}
```

Response:
```json
{
  "value": true,
  "resolved_values": {
    "streak_days": 47,
    "streak_red": 30,
    "price": 92.4,
    "price_threshold": 85
  },
  "warnings": []
}
```

Server implementation: reads the panel's cached `raw_series` + `scalars` from the last data fetch (no re-fetch), calls `evaluate_formula`, returns result.

### `POST /api/panic-thermometer/ruleset/preview`

Used for the live "Would trigger" preview in the rule editor.

Request:
```json
{
  "panel": "oil",
  "ruleset": {"rules": [...], "params": {...}, "streak_condition": "..."}
}
```

Response:
```json
{
  "status": "red",
  "matched_rule_index": 1,
  "label": "47 days elevated — scenario upgrade risk",
  "resolved_values": {...},
  "derived_scalars": {"ma20": 89.1, "ma200": 78.3, "streak_days": 47, ...},
  "warnings": []
}
```

### Cached panel data

Each panel's most recent fetched `raw_series` + `scalars` lives in the server-side cache keyed by panel. Test and preview endpoints read from this cache — they do not re-fetch. Cache invalidates on the next scheduled refresh.

Equivalent endpoints exist for Macro Research at `/api/macro-research/formula/parse`, `/test`, `/ruleset/preview`, backed by the same engine primitives.


## Data Requirements (for Setup Wizard)

The setup wizard probes each configured data provider to confirm capability coverage. Panels are disabled (with inline explanation) if their required capabilities are not met.

### Universal requirements

| Requirement | Why the engine needs it |
|---|---|
| Daily OHLC bars, date-indexed, chronologically ordered | Every time-series function walks these arrays |
| Minimum 252 trading days of history per ticker | MA200 needs 200 bars; 52-week high/low and `percentile(field, 252, ...)` need 252 |
| Recommended 504 trading days (~2 years) | Allows streak backtesting across a full cycle and percentile windows up to 1 year with meaningful prior context |
| Adjusted close preferred over raw close | Long-horizon MAs and percentiles distort with unadjusted splits/dividends |

### Per-panel requirements

**Panel 1 — Oil duration**
- Historical daily bars with `{date, open, high, low, close, adjusted_close, volume}`, user-configurable ticker (default `BNO.US`), ≥ 252 bars.
- Latest quote with `{price, previous_close, timestamp}`.

**Panel 2 — Inflation expectations**
- Historical daily bars for TIP ETF (default `TIP.US`).
- Latest quote for same.
- Economic events with `{date, event_name, actual, previous, estimate, country}`, `country=US`, filterable by event type (default "Michigan 5 Year Inflation Expectations").

**Panel 3 — Fed language**
- News articles with `{date, headline, summary, source, url}`, searchable by keyword/tag, lookback 30 days.
- Economic events, `country=US`, filterable for FOMC.

**Panel 4 — Wage growth**
- Economic events, `country=US`, filterable by event type (default "Average Hourly Earnings"), plus CPI MoM for real-wage derived fields. Lookback ≥ 12 months.

**Panel 5 — Diplomatic progress**
- News articles, searchable by user-defined keyword lists. Lookback 30 days.

### Capability aggregation

| Capability | Required by | Satisfied if provider returns... |
|---|---|---|
| `historical_prices` | Panels 1, 2 | OHLC daily array, date-indexed, ≥ 252 bars per ticker |
| `live_quote` | Panels 1, 2 | Latest price + previous close per ticker |
| `economic_events` | Panels 2, 3, 4 | Event array with `actual`, `previous`, filterable by country + event type, history ≥ 12 months |
| `company_news` | Panels 3, 5 | Article array with headline/summary/date, keyword search, date range filter |

### Wizard behavior

1. Probe each configured provider for each capability (small test fetches).
2. Show per-panel status: green / amber / red with inline explanation.
3. Warn on history depth: "Provider returns only N days. MA200 unavailable until more history accumulates."
4. Validate default tickers and event names exist in the provider's catalog; prompt the user to pick alternatives if not found.
5. Disable panels whose requirements are unmet; do not hide them.


## Caching and Performance

- Inside the engine, derived series (`ma20`, `ma50`, `ma200`, `atr_14`, `std_20`) are pre-computed in a single O(n × w_max) pass at the start of each `evaluate_ruleset` call. Time-series functions and streak evaluation read from these cached arrays.
- Each engine call assumes fresh inputs; no cache persists across calls.
- Server-side caching of fetched panel data between auto-refresh cycles is a server concern, not engine concern. The `/test` and `/preview` endpoints read the server's cache.


## Integration with Existing Architecture

- Core (`packages/core/openlia/formula/`): the engine. No HTTP, no I/O, no logging dependencies beyond stdlib.
- Department panels (`packages/core/openlia/departments/<dept>/panels/*.py`): orchestrate data fetching (through the data provider abstraction), build `raw_series` + `scalars`, call the engine, return results.
- Server (`packages/server/openlia_server/routes/`): thin wiring — receives requests, pulls cached data, calls engine, returns JSON.
- Frontend (`frontend/src/pages/PanicThermometer`, `MacroResearch`): consumes REST responses, no engine logic.


## Testing Strategy (High Level)

- **Unit tests per module:** tokenizer, parser, each AST node type, each built-in function, null propagation, short-circuit evaluation.
- **Derived scalars:** fixture-based tests comparing engine output against hand-computed reference values.
- **Streak backtesting:** fixtures covering known streak lengths, MA-relative conditions, insufficient-history truncation.
- **Rule-set evaluation:** end-to-end tests for each panel's default preset against snapshot data contexts.
- **Preset validation:** CI parses every preset formula and verifies identifier resolution.
- **Cross-department:** MR T1/T2 presets evaluate correctly through the same engine.
- Target: ~80% coverage in `packages/core/src/openlia/formula/` (per project standards in CLAUDE.md).


## Open Questions

- **EMA support:** Not in v1. If added, new reserved names (`ema20`, `ema50`, ...) rather than changing SMA semantics.
- **Wilder's ATR vs. simple ATR:** v1 uses simple average. Small numerical divergence from TradingView; document it.
- **Intraday bars:** out of scope for v1. All computations assume daily bars. If intraday is needed later, raw_series semantics extend naturally, but the reserved scalar names (`ma200`, etc.) would need clarification ("200 bars" vs "200 days").
- **Multi-timeframe conditions:** not supported. Each panel operates at one timeframe.
- **Live/delayed data staleness in test endpoint:** the server cache may be up to `refresh_interval` old when the user tests a formula. UI should surface the data timestamp.
