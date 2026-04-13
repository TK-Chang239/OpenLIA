PHASE1_SYSTEM = "You are an expert financial analyst. Respond with valid JSON only. No markdown code blocks, no explanatory text outside the JSON."

PHASE1_EXTRACT = """\
You are reviewing a professional investment bank research report (a short-form \
stock update or event note, typically 2-7 content pages). Your task is to extract \
structured content and analyze writing style patterns.

## Task

Map the report's content to the 7-section framework below. Not all sections may \
be present in every report -- only extract sections where the report has relevant \
content. Ignore boilerplate such as disclaimers, legal notices, analyst \
certifications, and disclosure pages.

### Framework Sections

1. **investment_thesis** -- The main investment thesis or key takeaway. Usually \
the opening paragraph or summary box. States the event, its significance, and the \
investment implication.

2. **event_analysis** -- Detailed analysis of the triggering event. What happened, \
why it matters, management commentary, context vs. expectations.

3. **financial_results** -- Key financial figures from the event. Revenue, EPS, \
margins vs. estimates. Quarter-over-quarter and year-over-year comparisons.

4. **estimate_revisions** -- Changes to forward estimates (revenue, EPS) for \
future fiscal years. Old vs. new estimates and direction of revisions.

5. **valuation_and_target** -- Price target and valuation methodology. Forward \
P/E, DCF, or other methods. Comparison to prior target.

6. **scenarios** -- Bull/bear/base case scenarios with target prices and \
assumptions for each.

7. **risks** -- Key risks mentioned in the report specific to the investment \
thesis.

## For Each Section Found, Extract

- **content**: The actual text content in the original language of the report. \
For tables, reproduce the data in a readable format. For charts, describe the \
data shown and any labels.
- **structure**: How is this section structured? (single paragraph, bullet points, \
table, narrative + table, summary box, etc.)
- **tone**: How does the author write? (direct, hedged, analytical, confident, etc.)
- **data_usage**: How are data points incorporated? (inline citations, separate \
tables, metric callouts, percentage changes in parentheses, etc.)
- **notable_phrases**: 2-3 exemplary phrases that capture the professional \
writing style. Include the original language.

## Also Extract

- **metadata**: bank name, ticker, company name, report date, rating (Buy/Hold/\
Sell or equivalent), target price with currency, language of the report, and \
report type (earnings update, rating change, event note, etc.)
- **overall_style**: General observations about the report's writing style, \
layout approach, and how it balances narrative with data.
- **visual_elements**: What charts, tables, or visual elements are used? Describe \
their type and purpose (e.g., "bar chart showing quarterly revenue trend", \
"earnings summary table with actuals vs estimates").
- **cover_layout**: How is the cover/first page laid out? What key information \
is displayed prominently? (rating badge, target price, key metrics sidebar, etc.)

## Output Format

Return a single JSON object:
{
  "metadata": {
    "bank": "",
    "ticker": "",
    "company": "",
    "date": "",
    "rating": "",
    "target_price": "",
    "currency": "",
    "report_language": "",
    "report_type": ""
  },
  "sections": [
    {
      "framework_section_id": "investment_thesis",
      "original_heading": "",
      "content": "",
      "style_observations": {
        "structure": "",
        "tone": "",
        "data_usage": "",
        "notable_phrases": []
      }
    }
  ],
  "overall_style": {
    "writing_tone": "",
    "data_presentation": "",
    "language_patterns": "",
    "visual_elements": "",
    "cover_layout": ""
  }
}
"""

PHASE2_SYSTEM = "You are an expert at analyzing writing patterns across documents. Respond with valid JSON only. No markdown code blocks, no explanatory text outside the JSON."

PHASE2_CROSS_REPORT = """\
You are analyzing {sample_count} examples of the "{section_title}" section \
(id: {section_id}) extracted from professional investment bank research reports \
by different banks.

Your goal is to identify consistent patterns in how this section is written \
across different banks and reports, and to distinguish universal conventions \
from bank-specific quirks.

## Extracted Examples

{examples_json}

## Analysis Required

1. **Structural patterns**: How is this section typically structured? Is there a \
common ordering of information? Do most reports use the same format (paragraph, \
bullets, table, hybrid)?

2. **Writing conventions**: What writing patterns are consistent across reports? \
How direct is the language? How is hedging used? Are there standard openings or \
closings? How long is this section typically?

3. **Data presentation**: What data points are commonly included? How are numbers \
cited (inline in prose, in tables, in callout boxes, with percentage changes in \
parentheses)? What units and formatting conventions are used (e.g., "NT$124.3B", \
"EPS of $2.14 vs. est. $2.08")?

4. **Vocabulary and phrasing**: What phrases appear across multiple reports? \
List specific recurring phrases or constructions. Note any industry-standard \
terms.

5. **Variation**: What differs across reports? Is the variation bank-specific \
(Goldman always does X, Citi always does Y) or report-specific (earnings notes \
do X, rating changes do Y)?

6. **Quality indicators**: Which examples are clearest and most effective? What \
specifically makes them good?

## Output Format

Return a single JSON object:
{{
  "section_id": "{section_id}",
  "section_title": "{section_title}",
  "sample_count": {sample_count},
  "structural_patterns": "",
  "writing_conventions": "",
  "data_presentation": "",
  "common_vocabulary": [],
  "variation_notes": "",
  "quality_indicators": ""
}}
"""

PHASE3_SYSTEM = "You are selecting exemplary writing samples. Respond with valid JSON only. No markdown code blocks, no explanatory text outside the JSON."

PHASE3_EXEMPLAR_SELECTION = """\
You are selecting the best examples of the "{section_title}" section to serve as \
few-shot exemplars for an LLM that will generate similar report sections.

## Selection Criteria

Select 2-3 exemplars that are:
1. **Representative**: Follow the common patterns identified in the cross-report \
analysis below.
2. **High quality**: Clear writing, strong data integration, professional tone.
3. **Diverse**: Cover different event types or banks to show acceptable variation.
4. **Self-contained**: The excerpt makes sense without the rest of the report.

## Cross-Report Pattern Analysis

{analysis_json}

## Available Examples

{examples_json}

## Output Format

Return a single JSON object:
{{
  "section_id": "{section_id}",
  "section_title": "{section_title}",
  "exemplars": [
    {{
      "source_report": "",
      "bank": "",
      "content": "",
      "selection_reason": ""
    }}
  ]
}}
"""

PHASE4_SYSTEM = "You are a writing style expert creating a comprehensive style guide. Respond in well-structured markdown."

PHASE4_STYLE_GUIDE = """\
You are synthesizing a comprehensive style guide for an LLM that generates \
professional stock update reports. You have cross-report pattern analyses and \
selected exemplars for each section type.

## Goal

Create a style guide that, when included in an LLM's system prompt alongside a \
report framework template, will produce reports matching the quality and style of \
professional investment bank research notes.

The style guide should be actionable and specific. Avoid vague advice like "be \
professional" -- instead give concrete rules like "lead every section with the \
conclusion, then support with data" or "cite numbers inline using the format: \
metric of $X.XB (+Y.Y% YoY)".

## Input: Cross-Report Analyses

{analyses_json}

## Input: Selected Exemplars

{exemplars_json}

## Required Output Structure

Write a markdown document with these sections:

### 1. Overall Writing Style
- General tone and voice
- How to handle uncertainty (hedging conventions)
- Number formatting and citation conventions
- Sentence structure and paragraph length norms
- What to avoid (promotional language, vague claims, filler)

### 2. Per-Section Guidelines
For each of the 7 framework sections:
- **Purpose**: What this section accomplishes in 1 sentence
- **Structure**: How to organize (paragraph count, ordering, format)
- **Tone**: Section-specific tone guidance
- **Data integration**: What data to include and how to cite it
- **Do**: 2-3 specific things to do
- **Don't**: 2-3 specific things to avoid
- **Exemplar**: The single best example with a brief annotation explaining \
what makes it effective

### 3. Data Presentation Rules
- Table formatting conventions
- Chart usage patterns
- How to present actuals vs. estimates
- How to show revisions (old vs. new)
- Currency and unit conventions

### 4. Cover Page Conventions
- What information appears on the cover
- How ratings and target prices are displayed
- Key metrics selection and formatting
"""
