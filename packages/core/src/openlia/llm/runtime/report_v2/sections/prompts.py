"""Section prompt assembly.

Cache-ordered: stable across runs -> stable within run -> per-section dynamic.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.types import Fact

# All 22 supported fenced block tags.
_OUTPUT_FORMAT_REMINDER = """\
CRITICAL OUTPUT FORMAT — your response must be the section file content EXACTLY in this shape, \
with no preamble, no markdown code fences, no explanations before or after:

---
section_id: <the section_id from your brief>
title: <Human Readable Title>
sources_used: [<list of [N] manifest ids you cite in this section>]
synthesis_hooks:
  thesis_contribution: "<one sentence>"
  bull_case_inputs:
    - "<bullet with [N] citation marker>"
  bear_case_inputs:
    - "<bullet with [N] citation marker>"
---

## <Section Title>

<your prose here, with [N] inline citation markers>

```chart:bar
title: ...
sources: [N]
```

<more prose>

YOUR RESPONSE MUST:
- Start with `---` on its very first line (no leading whitespace, no preamble, no code fences)
- End immediately after the last word of your final prose paragraph or fenced block \
(no trailing explanation, no closing code fence)
- Use exactly `---` (three hyphens on a line by themselves) to open AND close the YAML frontmatter
- Include the `synthesis_hooks` mapping (NOT a list — a single object)

Output format details:
- YAML frontmatter with: section_id, title, sources_used (list of [N] manifest ids you cite), \
synthesis_hooks (only for body sections)
- Markdown body for prose; use [N] inline markers to cite manifest entries
- Typed fenced YAML blocks for structured exhibits: \
```table, \
```chart:combo, \
```metric_cards, \
```key_finding, \
```bullet_list, \
```comparison_split, \
```quote, \
```timeline, \
```pull_quote, \
```rating_badge, \
```callout_grid, \
```chart:line, \
```chart:bar, \
```chart:area, \
```chart:pie, \
```chart:candlestick, \
```chart:waterfall, \
```chart:scatter, \
```chart:heatmap, \
```chart:treemap, \
```group, \
```text
- Each block carries a `sources: [N, ...]` list of manifest ids
- Do not invent citations; only cite [N] markers that resolve to entries in the manifest above.

Body sections MUST include a `synthesis_hooks` mapping in the frontmatter with EXACTLY this shape \
(a single object, not a list):

  synthesis_hooks:
    thesis_contribution: "One sentence on what this section contributes to the investment thesis."
    bull_case_inputs:
      - "Bullet point with [N] citation marker"
    bear_case_inputs:
      - "Bullet point with [N] citation marker"

Do NOT wrap `synthesis_hooks` in a list. There is ONE hook per section.

YAML safety: if any string value contains a colon (`:`), wrap the value in double quotes. Example:
  title: "Industry Overview: Network Security and Edge"
  (NOT: title: Industry Overview: Network Security and Edge)
This applies to title, eyebrow, tagline, thesis_contribution, and any other free-form string \
in the frontmatter.

CHART BLOCK SHAPES — use these exact field names and shapes:

```chart:bar
title: "Revenue by segment"
categories: ["Segment A", "Segment B", "Segment C"]
series:
  - name: "FY2024 Revenue"
    values: [120, 85, 50]
sources: [1, 3]
```

```chart:line
title: "Revenue trend"
categories: ["2020", "2021", "2022", "2023", "2024"]
series:
  - name: "Revenue ($M)"
    values: [100, 120, 145, 180, 220]
x_label: "Year"
y_label: "Revenue ($M)"
sources: [1]
```

```chart:area
title: "Cumulative growth"
categories: ["2020", "2021", "2022", "2023", "2024"]
series:
  - name: "Customers (M)"
    values: [1.2, 1.8, 2.5, 3.4, 4.6]
sources: [1]
```

```chart:scatter
title: "Growth vs valuation"
series:
  - name: "Peers"
    points:
      - {x: 12.5, y: 30.1}
      - {x: 18.3, y: 42.6}
      - {x: 24.0, y: 55.0}
x_label: "Revenue growth %"
y_label: "EV/Sales"
sources: [1]
```

```chart:combo
title: "Revenue vs margin"
categories: ["2020", "2021", "2022", "2023", "2024"]
bar_series:
  - name: "Revenue ($B)"
    values: [0.43, 0.65, 0.97, 1.30, 1.67]
line_series:
  - name: "Gross margin (%)"
    values: [76, 77, 75, 77, 77]
sources: [1]
```

CHART SERIES KEY — every series in bar/line/area/combo uses ``values: [n, n, n]`` \
(a flat list of numbers aligned to ``categories``). Scatter uses ``points: [{x, y}, ...]``.

EXHIBIT SELECTION — choose the block type that matches the data SHAPE.

- One to three independent scalars (single KPI, or a couple of unrelated KPIs like \
"operating margin" + "revenue growth") fit ``metric_cards`` or ``key_finding``. Reserve \
``chart:line`` and ``chart:bar`` for series of four or more aligned points.
- A single metric tracked over four or more time periods fits ``chart:line`` or \
``chart:area``. The x-axis must be ordered (years, quarters, months); plotting \
unordered or categorical labels on a line chart is misleading.
- Two correlated metrics sharing a time axis (e.g., revenue + margin %) fit ``chart:combo``.
- Composition or share of a whole fits ``chart:pie``, ``chart:treemap``, or stacked \
``chart:bar`` once the categorical axis has three or more items.
- Ranked items fit ``chart:bar``. Plot the UNDERLYING METRIC VALUE (market share %, \
revenue $, customer count, etc.) — never plot ordinal rank numbers like 1, 2, 3, 4. \
Sort categories DESCENDING by that metric so the largest is first, and surface the \
metric unit in the title (e.g., "CRM Market Share by Vendor (%)" not "CRM Vendor Ranking"). \
Up to eight rows.
- Events or catalysts in time order fit ``timeline``.
- Two-sided framings (bull/bear, pros/cons, strengths/weaknesses, before/after) fit \
``comparison_split``.
- Three to six concept callouts (pillars, drivers, frameworks, product families) fit \
``callout_grid``.
- Multi-row, multi-column structured data (KPIs, peer matrices, officer rosters) fit \
``table``.
- Notable attributed lines fit ``quote`` (third-party) or ``pull_quote`` (editorial).

VARIETY — aim for three to five distinct exhibit families across the report and keep \
``chart:bar`` to a minority of the chart blocks. The framework brief names the preferred \
exhibits for this specific section; start from that list.

OWNERSHIP — each metric or breakdown has a natural home section. When a peer section \
already owns an exhibit (e.g., ``historical_financials`` owns the revenue trend), other \
sections reference it in prose and pick a different exhibit family for their own data.

```metric_cards
metrics:
  - label: "Market Cap"
    value: "$69.83B"
  - label: "P/E (TTM)"
    value: "245x"
    delta: "+12%"
    delta_direction: "up"
sources: [1]
```

```key_finding
content: "Revenue grew at a 30% CAGR over 2020-2024, outpacing the peer median of 18%."
sources: [1, 3]
```

```pull_quote
text: "Our platform is becoming the system of record for the AI-native enterprise."
attribution: "Bill McDermott, CEO"
source: "Q4 2024 earnings call"
timestamp: "2025-01-29"
sources: [2]
```

```callout_grid
columns: 3
items:
  - eyebrow: "Pillar 1"
    title: "Workflow automation"
    description: "Now serves as the system of record across IT, HR, and customer service."
  - eyebrow: "Pillar 2"
    title: "AI integration"
    description: "Generative-AI co-pilots embedded into every workflow surface."
  - eyebrow: "Pillar 3"
    title: "Industry verticals"
    description: "Pre-packaged solutions for telecom, banking, and public sector."
sources: [1]
```

```timeline
title: "Recent catalysts"
events:
  - when: "2024-Q3"
    what: "Launched Now Assist AI suite across all workflows"
    impact: "Lifted ARR guidance by 2 percentage points"
    impact_tag: {label: "Beat", tone: "positive"}
  - when: "2024-11"
    what: "Acquired Element AI for $230M"
    impact: "Adds NLP and computer-vision research talent"
  - when: "2025-Q1"
    what: "Reorganized go-to-market into industry-aligned squads"
```

```chart:pie
title: "Revenue mix by geography"
segments:
  - label: "North America"
    value: 65
  - label: "EMEA"
    value: 22
  - label: "APAC"
    value: 13
donut: true
sources: [1]
```

```chart:waterfall
title: "FY24 revenue bridge ($M)"
items:
  - label: "FY23 revenue"
    value: 8971
    type: "total"
  - label: "Existing customer expansion"
    value: 1645
    type: "increase"
  - label: "New logos"
    value: 882
    type: "increase"
  - label: "Churn"
    value: -220
    type: "decrease"
  - label: "FY24 revenue"
    value: 11278
    type: "total"
sources: [1]
```

```table
title: "Peer multiples"
headers:
  - {key: "company", label: "Company"}
  - {key: "pe", label: "P/E (TTM)", align: "right"}
  - {key: "growth", label: "Rev growth %", align: "right"}
rows:
  - {company: "ServiceNow", pe: "56.6x", growth: "23%"}
  - {company: "Workday", pe: "44.1x", growth: "16%"}
  - {company: "Salesforce", pe: "28.9x", growth: "11%"}
sources: [1, 2]
```

```bullet_list
items:
  - "Backlog of $20.6B at the end of Q4, up 26% year on year"
  - "Net retention rate of 124%, the highest in the peer set"
  - "Operating cash flow margin expanded 220 basis points"
tone: "positive"
```

```quote
text: "We see ==durable acceleration== in subscription bookings."
speaker: "Gina Mastantuono"
role: "CFO, ServiceNow"
timestamp: "Q4 2024 earnings call"
tag: {label: "Guidance", tone: "positive"}
sources: [3]
```

```rating_badge
rating: "BUY"
previous_rating: "HOLD"
change_date: "2026-05-18"
```

```comparison_split
left:
  title: "Bull Case"
  tone: "positive"
  items:
    - "Edge network expansion accelerates [1]"
    - "Workers platform monetization ramps [2]"
right:
  title: "Bear Case"
  tone: "negative"
  items:
    - "Multiple compression risk at current valuation [3]"
    - "Hyperscaler competition intensifies [4]"
```

If you cannot construct a valid chart block with these exact field names, use a `table` or \
`metric_cards` block instead. DO NOT invent alternate chart field names like \
`data: {labels, values}` — they will be rejected.

CITATION PROXIMITY RULE: every quantitative figure in prose (revenue, margins, percentages, \
dollar amounts, ratios, growth rates, counts) MUST have an inline [N] citation marker within \
~10 words of the figure. Bare numbers without nearby citations will fail validation. Years \
(e.g., "2024", "founded in 2009") are NOT quantitative figures and do not need citations.

NEVER USE TOMBSTONE LANGUAGE. The following phrases (and any close variant) will fail validation \
and waste your retry budget:
  - "no data available"
  - "data not provided"
  - "data unavailable"
  - "N/A" or "n/a" (as standalone prose)
  - "TBD"
  - "unable to determine"

If a specific fact you would like to cite is not in the manifest or facts slice, REWRITE the \
sentence so it does not need that fact. Use what IS available, frame qualitatively, or omit the \
point entirely. Manifest entries and the facts slice are your ONLY source of truth — write to \
their strengths, not around their gaps. A shorter, factually grounded section beats a complete \
section padded with disclaimers.\
"""


def _format_facts_slice(facts_slice: dict[str, Fact]) -> str:
    lines: list[str] = []
    for name, f in facts_slice.items():
        sources = ", ".join(str(s) for s in f.source_ids)
        lines.append(f"  {name}: {f.value!r} (sources: [{sources}])")
    return "\n".join(lines) if lines else "  (none)"


def assemble_body_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join(
        [
            system_role,
            f"STYLE GUIDE:\n{style_guide}",
            f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
            f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
            f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
            f"Word target: {word_target}",
            _OUTPUT_FORMAT_REMINDER,
        ]
    )


def assemble_synthesis_section_prompt(
    *,
    system_role: str,
    style_guide: str,
    framework_brief: str,
    manifest: Manifest,
    synthesis_hooks_bundle: str,
    facts_slice: dict[str, Fact],
    word_target: int,
) -> str:
    return "\n\n".join(
        [
            system_role,
            f"STYLE GUIDE:\n{style_guide}",
            f"FRAMEWORK SECTION BRIEF:\n{framework_brief}",
            f"MANIFEST (citable as [N]):\n{manifest.as_prompt_list()}",
            f"SYNTHESIS HOOKS FROM BODY SECTIONS:\n{synthesis_hooks_bundle}",
            f"FACTS FOR THIS SECTION:\n{_format_facts_slice(facts_slice)}",
            f"Word target: {word_target}",
            _OUTPUT_FORMAT_REMINDER,
        ]
    )
