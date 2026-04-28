# Macro Research — Routing Context

## What this department does

Macro Research runs five Dalio-inspired regime dashboards: Debt Cycle,
Four Seasons, All-Weather Portfolio Audit, World Order, and Five
Interlocking Forces. Each dashboard is a pipeline of T1 (data fetch),
T2 (formula evaluation), T3 (closed-form numpy math),
T4 (LLM scoring of framework questions), and T5 (smart-mode
adjustments). It is a deterministic-runner department: most of the
work runs without an LLM in the path. In chat mode it answers
follow-up questions on a freshly-computed snapshot, citing the
dashboard outputs rather than re-fetching data.

## Data this department needs access to

The router should bias toward macro-grade data sources:

- Government and central-bank macro indicators: debt-to-GDP, interest
  expense as % of revenue, PMI, GDP YoY, CPI YoY (headline + core),
  USD share of FX reserves, central-bank gold-purchase volumes,
  foreign Treasury holdings.
- Quotes on macro-proxy ETFs and indices: TIP (real rates), UUP
  (DXY proxy), HYG and LQD (credit spreads), gold proxies.
- Geopolitical news headlines for the World Order dashboard.
- Broader news context for stage-call narrative when the user asks
  why a regime call shifted.

## Out-of-scope topics

- Single-name fundamentals or coverage initiations
  (route to Equity Research).
- Earnings-print analysis (route to Earnings Update).
- Daily generic market briefings (route to Morning Briefing).
- Retail/social sentiment metrics (route to Retail Sentiment).
- Short-term crash-probability scoring (route to Panic Thermometer).

## Example prompts and the data they imply

1. **"What stage of the debt cycle are we in?"** — Debt Cycle
   dashboard outputs: debt-to-GDP, interest-revenue, TIP price,
   UUP price; then a phase call ("Plateau", "Deleveraging", etc.).
2. **"Refresh the Four Seasons dashboard."** — T1 fetch of PMI,
   GDP YoY, headline + core CPI, plus HYG and LQD prices, then the
   season call (Spring/Summer/Autumn/Winter).
3. **"Run an All-Weather audit on my current portfolio."** —
   T3 risk-contribution math against the user's current weights;
   no T1 data fetch needed (this dashboard is closed-form).
4. **"How active are Dalio's five forces right now?"** — Five Forces
   dashboard, optionally with the user's smart-mode override applied.
5. **"Where are central banks accumulating gold?"** — World Order
   dashboard's central-bank-gold series, plus any geopolitical
   headlines explaining the shift.
6. **"Why did the season just flip from Spring to Summer?"** —
   recent CPI and PMI deltas with attribution to the formula
   thresholds; ideally answered from the cached snapshot rather
   than re-fetching.
