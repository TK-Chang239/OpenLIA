# Dalio Macro Report Template System — Design Documentation

**Version:** 1.0  
**Date:** April 2026  
**Covers:** T1 through T5 — visual design, functional logic, component inventory, data wiring, and agent integration notes  
**Companion file:** `dalio_macro_template_system_spec.md` (architecture, cadence, YAML prompt schema)

---

## How to read this document

Each template section below documents two things in parallel: what the template *looks like* (visual design — layout, components, colour semantics, typography choices) and what it *does* (functional logic — what computation runs, what each section is testing, what output it produces for downstream consumption). The separation is intentional: visual design choices are often made for functional reasons that are not obvious from looking at the rendered widget, and those reasons need to be explicit for anyone rebuilding or extending the templates.

---

## Shared design system

All five templates share a common visual grammar. Documenting it once here avoids repetition.

### Colour semantics

Colour in these templates always encodes **meaning**, never sequence or decoration.

| Colour | Semantic role | Example usage |
|---|---|---|
| Red (`#E24B4A`, `#FCEBEB`) | Critical / warning zone breached / confirmed negative signal | Debt/GDP in T1 scorecard; Stage 5 markers confirmed in T4 |
| Amber (`#EF9F27`, `#FAEEDA`) | Elevated / transitional / watch | TIPS yield in T1; transitioning season verdict in T2; gold target range |
| Green (`#639922`, `#EAF3DE`) | Healthy / expansionary / covered | PMI above 50 in T2; season coverage "full" in T3; spring quadrant |
| Blue (`#378ADD`, `#E6F1FB`) | Informational / stable / equities | Credit spreads tight in T2; equity sleeve in T3 charts |
| Purple (`#7F77DD`, `#EEEDFE`) | Bonds / mixed confidence signals | Bond allocation in T3 pie charts; season confidence label |
| Teal (`#1D9E75`, `#E1F5EE`) | Positive coverage / commodities | Season coverage "full" in T3; commodities allocation |
| Gray | Structural / neutral / historical | Past cycle stages in T4 timeline; header labels |

The rule enforced throughout: **text on any coloured background uses the 800 or 900 stop of the same ramp** — never black, never a gray. This ensures readability in both light and dark mode without conditional logic.

### Typography

- All headings: `font-weight: 500`, never 600 or 700 (too heavy against the host UI)
- Section labels: 11px, uppercase, `letter-spacing: 0.5px`, `color: var(--color-text-tertiary)`
- Body text: 13px, `color: var(--color-text-secondary)`, `line-height: 1.55`
- Emphasis within body: `color: var(--color-text-primary)`, `font-weight: 500` — never bold mid-sentence for decorative purposes
- Large metric values: 18–22px, `font-weight: 500`, coloured to match their semantic status
- Fine print / source attribution: 11px, `color: var(--color-text-tertiary)`

### Layout grid

- Two-column (`g2`): equal halves, `minmax(0, 1fr)` to prevent overflow
- Three-column (`g3`): used for metric card triplets and three-way comparisons
- Four-column (`g4`): asset playbook quadrant in T2; never used for dense text
- All grids use `gap: 10px`; padding inside cells is `10px 12px` for `.sm` and `14px 16px` for `.card`

### Card hierarchy

Three levels of containment, used consistently:

1. **`.card`** — raised white surface with `0.5px solid var(--color-border-tertiary)` border and `border-radius: var(--border-radius-lg)`. Primary section containers. Never nested inside each other.
2. **`.sm`** — secondary surface with `background: var(--color-background-secondary)`, no border. Used for metric cells, sub-sections, and contextual callouts inside a card.
3. **Coloured callout blocks** — no border, background from a semantic colour ramp (e.g. `#FAEEDA` for amber warnings, `#FCEBEB` for red alerts). Used for verdicts and direct quotes only.

### Badge component

`display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 12px`

Used for: status signals in scorecard rows, confidence labels in headers, season verdicts. The dot (`7px circle`) inside the badge encodes the same colour as the badge background but at full saturation — gives a secondary visual signal for colour-blind readers.

### Progress bar track

`height: 5px; background: var(--color-background-secondary); border-radius: 3px; overflow: hidden`

Used only in T1 and T2 scorecard rows — one per indicator. Fill colour (`fill-r` red, `fill-a` amber, `fill-g` green, `fill-b` blue) maps to the same indicator's badge status. Width is set manually as a percentage to indicate proximity to threshold, not a computed value. This is a visual approximation only and is not data-driven; it communicates relative severity at a glance without implying false precision.

### Separation rows

`border-bottom: 0.5px solid var(--color-border-tertiary)` on `.row-sep` or `.sep` classes. Used to divide items in a table or within a card. Last item in a group never has a bottom border.

### Section header strip

Every template opens with a two-element header: left side is the template ID, title, and date; right side carries the most important status badges. This follows the pattern of a status bar in a dashboard — the reader knows the overall verdict before reading the detail. The badges on the right are always the two or three highest-signal outputs of the entire template.

---

## T1 — Debt cycle position report

### Visual design

**Header badges:** "3 / 3 in warning zone" (red) and "Late plateau" (amber). Both are derived from Section A outputs — they summarise the scorecard before the reader reaches it.

**Section A — scorecard table.** Four-column grid: indicator name + spark bar, current value, Dalio warning zone description, status badge. The spark bar (5px height track) is a secondary encoding of the same red/amber/green signal carried by the badge — never the primary encoding. Column widths are `2fr / 1fr / 1.2fr / 90px` — the indicator column gets the most space because the name and sub-label need room; the value column is narrow because it carries a single number; the threshold description column is wider than the value because it needs to hold a sentence.

**Section B — phase assessment.** Two-element layout: a left-bordered callout block (amber `3px solid #EF9F27` left border, `border-radius: 0`) holding the phase narrative, followed by a 2-column grid for the historical analog and time-to-constraint fields. The left-border pattern is used here and only here across all five templates — it visually marks a forward-looking interpretive judgement rather than a data reading.

**Section C — monetary policy space.** Three metric cards in a `g3` grid. Each card has a small label (11px), a large value (18px), a unit description, and a 2–3 sentence note. The three values use different colours: `--color-text-primary` (neutral) for rate headroom, amber for QE credibility, red for debasement risk — matching the template's own semantic system.

**Section D — watchlist triggers.** Free-format rows with a `6px circle` dot on the left (red, amber, or green encoding the direction of the trigger), a fixed-width name column (`min-width: 160px`), and a free-flow description. This pattern is reused in T4 (Stage 5 markers) and T5 (force scorecard) — a consistent "signal list" component.

**Synthesis verdict.** Amber coloured callout block at the bottom. Explicitly labelled "bottom line for T5 and T3 consumption" — the downstream consumption note is part of the visual design, not just a footnote. It tells anyone reading the output what to do with it.

### Functional logic

T1 runs three indicators against Dalio's documented threshold zones. The logic is sequential:

1. Score each indicator against its threshold (red/amber/green)
2. Aggregate the three scores into a phase classification (expansion / plateau / late plateau / deleveraging)
3. Assess monetary policy space as a function of current rate level, inflation, and QE credibility
4. Generate the asset implication block and watchlist

The phase classification is the most important output — it is the primary input to T5's Force 1 score. The watchlist triggers define the conditions under which the phase classification would change, providing the agent with explicit update logic rather than requiring a full re-run of the template on every data refresh.

**What the scorecard is testing:**
- Indicator 1 (debt/GDP) tests whether the long-term debt accumulation is structurally constraining fiscal space
- Indicator 2 (interest/revenue) tests whether the constraint is already active — not a future risk but a present reality
- Indicator 3 (TIPS real yield) tests whether the monetary policy transmission mechanism for gold demand is engaged

All three can be red and the phase still "plateau" — the plateau only becomes "deleveraging" when a fiscal or monetary crisis event triggers forced adjustment. The template is designed to signal proximity to that event without claiming to predict its timing.

**Output fields consumed downstream:**
- Phase label → T5 Force 1 intensity score
- Debasement risk rating → T4 Section C cross-check
- Gold/real asset thesis → T3 Section C gold allocation check
- Watchlist triggers → morning briefing agent update conditions

---

## T2 — Four-seasons economic diagnostic

### Visual design

**Header badges:** "Transitioning summer → autumn" (amber) and "Mixed confidence" (purple). The purple badge is the only use of purple as a primary status colour across all five templates — it specifically signals epistemic uncertainty (two data inputs pointing in opposite directions) rather than a directional read. This distinction from the amber "elevated" badge is intentional.

**Section A — quadrant inputs table.** Five-column grid: indicator name + spark bar, current value, 3-month trend description, axis signal badge, directional arrow. The directional arrow (CSS triangles — no emoji) is a fifth encoding channel for the same directional signal already carried by the badge and the track fill. Multiple encodings are used because this is the most important table in the diagnostic — the reader needs to pattern-match quickly across five rows. The column layout is `1.8fr / 1fr / 0.9fr / 0.9fr / 100px`.

The CSS arrow shapes are rendered with inline border tricks — no images or external assets:
- Up arrow: `border-left: 5px transparent; border-right: 5px transparent; border-bottom: 7px solid [colour]`
- Down arrow: same with `border-top`
- Flat: a `10px × 3px` rectangle

**Section B — quadrant map.** This is the most visually distinctive component across all five templates. A fixed `aspect-ratio: 1.6/1` container divided into four quadrants by a horizontal and vertical separator line (`0.5px solid var(--color-border-secondary)`). Axis labels are positioned with `position: absolute` at the four edges. Each quadrant holds its season name, a two-line description, and a coloured asset pill.

Two position markers (red dot for April 2026, amber dot for January 2026) are placed with `position: absolute` using percentage-based `left` / `top` values calculated from the quadrant geometry. These are not data-driven coordinates — they are manually positioned to reflect the diagnostic verdict. Their purpose is to show directional movement, not precise quantitative positioning.

The map's background is `var(--color-background-secondary)` — lighter than the surrounding cards — which makes the quadrant structure visible without a heavy grid overlay.

**Section C — transition risk.** A two-panel `g2` layout inside the main card: bull case left, bear case right. No coloured background — this section deliberately avoids the red/green colouring used elsewhere because both scenarios are presented as equally worth understanding, not as good/bad. The final "key indicator to watch" block at the bottom is a single paragraph, not a table row — it is a synthesis statement, not a data field.

**Section D — asset playbook.** Four coloured cells in `g4`, each using the season quadrant colour: amber (commodities/summer), red (gold/autumn), green (equities/spring), blue (long bonds/winter). Each cell has three elements: an uppercase asset label, a 12px title describing the regime alignment, and an 11px body explaining the mechanism. The colour of each cell matches the quadrant the asset belongs to — equities get green (spring), gold gets red (autumn), long bonds get blue (winter). This creates a visual cross-reference between the quadrant map and the playbook.

**Portfolio stress test.** A gray background block at the bottom, separate from the coloured playbook cells. The stress test is always rendered in neutral colours because it describes a hypothetical that may or may not materialise — it should not carry the same visual weight as a confirmed signal.

### Functional logic

T2 has a deliberate split between two types of inputs: direction indicators (GDP trend, PMI trend) and level indicators (PMI absolute level). The framework's rule is that direction trumps level when the two conflict. This is documented in the "one key nuance" block and is the analytical crux of the April 2026 diagnostic, where PMI at 52.7 (level: healthy) contradicts GDP at +0.5% annualised (trend: clearly decelerating).

The quadrant classification algorithm:

1. Growth axis: is GDP trend rising or falling? (Primary signal.) Is PMI trend rising or falling? (Secondary signal.) If both agree, axis is clear. If they conflict, GDP direction wins and confidence is "mixed."
2. Inflation axis: is headline CPI yoy rising or falling? (Primary.) Is core CPI yoy rising or falling? (Secondary.) If headline is driven by a transitory component (e.g. energy shock), note this explicitly and weight core more heavily for the forward-looking season projection.
3. Combine: map to quadrant. If either axis is ambiguous, label as "transitioning" and name both the current and the adjacent candidate season.
4. Assign confidence: clear (both axes unambiguous), mixed (one axis ambiguous or conflicted), or transitioning (one axis in the process of flipping).

The credit spread indicator is used as a corroborating signal rather than a primary axis input. Tight spreads (as in April 2026) indicate that credit markets are not yet pricing a recession, which is a reason to moderate the growth-falling signal. Widening spreads would independently confirm it.

**What the transition risk section is testing:** It is forcing the analyst to state the falsifying condition — the specific data point that would change the season classification. This is the operationalised version of Dalio's epistemic principle ("when market reality diverges from your model, ask where your model is flawed"). The trigger must be specific (a PMI level, a GDP print, a named release date) not vague ("if things get worse").

**Output fields consumed downstream:**
- Season verdict + confidence → T3 Section A (coverage map) and Section D (retail caveat on bond allocation in inflationary regimes)
- Asset playbook tailwind/headwind → stock research agents as macro context
- Transition risk triggers → morning briefing agent watchlist

---

## T3 — All-weather allocation audit

### Visual design

**Header badges:** "Risk concentration: critical" (red) and "Gold gap: 0% held vs ~15% guidance" (amber). These two badges are chosen because they are the two findings most likely to require action — the risk concentration problem and the gold gap are both directly addressable by portfolio adjustment, unlike the macro regime findings in T1/T2 which are informational.

**Portfolio comparison strip.** Two `g2` cards side by side, each containing a Chart.js doughnut chart. The doughnut format is chosen over a bar chart because the question being answered is "what fraction of the whole does each asset represent?" — a composition question, not a comparison question. The `cutout: '60%'` setting creates a donut hole that reduces the visual mass of the chart and makes the proportions readable at the smaller size available in a two-column layout. Custom HTML legends are used instead of Chart.js defaults because the default legend renders oversized dots that misrepresent the data's nature.

The colour assignment in the donut charts uses the same ramp stops as the rest of the system: `#378ADD` (blue) for equities, `#7F77DD` (purple) for long bonds, `#AFA9EC` (light purple) for intermediate bonds, `#EF9F27` (amber) for gold, `#1D9E75` (teal) for commodities.

**Section A — coverage map.** Four coloured cells using a three-tier system: `.cov-none` (red background) for seasons the portfolio is exposed in, `.cov-part` (amber) for partial coverage, `.cov-full` / `.b-teal` for strong coverage. Each cell has a badge in the top-right corner for rapid scanning. The cell layout mirrors the quadrant map from T2 — spring/winter are on the bottom row, autumn/summer on the top — so the reader can mentally overlay the season coverage with the T2 diagnostic verdict.

**Section B — risk parity audit.** The bar chart rows are the analytical heart of T3. Each row is `display: flex; align-items: center; gap: 10px` with a `90px` right-aligned label, a flex-fill track, and a `44px` value. The fill colour is dynamically set in JavaScript: red if the contribution exceeds 60%, amber if 40–60%, green if below 40%. This encoding directly answers the question "is any single asset dominating portfolio risk?" — red means yes. The explanatory prose block below the bars is the "risk parity mechanism explained" note, which translates the visual into the arithmetic so the reader understands why the bars look the way they do.

**Section C — gold allocation check.** The gradient bar is the most visually unusual component in T3. It is a pure CSS `linear-gradient` from green (0%) through amber (40%) to red (80%+), representing the allocation range from too-low to Dalio's stress-environment guidance. Three vertical needle lines are positioned with `position: absolute; left: [X%]` to mark the key reference points (60/40's 0%, All-Weather baseline 7.5%, stress-environment ~15%). The needle at 0% has a red label; the others have amber and green labels. This component deliberately breaks from the table/card convention used everywhere else — it is the one place in all five templates where a continuous visual (the gradient) is used because the underlying concept is continuous (a range of allocation appropriateness).

Three metric cards below the gradient present current, applicable reference, and gap as point values — redundant with the gradient but necessary for precise reading. The gradient shows the shape, the cards give the numbers.

**Section D — retail investor caveats.** Four equal cells in a `g2` grid — each cell has a bold title and body text in `.body13`. There is no colour coding on these cells. This is intentional: the caveats are required reading regardless of their directional implication and should not be visually ranked. The only hierarchy is order — leverage assumption first (most fundamental), bond risk second (most relevant to current regime), rebalancing third, correlation regime fourth.

**Synthesis verdict.** Red coloured callout block — the only T3 section in red. This is reserved for the final analytical conclusion rather than being used at the indicator level, which would be redundant with the Section A coverage map signals.

### Functional logic

T3 is the only template that performs explicit arithmetic. The risk contribution calculation:

```
risk_contribution(asset) = capital_weight × annualised_volatility
risk_share(asset) = risk_contribution(asset) / sum(all_risk_contributions)
```

This is a simplified linear risk contribution model, not a full variance-covariance matrix. It does not account for correlations. For the purpose of the diagnostic — demonstrating that a 60/40 concentrates most of its risk in equities — the simplified model is sufficient and produces approximately the right answer (consistent with the research literature finding that 60/40 puts 80–90% of risk in equities). The exact figure shown (~87% for equities) is computed in JavaScript from the hardcoded volatility estimates:

- Equities: 16.5% annualised (long-run S&P 500 historical)
- Long bonds (TLT): 11.5% annualised (between long-run ~13% and current ~9%)
- Intermediate bonds: 7% annualised (intermediate Treasury typical)
- Gold: 16% annualised (GLD 30-year historical: 16.04%)
- Commodities: 18% annualised (representative broad commodity index)

These are hardcoded — not fetched from live data. They are long-run historical estimates that change slowly. The template is designed to be re-run when volatility regime changes materially (e.g. after a prolonged vol spike or compression), not on a monthly cadence.

**What the coverage map is testing:** Whether the portfolio has assets in every quadrant of the T2 four-seasons map. The coverage test is boolean at the season level (does the portfolio have at least one tailwind asset for this season?) and graded at the portfolio weight level (is that coverage material, or a token 1% allocation?). The threshold for "partial" vs "strong" coverage is implicit — a season with combined weight over 20% is "strong," 5–20% is "partial," below 5% is "exposed."

**The gold allocation check logic:**
1. Read T1 phase classification. If "late plateau" or "deleveraging": use stress-environment guidance (~15%). If "mid plateau" or below: use normal range (5–10%).
2. Read T2 season. If "autumn" or "transitioning summer/autumn": gold is seasonally aligned — do not discount the guidance. If "spring" or "summer with falling inflation": note that gold may underperform over the near term even if the structural case holds.
3. Read T5 active force count (if available). If 4–5 forces at 7+: stress-environment confirmed. If 2–3 forces: elevated but not at maximum stress.
4. Compare current gold weight to the applicable guidance. Compute gap in percentage points. Flag if gap exceeds 5pp.

**Output fields consumed downstream:**
- Coverage gaps → portfolio construction recommendations
- Gold allocation gap → T5 Section D synthesis (confirms stress-environment allocation)
- Leverage assumption caveat → agent prompt caveat when generating institutional vs retail recommendations

---

## T4 — Long-term world order assessment

### Visual design

**Header badges:** "Stage 5 — pre-breakdown" (red) and "Wealth shift: mid-stage" (amber). Stage 5 is the only place in all five templates where the status badge uses language from Dalio's own published classification rather than the template's own derived verdict — this is deliberate. When Dalio himself has made a direct public statement classifying the current stage (Fortune, March 2026), quoting that classification is more authoritative than the template's own recomputation of it.

**Section A — reserve currency health table.** Same four-column format as T1's scorecard — indicator name + spark bar, current value, trend context, status badge. The column weights are `1.8fr / 0.9fr / 1fr / 90px`. The spark bar is present here but plays a different role than in T1: in T1, it encodes proximity to a quantitative threshold; in T4, it encodes the directional velocity of a structural trend. A declining USD reserve share at 56.9% gets a shorter bar than a rapid central bank gold buying surge — the former is slow and gradual, the latter is structurally elevated.

**Reserve currency composition chart.** A Chart.js multi-line chart rendered in a `200px` height container. Five lines: USD (blue, solid, `borderWidth: 2`), EUR (purple, dashed, `borderWidth: 2`), JPY (amber, dashed, `borderWidth: 1.5`), CNY (teal, dashed, `borderWidth: 1.5`), Other (gray, dashed, `borderWidth: 1.5`). The USD line is visually dominant — heavier and solid — because it is the primary indicator. The others are secondary context. The y-axis runs 0–80% to show the full distribution including historical extremes. The data is hardcoded as representative annual snapshots from IMF COFER — not fetched live because COFER is released quarterly with a lag and the relevant trend is decadal.

**Section B — empire cycle stage.** The stage timeline strip is the most structurally complex visual component in T4. Six boxes in `display: flex`, using three visual states: `.past` (gray ramp getting progressively darker), `.active` (red, no border-radius on the active box to allow full red bleed from box edge to edge), `.future` (lighter background, muted text). The active box has `border-radius: 0` specifically — its neighbours have rounded corners from the parent's `overflow: hidden; border-radius: var(--border-radius-md)`, which means only the active box sits fully within a rounded container.

The direct Dalio quote block uses the amber coloured callout with `font-style: italic` for the quoted text and a source attribution line below. This is the only quoted text in all five templates that is displayed as a styled callout rather than embedded in prose — the distinction signals that this is Dalio's own words, not the template's interpretation of them.

**Stage 5 markers list.** Uses the same `shift-row` component as T2's transition risk section: a small coloured dot, a stage badge, and a body description. Three states: `stage-late` (red badge, "Confirmed"), `stage-mid` (amber badge, "Developing"), and a muted variant for "Not yet." This component deliberately mirrors the T5 force scorecard structure — a reader who has seen T5 recognises the pattern immediately.

**Historical analog grid.** Three equal cells using coloured backgrounds: green (pre-1971, most similar), amber (pound decline, partial parallel), red (Rome, illustrative/cautionary). The colour ordering here maps to confidence in the analogy — green for the closest parallel, amber for moderate, red for illustrative-only. Each cell has the same internal structure: bold title, "Similar:" paragraph, "Different:" paragraph. The "Different:" content is as important as the "Similar:" content — the template is designed to resist lazy analogising by requiring the analyst to explicitly document where the current situation departs from the historical pattern.

**Section C — wealth shift signals.** Four `shift-row` entries with stage badges. The stage labels ("Institutional," "Market," "Geopolitical," "Retail/ETF") map to observable signal sources, not to quality levels. The stage badge colours reflect timing of the signal: red for `stage-late` (institutional — this is the most advanced signal), amber for `stage-mid` (market and geopolitical), green for `stage-early` (retail/ETF).

**Section D — currency table and bond risk panels.** The currency table uses `display: flex; justify-content: space-between` rows with status badges on the right — a simple two-column format with no explicit column widths. The bond risk is split into two `g2` cells inside the card. No coloured backgrounds in Section D — investment implications are presented in neutral gray surface cards to distinguish them from the diagnostic sections above.

### Functional logic

T4 operates at the slowest timescale of the five templates. Its core function is a two-part assessment: (1) classify the empire cycle stage using Dalio's six-stage model against observable indicators, and (2) assess the progress of the "great wealth shift" from financial assets to real assets using three observable signal categories.

**Stage classification logic:**

The six stages are defined by Dalio and not derived by the template. The template's function is to check which Stage 5 markers are present in current data (binary: confirmed / developing / not yet) and to determine whether Stage 6 preconditions are emerging. Stage 6 would require a confirmed breakdown of the reserve currency system or a direct great-power hot war. The template outputs a stage label and a completeness score (how many of the five Stage 5 markers are confirmed vs developing).

**Wealth shift stage assessment:**

The three signal categories are assessed independently and then combined:
- Institutional (central bank gold buying): assessed as late-stage when purchasing is 2× or more above historical average on a sustained basis (3+ years). Currently confirmed.
- Market (gold/equity ratio trend): assessed as mid-stage when gold outperforms equities over a trailing 12-month period without equities having broken down. Late-stage would require a concurrent equity bear market.
- Retail/ETF (fund flows): assessed as early-stage when ETF inflows are rising but have not yet reached historical bubble-phase levels. The lag from institutional to retail is typically 12–24 months.

The combined wealth shift stage is set to the middle of the three component readings (not the average) — this prevents a strong institutional signal from inflating the overall assessment to "late-stage" when the market and retail signals are still early.

**What the analog comparison is testing:**

The historical analog section forces the analyst to answer: "Is what we're observing unprecedented, or does it rhyme with something that has happened before?" The "Different:" fields are specifically required because the most dangerous analytical errors come from over-applying a historical pattern that has one critical structural difference from the current situation (e.g. applying the 1971 gold peg break logic to a pure fiat system where there is no peg to break).

**Output fields consumed downstream:**
- Stage classification → T5 Force 3 (geopolitical cycle) intensity score
- Wealth shift stage → T3 gold allocation check (independent justification)
- Currency guidance → morning briefing agent FX exposure note
- Bond risk premium note → T1 cross-check on Treasury demand erosion

---

## T5 — Five interlocking forces dashboard

### Visual design

**Header badges:** "4 Critical" (red) and "1 High" (amber) — these are count badges, not directional badges. They answer the primary question immediately: how many forces are simultaneously elevated? The count is the single most important output of T5, because Dalio's framework argues that co-activation of 4–5 forces is historically rare and precedes major turning points. Showing the count in the header, before any detail, ensures the reader's first impression is calibrated to the significance of the finding.

**Section A — force scorecard.** Five rows in `.card`, each using the `force-row` grid: `120px / 1fr / auto`. The left cell carries the force label, sub-label, badge, and progress bar. The centre cell carries the evidence summary. The right cell is empty (auto) — it provides visual breathing room and keeps the badge column narrow. The force names are all prefaced with "Force 1" through "Force 5" — the numbering is not decorative; it is the identifier used in the agent prompt system and in cross-template references.

The progress bar in the force scorecard is different from those in T1 and T2. In T1/T2, the bar encodes proximity to a quantitative threshold. In T5, it encodes the intensity score (1–10) directly: `width: [score × 10]%`. The fill colour is red above 7/10, amber below — matching the badge. This is the one place where the bar is data-driven rather than manually set.

**Active force count block.** A wide banner card between Sections A and B, displaying the count in `font-size: 28px; font-weight: 500; color: #E24B4A` — larger than any other number in all five templates. This is intentional: the active force count is the headline finding and should be visually dominant. The surrounding card has `background: var(--color-background-secondary); border-color: var(--color-border-secondary)` — a slightly elevated surface to distinguish it from adjacent cards.

**Section B — reinforcement loop analysis.** Four `g2` cells, each describing one feedback loop. The loop component is a `.loop-block` — gray background, no border — with a title, two `arrow-row` entries (chip → arrow symbol → chip), and a prose description. The chips (`arrow-chip`) are small white-background bordered labels displaying the force label. The arrow symbol is a plain `→` character in `color: var(--color-text-tertiary)`. This component is the most abstract in the entire template system — it is describing a conceptual relationship, not a data point. The use of chips and arrows rather than prose is to make the directionality of the feedback loop scannable.

**Section C — market data.** Six metric cards in `g3`. Each follows the standard metric card pattern: `11px label / 20px value / 12px unit / 11px note`. The values are current data points (gold price, debt/GDP, interest/revenue, CB demand, BRICS gold share, TIPS yield) — the same data that appeared in T1 and T4, now consolidated in T5 as a single reference dashboard. No colour coding on the metric cards in Section C — they are reference data, not diagnostic outputs. Colour would imply a ranking or threshold assessment that is not being performed at this point in the template.

**Section D — gold allocation signal.** The gradient bar from T3 is reused here but with a different purpose. In T3, it was calibrated against the portfolio. In T5, it shows the derivation chain: active force count → Dalio guidance range → cross-check with T4 and T2. Three allocation reference markers are placed with `position: absolute` as in T3. The derivation is presented as numbered steps in the prose below the bar — this is the only numbered list across all five templates. The list format is used here because the derivation is genuinely sequential: each step depends on the previous one.

**Section E — scenario analysis.** Two coloured cells: `scenario-bull` (green background `#EAF3DE`) and `scenario-bear` (red background `#FCEBEB`). The labelling is "Bull case for forces decoupling" and "Bear case for all five intensifying" — these are scenario titles, not market direction calls. The green/red encoding is about whether the scenario is good or bad for risk assets, not about the probability of the scenario. Both scenarios are presented with equal visual weight (same size, same internal structure) to avoid the template implying that one is more likely than the other.

**Synthesis verdict.** The only T5-specific pattern: the synthesis block uses `.verdict` (amber, not red). T1's synthesis is red because its findings are structurally critical. T5's synthesis is amber because it is a forward-looking judgement about structural positioning, not a reading of a data point that has already crossed a threshold. This is a subtle but deliberate distinction.

### Functional logic

T5 is the synthesis template. Its primary function is to check whether the individual force assessments across T1, T2, and T4 are co-active and mutually reinforcing — which is the condition Dalio identifies as historically significant.

**Force intensity scoring logic:**

Each force is scored 1–10 against a historical baseline:
- 1–3: below historical average or manageable in isolation
- 4–6: moderately elevated — flagged but not alarming
- 7–8: significantly above historical norms — one of these alone would historically be notable
- 9–10: at or approaching historical extremes — conditions seen only in major turning-point periods

The scores for Forces 1 (debt) and 3 (geopolitical) are derived directly from T1 and T4 assessments — there is no independent T5 calculation. Force 2 (domestic political) is assessed from polarisation and institutional effectiveness indicators not covered in T1 or T4. Force 4 (technology) is assessed from AI adoption/disruption metrics. Force 5 (natural) is assessed from current conflict and climate indicators.

**Reinforcement loop identification logic:**

The template requires identification of at least three loop types:
1. A primary loop between two forces that are bidirectionally reinforcing (each makes the other worse)
2. A secondary loop between two different forces
3. An amplifier force — one that accelerates the primary loop without being a direct participant in it

The primary loop in April 2026 is Debt/Politics: high debt → political anger → gridlock → no fiscal consolidation → more debt. The secondary is Geopolitics/Gold: sanctions risk → CB gold buying → de-dollarization → more sanctions risk. The amplifier is Force 5 (natural/energy): Iran war → inflation spike → worsens debt trajectory and Fed constraint.

**Active force count interpretation table:**

| Active forces (score ≥ 7) | Dalio's framework interpretation |
|---|---|
| 0–1 | Normal — standard diversification adequate |
| 2–3 | Elevated — defensive positioning warranted |
| 4–5 | Historical turning point zone — structural hedging required |

This table is embedded in the template widget (Section A verdict block) but also documented here as the key decision rule. The gold allocation output in Section D is mechanically tied to this table: 4–5 active forces → stress-environment guidance (~15%).

**Gold allocation derivation — the five-step chain:**

1. Count active forces (score ≥ 7)
2. Map count to Dalio guidance range (from table above)
3. Cross-check with T4 world order stage (if Stage 5, do not discount guidance)
4. Cross-check with T2 season (if autumn or transitioning, gold is seasonally aligned)
5. Output recommended structural range with explicit rationale referencing each cross-check

This derivation is documented in the widget UI as a numbered prose section rather than a table, because it is a chain of reasoning, not a parallel set of data points.

**Output fields consumed downstream:**
- Active force count + intensity scores → T3 gold allocation check (stress-environment justification)
- Reinforcement loop analysis → morning briefing agent context when framing macro-sensitive company notes
- Scenario analysis → risk management watchlist in portfolio/risk agent

---

## Cross-template dependency and execution order

The five templates form a directed dependency graph:

```
T1 (debt cycle)  ──────────────────────────────┐
                                                 ▼
T4 (world order) ─────────────────────────────► T5 (five forces) ──► T3 (allocation audit)
                                                 ▲
T2 (four seasons) ─────────────────────────────┘
                         │
                         └──────────────────────► T3 (season context for bond caveat)
```

No template can be faithfully run without its upstream dependencies. Running T3 without T1 and T2 produces a meaningless gold allocation check because the applicable guidance range depends on the debt cycle phase (T1) and the seasonal alignment (T2). Running T5 without T1, T2, and T4 produces an incomplete force scorecard because Forces 1 and 3 are derived from those templates.

The correct execution sequence for a full quarterly run:

1. T1 — update on fresh fiscal data (CBO, PGPF, FRED DFII10)
2. T2 — update on ISM and BLS CPI release
3. T4 — update on IMF COFER release (or on geopolitical trigger)
4. T5 — synthesise T1, T2, T4 outputs with fresh political/tech/natural force readings
5. T3 — consume T1 + T2 + T5 outputs to run portfolio audit

For a morning briefing (monthly cadence), only T2 needs to run. T3 and T5 can consume the cached T1 and T4 outputs until the quarterly update.

---

## Component reuse across templates

Several components are reused across multiple templates. This is intentional — consistency reduces the cognitive load of reading the fifth template after the first.

| Component | Templates using it | Notes |
|---|---|---|
| Four-column scorecard grid | T1, T4 | Same column weights (name+bar / value / context / badge) |
| Shift-row list (dot + stage badge + body) | T1 watchlist, T4 Stage 5 markers, T5 force rows | Consistent visual language for "signal list" |
| Coloured season coverage cells | T2 playbook, T3 coverage map | Same four colours mapping to four seasons |
| Gradient allocation bar with needles | T3 Section C, T5 Section D | Identical component, different labelling context |
| Dalio stage badge (early/mid/late) | T4 wealth shift, T5 reinforcement loops | Same three-state badge with stage-early/mid/late CSS |
| Synthesis verdict block | T1, T3, T4, T5 | Always the final element in the template, always labelled with downstream consumption note |
| `g2` / `g3` / `g4` grid classes | All five templates | Consistent gap and `minmax(0,1fr)` overflow handling |

---

## Known design limitations

**The quadrant map position markers are not data-driven.** In T2, the red and amber dots on the quadrant map are positioned manually using `position: absolute; left: [X%]; top: [Y%]` values that reflect the analyst's qualitative assessment of where the economy sits in the two-dimensional growth/inflation space. They are not computed from the indicator values. This is a deliberate simplification — converting PMI and CPI readings into precise X-Y coordinates would imply a false precision that the four-seasons framework does not support. Future versions could compute the position as a weighted combination of the normalised indicator readings, but this would require calibration against historical data and should be documented as an assumption rather than a fact.

**The risk contribution bars in T3 do not account for correlations.** The simplified model uses weight × volatility, which is correct only when assets are uncorrelated. In practice, the equity-bond correlation in inflationary regimes flips from negative to positive (as seen in 2022), which makes the equity risk share worse than the simplified model shows. A full correlation-adjusted model would require a covariance matrix and would change the numbers meaningfully in regime-change periods. The template includes a prose caveat about this in the "risk parity mechanism explained" block, but the bars themselves do not reflect it. This is acceptable for a diagnostic template but should be noted in any context where the bars are being presented as precise risk contributions.

**The historical data in the T4 reserve chart is hardcoded.** The COFER composition data (USD/EUR/JPY/CNY/Other shares from 1999 to 2025) is embedded as literal arrays in the JavaScript. It reflects IMF-published data as of Q3 2025. When the quarterly COFER update is released (next: late March/April 2026 for Q4 2025 data), the template should be updated by amending the hardcoded arrays. A production version should fetch this data from the IMF COFER API.

**T5 Force 2 and Force 4 scores are qualitative, not data-driven.** The debt cycle (Force 1) score is derived from T1 indicators. The geopolitical cycle (Force 3) score is derived from T4 indicators. But Force 2 (domestic political) and Force 4 (technology wave) do not have dedicated templates with scored indicators — they are assessed narratively. In the April 2026 run, Force 2 was scored 8.5 (polarisation indicators, congressional approval data) and Force 4 was scored 7.2 (AI adoption rate, labor market disruption data). These scores are reproducible but not formula-driven. A future T2.5 (political cycle diagnostic) and T4.5 (technology wave diagnostic) could provide systematic scores for these forces.

---

*This document covers visual and functional design as implemented in the April 2026 full-run of the template system. Both documents (this file and `dalio_macro_template_system_spec.md`) should be maintained together and updated when any template is revised.*
