# Phase 17 — Formula Engine fix plan (→ 100%)

**Current:** ~60–65% shipped against the design spec; ~95% shipped against the implementation plan. **Root cause:** SPEC_DRIFT — the implementation plan and `planning/specs/systems/formula-engine-design.md` describe materially different DSLs (different keyword casing, different literal set, different function catalog, different public API, different rule-evaluation surface, different identifier-resolution pipeline). Phase 18 panels and Phase 19 dashboards already import the plan's surface verbatim; the spec's richer surface is almost entirely unshipped and has been partially re-implemented ad-hoc in `packages/server/src/openlia_server/services/pt_runner.py` (private `_evaluate_ruleset`, `_compute_streak_days`, `_build_context`) rather than inside the core engine where it belongs.

**Gap summary:**
- **DSL drift (the big one):** uppercase `AND`/`OR`/`NOT` vs shipped lowercase; `null` + string literals in spec vs. unshipped; 10 domain-specific functions (`cross_above`, `cross_below`, `consecutive`, `pct_change`, `avg`, `max`, `min`, `slope`, `percentile`, `days_since`) in spec vs 12 shipped functions (`min`/`max`/`abs`/`round`/`mean`/`median`/`stddev`/`sum`/`last`/`pct_change`/`rolling_mean`/`lag`), only 2 names overlap (`min`, `max`, `pct_change`).
- **Null semantics missing entirely.** Spec requires `null` propagation through comparisons and `null == null`. Shipped engine has no `null` literal, no null-arithmetic rules; division-by-zero raises `FormulaError` instead of returning null; `pct_change` with zero previous raises instead of returning null.
- **Reserved derived-scalar layer unshipped.** Spec lists 13 engine-computed scalars (`price`, `prev_close`, `change_pct`, `ma20/50/100/200`, `atr_14`, `std_20`, `high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`, `price_vs_ma200`, `ma50_vs_ma200`, `streak_days`). None are in `packages/core/src/openlia/formula/`. Panels hard-code these in panel-layer code (or don't compute them at all).
- **`RuleSet` / `evaluate_ruleset` absent from the engine.** Spec mandates `openlia.formula.rules` with `Rule`, `RuleSet`, `FormulaResult`, `PanelResult`, `evaluate_formula`, `evaluate_ruleset`. Shipped `openlia.formula` exports only `FormulaEngine.evaluate`, `EvaluationContext`, `FormulaError`, `parse`, `Expression`, `RequirementRef`, `extract_requirements`. `pt_runner.py` lines 156–250 reimplement rule-set evaluation in the server layer instead — violates the core-boundary rule and guarantees Phase 19 will drift from Phase 18.
- **Streak backtest lives outside the engine and is wrong.** `pt_runner._compute_streak_days` (lines ~136–178) walks `reversed(price_series)` and overwrites only `scalars["price"]` per iteration — does not recompute `ma200`, `atr_14`, `std_20` as-of each historical bar. Spec worked-example "price > ma200 × 1.15" will produce wrong streak counts. Also does not support the spec's MA-relative condition at all because `ma200` never enters the as-of context.
- **Identifier-resolution order drift.** Spec: reserved-derived > `scalars` > `params`. Shipped `pt_runner._build_context` merges params first, then scalars on top (reverse precedence for overlapping keys), with no reserved-derived layer and no `ValidationError` when a caller shadows a reserved name.
- **`raw_series` / `scalars` / `params` three-input contract collapsed to two.** `EvaluationContext(values, history)` folds `scalars`, `params`, and would-be derived scalars into one `values` dict at the server layer — the engine sees no distinction, so parse-time validation of "is `price` in `raw_series`?" is impossible.
- **`IfElse` ternary and `**` exponentiation and `%` modulo shipped but not in spec.** Spec section "Operators" explicitly says "No modulo, no exponentiation, no bitwise operators." Spec grammar has no ternary. Engine supports all three.
- **Label interpolation absent.** Spec requires `str.format_map` with missing-key fallback. Not implemented anywhere.
- **Frontend validation API missing.** Spec defines `POST /api/panic-thermometer/formula/parse`, `/test`, `/ruleset/preview`. Phase 18 ships `/test` and `/preview` that call into `pt_runner`'s private helpers; there is no `/parse` endpoint and no `openlia.formula.validate` primitive for it to delegate to.
- **Tests cover the shipped surface only.** 90 test functions across 14 test files exercise the Pratt parser, 12 functions, arithmetic, comparisons, logical, ternary, safety caps, history, requirements, errors, integration — zero tests for reserved scalars, rule-set evaluation, streak backtest, null propagation, label interpolation, or spec-mandated functions (`cross_above`, `cross_below`, `consecutive`, `avg`, `slope`, `percentile`, `days_since`).

## DSL comparison table (plan vs spec vs shipped)

| Surface element | Implementation plan | Design spec | Shipped |
|---|---|---|---|
| **Keywords — logical** | `and`, `or`, `not` (lowercase) | `AND`, `OR`, `NOT` (UPPERCASE) | Lowercase only — uppercase tokenizes as IDENT (observation 775) |
| **Literals — number** | Int, float, scientific | Int, float, scientific | Shipped (int/float/sci) |
| **Literals — string** | Absent | `"double-quoted"` required (for `consecutive`, `days_since`) | **Not shipped** — lexer has no STRING token |
| **Literals — boolean** | `true`, `false` | `true`, `false` | Shipped |
| **Literals — null** | Absent | `null` lowercase required | **Not shipped** — no NULL token, no null semantics |
| **Operator `%` (modulo)** | Included | Explicitly excluded | Shipped (drift from spec) |
| **Operator `**` (power)** | Included | Explicitly excluded | Shipped (drift from spec) |
| **Ternary `a if c else b`** | Included | Absent | Shipped (drift from spec) |
| **Grouping `()`** | Yes | Yes | Yes |
| **Comparison `< <= > >= == !=`** | Yes | Yes | Yes |
| **History `ident[t-N]`** | Included | Replaced by explicit functions (`lag`, `avg`, ...) | Shipped |
| **Strict-type comparisons** | Yes | Yes (numbers only; strings only `==`/`!=`) | Partial — numbers enforced; strings never reachable (no STRING token) |
| **Null propagation in comparisons** | N/A | `null > x → false`; `null == null → true`; `null == x → false` | **Not shipped** |
| **Short-circuit AND/OR** | Yes | Yes | Yes |
| **Division by zero** | Raise `FormulaError` | Return `null`, warn | Raises (drift) |
| **Insufficient history** | Raise | Return `null`, warn | Raises (drift) |
| **Function: `min`** | `min(*values)` variadic | N/A (spec has no variadic `min`) | Variadic shipped |
| **Function: `max`** | `max(*values)` variadic | N/A | Variadic shipped |
| **Function: `abs`** | Present | Absent | Shipped |
| **Function: `round`** | Present | Absent | Shipped |
| **Function: `mean`** | Present (variadic) | Absent | Shipped |
| **Function: `median`** | Present | Absent | Shipped |
| **Function: `stddev`** | Present (variadic scalars) | Absent (spec has `std_20` reserved derived, not fn) | Shipped; wrong shape for spec use |
| **Function: `sum`** | Present | Absent | Shipped |
| **Function: `last(series[,n])`** | Present | Absent (spec uses `[t-n]` implicitly; scalar `price` instead) | Shipped |
| **Function: `pct_change(series, n)`** | Present | Present (same signature) | Shipped — signatures match |
| **Function: `rolling_mean(series, n)`** | Present | Renamed `avg(field, n_days)` | Shipped as `rolling_mean`; spec name absent |
| **Function: `lag(series, n)`** | Present | Absent (use `[t-n]` in spec? but spec deprecates `[t-n]`) | Shipped |
| **Function: `avg(field, n)`** | Absent | Present (SMA) | **Not shipped** (alias of `rolling_mean`) |
| **Function: `cross_above(fast, slow)`** | Absent | Present | **Not shipped** |
| **Function: `cross_below(fast, slow)`** | Absent | Present | **Not shipped** |
| **Function: `consecutive(field, op_str, value)`** | Absent | Present (returns int; uses string op) | **Not shipped** (requires STRING literal) |
| **Function: `slope(field, n)`** | Absent | Present (linear-reg slope) | **Not shipped** |
| **Function: `percentile(field, lookback, pct)`** | Absent | Present | **Not shipped** |
| **Function: `days_since(event_type_str)`** | Absent | Present (requires `events` side-channel) | **Not shipped** |
| **Reserved derived scalars** | None | `price`, `prev_close`, `change_pct`, `ma20/50/100/200`, `atr_14`, `std_20`, `high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`, `price_vs_ma200`, `ma50_vs_ma200`, `streak_days` (13) | **Zero shipped**; panels compute ad-hoc or not at all |
| **Context shape** | `EvaluationContext(values, history)` two-slot | Three inputs: `raw_series` (series) + `scalars` (scalar injected) + `params` (user thresholds) | Two-slot; drift |
| **Identifier resolution order** | Single namespace | reserved-derived > scalars > params, reserved names unshadowable | Single namespace; `params` overridden by `scalars` in `pt_runner._build_context` (wrong direction) |
| **`parse_formula` public API** | N/A | `parse_formula(str) -> AST` | Shipped as bare `parse(str) -> Expression` |
| **`evaluate_formula` public API** | `FormulaEngine().evaluate(expr, ctx)` | `evaluate_formula(formula, context) -> FormulaResult` (with `.value`, `.resolved_values`, `.errors`, `.warnings`) | `FormulaEngine.evaluate` returns raw `float | bool`; no FormulaResult wrapper |
| **`evaluate_ruleset` public API** | Absent | `evaluate_ruleset(RuleSet, context) -> PanelResult` (first-match-wins, label interp, default green) | **Not in engine**; reimplemented privately in `pt_runner._evaluate_ruleset` |
| **`Rule` / `RuleSet` Pydantic types** | Absent | `Rule(status, formula, label)`, `RuleSet(rules, params, streak_condition)` | **Not shipped**; server uses `list[dict[str, Any]]` |
| **`PanelResult` / `FormulaResult` types** | Absent | Pydantic models with `status`, `matched_rule_index`, `label`, `resolved_values`, `derived_scalars`, `warnings` | **Not shipped**; `pt_runner` defines parallel dataclasses |
| **Streak backtest location** | N/A | Engine-owned (`compute_streak` in `rules.py` or `derived.py`); recomputes `ma200` as-of each bar | **In server** (`pt_runner._compute_streak_days`); does NOT recompute derived as-of bar — wrong for MA-relative conditions |
| **Label interpolation** | Absent | `str.format_map` with missing-key fallback | **Not shipped** |
| **Error taxonomy** | Single `FormulaError` | `ParseError`, `UnknownIdentifierError`, `TypeMismatchError`, `FormulaError` base | Single `FormulaError` + `LexError` (un-exported); no subclasses |
| **Structured error fields (`position`, `identifier`, `type_`)** | Absent | Required for frontend inline errors | Partial — `FormulaError` has `line`, `col`; no `identifier`, no `type_`, no `position` offset |
| **Frontend `/parse` endpoint backing** | Absent | `parse_formula` returns identifiers + unknowns | Missing — no identifier-listing primitive |
| **Module layout** | `engine.py`, `parser.py`, `lexer.py`, `tokens.py`, `requirements.py` (5 files) | `tokenizer.py`, `parser.py`, `ast_nodes.py`, `evaluator.py`, `functions.py`, `derived.py`, `rules.py`, `exceptions.py`, `types.py` (9 files) | 5-file plan layout (names diverge: `lexer.py` vs `tokenizer.py`) |
| **Safety caps (`MAX_AST_DEPTH=64`, `MAX_NODE_COUNT=1024`, `MAX_EVAL_STEPS=10000`)** | Yes | Not specified | Shipped (plan wins) |

**Function overlap summary:** Plan = 12 functions. Spec = 10 functions. Intersection = **3** names (`min`, `max`, `pct_change`), and only `pct_change` has a matching signature. Spec's 7 domain-specific functions are entirely unshipped. Plan's 9 general-math functions have no spec mandate.

## Decision required — which DSL is canonical?

**Option A (proposed in prior fix-plan): plan wins; amend spec additively.**
- **Impact:** keep `FormulaEngine`, `EvaluationContext(values, history)`, `parse`, `extract_requirements`, `RequirementRef` frozen; layer `openlia.formula.rules` and `openlia.formula.derived` on top. Add missing spec functions (`avg`, `cross_above`, `cross_below`, `slope`, `percentile`, `consecutive`, `days_since`) to the registry. Add `null` literal + propagation. Add case-insensitive `AND`/`OR`/`NOT` aliases. Amend spec to match shipped module names (5-file layout), drop spec's prohibition on `%` / `**` / ternary, and keep spec's type/null/rule-set sections.
- **Pro:** Phase 18 panels + Phase 19 dashboards already import the plan's API; reversing would rewrite ~400 LOC across `panic_thermometer/` and `macro_research/dashboards/` plus all green tests.
- **Con:** spec becomes a palimpsest; users comparing docs to behavior see drift in keywords (lowercase), literals (`null` + strings needed), operators (`%`/`**`/ternary shipped but spec prohibits).
- **Scope:** 8–10 engineer-days (see task list below).

**Option B: spec wins; rewrite engine + panel surface.**
- **Impact:** rename `FormulaEngine.evaluate` → `evaluate_formula`; introduce `RuleSet`/`Rule`/`PanelResult`/`FormulaResult` Pydantic types; rewrite `EvaluationContext` as three-slot `(raw_series, scalars, params)`; add reserved-derived layer; rewrite Phase 18 panel classes to hand three inputs to engine instead of merging; delete `pt_runner._evaluate_ruleset`/`_compute_streak_days`/`_build_context` and delegate; move streak into engine; replace 9 plan-only functions with 10 spec functions; enforce uppercase keywords; drop `%`/`**`/ternary.
- **Pro:** spec remains authoritative; engine matches Panic Thermometer + Macro Research worked examples verbatim.
- **Con:** breaks every green Phase 17/18/19 test (~90 core tests + ~40 server tests); rewrites 4 department assemblers; churns documented module layout; touches migration-sensitive `pt_config` service.
- **Scope:** 15–20 engineer-days.

**Recommendation:** **Option A (plan wins, additive spec amendment)** with **three concessions to the spec**:
1. Add case-insensitive `AND`/`OR`/`NOT` aliases (observation 775 — already a blocker for writing spec-style presets).
2. Add `null` literal + propagation semantics (observation 774 — null comparisons needed for `michigan_5y` and every other optionally-published indicator).
3. Move streak + reserved-derived + ruleset surface *into the engine* (spec's architectural claim that these belong in core is correct; server-layer `pt_runner._compute_streak_days` is both wrong for MA-relative conditions and a core-boundary violation).

Plan-vs-spec function set is left as-is (12 plan functions remain; 7 missing spec functions added to registry as additive). Spec section "Operators" and "Language Specification" amended to document `%`/`**`/ternary and lowercase keywords.

## Integration impact if drift remains

- **Phase 18 Panic Thermometer (P1-10, P1-13, P1-14 in master tracker):** Oil and Inflation panels cannot write MA-relative or volatility-adjusted presets because `ma200` / `atr_14` / `std_20` are not resolvable identifiers. `pt_config` default presets that reference `ma200` will silently evaluate to `FormulaError: undefined variable 'ma200'` at runtime; `pt_runner` catches it (line ~210) and emits a warning, so rules silently never match. User reports "wizard green-states everything" are traceable here.
- **Phase 19 Macro Research T2:** Dalio `four_seasons` preset uses `price > ma200 * 1.15` in `packages/core/src/openlia/macro_research/dashboards/four_seasons.py`; fails identically. Currently unshipped so latent, but blocks merge of Phase 19 T2.
- **Phase 10 Setup Wizard:** capability probe expects "provider returns ≥ 252 bars for MA200" → wizard has no way to know if MA200 is *consumable* by the engine, because the engine doesn't expose `ma200` at all.
- **Streak-based rules (Diplomacy panel, Wage panel, Fed panel):** streak backtest is wrong (see gap-6 above). Any rule referencing `streak_days` in an MA-relative or ATR-relative streak condition produces garbage counts.

## Tasks (in execution order)

0. **NEW-17-00 (decision) — Ratify Option A and amend the spec.**
   - Files: `planning/specs/systems/formula-engine-design.md`.
   - Edits: (a) prepend a "Shipped v1 DSL — authoritative" section listing the actual module files (`lexer.py`/`tokens.py`/`parser.py`/`engine.py`/`requirements.py` plus new `derived.py`/`rules.py`); (b) update "Operators" table to add `%`, `**`, and the `a if cond else b` ternary, marked "shipped, non-spec"; (c) change "AND/OR/NOT uppercase" to "accepted in either case, canonical lowercase"; (d) collapse the 9-file layout diagram into the 5→7-file actual layout; (e) add a "Function catalog" subsection listing the 12 shipped + 7 added functions with signatures; (f) keep null semantics, reserved-scalar table, rule-set semantics, streak algorithm sections unchanged — these remain the target surface.
   - Why new: supersedes the existing fix-plan's "P1-21" decision task; the decision itself needs a concrete acceptance artifact.
   - Acceptance: spec diff merged; no contradiction between spec's function catalog and `openlia.formula.engine.FUNCTION_REGISTRY`.

1. **NEW-17-01 — Add case-insensitive `AND`/`OR`/`NOT` aliases in lexer.**
   - Files: `packages/core/src/openlia/formula/lexer.py` (match `_KEYWORDS` with `text.lower()`); `packages/core/tests/formula/test_lexer.py` (parametrize mixed/upper/lower cases across `AND`/`OR`/`NOT`/`IF`/`ELSE`/`TRUE`/`FALSE`).
   - Spec ref: "Operators" table; observation 775.
   - Acceptance: `"price > 5 AND volume > 100"` tokenizes identically to lowercase; existing 90 tests still green.

2. **NEW-17-02 — Add `null` literal + null propagation semantics.**
   - Files: `tokens.py` (add `TokenKind.NULL`); `lexer.py` (add `"null"` keyword → `NULL`); `parser.py` (add `Literal(value=None)` in `primary()`); `engine.py` (update `_eval_binary` for arithmetic/comparison on `None`; update `_require_number`/`_require_bool` to allow `None` passthrough in comparisons; change `/` by zero from raise to return `None`; update `_coerce_final` to pass `None` through or raise depending on caller context).
   - New tests: `tests/formula/test_engine_null.py` covering all 6 null-comparison rules from spec + arithmetic propagation + short-circuit guards (`x != null AND x > 3`).
   - Spec ref: "Null Semantics (Propagation)"; observation 774.
   - Acceptance: `evaluate("null > 5", ctx) is False`; `evaluate("null == null", ctx) is True`; `evaluate("x != null and x > 3", ctx={"x": None})` returns `False` without raising.

3. **NEW-17-03 — Add `STRING` literal + string equality.**
   - Files: `tokens.py` (add `TokenKind.STRING`); `lexer.py` (double-quoted strings, escape `\"` and `\\`); `parser.py` (`Literal(value=str)` branch in `primary()`); `engine.py` (`_eval_binary` allow strings for `==`/`!=` only; raise `FormulaError` for `<`/`>`/`<=`/`>=` on strings — matches spec's "Strings compare only with `==` and `!=`").
   - New tests: `test_engine_strings.py` covering equality, inequality, and that ordering raises.
   - Spec ref: "Literals" + "Type Discipline (Strict)".
   - Acceptance: `evaluate('event_type == "FOMC"', ctx)` works for `consecutive` / `days_since`.

4. **NEW-17-04 — Create `openlia.formula.derived` module (reserved scalar computation).**
   - Files: create `packages/core/src/openlia/formula/derived.py` with `compute_derived_scalars(raw_series: dict[str, list[float]]) -> dict[str, float | None]` returning `price`, `prev_close`, `change_pct`, `ma20`, `ma50`, `ma100`, `ma200`, `atr_14`, `std_20`, `high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`, `price_vs_ma200`, `ma50_vs_ma200`. Missing-history cases → `None` (not raise). Also `compute_derived_series(raw_series) -> dict[str, list[float | None]]` for bar-by-bar history used by streak and `cross_above`/`cross_below`.
   - Reserved-name shadow guard: add `RESERVED_NAMES` frozenset; `EvaluationContext.from_raw_series(raw_series, scalars, params)` classmethod raises `FormulaError` if any reserved name appears in `scalars` or `params`.
   - Update `openlia.formula.__init__` re-exports.
   - New tests: `test_derived.py` with hand-computed reference values for each scalar + insufficient-history returns None; shadow-guard raise test.
   - Spec ref: "Reserved Scalars (Engine-Computed)".
   - Acceptance: `ctx = EvaluationContext.from_raw_series({"price": [...252...], "high": [...], "low": [...]}, scalars={}, params={})`; `engine.evaluate("price > ma200 * 1.15", ctx)` resolves without undefined-variable error.

5. **NEW-17-05 — Create `openlia.formula.rules` module (`Rule`, `RuleSet`, `evaluate_ruleset`, label interpolation).**
   - Files: create `packages/core/src/openlia/formula/rules.py` with Pydantic (or frozen-dataclass) `Rule(status, formula, label_template)`, `RuleSet(rules, params, streak_condition)`, `PanelResult(status, matched_rule_index, label, resolved_values, derived_scalars, warnings)`, `evaluate_ruleset(ruleset, raw_series, scalars) -> PanelResult` (first-match-wins; default green on no-match; label via `str.format_map` with missing-key fallback).
   - Update `openlia.formula.__init__`.
   - Delete `pt_runner._evaluate_ruleset` and `pt_runner.RulesetPreviewResult` dataclass; `pt_runner` delegates to `evaluate_ruleset`.
   - Spec ref: "Rule-set evaluation semantics", "Label interpolation".
   - Acceptance: `tests/formula/test_rules.py` covers first-match, default-green, missing-placeholder fallback, `params`-override-`reserved` validation error; Phase 18 `/preview` endpoint integration test stays green after `pt_runner` switch.

6. **NEW-17-06 — Move streak backtest into engine and fix MA-relative correctness.**
   - Files: create `compute_streak(raw_series, streak_condition_ast, scalars, params) -> int` inside `rules.py` or `derived.py`. Use `compute_derived_series` (from NEW-17-04) to get as-of-bar values for `ma200`, `atr_14`, `std_20`, etc., and evaluate the parsed streak condition against a per-bar context reconstructed as the spec's algorithm describes. Delete `pt_runner._compute_streak_days`.
   - New tests: `test_streak.py` — fixed-threshold streaks of known length (3, 30, 90 bars), MA-relative streaks where threshold line crosses at a known bar, empty/all-false/all-true conditions, insufficient-history truncation.
   - Spec ref: "Streak Computation" section — covers the worked example with MA-relative condition verbatim.
   - Acceptance: streak counts match spec's two worked-example tables exactly.

7. **NEW-17-07 — Add `avg(field, n)` and `slope(field, n)` and `percentile(field, lookback, pct)` to registry.**
   - Files: `engine.py` `FUNCTION_REGISTRY.update(...)`.
   - `avg` is an alias of `rolling_mean` with the spec's canonical name; keep `rolling_mean` for back-compat.
   - `slope`: linear-regression slope (`numpy.polyfit` or manual OLS) of last `n` bars vs bar index.
   - `percentile`: linear-interpolation percentile rank of `field[-1]` within `field[-lookback:]`.
   - New tests: `test_engine_functions.py` adds `avg`, `slope`, `percentile` coverage with hand-computed references.
   - Spec ref: "Built-in Functions".

8. **NEW-17-08 — Add `cross_above(fast, slow)` and `cross_below(fast, slow)`.**
   - Files: `engine.py`. Accept two `Var` args whose names must be series keys OR reserved-derived names with bar-by-bar series available (from NEW-17-04). Semantics per spec: `fast[-2] <= slow[-2] AND fast[-1] > slow[-1]` for `cross_above`.
   - New tests: fixture with fixed `ma50` / `ma200` series crossing at a known bar.
   - Spec ref: "Built-in Functions".

9. **NEW-17-09 — Add `consecutive(field, op_str, value)` and `days_since(event_type_str)`.**
   - Files: `engine.py`. `consecutive` requires the STRING literal from NEW-17-03; `op_str` in `{">", "<", ">=", "<=", "==", "!="}`. `days_since` reads an `events` side-channel on `EvaluationContext` (new field `events: list[dict[str, Any]] = field(default_factory=list)`).
   - New tests: `test_engine_events.py` covers `days_since("FOMC")`, `consecutive(price, ">", 85)`.
   - Spec ref: "Built-in Functions"; Diplomacy panel + Fed panel data requirements.

10. **NEW-17-10 — Error-taxonomy split: `ParseError`, `UnknownIdentifierError`, `TypeMismatchError` (subclasses).**
    - Files: `engine.py` (`FormulaError` stays base; three subclasses added); `parser.py` + `lexer.py` raise `ParseError`; `_eval_node` raises `UnknownIdentifierError` for missing vars; `_require_number`/`_require_bool` raise `TypeMismatchError`. `LexError` becomes `ParseError` subclass.
    - Add structured fields: `identifier: str | None`, `type_: str | None`, `position: int | None` (derived from `line`/`col`).
    - Update `openlia.formula.__init__` re-exports.
    - Update 90 existing tests if they match on class name (grep for `except FormulaError` — subclasses still caught).
    - Spec ref: "Error Model".

11. **NEW-17-11 — Divide-by-zero and insufficient-history return `null` + warning instead of raising.**
    - Files: `engine.py` (`/` branch, `pct_change`, `rolling_mean`, `lag`, `last` — return `None`; attach warning to a thread-local `_EvalState.warnings` list; `FormulaEngine.evaluate` returns a new `FormulaResult(value, warnings)` tuple — OR keep raising but add a `safe=True` flag to `evaluate()` that swaps to non-raising. Prefer the former; it matches spec's intent that a missing Michigan survey doesn't error the whole dashboard).
    - Breaks the "division by zero raises" contract — update `test_engine_arithmetic.py` + `test_errors.py`.
    - Spec ref: "Error Model" table.

12. **NEW-17-12 — `parse_formula` identifier-listing primitive for frontend `/parse` endpoint.**
    - Files: add `parse_formula(source) -> ParsedFormula` returning `(ast, identifiers, unknown_identifiers, warnings)` where `unknown_identifiers` is computed against a panel-supplied `known_names` set. Server routes at `/api/panic-thermometer/formula/parse` and `/api/macro-research/formula/parse` delegate.
    - New tests: `test_parse_formula.py` (identifiers extracted via AST walk; unknown-set subtraction; mixed valid/invalid).
    - Spec ref: "Validation and Debugging — POST /formula/parse".

13. **NEW-17-13 — Integrate: wire Phase 18 Oil + Inflation panels to `EvaluationContext.from_raw_series`.**
    - Files: `packages/core/src/openlia/panic_thermometer/panels/oil.py`, `.../panels/inflation.py`, `.../panels/fed_language.py`, `.../panels/wage_growth.py`, `.../panels/diplomacy.py`. Replace ad-hoc scalar merging with a single call to `EvaluationContext.from_raw_series(raw_series, scalars, params)`.
    - Files: `packages/server/src/openlia_server/services/pt_runner.py` — delete `_build_context`, `_evaluate_ruleset`, `_compute_streak_days`, `_evaluate_formula`'s context-building branch; replace with thin `evaluate_ruleset(...)` / `evaluate_formula(...)` delegations.
    - Plan ref: Phase 18 P1-10 / P1-13; closes master-tracker "MA-relative preset silently greens" complaint.
    - Acceptance: Phase 18 `test_pt_runner_formula_helpers.py` stays green or is rewritten to call the new engine surface; `FormulaEngine.evaluate("price > ma200 * 1.2", ctx)` resolves for the Oil panel in integration.

14. **NEW-17-14 — Integrate: wire Phase 19 `four_seasons` and `debt_cycle` dashboards to engine rule-set surface.**
    - Files: `packages/core/src/openlia/macro_research/dashboards/four_seasons.py`, `.../dashboards/debt_cycle.py`, `.../assembler.py`.
    - Replace private composite-indicator computation with `evaluate_ruleset` + reserved-derived scalars where applicable.
    - Plan ref: Phase 19 P1-TBD.
    - Acceptance: `test_dashboards_debt_cycle.py` + `test_dashboards_four_seasons.py` (latter to be added) pass.

15. **NEW-17-15 — Preset-validation CI gate.**
    - Files: new `packages/core/tests/formula/test_presets_validation.py` parametrized over every panel in `PT_PRESETS` and every dashboard in `MR_PRESETS`. For each preset formula, `parse_formula(formula, known_names=panel.known_identifiers())` must return zero `unknown_identifiers`.
    - Spec ref: "Validation at ship time".
    - Acceptance: CI red if any shipped preset references an unknown identifier.

16. **NEW-17-16 — Backfill tests for shipped-but-untested surface.**
    - Files: add `test_engine_coercion.py` (strict type discipline matrix); `test_engine_null.py` (all 6 null-comparison rules); `test_rules.py`; `test_derived.py`; `test_streak.py`; `test_engine_strings.py`; `test_engine_events.py`; `test_parse_formula.py`; `test_presets_validation.py`. Total new tests ~60 functions (raise total from 90 → ~150). Target ~85% coverage in `packages/core/src/openlia/formula/`.
    - Spec ref: "Testing Strategy (High Level)".

## Verification

- `uv run pytest packages/core/tests/formula/ -v` — all ~150 tests green.
- `uv run pytest packages/core/tests/panic_thermometer/ packages/server/tests/services/test_pt_runner_formula_helpers.py -v` — Phase 18 stays green after `pt_runner` delegation switch.
- `uv run pytest packages/server/tests/test_macro_research/ -v` — Phase 19 dashboards resolve `ma200` / `atr_14`.
- Manual: load PT preset with `"price > ma200 * 1.15"` on Oil panel → dashboard returns non-green status when historical MA200 crosses occur, matching spec's worked example.
- Spec diff: `planning/specs/systems/formula-engine-design.md` contains a "Shipped v1 DSL — authoritative" header; function catalog matches `FUNCTION_REGISTRY` exactly.
- Preset-validation CI: `test_presets_validation.py` passes — no preset references an unknown identifier.
