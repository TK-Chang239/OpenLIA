/**
 * T3 — All-Weather allocation audit (April 2026 reference instance).
 *
 * Shape matches AllWeatherData. When the backend produces this same
 * shape, AllWeatherView replaces `?? ALL_WEATHER_FALLBACK` with the
 * live result and this file is deleted.
 */

import type { AllWeatherData } from "./types";

export const ALL_WEATHER_FALLBACK: AllWeatherData = {
  header: {
    title: "T3 · All-Weather allocation audit",
    subtitle: "Benchmark: 60/40 (SPY/TLT) · April 2026",
    pills: [
      { tone: "red", label: "Risk concentration: critical" },
      { tone: "amber", label: "Gold gap: 0% held vs ~15% guidance" },
    ],
  },
  cardSummary:
    "60/40 audit: 0% gold vs ~15% guidance, no autumn coverage. Equity vol dominates risk — risk parity broken.",
  comparison: {
    label: "Portfolio under audit vs All-Weather reference",
    benchmark: {
      title: "60/40 benchmark",
      slices: [
        { label: "Equities", pct: 60, tone: "accent" },
        { label: "Long bonds", pct: 40, tone: "olive" },
      ],
    },
    reference: {
      title: "All-Weather reference",
      slices: [
        { label: "Equities", pct: 30, tone: "accent" },
        { label: "Long bonds", pct: 40, tone: "olive" },
        { label: "Int. bonds", pct: 15, tone: "neutral" },
        { label: "Gold", pct: 7.5, tone: "amber" },
        { label: "Commodities", pct: 7.5, tone: "rust" },
      ],
    },
  },
  coverage: {
    label: "Section A — season coverage map",
    cells: [
      {
        title: "Autumn (stagflation) — growth falling, inflation rising",
        badgeLabel: "Exposed",
        badgeTone: "red",
        bodyTone: "red",
        body: "60/40 has no autumn coverage. Equities underperform when growth slows; long bonds underperform when inflation rises. Both legs fail simultaneously — textbook 2022: 60/40 fell ~17%. No gold, no real assets, no inflation-linked bonds.",
        bridgeLabel: "All-Weather coverage",
        bridge: "gold (7.5%) + commodities (7.5%) = 15% direct autumn cover.",
      },
      {
        title: "Summer (growth rising, inflation rising)",
        badgeLabel: "Exposed",
        badgeTone: "red",
        bodyTone: "red",
        body: "60/40 lacks commodities and TIPS. In a summer regime, long nominal bonds are the worst-performing asset (rising inflation destroys real yield). 60/40 devotes 40% to long bonds — a structural headwind in every inflationary regime. Equities can hold but commodities and TIPS dominate.",
        bridgeLabel: "All-Weather coverage",
        bridge: "commodities (7.5%) + equities (30%) = summer participation.",
      },
      {
        title: "Spring (growth rising, inflation falling)",
        badgeLabel: "Strong",
        badgeTone: "green",
        bodyTone: "green",
        body: "60/40 is optimally positioned for spring — equities thrive on rising growth and falling inflation. Bonds provide cushion. This is the regime 60/40 was implicitly designed for, and it dominated the 2010–2021 low-inflation bull market. 60% equity exposure captures the full spring upside.",
        bridgeLabel: "All-Weather coverage",
        bridge: "equities (30%) — intentionally lower to free risk budget for other seasons.",
      },
      {
        title: "Winter (growth falling, inflation falling)",
        badgeLabel: "Partial",
        badgeTone: "blue",
        bodyTone: "blue",
        body: "60/40 has meaningful winter cover via the 40% long bond allocation. In deflationary recessions, Treasuries rally as yields fall. Cash and long bonds both work. However, the 60% equity sleeve is a headwind. 60/40 survives winter but takes significant equity drawdown alongside the bond cushion.",
        bridgeLabel: "All-Weather coverage",
        bridge: "long bonds 40% + intermediate bonds 15% = 55% winter allocation.",
      },
    ],
  },
  riskParity: {
    label: "Section B — risk parity audit",
    intro:
      "The core insight: capital weight ≠ risk weight. Because equity volatility (~16–17% annualised) is roughly 1.5–2× bond volatility (~10–13% for long Treasuries), a 60/40 capital split concentrates far more than 60% of portfolio risk in equities. The maths below uses long-run volatility estimates calibrated against historical data.",
    benchmarkTitle: "60/40 — risk contribution by asset class",
    benchmarkBars: [
      { label: "Equities", pct: 68 },
      { label: "Long bonds", pct: 32 },
    ],
    referenceTitle: "All-Weather — risk contribution by asset class (approximate)",
    referenceBars: [
      { label: "Equities", pct: 38 },
      { label: "Long bonds", pct: 35 },
      { label: "Int. bonds", pct: 8 },
      { label: "Gold", pct: 9 },
      { label: "Commodities", pct: 10 },
    ],
    mechanism: {
      title: "The risk parity mechanism explained",
      body: "In the 60/40, equities at 60% capital weight × ~17% vol contributes ~10.2 vol-weighted units of risk. Bonds at 40% × ~11% vol contributes ~4.4 units. Equities' share: 10.2 ÷ (10.2 + 4.4) ≈ 70% — but in practice it's worse because equities and bonds can correlate positively in inflationary regimes (2022), making the equity risk share closer to 85–90% of realised portfolio volatility. All-Weather corrects this by halving the equity weight and increasing the bond weight, while adding gold and commodities whose high individual vol but low equity correlation brings their risk contribution in line with equities.",
    },
  },
  stressTest: {
    label: "Section E — Monte-Carlo stress test",
    intro:
      "10,000-path 1-year Monte-Carlo simulation under baked reference parameters (long-run expected returns, volatilities, and cross-asset correlations). Stress regimes are parameter overlays, not a fat-tail model.",
    distribution: {
      title: "Base-case 1-year return distribution — 60/40 vs All-Weather reference",
      bars: [
        { label: "5th pct (VaR-95)", userPct: -0.18, refPct: -0.09 },
        { label: "25th pct", userPct: -0.04, refPct: -0.01 },
        { label: "Median", userPct: 0.06, refPct: 0.05 },
        { label: "75th pct", userPct: 0.17, refPct: 0.12 },
        { label: "95th pct", userPct: 0.31, refPct: 0.2 },
      ],
    },
    scenarios: [
      {
        name: "Base case",
        userMedianPct: 0.06,
        userP5Pct: -0.18,
        refMedianPct: 0.05,
        refP5Pct: -0.09,
        tone: "amber",
      },
      {
        name: "Stagflation",
        userMedianPct: -0.05,
        userP5Pct: -0.27,
        refMedianPct: -0.01,
        refP5Pct: -0.14,
        tone: "red",
      },
      {
        name: "Rate shock",
        userMedianPct: -0.03,
        userP5Pct: -0.24,
        refMedianPct: -0.04,
        refP5Pct: -0.17,
        tone: "red",
      },
      {
        name: "Equity crash / deleveraging",
        userMedianPct: -0.22,
        userP5Pct: -0.41,
        refMedianPct: -0.08,
        refP5Pct: -0.19,
        tone: "red",
      },
    ],
    note: "Reference assumptions; not investment advice. Gaussian draws — tails are conservative relative to historical crashes.",
  },
  gold: {
    label: "Section C — gold allocation check",
    title: "60/40 gold weight vs Dalio guidance ranges",
    needles: [
      { label: "60/40: 0%", leftPct: 0, tone: "red" },
      { label: "AW base: 7.5%", leftPct: 50, tone: "amber" },
      { label: "Stress env: ~15%", leftPct: 75, tone: "green" },
    ],
    stats: [
      {
        label: "Current gold weight",
        value: "0%",
        valueTone: "red",
        note: "No gold in 60/40",
      },
      {
        label: "Applicable reference range",
        value: "~15%",
        valueTone: "amber",
        note: "Stress-environment guidance (Oct 2025). Justified by T1 + T2 + T5 outputs.",
      },
      {
        label: "Allocation gap",
        value: "−15 pp",
        valueTone: "red",
        note: "To reach stress-env guidance from zero",
      },
    ],
    rationale: {
      title: "Gold allocation rationale (cross-referencing T1 + T2 + T5)",
      body: "T1 (debt cycle): interest/revenue at 18.6%, past critical threshold, real yields declining — the debasement precondition is active. T2 (four seasons): transitioning summer → autumn; gold is the canonical autumn asset. T5 (five forces): 4/5 forces at critical intensity, all co-active — Dalio's stress-environment definition is fully met. All three templates point to the same conclusion. Dalio's October 2025 public guidance: raise gold to close to 15% in this type of environment. The 60/40 portfolio holds zero gold, making it fully exposed to the precise macro scenario Dalio designed gold allocation to hedge.",
    },
  },
  caveats: {
    label: "Section D — retail investor caveats (required)",
    cards: [
      {
        title: "Leverage assumption",
        body: "The original All-Weather portfolio was designed for institutional investors with access to leverage tools. The 40% long bond + 15% intermediate bond = 55% bond allocation only achieves risk parity with equities when the bond sleeve is leveraged to match equity's risk contribution. Without leverage, the bond allocation is large but still under-contributes risk relative to equities. For retail investors running the All-Weather unlevered: the portfolio is still far better diversified than 60/40, but the risk contributions will not be as balanced as in the institutional version.",
      },
      {
        title: "Bond allocation risk — critical in current regime",
        body: "The T2 season is transitioning summer → autumn — an inflationary environment. The 40–55% bond allocation in All-Weather (and even the 40% in 60/40) is a structural headwind in inflationary regimes because rising inflation pushes yields up, which crushes long-duration bond prices. This is the key caveat Dalio himself makes: \"retail investors who simply copy the weights may end up disappointed because the high bond allocation can underperform expectations in inflationary environments.\" Adjust by: shortening duration (prefer intermediate or TIPS over TLT-equivalent in current regime), and increasing inflation-linked bond exposure.",
      },
      {
        title: "Rebalancing cadence",
        body: "Recommended cadence: threshold-based — rebalance when any position drifts more than 5 percentage points from its target weight. This is more efficient than calendar-based rebalancing in volatile regimes (like current) because it automatically triggers more frequently when markets move sharply, and less frequently in calm periods. At minimum, rebalance quarterly. In a transitional summer/autumn regime, the equity sleeve may drift significantly as equities underperform — threshold rebalancing captures this systematically.",
      },
      {
        title: "Equity-to-bond correlation regime",
        body: "The fundamental assumption of 60/40 is that equities and bonds are negatively correlated — when stocks fall, bonds rally and cushion the portfolio. This was largely true from 1998–2021. In 2022, the correlation flipped positive: both fell simultaneously because the common driver was inflation (bad for both). In the current transitional summer/autumn regime, with headline CPI re-accelerating to 3.3%, the equity-bond correlation is more likely to be positive (or near zero) than negative. The 60/40 diversification assumption is structurally compromised until inflation firmly retreats below 2%.",
      },
    ],
  },
  verdict: {
    title: "Synthesis verdict — bottom line for the 60/40 benchmark in April 2026",
    body: "The 60/40 portfolio concentrates approximately 87% of its effective risk in the equity sleeve, covers only two of four economic seasons (spring and partially winter), holds zero gold against a T1+T2+T5 signal that unanimously supports ~15% allocation, and relies on a negative equity-bond correlation that is structurally compromised in inflationary regimes. The current macro environment — transitioning summer→autumn, all five forces co-active, interest/revenue at record highs — is precisely the regime where 60/40's vulnerabilities are maximally exposed. The 2022 episode (-17.5%) was a clear precedent. The risk of a repeat or worse is elevated given the structural debt cycle context is now more severe than it was going into 2022.",
  },
  sources:
    "Volatility estimates: S&P 500 long-run annualised vol ~16–17% (PortfoliosLab, historical); TLT/long Treasury ~10–13%; GLD ~16% annualised (LazyPortfolioETF 30yr: 16.04%); commodities ~18–20% (representative). Risk contribution calculation: weight × vol, normalised. 60/40 2022 return: −16.7% to −17.5% per State Street/Morgan Stanley. All-Weather weights: Dalio public allocation (30/40/15/7.5/7.5). Gold guidance: Dalio Oct 2025 public commentary. Not investment advice.",
};
