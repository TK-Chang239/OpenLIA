/**
 * T2 — Four-seasons economic diagnostic. April 2026 reference instance.
 *
 * Shape matches FourSeasonsData. When the backend produces this same
 * shape, FourSeasonsView replaces `?? FOUR_SEASONS_FALLBACK` with the
 * live result and this file is deleted.
 */

import type { FourSeasonsData } from "./types";

export const FOUR_SEASONS_FALLBACK: FourSeasonsData = {
  header: {
    title: "T2 · Four-seasons diagnostic — US",
    subtitle: "April 2026 · data as of 10 Apr 2026",
    pills: [
      { tone: "amber", label: "Transitioning summer → autumn" },
      { tone: "purple", label: "Mixed confidence" },
    ],
  },
  cardSummary:
    "Manufacturing PMI rising, Q4 GDP +0.5%, CPI 3.3%. Transitioning summer → autumn (stagflation).",
  scorecard: {
    rows: [
      {
        name: "Manufacturing PMI",
        sub: "ISM Mar 2026",
        fillPct: 72,
        fillTone: "green",
        current: "52.7",
        currentTone: "green",
        currentMeta: "3rd month above 50",
        trend:
          "Jan 50.9 → Feb 52.4 → Mar 52.7. Modestly rising. 12-month avg 49.6 — current well above. New orders eased 2.3pt to 53.5; employment still in contraction.",
        axisLabel: "Growth rising",
        axisTone: "green",
        direction: "up",
        directionLabel: "Rising",
        directionTone: "green",
      },
      {
        name: "Real GDP (annualised)",
        sub: "BEA Q4 2025 (third est.)",
        fillPct: 35,
        fillTone: "red",
        current: "+0.5%",
        currentTone: "red",
        currentMeta: "vs +4.4% in Q3",
        trend:
          "Collapsed from 4.4% (Q3) to 0.5% (Q4). Govt shutdown subtracted 1.0pp. Iran war, tariffs, and consumer fatigue expected to weigh on Q1 2026. SPF 2026 consensus: 1.8% full-year — well below 2025's 2.1%.",
        axisLabel: "Growth slowing",
        axisTone: "red",
        direction: "down",
        directionLabel: "Falling",
        directionTone: "red",
      },
      {
        name: "CPI (all items, yoy)",
        sub: "BLS Mar 2026",
        fillPct: 78,
        fillTone: "red",
        current: "+3.3%",
        currentTone: "red",
        currentMeta: "vs 2.4% in Feb",
        trend:
          "Jumped 0.9% mom — largest monthly move since Jun 2022. Energy +10.9%; gasoline +21.2% (Iran war). Highest since May 2024. But core CPI only +2.6% yoy (+0.2% mom) — underlying inflation relatively tame.",
        axisLabel: "Inflation rising",
        axisTone: "red",
        direction: "up",
        directionLabel: "Rising",
        directionTone: "red",
      },
      {
        name: "Core CPI (ex-food/energy, yoy)",
        sub: "BLS Mar 2026",
        fillPct: 52,
        fillTone: "amber",
        current: "+2.6%",
        currentTone: "amber",
        currentMeta: "vs 2.5% in Feb",
        trend:
          "Ticked up 0.1pp — below 2.7% forecast. Services ex-energy 3%; shelter 3%; transport services 4.1%; medical care 3.1%. Sticky, above Fed target, but not accelerating rapidly in underlying terms.",
        axisLabel: "Inflation sticky",
        axisTone: "amber",
        direction: "flat",
        directionLabel: "Flat / rising",
        directionTone: "amber",
      },
      {
        name: "HY credit spread (OAS)",
        sub: "ICE BofA / FRED Apr 2026",
        fillPct: 30,
        fillTone: "blue",
        current: "~2.9%",
        currentTone: "blue",
        currentMeta: "Apr 9 2026 — tight",
        trend:
          "~2.9% OAS historically tight — credit markets are NOT pricing recession or default stress. Widened modestly in Feb on AI disruption fears; IG spreads ~1.4%. Not signalling credit distress yet.",
        axisLabel: "Credit stable",
        axisTone: "green",
        direction: "flat",
        directionLabel: "Flat / tight",
        directionTone: "green",
      },
    ],
  },
  quadrant: {
    seasons: {
      tl: {
        name: "Autumn",
        sub: "Growth falling · inflation rising (stagflation)",
        pillLabel: "Gold · real assets",
        tone: "red",
      },
      tr: {
        name: "Summer",
        sub: "Growth rising · inflation rising",
        pillLabel: "Commodities · TIPS",
        tone: "amber",
      },
      bl: {
        name: "Winter",
        sub: "Growth falling · inflation falling",
        pillLabel: "Long bonds · cash",
        tone: "blue",
      },
      br: {
        name: "Spring",
        sub: "Growth rising · inflation falling",
        pillLabel: "Equities",
        tone: "green",
      },
    },
    markers: [
      { label: "Apr 2026", xPct: 46, yPct: 14, variant: "now", tone: "red" },
      { label: "Jan 2026", xPct: 50, yPct: 30, variant: "prev", tone: "amber" },
    ],
  },
  verdict: {
    title: "Transitioning summer → autumn",
    body: "GDP collapsed from 4.4% to 0.5% annualised between Q3 and Q4 2025 — the growth axis is clearly turning negative. Headline CPI re-accelerated to 3.3% in March on Iran energy shock while core remains sticky at 2.6%. Growth falling + inflation rising = the definition of the autumn quadrant (stagflation). The transition is not yet complete: PMI is still above 50 and credit spreads are tight, which is why the confidence level is mixed rather than clear.",
    sideCards: [
      {
        label: "Confidence level",
        value: "Mixed",
        valueTone: "amber",
        note: "Growth axis ambiguous; inflation axis clearer",
      },
      {
        label: "Nearest comparable period",
        value: "H1 2022",
        valueTone: "blue",
        note: "And early 1974 (oil shock + slowing growth)",
      },
    ],
  },
  parallels: {
    cards: [
      {
        title: "H1 2022 — the closer parallel",
        body: "Inflation re-accelerated driven by energy (Russia-Ukraine oil shock). Real GDP growth slowed sharply. Fed was stuck — hikes needed to fight inflation but growth was fading. Result: stocks and bonds both fell simultaneously (textbook autumn). Key similarity: exogenous energy shock driving headline inflation while underlying growth is weakening. Key difference: core inflation in 2022 was far more broad-based (8%+ all-items); today core is only 2.6%.",
      },
      {
        title: "1973–74 — the structural analog",
        body: "Arab oil embargo triggered an energy spike while underlying growth was already decelerating. The parallels to today are notable: a Middle East conflict disrupting oil supply, dollar under pressure, fiscal constraints limiting policy response. Key similarity: geopolitical energy shock on top of an already-fragile fiscal backdrop. Key difference: 1974 came with broad wage-price spiral; today's labor market and wage dynamics are much weaker.",
      },
    ],
  },
  transitionRisk: {
    intro:
      "The primary risk is a confirmed move into full autumn (both axes clearly negative) if: (1) the Iran war persists and energy prices remain elevated, feeding inflation while simultaneously depressing consumer spending and real growth; or (2) the PMI rolls over below 50 on new orders deterioration — new orders already eased 2.3pt in March and ISM's own chair warned demand sentiment is \"going in the wrong direction.\"",
    bull: {
      title: "If summer persists (bull case)",
      body: "Iran ceasefire holds and oil retraces. Core inflation stays at 2.6% or falls. GDP rebounds in Q1 2026 (BEA advance estimate due Apr 30). PMI new orders recover above 55. Season stays summer — commodities/TIPS are tailwinds, equities can hold. Season label: summer with residual stagflation risk.",
    },
    bear: {
      title: "If autumn confirms (bear case)",
      body: "Iran war drags on, energy inflation feeds into transportation and services. PMI rolls below 50. Q1 GDP disappoints. Fed trapped — cannot cut (inflation) or hike (growth already fragile). Classic stagflation trap. Season label: autumn confirmed — gold and real assets displace equities and long bonds as portfolio anchors.",
    },
    keyIndicator: {
      title: "Key indicator to watch",
      body: "BEA Q1 2026 GDP advance estimate (Apr 30) is the single highest-impact data release for season reclassification. A reading below 1.0% would confirm the growth axis as firmly negative. ISM April PMI (May 1) is the second trigger — particularly new orders sub-index.",
    },
  },
  assetPlaybook: {
    cards: [
      {
        tone: "amber",
        label: "Commodities",
        posture: "Summer + autumn tailwind",
        body: "Energy is the most direct play on the Iran war. Commodities broadly benefit in summer (rising inflation + growth) and in autumn (inflation > growth). The transition doesn't change the commodity thesis — it strengthens it. Currently confirmed: WTI crude +4.66% recently.",
      },
      {
        tone: "red",
        label: "Gold",
        posture: "Autumn-specific signal strengthening",
        body: "Gold is the canonical autumn asset. As growth decelerates and inflation stays elevated, real purchasing power is eroding and monetary policy cannot respond normally. Gold's role as structural hedge against both inflation and credit system stress is reinforced by the debt cycle read from T1. Combine T1 + T2 signals: both point gold-positive.",
      },
      {
        tone: "green",
        label: "Equities",
        posture: "Cautious — avoid spring-tilted",
        body: "Equities are spring assets. In summer they can hold; in autumn they typically fall. The PMI is still expansionary, credit spreads are still tight — that keeps equities from outright collapse. But the directional risk is negative as growth slows. Reduce concentration in long-duration growth tech; prefer value/energy/commodity producers. Employment PMI is still in contraction — caution on cyclicals.",
      },
      {
        tone: "blue",
        label: "Long-duration bonds",
        posture: "Avoid — dual headwind in autumn",
        body: "Long bonds face the worst setup in an autumn regime: inflation is rising (pushing yields up → prices down) while growth is slowing (bad for credit quality). The 2022 precedent where both stocks and bonds posted double-digit losses came from this exact configuration. The T1 debt cycle read adds a structural supply-demand headwind (large issuance, declining foreign demand) on top.",
      },
    ],
  },
  notes: [
    {
      title: "Portfolio stress test — if transitional summer/autumn persists 2–4 quarters",
      body: "A conventional 60/40 portfolio faces its worst structural alignment: equities (spring asset) decline as growth slows, long bonds (winter asset) underperform as inflation stays elevated. This is exactly the 2022 scenario where both legs of 60/40 posted double-digit losses simultaneously. The assets running with the wind in a persistent transitional autumn are: energy commodities, gold, TIPS/inflation-linked bonds, and short-duration credit. Assets running into the wind: long-duration nominal Treasuries, high-multiple growth equities, and EM assets with dollar-denominated liabilities.",
    },
    {
      title: "One key nuance: the growth signal is split",
      body: "Manufacturing PMI at 52.7 (above 50, rising) and services PMI at 54.0 (21 consecutive months of expansion) are both pointing to a growing economy. But real GDP at +0.5% annualised in Q4 tells the opposite story — growth has nearly stalled. This split is the central diagnostic challenge. Dalio's framework resolves it by weighting the GDP trend over the PMI level: GDP direction is the more structural signal, PMI level is the more coincident one. With GDP clearly decelerating even as PMI looks healthy, the framework calls this a growth-decelerating environment — which maps onto the left half of the quadrant map.",
    },
  ],
  sources:
    "ISM Manufacturing PMI Mar 2026 (52.7, ISM/PRNewswire Apr 1 2026); ISM Services PMI Mar 2026 (54.0, ISM Apr 6 2026); BLS CPI Mar 2026 (3.3% yoy, 0.9% mom; core 2.6% yoy; Apr 10 2026); BEA GDP Q4 2025 third estimate (0.5% annualised, Apr 9 2026); ICE BofA HY OAS ~2.9% (FRED / YCharts Apr 9 2026); Philadelphia Fed SPF Q4 2025 (2026 GDP consensus 1.8%). Not investment advice.",
};
