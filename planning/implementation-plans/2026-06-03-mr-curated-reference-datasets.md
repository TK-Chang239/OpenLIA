# Curated Reference Datasets for the MR Quant Engines — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-picked baked parameters in the three MR quant engines with documented-provenance values — All-Weather second moments computed from real EODHD history, the Four Seasons transition matrix curated from cited literature, the Five Forces couplings documented — without changing any behaviour contract.

**Architecture:** A one-shot offline derivation script computes All-Weather vols + correlations from EODHD proxy-ETF series; the printed constants are pasted into `risk_math.py`. The Four Seasons matrix is re-anchored to the Investment Clock rotation + cited phase dwell. Five Forces is documentation-grade (values unchanged by default). A single provenance doc records every source/method/value. Parameters stay baked module constants — no runtime fetch, determinism preserved.

**Tech Stack:** Python 3, `uv`, `ruff`, `pytest`, `numpy`, the `eodhd` `APIClient`. Reference: design spec `planning/specs/systems/macro-research-reference-datasets-curation-design.md`.

**Environment note:** Running the derivation script needs the EODHD key (`.env` has `EODHD_API_KEY`/`EODHD_API_TOKEN`) and live network. If the command sandbox raises `Operation not permitted` on `~/.cache/uv` or blocks the EODHD host, re-run that single command with the sandbox disabled. This affects only Task 2's script run; every other step is offline.

---

## File Structure

- **Create** `scripts/derive_all_weather_params.py` — offline dev tool; fetches the five proxies, computes vols/correlations + realized-CAGR reference, prints paste-ready constants. NOT imported by any runtime module (keeps `openlia-core` import-clean and fetch-free).
- **Modify** `packages/core/src/openlia/macro_research/risk_math.py` — `DEFAULT_VOLS` + `CORRELATIONS` (computed), `EXPECTED_RETURNS` (curated forward), docstrings.
- **Modify** `packages/core/src/openlia/macro_research/quant/markov.py` — `TRANSITION_MATRIX` + docstring.
- **Modify** `packages/core/src/openlia/macro_research/quant/forces_network.py` — `INFLUENCE` docstring pointer (values unchanged).
- **Modify** `packages/core/tests/macro_research/test_markov.py` — four matrix-derived assertions.
- **Modify** `packages/core/tests/macro_research/test_risk_math.py` — one stale "hand-tuned" comment.
- **Create** `planning/specs/systems/macro-research-reference-datasets-provenance.md` — the audit trail.

---

## Task 1: All-Weather derivation script

**Files:**
- Create: `scripts/derive_all_weather_params.py`

- [ ] **Step 1: Write the derivation script**

```python
"""Derive All-Weather second moments (vols + correlations) from real EODHD data.

Offline dev tool -- NOT imported by any runtime module. Fetches daily adjusted
closes for the five proxy ETFs over their maximal common window, computes
annualized volatilities (from daily log returns), the cross-asset correlation
matrix, and the realized annualized return (CAGR) as a sanity reference, then
prints paste-ready constants for macro_research/risk_math.py.

Run:
    set -a && . ./.env && set +a
    uv run python scripts/derive_all_weather_params.py
"""

from __future__ import annotations

import os

import numpy as np
from eodhd import APIClient

PROXIES: dict[str, str] = {
    "equities": "SPY.US",
    "long_bonds": "TLT.US",
    "intermediate_bonds": "IEF.US",
    "gold": "GLD.US",
    "commodities": "DBC.US",
}
ASSET_ORDER = ("equities", "long_bonds", "intermediate_bonds", "gold", "commodities")
FROM_DATE = "2004-01-01"
TO_DATE = "2025-12-31"  # most recent complete year-end
TRADING_DAYS = 252


def _fetch(client: APIClient, symbol: str) -> dict[str, float]:
    rows = client.get_eod_historical_stock_market_data(
        symbol=symbol, period="d", from_date=FROM_DATE, to_date=TO_DATE, order="a"
    )
    return {
        r["date"]: float(r["adjusted_close"])
        for r in rows
        if r.get("adjusted_close") is not None
    }


def main() -> None:
    key = os.environ.get("EODHD_API_KEY") or os.environ.get("EODHD_API_TOKEN")
    if not key:
        raise SystemExit("EODHD_API_KEY (or EODHD_API_TOKEN) must be set")
    client = APIClient(api_key=key)

    series = {asset: _fetch(client, sym) for asset, sym in PROXIES.items()}

    # Maximal common date intersection, ascending.
    common = set.intersection(*(set(s) for s in series.values()))
    dates = sorted(common)
    if len(dates) < TRADING_DAYS:
        raise SystemExit(f"insufficient common history: {len(dates)} days")

    prices = np.array([[series[a][d] for a in ASSET_ORDER] for d in dates], dtype=float)
    log_ret = np.diff(np.log(prices), axis=0)

    vols = log_ret.std(axis=0, ddof=1) * np.sqrt(TRADING_DAYS)
    corr = np.corrcoef(log_ret, rowvar=False)

    years = (np.datetime64(dates[-1]) - np.datetime64(dates[0])) / np.timedelta64(365, "D")
    cagr = (prices[-1] / prices[0]) ** (1.0 / years) - 1.0

    print(f"# Window: {dates[0]} .. {dates[-1]}  ({len(dates)} common trading days)")
    print("# Proxies: " + ", ".join(f"{a}={PROXIES[a]}" for a in ASSET_ORDER))
    print()
    print("DEFAULT_VOLS = {")
    for i, a in enumerate(ASSET_ORDER):
        print(f'    "{a}": {vols[i]:.3f},')
    print("}")
    print()
    print("CORRELATIONS = {")
    for i in range(len(ASSET_ORDER)):
        for j in range(i + 1, len(ASSET_ORDER)):
            print(f'    ("{ASSET_ORDER[i]}", "{ASSET_ORDER[j]}"): {corr[i, j]:.2f},')
    print("}")
    print()
    print("# Realized annualized return (CAGR) over window -- SANITY REFERENCE ONLY,")
    print("# not adopted as EXPECTED_RETURNS (forward CMAs):")
    for i, a in enumerate(ASSET_ORDER):
        print(f"#   {a}: {cagr[i]:.3f}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Lint the script**

Run: `uv run ruff check scripts/derive_all_weather_params.py && uv run ruff format scripts/derive_all_weather_params.py`
Expected: clean (or autoformatted).

- [ ] **Step 3: Commit**

```bash
git add scripts/derive_all_weather_params.py
git commit -m "feat(macro-research): All-Weather param derivation script"
```

---

## Task 2: Apply computed vols + correlations + curated returns to risk_math.py

**Files:**
- Modify: `packages/core/src/openlia/macro_research/risk_math.py`
- Modify: `packages/core/tests/macro_research/test_risk_math.py`

- [ ] **Step 1: Run the derivation script and capture output**

Run: `set -a && . ./.env && set +a && uv run python scripts/derive_all_weather_params.py`
(If sandboxed, re-run this one command with the sandbox disabled.)
Expected: a window header, paste-ready `DEFAULT_VOLS` and `CORRELATIONS` blocks, and a commented realized-CAGR table. **Save the full output verbatim** — it goes into both `risk_math.py` (Step 2) and the provenance doc (Task 5).

- [ ] **Step 2: Replace `DEFAULT_VOLS` and `CORRELATIONS` with the computed blocks**

In `risk_math.py`, replace the existing `DEFAULT_VOLS` dict (currently lines ~8-14) and `CORRELATIONS` dict (currently lines ~55-66) with the blocks printed by Step 1. Update their comments:

```python
# Annualized volatilities, computed from daily log returns of the proxy ETFs
# over the common window. See planning/specs/systems/
# macro-research-reference-datasets-provenance.md.
DEFAULT_VOLS: dict[str, float] = {
    # <-- paste the DEFAULT_VOLS block from Step 1 here (values only) -->
}
```

```python
# Cross-asset correlations (upper-triangle; symmetric, unit diagonal), computed
# as Pearson correlation of daily log returns over the common window. Empirical
# => positive-semi-definite. See the provenance doc.
CORRELATIONS: dict[tuple[str, str], float] = {
    # <-- paste the CORRELATIONS block from Step 1 here (values only) -->
}
```

- [ ] **Step 3: Set the curated forward `EXPECTED_RETURNS`**

Replace the `EXPECTED_RETURNS` dict (currently lines ~45-51) with the curated forward capital-market assumptions (long-run real return + ~2.5% inflation; realized CAGR is logged in the provenance doc as a sanity reference only, NOT adopted here):

```python
# Long-run nominal expected returns -- CURATED forward capital-market
# assumptions (long-run real return + a ~2.5% inflation assumption), used as
# the Monte-Carlo drift. NOT the realized window CAGR (which is a poor proxy for
# forward returns and is recorded only as a sanity reference in the provenance
# doc). See planning/specs/systems/macro-research-reference-datasets-provenance.md.
EXPECTED_RETURNS: dict[str, float] = {
    "equities": 0.07,
    "long_bonds": 0.04,
    "intermediate_bonds": 0.035,
    "gold": 0.03,
    "commodities": 0.04,
}
```

- [ ] **Step 4: Fix the stale test comment**

In `test_risk_math.py`, the PSD test comment (lines ~38-39) says "Hand-tuned reference correlations". Replace with:

```python
    # Empirical correlations (computed from daily log returns) form a valid (PSD)
    # matrix so the Gaussian simulator can draw from it.
```

- [ ] **Step 5: Run the All-Weather suites**

Run: `uv run pytest packages/core/tests/macro_research/test_risk_math.py packages/core/tests/macro_research/test_monte_carlo.py packages/core/tests/runtime/report_dash_mr/test_runner_all_weather.py -q`
Expected: PASS. `test_risk_math` reads the constants, so structure (shape, symmetry, PSD, `cov[i,i]==vol**2`) holds. `test_monte_carlo` asserts only relational properties (percentile ordering; equity-crash worse than base and than reference; crash tone red; determinism).

If any `test_monte_carlo` relational assert fails (e.g. crash tone is no longer red, or crash is no longer worse than base), STOP and apply superpowers:systematic-debugging: confirm the new params are correct, then decide whether the scenario shock definitions in `monte_carlo.py` need re-tuning (a behaviour change — escalate) vs the test assumption is stale. Do not paper over it.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
uv run ruff format packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
git add packages/core/src/openlia/macro_research/risk_math.py packages/core/tests/macro_research/test_risk_math.py
git commit -m "feat(macro-research): computed All-Weather vols/correlations + curated forward returns"
```

---

## Task 3: Four Seasons curated transition matrix

**Files:**
- Modify: `packages/core/tests/macro_research/test_markov.py`
- Modify: `packages/core/src/openlia/macro_research/quant/markov.py`

- [ ] **Step 1: Update the test expectations to the curated matrix (test-first)**

In `test_markov.py`, update the four matrix-derived assertions to the new values (the new matrix is in Step 3; these are the values it produces):

`test_outlook_distribution_is_the_matrix_row` — the Summer row:
```python
    assert out.distribution == {
        "Spring": 0.07,
        "Summer": 0.65,
        "Autumn": 0.25,
        "Winter": 0.03,
    }
```

`test_outlook_persistence_is_diagonal` — Autumn diagonal:
```python
    out = markov_outlook("Autumn")
    assert out.persistence == 0.60
```

`test_outlook_most_likely_next_and_adverse` — adverse prob (Summer -> Autumn):
```python
    assert out.adverse_prob == 0.25
```
(`most_likely_next == "Summer"` and `adverse_season == "Autumn"` are unchanged.)

`test_outlook_expected_dwell` — Spring persistence is now 0.65:
```python
    out = markov_outlook("Spring")  # persistence 0.65
    assert abs(out.expected_dwell_quarters - (1.0 / (1.0 - 0.65))) < 1e-9
```

- [ ] **Step 2: Run test_markov to verify it fails**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: FAIL — the four updated assertions disagree with the old matrix; the structural tests (row-stochastic, resolver, horizon, unknown-season) still pass.

- [ ] **Step 3: Replace `TRANSITION_MATRIX` and its comment**

In `markov.py`, replace the `TRANSITION_MATRIX` dict (currently lines ~30-35) and its preceding comment (lines ~26-29):

```python
# Quarterly transition probabilities (rows = from, cols = to). Curated reference:
# the off-diagonal rotation follows the Merrill Lynch Investment Clock clockwise
# cycle (Recovery -> Overheat -> Stagflation -> Reflation, i.e.
# Spring -> Summer -> Autumn -> Winter -> Spring); the diagonal/persistence is
# anchored to documented average business-cycle phase dwell (~2.5-2.9 quarters).
# Stagflation (Autumn) is set slightly less persistent (resolves toward Winter).
# Each row sums to 1.0. See planning/specs/systems/
# macro-research-reference-datasets-provenance.md.
TRANSITION_MATRIX: dict[str, dict[str, float]] = {
    "Spring": {"Spring": 0.65, "Summer": 0.25, "Autumn": 0.03, "Winter": 0.07},
    "Summer": {"Spring": 0.07, "Summer": 0.65, "Autumn": 0.25, "Winter": 0.03},
    "Autumn": {"Spring": 0.03, "Summer": 0.07, "Autumn": 0.60, "Winter": 0.30},
    "Winter": {"Spring": 0.25, "Summer": 0.03, "Autumn": 0.07, "Winter": 0.65},
}
```

- [ ] **Step 4: Run test_markov to verify it passes**

Run: `uv run pytest packages/core/tests/macro_research/test_markov.py -q`
Expected: PASS (all tests). Confirms rows sum to 1.0, the horizon test still holds (4-step Spring ≈ 0.293 < 1-step 0.65), and the four updated values match.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
uv run ruff format packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git add packages/core/src/openlia/macro_research/quant/markov.py packages/core/tests/macro_research/test_markov.py
git commit -m "feat(macro-research): Investment-Clock-anchored Four Seasons transition matrix"
```

---

## Task 4: Five Forces provenance docstring (values unchanged)

**Files:**
- Modify: `packages/core/src/openlia/macro_research/quant/forces_network.py`

- [ ] **Step 1: Add a provenance pointer to the `INFLUENCE` comment**

In `forces_network.py`, extend the comment above `INFLUENCE` (currently lines ~42-44). Do NOT change any numeric value:

```python
# Directed structural coupling A[driver][driven] in [0, 1], zero diagonal.
# Reference assumptions (adjustable); Dalio's documented force linkages from
# "Principles for Dealing with the Changing World Order". Structural, NOT fitted
# from data (the inputs are soft 0-10 scores, not time series). Each non-zero
# coupling's linkage rationale is documented in planning/specs/systems/
# macro-research-reference-datasets-provenance.md. Only non-zero entries are
# listed; missing pairs are 0.0.
INFLUENCE: dict[str, dict[str, float]] = {
    "debt_money": {"political": 0.6, "geopolitical": 0.4},
    "political": {"geopolitical": 0.5, "debt_money": 0.4},
    "geopolitical": {"debt_money": 0.5, "political": 0.4},
    "technology": {"political": 0.4, "debt_money": 0.2},
    "natural": {"debt_money": 0.4, "political": 0.3, "geopolitical": 0.2},
}
```

- [ ] **Step 2: Run test_forces_network to confirm nothing changed**

Run: `uv run pytest packages/core/tests/macro_research/test_forces_network.py -q`
Expected: PASS — values are unchanged, so the hard-coded coupling/contagion assertions still hold.

- [ ] **Step 3: Lint + commit**

```bash
uv run ruff check packages/core/src/openlia/macro_research/quant/forces_network.py
uv run ruff format packages/core/src/openlia/macro_research/quant/forces_network.py
git add packages/core/src/openlia/macro_research/quant/forces_network.py
git commit -m "docs(macro-research): document Five Forces influence-matrix provenance"
```

---

## Task 5: Provenance document

**Files:**
- Create: `planning/specs/systems/macro-research-reference-datasets-provenance.md`

- [ ] **Step 1: Write the provenance doc**

Use the captured Task 2 Step 1 output for the All-Weather section. Structure:

```markdown
# Macro Research — Reference Datasets Provenance

- **Date derived:** 2026-06-03
- **Spec:** macro-research-reference-datasets-curation-design.md
- Parameters are baked module constants; no runtime fetch. This doc is the audit
  trail for how each was sourced.

## All-Weather (risk_math.py)

- **Source:** EODHD daily `adjusted_close` for proxy ETFs
  (equities=SPY.US, long_bonds=TLT.US, intermediate_bonds=IEF.US, gold=GLD.US,
  commodities=DBC.US).
- **Window:** <paste window header from the derivation run>.
- **Method:** `DEFAULT_VOLS` = annualized stdev of daily log returns
  (× sqrt(252)); `CORRELATIONS` = Pearson correlation of daily log returns.
- **Computed values:** <paste the DEFAULT_VOLS + CORRELATIONS blocks>.
- **EXPECTED_RETURNS (curated forward):** long-run real return + ~2.5% inflation
  per asset; values: equities 0.07, long_bonds 0.04, intermediate_bonds 0.035,
  gold 0.03, commodities 0.04. Realized window CAGR (sanity reference only,
  NOT adopted): <paste the CAGR table>.
- **Re-derive:** `set -a && . ./.env && set +a && uv run python scripts/derive_all_weather_params.py`

## Four Seasons (quant/markov.py)

- **Source / citations:** Merrill Lynch Investment Clock (Trevor Greetham) for
  the clockwise growth-inflation rotation; NBER business-cycle dating /
  Investment Clock phase persistence for the average phase dwell.
- **Mapping:** Spring=Recovery, Summer=Overheat, Autumn=Stagflation,
  Winter=Reflation; clockwise Spring->Summer->Autumn->Winter->Spring.
- **Method:** diagonal anchored to ~2.5-2.9 quarter average dwell
  (1/(1-p)); dominant off-diagonal = next clockwise phase; small reversion +
  minimal skip mass. Autumn slightly less persistent.
- **Matrix:** <paste the curated TRANSITION_MATRIX>.

## Five Forces (quant/forces_network.py)

- **Source:** Dalio, "Principles for Dealing with the Changing World Order" —
  the Big Cycle's description of how the five forces drive one another.
- **Status:** STRUCTURAL, not fitted from data (inputs are soft 0-10 scores).
- **Per-coupling rationale:**
  - debt_money -> political (0.6): debt/money stress drives internal political conflict.
  - debt_money -> geopolitical (0.4): financial stress strains external relations.
  - political -> geopolitical (0.5): internal conflict spills into external conflict.
  - political -> debt_money (0.4): political dysfunction degrades fiscal/monetary order.
  - geopolitical -> debt_money (0.5): external conflict drives spending/inflation.
  - geopolitical -> political (0.4): external threats reshape internal politics.
  - technology -> political (0.4): tech disruption shifts power/employment.
  - technology -> debt_money (0.2): tech alters productivity and growth.
  - natural -> debt_money (0.4): disasters/acts of nature drive emergency spending.
  - natural -> political (0.3): natural shocks strain governance.
  - natural -> geopolitical (0.2): resource/climate stress drives external conflict.
- **PERSISTENCE 0.7:** each force partly persists period-over-period (one-step map).
```

- [ ] **Step 2: Commit**

```bash
git add planning/specs/systems/macro-research-reference-datasets-provenance.md
git commit -m "docs(macro-research): reference-dataset provenance audit trail"
```

---

## Task 6: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Lint the whole repo**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 2: Run the MR core + engine suites**

Run: `uv run pytest packages/core/tests/macro_research packages/core/tests/runtime/report_dash_mr -q`
Expected: all PASS.

- [ ] **Step 3: Sanity-check determinism is intact**

Run: `uv run pytest packages/core/tests/macro_research/test_monte_carlo.py::test_is_deterministic_for_same_weights packages/core/tests/macro_research/test_markov.py -q`
Expected: PASS — engines remain deterministic under the new constants (the cache contract depends on it).

- [ ] **Step 4: Final commit (if any lint/format fixes were needed)**

```bash
git add -A
git commit -m "chore(macro-research): lint/format pass for reference-dataset curation" || echo "nothing to commit"
```

---

## Post-implementation amendments

(Record any divergence from this plan here as it is executed — e.g. final computed
vols/correlations, any monte_carlo re-tuning, any Five Forces value change forced
by a documented contradiction.)
