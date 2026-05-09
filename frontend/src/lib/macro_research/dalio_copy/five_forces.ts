/**
 * T5 — Five interlocking forces dashboard. April 2026 reference instance.
 *
 * Shape matches FiveForcesData. When the backend produces this same shape,
 * FiveForcesView replaces `?? FIVE_FORCES_FALLBACK` with the live result and
 * this file is deleted.
 */

import type { FiveForcesData } from "./types";

export const FIVE_FORCES_FALLBACK: FiveForcesData = {
  header: {
    title: "Five interlocking forces — April 2026",
    subtitle: "Dalio framework scored against current data",
    badges: [
      { tone: "red", label: "4 Critical" },
      { tone: "amber", label: "1 High" },
    ],
  },
  cardSummary:
    "5 of 5 forces active — 4 Critical, 1 High. Synthesis points to stress-environment portfolio guidance (~15% gold).",
  scorecard: {
    label: "Section A — force intensity scorecard",
    rows: [
      {
        forceLabel: "Force 1",
        forceSub: "Debt & money cycle",
        pillTone: "red",
        pillLabel: "Critical",
        scorePct: 92,
        scoreTone: "red",
        scoreValue: "9.2 / 10",
        body: "US debt/GDP now **~122.5%** (Q4 2025), trajectory toward 134% by 2035 under alternative scenario. Interest outlays hit **$970B in FY2025** — 18.5% of federal revenue, eclipsing the 1991 record. Moody's downgraded the US from AAA to Aa1 in May 2025, the first downgrade since 1917. CBO projects interest costs rise to **25.8% of revenue by 2036**. In Q1 FY2026 alone, $104B in interest was spent — $11B/week. Conventional monetary policy is structurally constrained.",
      },
      {
        forceLabel: "Force 2",
        forceSub: "Domestic political cycle",
        pillTone: "red",
        pillLabel: "Critical",
        scorePct: 85,
        scoreTone: "red",
        scoreValue: "8.5 / 10",
        body: "Only **17% of Americans** believe Congress represents their interests; 60% have no confidence the system solves problems. Deep partisan divide expected to persist through 2026 midterms. \"No Kings\" movement protests active. Populist MAGA agenda vs Democratic disarray creates fiscal policy gridlock — the political conditions that make debt consolidation structurally impossible. Inequality widening: raising a child now costs **$300K+**, housing affordability at historic lows.",
      },
      {
        forceLabel: "Force 3",
        forceSub: "Geopolitical cycle",
        pillTone: "red",
        pillLabel: "Critical",
        scorePct: 88,
        scoreTone: "red",
        scoreValue: "8.8 / 10",
        body: "US Supreme Court struck down many 2025 tariffs in Feb 2026; new Section 301 investigations launched against China, Vietnam, Taiwan, EU and others in March. China rare-earth export controls nearly halted US auto manufacturing twice in 2025. Trade truce extended one year (Oct 2025) but structural fragmentation deepening. UNCTAD: geopolitical tensions and trade fragility rising. Dollar's reserve share declining — **BRICS+ now hold 17.4% of global gold reserves**, up from 11.2% in 2019. Strait of Hormuz disruptions adding energy inflation.",
      },
      {
        forceLabel: "Force 4",
        forceSub: "Technology wave",
        pillTone: "amber",
        pillLabel: "High",
        scorePct: 72,
        scoreTone: "amber",
        scoreValue: "7.2 / 10",
        body: "**35.9% of US workers** used generative AI by Dec 2025. ~60% of jobs in advanced economies have AI exposure; 33% face full automation risk. Youth unemployment in tech-exposed occupations up ~3pp since early 2025. Fed Governor Barr (Feb 2026): adoption speed may be faster than any prior general-purpose technology. Distributional effects are uneven — AI widens the productivity gap between large firms and SMEs, amplifying inequality that feeds back into Force 2.",
      },
      {
        forceLabel: "Force 5",
        forceSub: "Natural forces",
        pillTone: "red",
        pillLabel: "Critical",
        scorePct: 80,
        scoreTone: "red",
        scoreValue: "8.0 / 10",
        body: "Middle East conflict and Strait of Hormuz disruptions actively intensifying inflationary pressure on energy prices. UNCTAD (April 2026) explicitly flags these as intensifying pressures on an already-strained global economy. Iran-US tensions escalating (threats to warships, April 2026). Combined with post-COVID supply chain fragility still unresolved, this force is acting as an amplifier — particularly to Forces 1 (inflation makes debt harder to service) and 3 (geopolitical weaponization of energy).",
      },
    ],
  },
  loops: {
    label: "Section B — reinforcement loop analysis",
    blocks: [
      {
        title: "Primary loop · debt → politics → more debt",
        arrows: [
          { fromLabel: "F1 · Debt crisis", toLabel: "F2 · Populist anger" },
          { fromLabel: "F2 · Gridlock", toLabel: "F1 · No consolidation" },
        ],
        body: "High debt constrains government, raises inequality, fuels populism. Populist gridlock makes deficit reduction politically impossible. The debt grows. The loop is self-reinforcing and currently has no obvious off-ramp.",
      },
      {
        title: "Secondary loop · geopolitics → gold demand",
        arrows: [
          { fromLabel: "F3 · Sanctions risk", toLabel: "CB gold buying" },
          { fromLabel: "F1 · Dollar risk", toLabel: "De-dollarization" },
        ],
        body: "Post-Russia sanctions (2022), central banks globally concluded that dollar-denominated reserves carry confiscation risk. This drove the structural shift to gold that is now self-sustaining. 68% of central banks plan to increase gold holdings in 2026.",
      },
      {
        title: "Tertiary loop · tech → inequality → political strain",
        arrows: [
          { fromLabel: "F4 · AI displacement", toLabel: "F2 · Inequality" },
          { fromLabel: "F2 · Anger", toLabel: "F3 · Protectionism" },
        ],
        body: "AI-driven productivity gains are accruing to capital and large firms, widening wealth gaps. This feeds directly into political polarization and the protectionist trade policies that are fracturing the geopolitical order.",
      },
      {
        title: "Amplifier · natural forces accelerate all three",
        arrows: [
          { fromLabel: "F5 · Energy shock", toLabel: "F1 · Inflation → debt cost" },
          { fromLabel: "F5 · Hormuz risk", toLabel: "F3 · War premium" },
        ],
        body: "Middle East conflict and energy price spikes directly worsen fiscal trajectories (higher CPI → higher nominal interest costs), deepen geopolitical fault lines, and compress central bank rate-cut optionality.",
      },
    ],
    active: {
      countText: "5 / 5",
      countTone: "red",
      title: "All forces simultaneously active — historical turning point zone",
      body: "Dalio's key insight: individual forces are manageable in isolation. Co-activation of all five is historically rare and has preceded major monetary system restructurings (1930s, 1971–80).",
    },
  },
  signals: {
    label: "Section C — current market data",
    cards: [
      {
        label: "Gold spot (XAUUSD)",
        value: "~$3,200",
        unit: "per troy oz, Apr 2026",
        note: "ATH $5,595 hit Jan 2026. Currently correcting. CB buying ~750–850t expected 2026.",
      },
      {
        label: "US debt / GDP",
        value: "122.5%",
        unit: "Q4 2025",
        note: "Dalio warn zone: sustained >100%. On track for 134% by 2035 under alt scenario.",
      },
      {
        label: "Interest / federal revenue",
        value: "18.5%",
        unit: "FY2025 — record high",
        note: "Dalio: pressure escalates steeply above 15%. Projects 25.8% by 2036.",
      },
      {
        label: "CB gold demand 2025",
        value: "863t",
        unit: "net purchases, WGC",
        note: "Below 1,000t+ peak but still 2× the 2015–19 avg. 68% of CBs plan to add more in 2026.",
      },
      {
        label: "BRICS+ gold reserve share",
        value: "17.4%",
        unit: "of global gold reserves",
        note: "Up from 11.2% in 2019. Structural de-dollarization trend confirmed.",
      },
      {
        label: "10yr TIPS real yield",
        value: "~+2%",
        unit: "early 2026",
        note: "Above 0% = gold opportunity cost present. But declining toward 0% = strong gold trigger.",
      },
    ],
  },
  goldAllocation: {
    label: "Section D — gold allocation signal",
    block: {
      title: "Dalio allocation range vs current environment",
      ticks: ["0%", "5%", "10%", "15%", "20%+"],
      stats: [
        {
          label: "All-Weather baseline",
          value: "7.5%",
          note: "Normal macro regime",
          highlight: false,
        },
        {
          label: "Normal environment",
          value: "5–10%",
          note: "Dalio's baseline range",
          highlight: false,
        },
        {
          label: "Stress environment (Oct 2025)",
          value: "~15%",
          note: "Dalio's explicit guidance",
          highlight: true,
        },
      ],
      body: "With all five forces active simultaneously, the current environment satisfies every condition Dalio cited for his October 2025 \"close to 15%\" recommendation: high debt load, elevated inflation risk, monetary system pressure, geopolitical reserve fragmentation, and multi-force co-activation. The article notes this is the macro backdrop Dalio explicitly compares to the early 1970s — the period preceding gold's 20-fold run from $35 to $850/oz between 1971 and 1980. The one restraining factor is that the 10yr TIPS real yield is still ~+2% (not yet near zero), meaning the opportunity cost of holding gold has not yet fully collapsed — but it is the direction of travel that matters most in Dalio's framework.",
    },
  },
  scenarios: {
    label: "Section E — what would change the assessment",
    cards: [
      {
        variant: "bull",
        title: "Bull case for forces decoupling",
        body: "US fiscal grand bargain reduces deficit trajectory. US-China trade truce becomes structural. Fed achieves soft landing — real rates stabilize at +1–2%. AI productivity gains broad-based, reducing inequality. One or more forces decouples. Gold allocation: revert toward 7.5–10% baseline.",
      },
      {
        variant: "bear",
        title: "Bear case for all five intensifying",
        body: "Hormuz closure triggers stagflation spike. Moody's downgrade triggers bond market selloff. Political deadlock prevents debt ceiling resolution. China rare-earth embargo expands. All five forces intensify simultaneously — the scenario Dalio called a potential \"1971 moment.\" Gold and real assets become primary wealth preservation vehicles.",
      },
    ],
  },
  verdict: {
    title: "Synthesis verdict",
    body: "The five-forces framework currently registers its most extreme reading since the framework was developed. Four of five forces are in critical territory; the fifth (technology) is high. The three reinforcing feedback loops — debt/politics, geopolitics/gold, and tech/inequality — are all active and mutually amplifying rather than offsetting. Dalio's core argument is that gold's value in this environment is not about short-term price prediction but about structural protection against monetary and credit-system erosion when multiple forces converge. That condition is present at maximum intensity as of April 2026. The practical allocation implication is a structural position near Dalio's 15% stress-environment guidance — held as a strategic anchor, not a directional trade.",
  },
  sources:
    "CRFB, CBO, Wolf Street (Q4 2025 debt/GDP), Peter G. Peterson Foundation (interest/revenue), World Gold Council (CB demand 2025, March 2026 survey), PIIE (US-China trade), McKinsey/UNCTAD (trade fragmentation April 2026), Goldman Sachs / Fed Governor Barr (AI/labor). This is a macro framework exercise, not investment advice.",
};
