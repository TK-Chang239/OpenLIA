/**
 * T4 — World Order assessment (April 2026 reference instance).
 *
 * Shape matches WorldOrderData. When the backend produces this same
 * shape, WorldOrderView replaces `?? WORLD_ORDER_FALLBACK` with the
 * live result and this file is deleted.
 */

import type { WorldOrderData } from "./types";

export const WORLD_ORDER_FALLBACK: WorldOrderData = {
  header: {
    title: "T4 · World order assessment — US empire cycle",
    subtitle: "April 2026 · Dalio framework · annual cadence",
    pills: [
      { tone: "red", label: "Stage 5 — pre-breakdown" },
      { tone: "amber", label: "Wealth shift: mid-stage" },
    ],
  },
  cardSummary:
    "USD reserve share 56.9% (down from 71.2% in 1999), central banks bought 863t of gold in 2025. Stage 5 — pre-breakdown.",
  scorecard: {
    label: "Section A — reserve currency health indicators",
    rows: [
      {
        name: "USD share of global FX reserves",
        sub: "IMF COFER Q3 2025",
        current: "56.9%",
        currentTone: "amber",
        currentMeta: "Q3 2025",
        fillPct: 62,
        fillTone: "amber",
        trend:
          "Down from 71.2% in 1999. Lowest in decades. Exchange-rate adjustments explain ~92% of Q2 decline — portfolio reallocation modest but directional. IMF: \"little changed after adjusting for FX.\" 73% of central banks surveyed expect USD share to decline further over next 5 years.",
        signalLabel: "Gradual drift",
        signalTone: "amber",
      },
      {
        name: "Net central bank gold purchases",
        sub: "World Gold Council 2025 full year",
        current: "863t",
        currentTone: "red",
        currentMeta: "FY2025 net",
        fillPct: 86,
        fillTone: "red",
        trend:
          "4th consecutive year above 800t; 2023–25 avg over 1,000t — more than 2× the 2010–2020 average. BRICS+ now hold 17.4% of global gold reserves, up from 11.2% in 2019. WGC 2026 survey: 76% of central banks plan to increase gold holdings. Dalio: this is the behavioural signal, not just price.",
        signalLabel: "Structural",
        signalTone: "red",
      },
      {
        name: "Foreign Treasury holdings trend",
        sub: "US TIC data · Jan 2026",
        current: "$9.3T",
        currentTone: "amber",
        currentMeta: "+8% yoy",
        fillPct: 48,
        fillTone: "amber",
        trend:
          "Total holdings rose to $9.31T in Jan 2026, +8% yoy — demand still present. But China down 9% cumulatively since start of 2025. Mixed: private demand strong (flight-to-quality during Iran war), official demand diverging (7 of top-10 added in Jan; Canada cut $72B; Japan/China inconsistent). Not collapse — but official demand increasingly discretionary.",
        signalLabel: "Diverging",
        signalTone: "amber",
      },
      {
        name: "Dollar Index (DXY)",
        sub: "Apr 13, 2026",
        current: "~98.7",
        currentTone: "amber",
        currentMeta: "−9.4% in 2025",
        fillPct: 45,
        fillTone: "amber",
        trend:
          "DXY fell 9.4% in 2025 — worst annual decline since 2017. Stabilised below 99 in 2026. Down ~10% from Jan 2025 high of 109+. BIS data: dollar still on one side of ~89% of global FX trades. Structural support remains but cyclical headwinds (rate cuts, tariff uncertainty, fiscal expansion) ongoing.",
        signalLabel: "Weakening",
        signalTone: "amber",
      },
    ],
  },
  reserveChart: {
    title: "USD reserve share — long-run decline (1999–2026)",
    years: [1999, 2001, 2003, 2005, 2007, 2009, 2011, 2013, 2015, 2017, 2019, 2021, 2023, 2025],
    series: [
      {
        label: "USD",
        isPrimary: true,
        values: [71.2, 70.7, 65.9, 66.9, 63.9, 61.9, 62.2, 61.2, 65.7, 63.8, 60.9, 59.2, 58.4, 56.9],
      },
      {
        label: "EUR",
        values: [17.9, 19.8, 25.3, 24.1, 26.4, 27.7, 24.4, 24.2, 20.5, 20.0, 20.1, 21.2, 20.0, 20.3],
      },
      {
        label: "JPY",
        values: [6.4, 5.0, 4.1, 3.8, 2.9, 3.0, 3.6, 3.8, 4.0, 4.9, 5.8, 5.6, 5.5, 5.8],
      },
      {
        label: "CNY",
        values: [0, 0, 0, 0, 0, 0, 0, 1.1, 1.1, 1.2, 2.0, 2.7, 2.3, 1.9],
      },
      {
        label: "Other",
        values: [4.5, 4.5, 4.7, 5.2, 6.8, 7.4, 9.8, 9.7, 8.7, 10.1, 11.2, 11.3, 13.8, 15.1],
      },
    ],
  },
  empireCycle: {
    label: "Section B — empire cycle stage",
    stripTitle: "Dalio's Big Cycle — six stages (75-year typical arc)",
    stages: [
      { num: "1", name: "Rise", range: "1944–1970s", state: "past", weight: 1 },
      { num: "2", name: "Peak", range: "1970s–1990s", state: "past", weight: 2 },
      { num: "3", name: "Plateau", range: "1990s–2008", state: "past", weight: 3 },
      { num: "4", name: "Pressure", range: "2008–2020", state: "past", weight: 4 },
      { num: "5", name: "Pre-breakdown", range: "2020–now ←", state: "active" },
      { num: "6", name: "Breakdown", range: "ahead", state: "future" },
    ],
    quote: {
      title: "Dalio's direct classification — March 2026",
      body: "\"We are now in a new Stage 5, the stage that immediately precedes the breakdowns. The key markers of Stage 5 as it progresses toward Stage 6 are: large and rapidly rising government debts and geopolitical conflicts that lead to concerns about the value of and security of money, especially of the reserve currency, which drives a movement out of fiat currencies and into gold.\"",
      attribution: "— Ray Dalio, Fortune, March 2026 (direct quote)",
      tone: "red",
    },
    markersTitle: "Stage 5 markers — status check April 2026",
    markers: [
      {
        tone: "red",
        pillLabel: "Confirmed",
        leadPhrase: "Large and rising government debts",
        body: "US debt/GDP at 125%, interest/revenue at record 18.6%, deficit $1.9T in FY2026. CBO projects debt spiral risk by FY2031.",
      },
      {
        tone: "red",
        pillLabel: "Confirmed",
        leadPhrase: "Geopolitical conflicts escalating",
        body: "US-China tech/trade war ongoing (Section 301 investigations launched Mar 2026 against 30+ nations); Iran war started Feb 28, Hormuz disruptions; Greenland crisis; China asset freezes of US defense firms (Dec 2025); US pressure on Denmark over sovereignty.",
      },
      {
        tone: "red",
        pillLabel: "Confirmed",
        leadPhrase: "Breaking down of post-1945 multilateral order",
        body: "NATO burden-sharing crisis (Hague Commitment: 5% GDP defense spend demanded); WTO rules sidelined by tariff blocs; SWIFT fragmentation via BRICS Pay; US withdrawal from global leadership posture (\"days of propping up the entire world order are over\" — Rubio, 2026).",
      },
      {
        tone: "red",
        pillLabel: "Confirmed",
        leadPhrase: "Movement out of fiat currencies into gold",
        body: "Central banks bought 863t in 2025 (4th consecutive year above 800t; 2×+ pre-2022 average). BRICS \"The Unit\" pilot currency launched Oct 2025, pegged to 1g of gold, backed 40% physical gold. 76% of central banks plan to increase gold holdings in 2026.",
      },
      {
        tone: "amber",
        pillLabel: "Developing",
        leadPhrase: "Reserve currency status beginning to wobble",
        body: "USD at 56.9%, lowest in decades but decline still gradual; DXY down 9.4% in 2025 but stabilised near 99 in 2026. Dollar remains on one side of 89% of FX trades — structural position intact but erosion underway. Moody's downgrade confirms institutional acknowledgment.",
      },
      {
        tone: "amber",
        pillLabel: "Not yet",
        leadPhrase: "Hot war between major powers",
        body: "Dalio Stage 6 marker. US-China managed via trade truce (extended Oct 2025; Trump-Xi meeting planned Apr 2026). No direct US-China military confrontation yet. Iran war is regional, not great-power direct conflict. Stage 6 not yet reached; \"managed decline\" still possible.",
      },
    ],
  },
  analogs: {
    label: "Historical analog — similarities and differences",
    cells: [
      {
        era: "Pre-1971 US (Bretton Woods late stage)",
        tone: "green",
        body: "Similar: Reserve currency under pressure from fiscal excess; foreign holders beginning to doubt convertibility; gold outflows accelerating; political fractures over war costs (Vietnam then; geopolitical overreach now).\n\nDifferent: 1971 had a hard gold peg that could be explicitly broken. Today's system is pure fiat — there is no peg to break, so the stress is transmitted through inflation, currency depreciation and bond yields rather than a single discrete convertibility event.",
      },
      {
        era: "British pound decline (1918–1944)",
        tone: "amber",
        body: "Similar: Reserve currency declining gradually over decades, not in a single event. WWI debt burden eroded fiscal space; UK maintained reserve status for decades after economic primacy passed to the US. Structural decline coexisted with continued institutional demand.\n\nDifferent: The pound's decline accelerated during WWII — an exogenous shock rather than a purely endogenous process. The US has no equivalent ready successor (USD still 57% of reserves vs EUR at 20%, CNY at 2%). The transition timescale is likely decades, not years.",
      },
      {
        era: "Rome's late imperial stage (illustrative)",
        tone: "red",
        body: "Similar (pattern only): Dalio explicitly references the Roman pattern — debt debasement, military overextension, internal political fracture, external challenger rising. The \"guns and butter\" trilemma: cannot sustain military, social spending, and currency stability simultaneously at high debt levels.\n\nDifferent: Modern monetary sovereignty allows for much longer debasement periods before crisis because the Fed can print. Rome could not. This extends the timeline but does not change the directional logic.",
      },
    ],
  },
  wealthShift: {
    label: "Section C — great wealth shift signals",
    intro:
      "Dalio's \"great shift from financial wealth to real wealth\" occurs in Stage 5–6 as confidence in paper money erodes. It manifests in three observable ways: institutional behaviour (central bank gold buying), market behaviour (gold/equity ratio trend), and geopolitical behaviour (sanctions avoidance, reserve fragmentation).",
    rows: [
      {
        tone: "red",
        pillLabel: "Institutional",
        leadPhrase: "Central bank gold accumulation — structurally elevated.",
        body: "Four consecutive years above 800t. BRICS+ hold 17.4% of global gold reserves (vs 11.2% in 2019). 76% plan to increase further in 2026. BRICS \"The Unit\" pilot (Oct 2025): 40% gold-backed settlement currency — the most explicit institutional signal that sovereigns are building gold-linked monetary infrastructure outside the dollar system.",
      },
      {
        tone: "amber",
        pillLabel: "Market",
        leadPhrase: "Gold/equity ratio — shifting in gold's favour.",
        body: "Gold surged ~42% in 2025; S&P 500 +18% over the same period. Gold hit ATH of $5,595/oz in Jan 2026. Relative performance of gold vs equities is a structural signal in Dalio's framework — when gold outperforms over multi-year periods, it signals that capital is migrating from financial assets toward hard assets. Currently mid-stage: gold is outperforming but equities have not broken down.",
      },
      {
        tone: "amber",
        pillLabel: "Geopolitical",
        leadPhrase: "Sanctions weaponisation driving reserve fragmentation.",
        body: "Russia's $300B+ dollar reserves frozen in Feb 2022 — the single most consequential catalyst for global de-dollarization. Since then: BRICS Pay digital infrastructure, bilateral local-currency trade deals, BRICS+ expansion (now ~45% of world population, 37% of GDP). China froze US defense firm assets in Dec 2025 in retaliation for Taiwan arms sale — asset freeze as geopolitical weapon is now explicitly reciprocal.",
      },
      {
        tone: "green",
        pillLabel: "Retail / ETF",
        leadPhrase: "ETF and retail flows — early-stage but accelerating.",
        body: "SPDR GLD AUM reached record $150.3B in Jan 2026. Strong ETF inflows in 2025. However, this is still the smallest component of the shift — the dominant driver remains institutional/sovereign. ETF flows tend to lag the institutional signal by 12–24 months and can reverse quickly; the central bank signal is the more durable foundation.",
      },
    ],
    assessment: {
      title: "Wealth shift stage assessment: mid-stage",
      body: "The institutional signal (central bank gold) is at full intensity — this is late-stage in terms of sovereign behaviour. The market signal (gold/equity ratio) is mid-stage — gold outperforming but equities not yet breaking down. The retail/ETF signal is early-stage. Taken together: the shift is past its inception but has not yet reached the disorderly acceleration phase that Dalio associates with the final breakdown. The 1971–1980 analog saw gold rise 20× over nine years after the institutional shift was visible. The current institutional shift has been underway since 2022 — which on that timeline suggests the main wave is still ahead.",
    },
  },
  investment: {
    label: "Section D — investment implications",
    goldRange: {
      title: "Gold allocation range — world order justification",
      stats: [
        { label: "Normal env", value: "5–10%", highlight: false },
        { label: "AW base", value: "7.5%", highlight: false },
        { label: "T4 justified", value: "~15%", highlight: true },
      ],
      body: "T4 world order reading independently justifies the stress-environment guidance. The institutional gold signal (central bank buying 4×+ pre-2022 average) plus the geopolitical reserve fragmentation (BRICS+ building dollar-bypass infrastructure) plus Stage 5 classification by Dalio himself in March 2026 all converge on the same conclusion. This is not a tactical trade — it is a structural reserve position in a world where sovereign wealth is slowly migrating from financial assets to gold.",
    },
    currency: {
      title: "Currency exposure guidance",
      rows: [
        {
          name: "USD (long positions)",
          badgeLabel: "Reduce structural weight",
          badgeTone: "amber",
          body: "DXY down 9.4% in 2025, still structurally supported by 89% FX trade share. Not collapse but gradual headwind. Reduce vs diversified basket.",
        },
        {
          name: "EUR / JPY",
          badgeLabel: "Modest overweight",
          badgeTone: "blue",
          body: "Both gained reserve share in 2025. EUR rose to 20.3% of global reserves. Yen to 5.82%. Neither is a structural replacement for USD but tactical beneficiaries of diversification flows.",
        },
        {
          name: "CNY",
          badgeLabel: "Monitor, not overweight",
          badgeTone: "amber",
          body: "CNY at only 1.93% of global reserves — far below China's economic weight. Capital controls constrain internationalisation. Growing but not investable at scale for most portfolios.",
        },
        {
          name: "Gold (hard currency proxy)",
          badgeLabel: "Strategic core position",
          badgeTone: "red",
          body: "No counterparty risk, no sovereign risk, no sanctions exposure. In Dalio's framework: the only universally accepted reserve asset across the multipolar world order. Central banks are acting on this — investors should follow with appropriate lag.",
        },
      ],
    },
    sovereignBond: {
      title: "Sovereign bond risk premium — T4 perspective",
      intro:
        "The world order lens adds a structural risk premium to US Treasuries that the debt cycle lens (T1) already captures from a fiscal angle. From T4, the additional risk is demand-side: as sovereign buyers systematically diversify away from Treasuries toward gold, the natural clearing price for US debt issuance requires higher yields — adding term premium beyond what the fiscal trajectory alone implies.",
      pair: {
        left: {
          title: "What the yield does NOT fully price",
          body: "The structural erosion of the foreign official buyer base. China down 9% cumulatively in 2025. Canada cut $72B in Jan 2026. As BRICS+ build gold-linked infrastructure and the dollar's reserve share gradually declines, the marginal buyer of Treasuries shifts from price-insensitive sovereign wealth funds to price-sensitive private investors — who demand more yield. This is a slow-moving structural headwind that term premiums have not fully incorporated.",
        },
        right: {
          title: "What would trigger a repricing event",
          body: "A disorderly abandonment of Treasuries by a major sovereign holder (China's $694B, Japan's $1.2T), a failed Treasury auction, or a rapid acceleration of the BRICS \"Unit\" gold-linked settlement system achieving scale. None of these is imminent — but all are more probable than they were five years ago. A China-Taiwan escalation is the highest-probability trigger for a sudden repricing, as it would likely combine asset freeze threats with large-scale official selling.",
        },
      },
    },
  },
  verdict: {
    title: "T4 synthesis — bottom line for T5 and T3 consumption",
    body: "Dalio himself has classified the US as Stage 5 (pre-breakdown) as recently as March 2026. All four Stage 5 markers are confirmed by current data. The great wealth shift is mid-stage: institutional (strong), market (building), retail (early). The dollar is not collapsing — its institutional scaffolding remains — but the direction of every structural indicator points to continued erosion. Fed into T5: contributes a critical reading for Force 3 (geopolitical cycle) and Force 1 (debt/money). Fed into T3: gold allocation of ~15% is independently justified by T4 alone; the T1 and T2 signals are additive confirmations, not prerequisites.",
    tone: "amber",
  },
  sources:
    "IMF COFER Q3 2025 (56.92% USD share, Dec 2025 data brief); IMF blog Oct 2025 (exchange-rate-adjusted reserve data); WGC central bank gold 2025 full year (863t, Jan 2026); WGC 2026 survey (76% CB plan to increase); BRICS \"The Unit\" pilot (Oct 2025, London Gold Exchange); TIC Jan 2026 (US Treasury, $9.31T total); DXY Trading Economics / US Bank (−9.4% in 2025; ~98.7 Apr 13 2026); Dalio, Fortune, March 2026 (direct Stage 5 classification); Dalio LinkedIn / June 2025 essay \"How Countries Go Broke\"; BRICS+ membership data. Not investment advice.",
};
