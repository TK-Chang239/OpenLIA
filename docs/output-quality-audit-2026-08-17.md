# Output-Quality Audit — Live Department Tests (2026-08-17)

Method: every department exercised live in the browser (dev stack, backend :8080, Vite :5173, GPT 5.4).
Every checkable figure cross-verified against EODHD directly (real-time + EOD history + fundamentals).
Runs performed: Secretary chat (AAPL), Equity Research v3 initiation (NVDA.US) incl. HTML/PDF downloads,
Earnings Update on-demand (AAPL.US), Morning Briefing "Run now", Retail Sentiment dashboard (TSLA),
Macro Research "Generate now", Panic Thermometer live dashboard, Portfolio, Home.

## Verdict

LLM prose and quantitative accuracy are strong across every engine — dozens of spot-checked figures
(prices, closes, YoY math, valuation arithmetic) matched EODHD exactly. The dominant quality problems
are in the presentation and data-hygiene layer: chart rendering, citation rendering, stale caches
presented as fresh, and keyword-classifier false positives.

## Cross-verified accurate (sample)

| Claim in product | Source check | Result |
|---|---|---|
| Home market strip (S&P 7,745 −0.52%, NASDAQ 26,645, VIX 15.19, BTC 64,212) | EODHD real-time | exact |
| Secretary: AAPL close 305.59, 52w high 344.27, −11.2%, P/E 35.08 | EODHD RT + fundamentals | exact |
| v3 NVDA: close 225.01, FY22–26 rev/FCF history, 24.2B shares implied, comps math | EODHD + arithmetic | exact |
| EU AAPL: rev 109.4B +16.4%, EPS 2.02 vs 1.88 (+7.4%), −7.4% next-day (333.43→308.91), 303.42 Aug 3, 313.33 Aug 7 | EODHD EOD | exact |
| MB: SPY 777.88 Aug 13 / 776.34 Aug 14, TLT 83.89 Jul 20, SPY 742.09 Jul 20, USO/GLD/UUP live | EODHD EOD/RT | exact |
| MR summary strip: SPY 772.67 −0.47%, GLD 405.49 +1.00%, USO 130.29 +2.91% | EODHD RT | exact |
| RS TSLA: current price ~$339 | EODHD RT (339.30) | exact |

## Critical issues

### C1. Portfolio prices are 2.5 months stale but claim a fresh sync
AAPL held position priced at **$315.20 = the 2026-06-02 close** (verified against EODHD EOD).
Live close is $305.59 → NAV overstated ~$961 (3.1%). Header says "LAST SYNCED 05:17 UTC" (same day);
manual refresh does not correct the price. "DAY ±" and "7D" columns render "—". This is the
need-resolution price path (fetch_need) not actually refreshing quotes.

### C2. v3 chart renderer: multi-series line collapses into one line
NVDA "revenue and FCF trajectory" plots both series as a single continuous line — x-axis reads
FY2022..FY2026,FY2022..FY2026 and the line crashes from $215B to $8B mid-chart. The renderer ignores
the `series` field of the chart spec. Also raw-matplotlib presentation: `1e11` axis offset, no legend,
no $B tick formatting, caption duplicates title.

### C3. v3 chart renderer: table-type chart renders with an empty value column
"Valuation summary: DCF vs selected multiples" shows row labels but **all values blank** in both HTML
and PDF exports; values exist in the spec ($126.38, $3.48T, $2.79T, $176.31, $5.45T). The table
renderer drops the `value` field.

### C4. Citations render as raw tokens across engines
- v3 preview + HTML export: 62 literal `[^eodhd_1]`-style markers in prose; PDF shows `[^1]`.
  Bibliography (Sources [1]–[6]) is correct but nothing links to it.
- EU/MB "Highlights" boxes: raw `[^eodhd_1]`, `[^newsapi_ai__geopolitical_news_1]` (body sections
  correctly show numeric [1][2] — the highlights path misses the transform).
- Retail Sentiment narrative: literal `[^web_2] [^web_10] [^web_50]` throughout the hero prose.
- Macro Research Debt Cycle prose: literal `[^web_21][^web_30]` etc.

### C5. Panic Thermometer keyword classifiers produce false positives that drive the composite
- Fed language tracker went RED/HAWKISH on "persistent inflation" matched inside an **equity story
  about Intercontinental Exchange's data moat** — company news, not Fed communication.
- Diplomacy feed tags **every** headline "progress signal", including "Iran uses diplomatic pause to
  prepare for wider regional war", "Hormuz Attacks Push Oil Toward $100", and an unrelated Micron
  memory-chip story. Progress 10 / Escalation 10 counts are not credible.
- These panels feed the composite "2 of 5 red / HIGH" reading.

## Major issues

### M1. Stale content presented as current
- Home "TODAY'S READ" card shows the June 3 Morning Briefing (75 days old) with June 3 ticker data.
- Earnings Update "Up next" lists AAPL **2026-07-30** (18 days past) as upcoming; weekly calendar
  refresh isn't re-bucketing. Revenue estimates show "—".
- Macro Research: fresh Aug summary asserts "The Debt Cycle sits at Late Plateau (T1)" but the T1
  dashboard is dated **June 1** (2.5 months old) with no staleness flag; T3/T4/T5 never generated
  (summary does disclose that part honestly).
- Retail Sentiment evidence list includes 5–6 month-old items (2/21, 3/12) feeding an
  "as of mid-August" reading, plus one exact duplicate item; no staleness marking.

### M2. v3 report data-reconciliation gap
"cash and short-term investments $80.6B, long-term debt $7.5B, and net debt of negative $0.4B" —
internally contradictory (implies ~$73B net cash); the vendor `netDebt` field is repeated without
reconciliation and headlines the cover stat card as "NET DEBT ($0.4B)".

### M3. Panic Thermometer charts/latency
- First paint blocks ~30–40s on a ~14s `/dashboard` endpoint with a single global spinner; 5-min
  auto-refresh will re-block. No per-panel skeleton.
- Wage panel: 12-month lookback renders only 2 bars. FOMC timeline says "LAST 3 MEETINGS" but renders
  a single dot dated Aug 17 (not a meeting date). Michigan-5y level mislabeled "y/y".

### M4. Scale/unit mislabels
- RS crosscheck card: "AGGREGATED SENTIMENT 67.000 [-1,1]" — a 0–100 StockTwits score displayed under
  a [-1,1] scale annotation.
- Report cover pill labels the engine's own output "CONSENSUS" (v3 shows its Hold rating as
  "CONSENSUS Hold"; MB shows "CONSENSUS N/A" — N/A leaking to UI).
- Home 10Y 4.73 vs MR 10Y 4.68 — two different sources shown without timestamps.

## Minor / polish

- Greeting name fallback broken: Home "Good evening, Hello." / Secretary "Welcome back, there."
- v3 chart placeholders split sentences ("...is shown in" [chart] "."), leaving orphan periods;
  PDF ends with a nearly blank page containing only the disclaimer line.
- PT copy: "last 20progress / escalation tags" (missing space); thermometer graphic anchored "04 MAY".
- Secretary repeated vendor P/E (35.08) alongside EPS 8.72 and close 305.59 without noting the
  figures don't quite reconcile (vendor staleness) — cosmetic.
- Home portfolio NAV sparkline and Portfolio NAV chart empty at every range (no NAV history recorded)
  — consequence of C1's dead price/NAV pipeline.

## What is working well

- Numeric discipline of the LLM engines is excellent: no hallucinated figures found in any run; all
  derived math (YoY, margins, implied shares, multiple cross-checks) is internally consistent.
- EU and MB body sections cite with clean numeric footnotes and honest hedging ("not listed in the
  economic calendar feed here").
- v3 discloses DCF assumptions, includes computed-provenance citations (run_dcf/run_comps), and both
  HTML and PDF downloads work with embedded charts and an AI disclaimer.
- RS/MR/PT/EU/MB all completed live runs without errors in reasonable time (RS ~3–4 min, MB ~2 min,
  EU ~3 min, v3 ~10 min).

## Suggested priority order

1. C1 Portfolio price refresh (wrong money numbers on the flagship page)
2. C2/C3 v3 chart renderer (line-series grouping + table values — every exported report affected)
3. C4 citation rendering (one shared transform for preview/highlights/HTML/PDF)
4. C5 PT classifier gating (restrict Fed matcher to Fed-tagged news; fix progress/escalation labeler)
5. M1 staleness UX (age badges + auto-refresh/bucketing for EU calendar, Home card, MR frameworks)
