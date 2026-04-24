# Phase 17 — Formula Engine fix plan (→ 100%)


**Current:** ~70% shipped. **Root cause:** SPEC_DRIFT — plan and `formula-engine-design.md` describe materially different DSLs.

**Gap summary:** Engine shipped per plan's canonical API. Spec requires a richer surface: `RuleSet` + `evaluate_ruleset` (ordered first-match-wins), reserved derived scalars (`ma20`/`ma200`/`atr_14`/`std_20`/`streak_days`/`high_52w`/...), separate `raw_series` vs `scalars` vs `params` context, uppercase `AND`/`OR`/`NOT` keywords, `days_since`, and `cross_above`/`cross_below` time-series functions. Phases 18 + 19 consume the plan's API today, so the spec's surface is entirely unshipped.

**Decision task (must execute first):**

0. **P1-21 (Decision) — Plan wins; amend spec to match engine + layer additive spec surface on top.**

   **Rationale:** (a) plan is merged and two downstream phases import its names verbatim; (b) spec's extra surface is additive, not contradictory, and can be layered without breaking imports; (c) reversing direction means rewriting Phase 18 panel code + Phase 19 T2 wiring + all tests already green.

   **Concretely:** keep `FormulaEngine.evaluate`, `EvaluationContext(values, history)`, `parse`, `extract_requirements`, `RequirementRef` frozen. Add the spec's ruleset + reserved-scalar layer as NEW submodules (`openlia.formula.rules`, `openlia.formula.derived`). Amend `planning/specs/systems/formula-engine-design.md`: update "Module Placement" to list actual files; update "Operators" to note `and`/`or`/`not` are lowercase (matches Python conventions) with an alias layer if uppercase requested; drop `ast_nodes.py`/`tokenizer.py`/`evaluator.py`/`exceptions.py`/`types.py` as separate files.

**Tasks (in execution order):**

1. **NEW-17-01 — Write the spec-vs-engine reconciliation section inside the spec.**
   - Files: `planning/specs/systems/formula-engine-design.md` (prepend "Shipped v1 surface" section).
   - Why new: no existing ticket covers the spec amendment itself.
   - Acceptance: spec no longer references separated modules; lists shipped canonical imports verbatim.

2. **NEW-17-02 — Implement `openlia.formula.rules` (`RuleSet`, `Rule`, `evaluate_ruleset`).**
   - Files: create `packages/core/src/openlia/formula/rules.py` with `Rule(condition, status, label_template)`, `RuleSet(rules)`, `evaluate_ruleset(ruleset, ctx) -> RuleSetResult` (first-match-wins with label interpolation, default green).
   - Update `openlia.formula.__init__` re-exports.
   - Spec ref: "Rule set evaluation (first-match-wins)" — Goals #1.
   - Acceptance: `tests/formula/test_rules.py` covers first-match, default green, label-template interpolation.

3. **NEW-17-03 — Implement `openlia.formula.derived` (reserved scalars from `raw_series`).**
   - Files: create `packages/core/src/openlia/formula/derived.py` — `derived_scalars(raw_series) -> dict` computing `price`, `prev_close`, `change_pct`, `ma20/50/100/200`, `atr_14`, `std_20`, `high_52w`, `low_52w`, `pct_from_high`, `pct_from_low`, `price_vs_ma200`, `ma50_vs_ma200`, `streak_days`. Missing-history cases return `None`.
   - Wire into `EvaluationContext.from_raw_series(raw_series, scalars, params)` classmethod.
   - Spec ref: "Reserved Scalars (Engine-Computed)".
   - Acceptance: `tests/formula/test_derived.py` exercises each reserved scalar; Phase 18 `OilPanel` / `InflationPanel` resolve `ma200` and `atr_14` (closes P1-10).

4. **P1-10 (downstream cleanup) — Wire Oil + Inflation panels to use `EvaluationContext.from_raw_series`.**
   - Files: `packages/core/src/openlia/panic_thermometer/panels/oil.py`, `panels/inflation.py`.
   - Spec ref: PanicThermometerPageSpec "MA-relative preset" + "Volatility-adjusted preset".
   - Acceptance: `FormulaEngine.evaluate("price > ma200 * 1.2", ctx)` resolves; MA-relative preset no longer silently greens.

5. **NEW-17-04 — Add case-insensitive `AND`/`OR`/`NOT` keyword aliases in lexer.**
   - Files: `packages/core/src/openlia/formula/lexer.py`; `tests/formula/test_lexer.py` parametrize uppercase.
   - Acceptance: uppercase vs lowercase evaluate identically.

6. **NEW-17-05 — Add `days_since(iso_date_str)` and `cross_above/cross_below` to `FUNCTION_REGISTRY`.**
   - Files: `packages/core/src/openlia/formula/engine.py`.
   - Spec ref: Diplomacy panel uses `days_since`, PT MA presets use `cross_above`.
   - Acceptance: `tests/formula/test_engine_functions.py` adds coverage.

**Verification:** `uv run pytest packages/core/tests/formula/ -v`; Phase 18 panels + Phase 19 T2 still green; spec's "Shipped v1 surface" section lists actual files.
