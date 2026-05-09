/**
 * T1 — Debt Cycle position report. April 2026 reference instance.
 *
 * Shape matches DebtCycleData. When the backend produces this same shape,
 * DebtCycleView replaces `?? DEBT_CYCLE_FALLBACK` with the live result and
 * this file is deleted.
 */

import type { DebtCycleData } from "./types";

export const DEBT_CYCLE_FALLBACK: DebtCycleData = {
  header: {
    title: "T1 · US debt cycle position report",
    subtitle: "April 2026 · Dalio framework",
    pills: [
      { tone: "red", label: "3 / 3 in warning zone" },
      { tone: "amber", label: "Late plateau" },
    ],
  },
  cardSummary:
    "Debt/GDP 125.2%, interest/revenue 18.6% — all three Dalio indicators in warning. Late plateau approaching structural constraint.",
  scorecard: {
    rows: [
      {
        name: "Govt debt / GDP",
        sub: "Gross federal debt · Q4 2025",
        current: "125.2%",
        currentTone: "red",
        currentMeta: "CEIC Q4 2025",
        threshold:
          "Sustained >100% = fiscal & monetary space constrained. Historical analog: 130% post-WWII peak (1946).",
        status: "Critical",
        statusTone: "red",
        fillPct: 93,
        fillTone: "red",
      },
      {
        name: "Interest cost / federal revenue",
        sub: "Net interest as % of receipts · FY2026",
        current: "18.6%",
        currentTone: "red",
        currentMeta: "CBO Feb 2026 · record high",
        threshold:
          "Dalio: pressure escalates sharply above ~15%. Now above the 1991 previous record. On path to 25.8% by 2036.",
        status: "Critical",
        statusTone: "red",
        fillPct: 88,
        fillTone: "red",
      },
      {
        name: "10yr TIPS real yield (DFII10)",
        sub: "Inflation-indexed Treasury yield · Apr 10, 2026",
        current: "+1.94%",
        currentTone: "amber",
        currentMeta: "Trading Economics / Fed H.15",
        threshold:
          "Gold demand spikes when approaching 0% or turning negative. Currently positive but down 0.36pp vs one year ago — direction bearish for real yields.",
        status: "Elevated",
        statusTone: "amber",
        fillPct: 55,
        fillTone: "amber",
      },
    ],
  },
  phaseBox: {
    title: "Phase: late plateau — approaching structural constraint",
    body: "Debt has been above 100% of GDP since 2013, and conventional monetary policy has already been used to manage three distinct crises (2008, COVID-2020, inflation 2022–24). Each crisis left interest rates and debt levels higher than before. The structural feature of the plateau phase — where debt is high but still serviceable — is now being tested by the interest-burden indicator, which has crossed into warning territory for the first time since 1991.",
    tone: "amber",
  },
  analogPair: {
    analog: {
      title: "US 1968–1980 (closest); Japan 1995–2005 (partial)",
      body: "Similar to 1968–80: high debt, sticky inflation preventing aggressive rate cuts, political gridlock blocking fiscal consolidation, dollar under structural pressure from fiscal excess. Gold surged ~20× in the 1970s as debasement materialized.\n\nDifferent from 1968–80: the US still holds reserve currency status and dollar-denominated debt retains global demand, which extends the plateau. Japan's 1995–2005 experience (debt/GDP over 100%, near-zero rates, deflation rather than inflation) shows a plateau can persist far longer than expected when the sovereign has monetary sovereignty and domestic savings base.",
    },
    timeToConstraint: {
      title: "Constraint already active; acute pressure within 3–7 years",
      body: "The interest/revenue ratio is already above the historical danger threshold. The constraint is not a future risk — it is present now and compounding. CRFB analysis warns that if the average interest rate on debt exceeds GDP growth rate (projected by FY2031 under baseline), the US enters a debt spiral dynamic. The 3–7 year window before acute crisis reflects the buffer of reserve currency status and domestic institutional demand for Treasuries — not a clean bill of fiscal health.",
    },
  },
  policySpace: {
    cards: [
      {
        label: "Rate cut headroom",
        value: "~150–175 bps",
        valueTone: "amber",
        unit: "to effective lower bound",
        note: "Fed funds: 3.50–3.75% (Mar 2026 hold). Fed median projection: one cut in 2026. JPM expects on-hold all year. Effective lower bound ~2.0–2.5%. Headroom limited vs pre-2008 norm of 500+ bps.",
      },
      {
        label: "QE credibility",
        value: "Degraded",
        valueTone: "amber",
        unit: "inflation still above 2% target",
        note: "Core PCE ~2.5–2.8%; CPI jumped to 3.26% in March 2026 (JEC). Any QE deployment now risks re-igniting inflation expectations. Fed explicitly cannot run QE freely while inflation is above target — a key constraint Dalio identifies as the tell-tale sign of a late plateau.",
      },
      {
        label: "Currency debasement risk",
        value: "Elevated",
        valueTone: "red",
        unit: "structural, not cyclical",
        note: "Moody's downgraded US to Aa1 (May 2025) — now rated below Aa1 by all three major agencies. Deficits projected at ~6% of GDP through 2035. CBO Feb 2026: interest will double nominally by 2036. These are debasement preconditions, not triggers.",
      },
    ],
  },
  assetThesis: {
    gold: {
      title: "Gold / real assets thesis",
      body: "The debt cycle framework produces a clear directional signal: as the real yield on TIPS trends toward zero (currently +1.94%, down 0.36pp YoY), the opportunity cost of gold declines. The interest/revenue ratio already exceeding the 1991 record — and compounding toward 25.8% by 2036 — increases the structural probability of monetization rather than fiscal consolidation as the resolution path. Gold is the canonical beneficiary of monetization: it carries no counterparty risk and no sovereign default risk. Dalio's Oct 2025 guidance for this type of environment: raise strategic gold allocation toward 15% of total portfolio.",
    },
    longBond: {
      title: "Long-duration bond risk",
      body: "Long-duration Treasuries face a structurally adverse setup. The supply of issuance is rising (deficit ~$1.9T in FY2026; CBO), while the natural demand base is eroding as foreign central banks diversify into gold. The term premium is not adequately compensating for this risk. If the Fed is forced to monetize (QE into a high-inflation environment), long bonds would face simultaneous duration risk (yields rising) and currency debasement. The classic All-Weather 40% long-bond allocation requires explicit leverage caveats in this environment — an inflationary late-plateau is the one macro regime where that position structurally underperforms.",
    },
  },
  watchlist: {
    rows: [
      {
        tone: "green",
        name: "Interest/revenue stabilizes or declines",
        body: "If a credible multi-year fiscal consolidation plan passes (spending cuts + revenue measures) and the CBO forward path for interest/revenue bends down, reassess phase from late plateau toward mid plateau. This is the most important single indicator to monitor quarterly.",
      },
      {
        tone: "amber",
        name: "TIPS real yield falls below +1%",
        body: "Historically, TIPS yields moving below +1% have been associated with gold entering a sustained bull phase. Currently at +1.94% — falling 0.36pp YoY. Track monthly: a further 0.5–1pp decline materially strengthens the gold thesis.",
      },
      {
        tone: "red",
        name: "Interest rate exceeds GDP growth rate (debt spiral threshold)",
        body: "CRFB projects this crossover by FY2031 under baseline. If it occurs earlier due to re-inflation or recession-driven growth slowdown, phase reclassifies from late plateau to early deleveraging — the most serious escalation step. Monitor avg debt interest rate (JEC monthly) vs nominal GDP growth (BEA quarterly).",
      },
      {
        tone: "red",
        name: "Foreign demand for Treasuries deteriorates sharply",
        body: "TIC data showing sustained net selling by foreign official holders, combined with rising term premiums, would signal the dollar's safe-haven bid is weakening. This is the transmission mechanism from debt cycle stress into currency debasement. Track monthly TIC report.",
      },
      {
        tone: "amber",
        name: "Fed chair transition (Powell term ends May 2026)",
        body: "Kevin Warsh nominated as new chair (Trump, Jan 2026). A chair perceived as more politically compliant could raise inflation expectations and weaken dollar safe-haven status, accelerating debasement risk. Monitor Fed communication tone and market inflation breakeven rate.",
      },
    ],
  },
  verdict: {
    title: "Section D synthesis — bottom line for T5 and T3 consumption",
    body: "All three Dalio indicators are in warning territory simultaneously for the first time since the early 1990s, with the interest/revenue ratio now exceeding the 1991 record. The cycle phase is late plateau: debt is historically elevated, monetary policy headroom is limited, QE credibility is degraded by sticky inflation, and a debt spiral threshold is projected within the current decade. This reading, fed into T5 (five forces), contributes a critical score for Force 1. Fed into T3 (allocation audit), it justifies a gold allocation near or at Dalio's stress-environment guidance of ~15%, subject to cross-check with the T2 season and T4 world order readings.",
    tone: "amber",
  },
  sources:
    "CEIC/BEA (debt/GDP Q4 2025 125.2%), PGPF/CBO Feb 2026 (interest/revenue 18.6% in FY2026, path to 25.8% by 2036), Trading Economics / Fed H.15 (DFII10 +1.94% Apr 10 2026), JEC Monthly Debt Update (total debt $38.98T as of Apr 3 2026, avg rate 3.365%), CRFB Feb 2026 baseline, Moody's downgrade May 2025, iShares/JPM (Fed funds 3.50–3.75%, on-hold outlook). Not investment advice.",
};
