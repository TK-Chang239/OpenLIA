# Macro Research — Reference Datasets Provenance

- **Date derived:** 2026-06-03
- **Spec:** `macro-research-reference-datasets-curation-design.md`
- Parameters are baked module constants; there is no runtime fetch. This document
  is the audit trail for how each parameter was sourced.

## All-Weather (`macro_research/risk_math.py`)

- **Source:** EODHD daily `adjusted_close` (total return, incl. distributions) for
  proxy ETFs:
  | asset class | proxy |
  | --- | --- |
  | equities | SPY.US |
  | long_bonds | TLT.US |
  | intermediate_bonds | IEF.US |
  | gold | GLD.US |
  | commodities | DBC.US |
- **Window:** 2006-02-03 .. 2025-12-31 (5009 common trading days — the maximal
  overlap, bound by DBC.US inception).
- **Method:** `DEFAULT_VOLS` = annualized stdev of daily log returns (x sqrt(252));
  `CORRELATIONS` = Pearson correlation of daily log returns. The rounded
  correlation matrix is positive-semi-definite (min eigenvalue 0.0885).
- **Computed `DEFAULT_VOLS`:** equities 0.194, long_bonds 0.149,
  intermediate_bonds 0.069, gold 0.179, commodities 0.192.
- **Computed `CORRELATIONS`:** eq/lb -0.31, eq/ib -0.30, eq/gold 0.06,
  eq/comm 0.41, lb/ib 0.91, lb/gold 0.16, lb/comm -0.22, ib/gold 0.21,
  ib/comm -0.19, gold/comm 0.37.
- **`EXPECTED_RETURNS` (curated forward CMAs, NOT computed):** equities 0.07,
  long_bonds 0.04, intermediate_bonds 0.035, gold 0.03, commodities 0.04.
  Basis: long-run real return + a ~2.5% inflation assumption. Realized window
  CAGR is recorded below as a sanity reference only and is deliberately NOT
  adopted as forward drift:
  | asset | realized CAGR (2006-2025) |
  | --- | --- |
  | equities | 0.109 |
  | long_bonds | 0.030 |
  | intermediate_bonds | 0.034 |
  | gold | 0.103 |
  | commodities | 0.007 |
  (Gold's 10.3% and commodities' 0.7% realized returns are window artifacts — the
  clearest illustration of why realized returns are not forward expectations.)
- **Re-derive:** `set -a && . ./.env && set +a && uv run python scripts/derive_all_weather_params.py`

## Four Seasons (`macro_research/quant/markov.py`)

- **Citations:** Merrill Lynch *Investment Clock* (Trevor Greetham) for the
  clockwise growth-inflation rotation; NBER business-cycle dating / Investment
  Clock phase persistence for average phase dwell.
- **Quadrant ↔ phase mapping:** Spring = Recovery (rising growth, falling
  inflation), Summer = Overheat (rising growth, rising inflation), Autumn =
  Stagflation (falling growth, rising inflation), Winter = Reflation (falling
  growth, falling inflation).
- **Method:** the diagonal is anchored to a ~2.5-2.9 quarter average dwell
  (`1/(1-p)`); the dominant off-diagonal mass goes to the next clockwise phase,
  with small reversion mass and minimal "skip" mass. Stagflation (Autumn) is set
  slightly less persistent (it historically resolves toward Winter). Each row
  sums to 1.0.
- **Matrix (rows = from, cols = to):**
  | from \ to | Spring | Summer | Autumn | Winter |
  | --- | --- | --- | --- | --- |
  | Spring | 0.65 | 0.25 | 0.03 | 0.07 |
  | Summer | 0.07 | 0.65 | 0.25 | 0.03 |
  | Autumn | 0.03 | 0.07 | 0.60 | 0.30 |
  | Winter | 0.25 | 0.03 | 0.07 | 0.65 |

## Five Forces (`macro_research/quant/forces_network.py`)

- **Source:** Ray Dalio, *Principles for Dealing with the Changing World Order* —
  the Big Cycle's account of how the five forces drive one another.
- **Status:** STRUCTURAL, NOT fitted from data (the inputs are soft 0-10 scores,
  not time series). Values were not changed by this curation; this section
  documents the rationale for each non-zero coupling.
- **Per-coupling rationale (`A[driver][driven]`):**
  | driver -> driven | strength | rationale |
  | --- | --- | --- |
  | debt_money -> political | 0.6 | debt/money stress drives internal political conflict |
  | debt_money -> geopolitical | 0.4 | financial stress strains external relations |
  | political -> geopolitical | 0.5 | internal conflict spills into external conflict |
  | political -> debt_money | 0.4 | political dysfunction degrades fiscal/monetary order |
  | geopolitical -> debt_money | 0.5 | external conflict drives spending / inflation |
  | geopolitical -> political | 0.4 | external threats reshape internal politics |
  | technology -> political | 0.4 | tech disruption shifts power / employment |
  | technology -> debt_money | 0.2 | tech alters productivity and growth |
  | natural -> debt_money | 0.4 | disasters / acts of nature drive emergency spending |
  | natural -> political | 0.3 | natural shocks strain governance |
  | natural -> geopolitical | 0.2 | resource / climate stress drives external conflict |
- **`PERSISTENCE` 0.7:** each force partly persists period-over-period (the
  one-step VAR-style map).
