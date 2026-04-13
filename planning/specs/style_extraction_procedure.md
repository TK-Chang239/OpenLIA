# Style Extraction Pipeline: Procedure and Future Feature Design

Procedure for extracting writing style patterns from professional investment bank research reports, and how this maps to a future user-facing feature for custom report style customization.

## Overview

The pipeline takes a set of example reports (PDFs) and produces two outputs:
1. A **style guide** (markdown) codifying the writing conventions observed across examples
2. Enriched **framework instructions** (JSON) with section-level guidance derived from the examples

These outputs are consumed by the LLM at report generation time: the style guide as a system prompt component, and the framework instructions as per-section directives.

## The 4-Phase Pipeline

### Phase 1: Per-Report Section Extraction

**Input:** Individual PDF reports
**Output:** One JSON file per report containing structured content mapped to framework sections

Each report is sent to the LLM with the full PDF and a prompt that asks it to:
- Map report content to the 7-section framework (investment_thesis, event_analysis, financial_results, estimate_revisions, valuation_and_target, scenarios, risks)
- Extract the actual text content of each section found
- Annotate each section with style observations: structure (paragraph/bullets/table/hybrid), tone (direct/hedged/analytical), data_usage (inline citations, table format, metric callouts), and notable_phrases (2-3 exemplary phrases)
- Extract metadata: bank name, ticker, company, date, rating, target price, currency, language, report type
- Capture overall_style observations, visual_elements, and cover_layout

**Key design decisions:**
- Reports are processed individually (no cross-report context needed), so this phase parallelizes well
- Not all 7 sections appear in every report; the LLM only extracts what exists
- Boilerplate (disclaimers, legal notices, analyst certifications) is explicitly excluded
- Claude's API accepts PDFs natively via base64 document content blocks, so no PDF-to-text conversion is needed

### Phase 2: Cross-Report Pattern Analysis

**Input:** All Phase 1 JSON outputs, grouped by section type
**Output:** One JSON analysis file per section type (7 total)

Section extracts are grouped by framework_section_id. For each section type, all examples from all reports are sent together with a prompt asking the LLM to identify:
- **Structural patterns**: Common ordering, format (paragraph vs bullets vs table)
- **Writing conventions**: Consistent language patterns, hedging usage, standard openings/closings, typical length
- **Data presentation**: What data points are commonly included, how numbers are cited, formatting conventions
- **Common vocabulary**: Recurring phrases and constructions across banks
- **Variation notes**: What differs across banks (GS style vs MS style) vs across report types (earnings vs event note)
- **Quality indicators**: Which examples are clearest and most effective, and why

**Key design decisions:**
- Grouping by section type (not by bank or by report) ensures the analysis captures what is universal about each section
- Bank attribution is preserved so bank-specific patterns can be identified without losing the source
- This phase requires all Phase 1 outputs as input

### Phase 3: Exemplar Selection

**Input:** Phase 1 extracts (grouped by section) + Phase 2 analyses
**Output:** One JSON file per section type containing 2-3 selected exemplars

For each section type, the LLM reviews all available examples against the patterns identified in Phase 2 and selects the 2-3 best exemplars based on:
- **Representativeness**: Follows common patterns from the cross-report analysis
- **Quality**: Clear writing, strong data integration, professional tone
- **Diversity**: Different banks or event types to show acceptable variation
- **Self-containment**: The excerpt makes sense without the rest of the report

Each selected exemplar includes the content, source report, bank, and a selection_reason explaining why it was chosen.

**Key design decisions:**
- 2-3 exemplars per section balances coverage with token budget at generation time
- The selection_reason serves double duty: it validates the choice and can be shown to users in the future feature

### Phase 4: Style Guide Synthesis

**Input:** Phase 2 analyses + Phase 3 exemplars
**Output:** A single markdown style guide document

The LLM synthesizes all pattern analyses and exemplars into an actionable style guide structured as:

1. **Overall Writing Style** -- tone/voice, hedging conventions, number formatting rules, sentence structure norms, what to avoid
2. **Per-Section Guidelines** -- for each of the 7 sections: purpose, structure, tone, data integration rules, do/don't lists, annotated exemplar
3. **Data Presentation Rules** -- table formatting, chart patterns, actuals vs estimates presentation, currency/unit conventions
4. **Cover Page Conventions** -- information layout, rating/target display, key metrics selection

**Key design decisions:**
- The guide is written for LLM consumption (actionable rules, not abstract advice)
- Exemplars include annotations explaining what makes them effective, so the LLM understands the principle behind the example
- The guide is a standalone document that can be included in a system prompt alongside the framework JSON

## Current Artifacts

### Scripts

- `scripts/extraction/pipeline.py` -- Main pipeline runner. Supports resumable execution (checks for cached outputs), phase selection (`--phase 2`), model override (`--model`), and cache clearing (`--clean --phase 1`). Uses the Anthropic Python SDK to send PDFs directly to Claude.
- `scripts/extraction/prompts.py` -- All 4 phase prompts as Python string constants. System prompts and user prompts are separated for each phase.

### Usage

```bash
# Run the full pipeline
uv run --with anthropic python scripts/extraction/pipeline.py --reports-dir path/to/pdfs/

# Run a specific phase
uv run --with anthropic python scripts/extraction/pipeline.py --phase 2

# Use a different model
uv run --with anthropic python scripts/extraction/pipeline.py --model claude-opus-4-20250514

# Re-run a phase (clear cache first)
uv run --with anthropic python scripts/extraction/pipeline.py --clean --phase 1
```

### Output Structure

```
scripts/extraction/output/          # gitignored (may contain proprietary content)
  phase1/
    {report_stem}.json              # one per report
  phase2/
    {section_id}.json               # one per section type (7 total)
  phase3/
    {section_id}.json               # exemplars per section type
  phase4/
    style_guide.md                  # final synthesized style guide
```

### Generated Outputs (committed)

- `planning/frameworks/stock_update_style_guide.md` -- The style guide produced by this pipeline, manually reviewed and committed. Used as a reference during report generation.
- `planning/frameworks/stock_update_framework.json` -- The framework template with section instructions enriched using patterns from the extraction. The instructions field in each section was updated to reflect writing conventions, data citation formats, table structures, and exemplar patterns observed in the 34 professional reports.

## Mapping to a User-Facing Feature

### Feature Concept

Users upload their own collection of example reports (PDFs). The system runs the extraction pipeline and produces a custom style guide + enriched framework instructions that match the user's preferred writing conventions. This allows each user or organization to have reports generated in their house style.

### Architecture

```
User uploads PDFs
  |
  v
[Phase 1] Per-report extraction (parallelized, one LLM call per PDF)
  |
  v
[Phase 2] Cross-report pattern analysis (one LLM call per section type)
  |
  v
[Phase 3] Exemplar selection (one LLM call per section type)
  |
  v
[Phase 4] Style guide synthesis (one LLM call)
  |
  v
Custom style guide + enriched framework stored per user/org
  |
  v
Report generation uses custom style guide in system prompt
```

### Integration Points

1. **Upload interface**: Settings page or Equity Research department settings. User selects report mode (stock_update, stock_initiation), uploads 5-30 PDF examples.
2. **Processing**: Background job runs the 4-phase pipeline. Progress shown to user (Phase 1 is the longest, one call per report).
3. **Storage**: Style guide and enriched framework stored alongside user/org settings. Could be stored as files in the repository (for self-hosted) or in the database.
4. **Consumption**: At report generation time, the custom style guide is prepended to the system prompt. The enriched framework instructions replace the default framework's instructions field.
5. **Iteration**: Users can re-run extraction with updated examples. They can also manually edit the generated style guide.

### Design Considerations

- **Minimum example count**: The pipeline works with as few as 3-5 reports, but pattern analysis improves with 15-30. Consider showing a quality indicator based on example count.
- **Mixed sources**: Examples from different banks/authors produce a blended style. If users want a pure Goldman style, they should upload only Goldman reports. The UI should communicate this.
- **Report mode scoping**: Each report mode (stock_update, stock_initiation) needs its own extraction run with mode-appropriate section definitions. The SECTION_IDS and SECTION_TITLES in pipeline.py must be parameterized by mode.
- **Cost**: Phase 1 dominates cost (one LLM call per report with full PDF). For 30 reports using claude-sonnet, estimate ~$3-8. Consider showing estimated cost before starting.
- **Framework sections**: The current pipeline hardcodes 7 sections for stock_update. To support stock_initiation (13 sections) or future report modes, the section definitions should be loaded from the framework JSON rather than hardcoded.
- **Language**: The pipeline handles reports in any language. Non-English reports produce style guides with non-English exemplars, which is correct behavior since the generated reports should match the input language conventions.

### Required Changes for Productionization

1. **Parameterize by report mode**: Load section IDs/titles from the framework JSON file instead of hardcoding
2. **Add to core package**: Move pipeline logic into `packages/core/src/openlia/reports/style_extraction/` so it's accessible from the server
3. **Server route**: Add endpoint in `packages/server/` to trigger extraction, report progress via SSE, and store results
4. **Progress reporting**: Phase 1 progress is per-report; Phases 2-4 are per-section-type. Report both via SSE events.
5. **Error handling**: Phase 1 JSON parse failures should be retried once (the LLM occasionally wraps JSON in markdown code blocks despite the system prompt). The current `parse_json_response` already strips code block wrappers.
6. **Storage**: Decide between filesystem (planning/frameworks/ pattern) and database. Filesystem is simpler for self-hosted single-user; database is needed for multi-user company mode.

## First Extraction Run: Reference

The first extraction was performed manually on 34 professional reports from 6 investment banks:
- Goldman Sachs (11 reports)
- Morgan Stanley (8 reports, including US-listed stocks)
- Citi (3 reports)
- HSBC (1 report)
- Daiwa (4+ reports)
- GF Securities (1 report)

Coverage: Taiwan tech, US semiconductors/tech, shipping, textiles, utilities. Mix of earnings updates, rating changes, and event notes. All reports were short-form (2-7 content pages), matching the stock_update report mode.

Key findings that shaped the framework and style guide:
- Thesis-first writing is universal across all banks
- Inline data citation format is highly consistent: "metric of $X.XB (+Y.Y% YoY)"
- Hedging language conventions are standard: "we believe", "in our view", "we expect"
- Only Morgan Stanley consistently uses structured bull/bear/base scenarios; other banks use risk lists instead
- Table structures for financial results and estimate revisions are highly standardized
- Cover page layouts vary by bank but always include: rating, target price, current price, key forecast table
