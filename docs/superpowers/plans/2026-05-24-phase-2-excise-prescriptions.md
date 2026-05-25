# Phase 2: Excise Hardcoded Prescriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the hardcoded content prescriptions that survived Phase 1 — the `MAX_CLARIFY_QUESTIONS = 3` cap, NVDA-specific examples in CLARIFY/PLAN prompts, the 20-word central_argument hard cap, the 50-line chart-selection guide + anti-patterns block in SYNTHESIZE, the per-length word budgets in WRITE, and the scattered negative phrasings across prompts. Each deletion either has a structural enforcement mechanism that makes the prompt-side prescription redundant (chart renderability), or expresses an opinion the user template should own (length, structure), or just expresses an arbitrary UX cap (3 questions).

**Architecture:** Pure prompt-string surgery — no schema changes, no new modules, no behavior-changing code. Tests pin each deletion ("the string 'X' is no longer in PROMPT") so a future inadvertent re-introduction fails CI. Each task is a small atomic PR-shaped commit; tests stay green throughout because every deletion either removes a directive the LLM would have followed (so behavior shifts toward LLM autonomy, which is the intent) or removes a guardrail that a Phase 0/1 deterministic check already covers.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, uv. All changes in `packages/core/src/openlia/llm/runtime/report_v2_3/clients/` (prompts) and `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py` (one constant deletion).

**Scope decisions resolved up front:**
- **Forced-ticker prompt in CLARIFY** stays for Phase 3 — it's coupled to `TemplateSpec.ticker_anchored` (added in Phase 1 but unused), which Phase 3 will start consuming alongside relaxing `Outline.tickers: min_length=1`. Pulling it forward now would conflate two phases.
- **Word budgets in WRITE** get **deleted entirely**, not moved to `template.default_length`. The length enum (CONCISE/NORMAL/ELABORATIVE) is semantic; modern LLMs honor it without a numeric word-band table. Users who want strict word counts express that via the template's section `intent` text.
- **NVDA examples** become sector-neutral placeholders (e.g. `<TICKER>` or generic strings) — does not require a sector-rotation strategy.
- **Negative-phrasing sweep** is bounded: only content-prescriptive negatives (e.g. "do NOT prepend currency", "Never invent fact_id") that have a positive equivalent. Schema-level shape constraints expressed as "must be one of [enum values]" stay as-is — those are accurate API contract statements, not opinions.

**Out of scope (Phase 2):**
- Anything requiring schema changes — those belong to Phase 3 (`Outline.tickers` min_length, `RESEARCH bundle non-empty`, `ChartType` enum widening)
- Anything requiring user-template upload UI — Phase 1.5
- Methodology adherence verification — parked

---

## File Structure

**Modified files:**
- `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py` — delete `MAX_CLARIFY_QUESTIONS = 3` constant; remove the `max_length=MAX_CLARIFY_QUESTIONS` validator on `ClarifyNeedsInput.questions`
- `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py` — remove `MAX_CLARIFY_QUESTIONS` import + the prompt sentence mentioning the cap; replace NVDA examples with neutral placeholders
- `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — multiple prompt surgeries (PLAN NVDA examples, SYNTHESIZE 20-word cap, SYNTHESIZE chart-selection guide, WRITE word budgets, negative-phrasing rewrites)
- Various test files — add deletion-pin tests; remove tests that asserted the deleted-content behavior

---

## Task 1: Delete `MAX_CLARIFY_QUESTIONS` cap

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py` — delete the `MAX_CLARIFY_QUESTIONS = 3` constant and remove `max_length=MAX_CLARIFY_QUESTIONS` from the `ClarifyNeedsInput.questions` field
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py` — remove the `MAX_CLARIFY_QUESTIONS` import; remove the prompt sentence that says "If you do ask, cap at {MAX_CLARIFY_QUESTIONS} and only ask what you actually need" (or rewrite it positively without the numeric cap)
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py` — add a deletion-pin test
- Test: `packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py` — remove or update any test that asserts the 3-question cap behavior

### Step 1: Read the relevant files

Read in full:
- `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py` around lines 390-430 (find `MAX_CLARIFY_QUESTIONS` and its usage on `ClarifyNeedsInput.questions`)
- `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py` — find `MAX_CLARIFY_QUESTIONS` import and its mention in the prompt
- `packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py` — find any test that asserts the 3-question cap (likely tests a `> 3` case rejects)

### Step 2: Write failing tests

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py`:

```python
def test_max_clarify_questions_cap_no_longer_exists():
    """The arbitrary 3-question cap on ClarifyNeedsInput has been
    removed (Phase 2 deletion). Clarifier should ask as many genuinely
    necessary questions as it judges; this is not an engine opinion."""
    from openlia.llm.runtime.report_v2_3.schemas import ClarifyNeedsInput, ClarifyQuestion

    # Build a ClarifyNeedsInput with 5 questions (more than the old cap)
    questions = [
        ClarifyQuestion(text=f"Q{i}", kind="free_text") for i in range(5)
    ]
    # Must not raise — the cap is gone
    needs = ClarifyNeedsInput(questions=questions)
    assert len(needs.questions) == 5


def test_max_clarify_questions_symbol_not_importable_from_schemas():
    """MAX_CLARIFY_QUESTIONS was deleted; importing it should fail."""
    import pytest

    with pytest.raises(ImportError):
        from openlia.llm.runtime.report_v2_3.schemas import (  # noqa: F401
            MAX_CLARIFY_QUESTIONS,
        )
```

(If `ClarifyQuestion` requires fields beyond `text` and `kind`, adapt the constructor — read the schema to confirm.)

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py`:

```python
def test_clarifier_prompt_no_longer_caps_question_count():
    """The CLARIFIER prompt no longer says 'cap at N questions' — the
    Phase 2 deletion removes the arbitrary UX cap."""
    from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import (
        CLARIFIER_SYSTEM_PROMPT,  # or whatever the prompt constant is named
    )

    # The exact phrasing that referenced the cap should be gone.
    # MAX_CLARIFY_QUESTIONS was the only formatted N value.
    assert "cap at 3" not in CLARIFIER_SYSTEM_PROMPT.lower()
    assert "max_clarify_questions" not in CLARIFIER_SYSTEM_PROMPT.lower()
```

If `CLARIFIER_SYSTEM_PROMPT` is named differently (read the file to find it — search for the string "If you do ask" or "cap at"), use the correct name.

### Step 3: Run tests to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_schemas.py packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py -v`
Expected: failures — `MAX_CLARIFY_QUESTIONS` still exists, prompt still has the cap.

### Step 4: Delete `MAX_CLARIFY_QUESTIONS` from schemas

In `packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py`:

1. Delete the line `MAX_CLARIFY_QUESTIONS = 3` (around line 392).
2. In the `ClarifyNeedsInput` model, change `questions: list[ClarifyQuestion] = Field(..., min_length=1, max_length=MAX_CLARIFY_QUESTIONS)` to `questions: list[ClarifyQuestion] = Field(..., min_length=1)`. Keep `min_length=1` — empty needs_input would be nonsense.

### Step 5: Remove the cap from the clarifier prompt

In `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py`:

1. Remove the `from ..schemas import MAX_CLARIFY_QUESTIONS` import (or remove `MAX_CLARIFY_QUESTIONS` from the multi-import line if it's combined with other names).
2. Find the prompt sentence that says "If you do ask, cap at {MAX_CLARIFY_QUESTIONS} and only ask what you actually need." Delete the "cap at {MAX_CLARIFY_QUESTIONS}" clause but keep the spirit: rewrite to "If you do ask, only ask what you actually need." Positive phrasing.

### Step 6: Run the tests

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -20`
Expected: all new tests pass. Any pre-existing test that asserted the 3-question cap should be removed or updated (it would now be testing the absence of removed behavior).

### Step 7: Commit

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/schemas.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py packages/core/tests/test_runtime/test_report_v2_3/
git commit -m "refactor(report_v2_3): drop MAX_CLARIFY_QUESTIONS cap and prompt mention"
```

---

## Task 2: Neutralize NVDA-specific examples in CLARIFY and PLAN prompts

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py` — replace NVDA examples on lines ~60, 65, 89 with neutral placeholders
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — replace NVDA in the PLAN system prompt's JSON example (line ~181)
- Test: pin the deletion

### Step 1: Find every NVDA mention in v2.3 prompts

Run: `grep -n "NVDA\|nvidia" packages/core/src/openlia/llm/runtime/report_v2_3/clients/`

Note: the `_planner_payload` integration test in `test_llm_stage_clients.py` uses NVDA as a fixture ticker — those are fine and stay (they're test setup, not prompt content). Phase 2 only targets prompt content seen by the LLM.

### Step 2: Write failing tests

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py`:

```python
def test_clarifier_prompt_no_longer_uses_nvda_as_example():
    """The CLARIFIER prompt should use sector-neutral placeholders so
    the LLM is not biased toward US semiconductor tickers."""
    from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import (
        CLARIFIER_SYSTEM_PROMPT,
    )

    assert "NVDA" not in CLARIFIER_SYSTEM_PROMPT
    assert "Nvidia" not in CLARIFIER_SYSTEM_PROMPT
```

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py`:

```python
def test_plan_system_prompt_no_longer_uses_nvda_as_example():
    """PLAN_SYSTEM_PROMPT's JSON example should use a neutral
    placeholder ticker, not NVDA."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        PLAN_SYSTEM_PROMPT,
    )

    assert "NVDA" not in PLAN_SYSTEM_PROMPT
```

### Step 3: Run tests to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_clarifier.py packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -k "nvda" -v`
Expected: failures.

### Step 4: Replace NVDA in CLARIFIER_SYSTEM_PROMPT

In `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py`:

Three NVDA mentions to replace (verify exact lines via grep before editing):
- A phrase like `("Initiation on NVDA"), name the company instead ("Update on ...")` — replace `NVDA` with `<TICKER>` and `Update on ...` with `Update on <COMPANY>`
- A list like `e.g. "NVDA", "AAPL", "TSM" — bare US tickers; for ...` — replace with `e.g. <TICKER> — bare US tickers; for ...` (drop the multi-example NVDA/AAPL/TSM list; one placeholder is enough)
- A JSON example like `"inferred_tickers": ["NVDA"]` — replace with `"inferred_tickers": ["<TICKER>"]`

Use sector-neutral placeholders. Do not invent a fake ticker (e.g. `"XYZ"`) — `<TICKER>` is clearer that it's a placeholder.

### Step 5: Replace NVDA in PLAN_SYSTEM_PROMPT

In `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` around line 181, in the JSON example for the Outline output:

```python
  "tickers": ["NVDA"],
```

Change to:

```python
  "tickers": ["<TICKER>"],
```

If there are other NVDA mentions in the same prompt block (e.g. expected_fact_ids like `rev_ttm` aren't NVDA-specific so they stay), only swap the literal NVDA.

### Step 6: Run tests

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -10`
Expected: all pass, including the new deletion-pin tests.

### Step 7: Commit

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/tests/test_runtime/test_report_v2_3/
git commit -m "refactor(report_v2_3): neutralize NVDA-specific examples in CLARIFY and PLAN prompts"
```

---

## Task 3: Remove 20-word cap on `central_argument` in SYNTHESIZE prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — find the two places that mention the 20-word cap (line ~362 in the JSON example, line ~396 in the rules section) and remove them
- Test: pin

### Step 1: Read the SYNTHESIZE prompt

Read `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` around lines 330-420 (find `SYNTHESIZE_SYSTEM_PROMPT` and its `central_argument` mentions).

### Step 2: Write the failing test

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py`:

```python
def test_synthesize_prompt_no_longer_caps_central_argument_to_20_words():
    """The 20-word hard cap on central_argument was an engine opinion
    not a methodology guarantee — deleted in Phase 2."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        SYNTHESIZE_SYSTEM_PROMPT,
    )

    assert "20 words" not in SYNTHESIZE_SYSTEM_PROMPT
    assert "20-word" not in SYNTHESIZE_SYSTEM_PROMPT
    assert "Hard cap" not in SYNTHESIZE_SYSTEM_PROMPT
```

### Step 3: Run to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -k "central_argument" -v`
Expected: failures.

### Step 4: Edit the prompt

In `SYNTHESIZE_SYSTEM_PROMPT`:

1. In the JSON example, change `"central_argument": "ONE SHORT SENTENCE — max 20 words. Hard cap."` to `"central_argument": "ONE SHORT SENTENCE — the report's hero line."`
2. In the rules section, find the bullet that says something like "central_argument is the cover hero — keep it to ONE sentence, ≤ 20 words, no clauses chained with 'but'/'however' that bury the punchline." Rewrite to: "`central_argument` is the cover hero — keep it to one sentence. Lead with the takeaway."

The "lead with the takeaway" sentence is positive and replaces the "no clauses chained with 'but'/'however' that bury the punchline" negative.

### Step 5: Run tests and commit

```bash
uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -5
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py
git commit -m "refactor(report_v2_3): drop 20-word central_argument cap from SYNTHESIZE prompt"
```

---

## Task 4: Delete chart-selection guide and anti-patterns block from SYNTHESIZE prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — delete the ~50-line chart-selection guide + anti-patterns block (around lines 420-460)
- Test: pin

### Step 1: Read the chart-selection block

Read `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` around lines 420-460 to identify the exact block (typically starts with "Chart-selection guide" and includes an "Anti-patterns — do NOT do these" sub-block).

### Step 2: Write the failing test

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py`:

```python
def test_synthesize_prompt_no_longer_dictates_chart_selection():
    """VisualizeStage already drops un-renderable charts deterministically.
    The 50-line chart-selection guide + anti-patterns prose in
    SYNTHESIZE_SYSTEM_PROMPT was redundant aesthetic opinion — deleted
    in Phase 2."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        SYNTHESIZE_SYSTEM_PROMPT,
    )

    assert "Chart-selection guide" not in SYNTHESIZE_SYSTEM_PROMPT
    assert "Anti-patterns" not in SYNTHESIZE_SYSTEM_PROMPT
```

### Step 3: Run to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -k "chart_selection" -v`

### Step 4: Delete the block

In `SYNTHESIZE_SYSTEM_PROMPT`, find and delete the entire block that starts with `Chart-selection guide` and ends after the anti-patterns sub-block. Replace with one short positive line:

```
For each chart you choose, pick the form that fits the data. The
VISUALIZE stage downstream will drop any chart whose data shape does
not render cleanly, so prefer the simplest form that supports the
claim — do not invent elaborate forms to satisfy an aesthetic.
```

(The new line is short and trusts VISUALIZE's deterministic check. If you want to omit even this line, that's also acceptable — the schema's `ChartType` enum already constrains the LLM's choices.)

### Step 5: Run tests and commit

```bash
uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -5
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py
git commit -m "refactor(report_v2_3): delete redundant chart-selection prose from SYNTHESIZE"
```

---

## Task 5: Remove per-length word budgets from WRITE prompt

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — delete the "Length budget" block in WRITE_SYSTEM_PROMPT (around lines 696-704) that maps each `ReportLength` enum value to a word band
- Test: pin

### Step 1: Read the WRITE length-budget block

Read `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` around lines 690-710. The block likely looks like:

```
Length budget — match the requested length:
- concise:     ~150-250 words. One tight paragraph or two short ones.
- normal:      ~300-500 words. 2-3 paragraphs. Headline + supporting...
- elaborative: ~600-900 words. 3-5 paragraphs. Add second-order...
```

### Step 2: Write the failing test

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py`:

```python
def test_write_prompt_no_longer_dictates_per_length_word_budgets():
    """The hardcoded word bands per ReportLength enum value were an
    engine opinion — the enum's semantic name (concise/normal/
    elaborative) conveys intent without a numeric table. Deleted in
    Phase 2."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        WRITE_SYSTEM_PROMPT,
    )

    # These bands were the most prescriptive — none should survive
    for band in ("150-250", "300-500", "600-900"):
        assert band not in WRITE_SYSTEM_PROMPT, (
            f"WRITE_SYSTEM_PROMPT still contains word band {band!r}"
        )
```

### Step 3: Run to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -k "word_budget" -v`

### Step 4: Delete the block

In `WRITE_SYSTEM_PROMPT`, find and delete the entire "Length budget" block (the heading + 3 bullets). Replace with a single positive sentence that conveys the same intent without numbers:

```
Match the requested length: `concise` is short and surface-only;
`normal` is the default depth; `elaborative` adds second-order detail
and counterpoints.
```

If the surrounding prompt structure has a heading style (e.g. "Length budget —"), match the new short text to it. The new sentence trusts the LLM to interpret the semantic enum names.

### Step 5: Run tests and commit

```bash
uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -5
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py
git commit -m "refactor(report_v2_3): drop per-length word budgets from WRITE prompt"
```

---

## Task 6: Negative-phrasing sweep across v2.3 prompts

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py` — rewrite remaining "do NOT" / "Never" / "MUST NOT" content prescriptions to positive phrasing across PLAN / SYNTHESIZE / WRITE / VERIFY prompts
- Modify: `packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_researcher.py` — same sweep applies (RESEARCH prompt had several negative phrasings per the audit)
- Test: pin a sample to prevent regression

### Step 1: Find every negative phrasing

Run from the repo root:

```bash
grep -nE "do NOT|DO NOT|Do NOT|Never |never |MUST NOT|must not|don't" packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_researcher.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_clarifier.py
```

Many of these will be inside prompt strings — those are the targets. Some will be in docstrings or comments — those stay (only LLM-facing prompt text matters).

For each LLM-facing negative phrasing, rewrite to a positive equivalent. Examples:

- `"do NOT prepend currency symbols, units, or the numeric value yourself"` → `"leave currency symbols, units, and numeric values to the engine"`
- `"Never invent a fact_id"` → `"every fact_id you cite must already exist in the bundle"`
- `"do NOT make a line"` → `"use line charts only when you have ≥4 periods"` (already template-driven after Task 4's chart-selection deletion, but if any negative survives, rewrite)
- `"don't expand scope"` → `"keep the rewrite focused on the issue"`

**Schema-level negatives stay:** "chart_type MUST be one of the enum values" is an accurate API contract statement, not an opinion — leave it alone. The convention from `feedback_positive_prompts` targets content prescriptions, not schema constraints.

### Step 2: Write a representative pin test

Add to `packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py`:

```python
def test_v23_prompts_use_positive_phrasing_for_content_prescriptions():
    """Per the `feedback_positive_prompts` convention, content-level
    instructions in v2.3 prompts should be phrased positively. Schema-
    level enum constraints (\"chart_type MUST be one of ...\") stay as
    accurate API contract statements; this test targets the content-
    prescriptive negatives from the audit."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        PLAN_SYSTEM_PROMPT,
        SYNTHESIZE_SYSTEM_PROMPT,
        WRITE_SYSTEM_PROMPT,
        VERIFY_SYSTEM_PROMPT,
    )

    # Sentinel phrases the audit flagged — none should survive
    forbidden_phrases = [
        "do NOT prepend",
        "Never invent a fact_id",
        "don't expand scope",
    ]
    for prompt_name, prompt in (
        ("PLAN", PLAN_SYSTEM_PROMPT),
        ("SYNTHESIZE", SYNTHESIZE_SYSTEM_PROMPT),
        ("WRITE", WRITE_SYSTEM_PROMPT),
        ("VERIFY", VERIFY_SYSTEM_PROMPT),
    ):
        for phrase in forbidden_phrases:
            assert phrase not in prompt, (
                f"{prompt_name}_SYSTEM_PROMPT still contains {phrase!r}"
            )
```

(Adapt the imports to whatever the actual prompt constant names are. Verify by reading `llm_stage_clients.py` first.)

### Step 3: Run to confirm failure

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/test_llm_stage_clients.py -k "positive_phrasing" -v`

### Step 4: Sweep the prompts

For each negative content prescription found in Step 1, rewrite to a positive equivalent. The goal is intent preservation, not literal translation — sometimes a "do not" becomes a sentence dropped entirely because the positive version is implied by other guidance.

For prompts in `llm_researcher.py`, the same approach applies — find the negative phrasings inside the RESEARCH system prompt and rewrite positively.

Do not modify the `responses.py` adapter or any other non-prompt code — this sweep is prompt-strings only.

### Step 5: Run all tests as a regression check

Run: `uv run pytest packages/core/tests/test_runtime/test_report_v2_3/ -v 2>&1 | tail -10`
Expected: all pass. Several prompt-content tests may have been written against the negative phrasing; if any fail because they grep for "do NOT" in a prompt, those tests need updating to the new positive equivalent.

### Step 6: Commit

```bash
git add packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_stage_clients.py packages/core/src/openlia/llm/runtime/report_v2_3/clients/llm_researcher.py packages/core/tests/test_runtime/test_report_v2_3/
git commit -m "style(report_v2_3): rewrite content-prescriptive negatives as positives across v2.3 prompts"
```

---

## Task 7: Server-side regression check

After Tasks 1-6, the v2.3 prompt surface has shifted meaningfully. Run the server test suite as a final regression check before opening the PR.

### Step 1: Run server tests

```bash
uv run pytest packages/server/tests/ -v 2>&1 | tail -10
```

Expected: 2103/2103 pass. If any test fails, it's likely because that test asserted on a specific prompt string (snapshot test). For each failure, decide:

- If the assertion was on schema-level shape (e.g. "the planner output contains a `sections` list") → fix the test if the schema didn't change but the prompt did
- If the assertion was on a prompt's literal text (e.g. "the prompt mentions '4-8 sections'") → that test was asserting the old behavior; delete or update

### Step 2: Run lint

```bash
uv run ruff format packages/core/src/openlia/llm/runtime/report_v2_3/clients/ packages/core/tests/test_runtime/test_report_v2_3/ && uv run ruff check packages/core/src/openlia/llm/runtime/report_v2_3/clients/ packages/core/tests/test_runtime/test_report_v2_3/
```

Expected: no issues.

### Step 3: Commit any remaining fixes from the regression check

If steps 1-2 surfaced fixes, group them by what they fix. Prefer separate commits per fix-type to keep the history reviewable:

```bash
git add <changed files>
git commit -m "test(report_v2_3): update post-Phase-2 prompt-content assertions"
```

If nothing needed fixing, this task has no commit — that's fine.

---

## Self-Review Notes

- **Spec coverage:** every Phase 2 roadmap item that survived Phase 1 has a task — MAX_CLARIFY_QUESTIONS cap (1), NVDA examples (2), 20-word central_argument cap (3), chart-selection prose (4), word budgets (5), negative-phrasing sweep (6), regression check (7). Items handled in earlier phases (the "4-8 sections" line in PLAN, `_BUILTIN_TEMPLATE_SHAPES` in CLARIFY) are NOT re-touched.
- **Forced-ticker prompt** is deferred to Phase 3 with a one-sentence rationale in the architecture header (coupled to `TemplateSpec.ticker_anchored` consumption).
- **No placeholders:** every code-bearing step shows the exact substitution / deletion. The few "exact line numbers may differ — verify via grep" notes mark places where the implementer must read the file before editing, not "implement later" deferrals.
- **Type consistency:** no new types introduced. Existing prompt constants (`PLAN_SYSTEM_PROMPT`, `SYNTHESIZE_SYSTEM_PROMPT`, `WRITE_SYSTEM_PROMPT`, `VERIFY_SYSTEM_PROMPT`, `CLARIFIER_SYSTEM_PROMPT`) referenced consistently across tasks.

---

**Plan complete and saved to `docs/superpowers/plans/2026-05-24-phase-2-excise-prescriptions.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between, fast iteration.

**2. Inline Execution** — batch execution with checkpoints.

**Which approach?**
