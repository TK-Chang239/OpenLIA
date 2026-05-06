/** Curated bank of dispatch suggestions surfaced on the Home page.
 *  Picker selects one entry per dept slot, deterministically per day so the
 *  set is stable through refresh but rotates at midnight. The Refresh button
 *  shifts the seed to surface a different selection. */

export type SuggestionDept =
  | "earnings_update"
  | "macro_research"
  | "portfolio"
  | "retail_sentiment";

export interface Suggestion {
  dept: SuggestionDept;
  /** Mono uppercase tag rendered in the card head. */
  tag: string;
  /** Whether the card head dot is the live accent color. */
  live?: boolean;
  /** The user-facing question text. */
  question: string;
  /** Short mono footer hinting at the data sources LIA would use. */
  sourceHint: string;
}

export const SUGGESTION_BANK: readonly Suggestion[] = [
  // Earnings Update
  {
    dept: "earnings_update",
    tag: "Earnings Update · live",
    live: true,
    question:
      "Summarize NVDA Q3 — focus on data-center and the Q4 guide.",
    sourceHint: "10-Q · transcript · consensus",
  },
  {
    dept: "earnings_update",
    tag: "Earnings Update",
    question:
      "What did AMZN guide for AWS this quarter, and how did the buyside react?",
    sourceHint: "press release · call · sell-side notes",
  },
  {
    dept: "earnings_update",
    tag: "Earnings Update",
    question: "Compare TSLA's auto gross margin trend to last 4 quarters.",
    sourceHint: "10-Q × 4 · supplementals",
  },
  // Macro Research
  {
    dept: "macro_research",
    tag: "Macro Research",
    question: "Bull / bear setup heading into Thursday's CPI print.",
    sourceHint: "BLS · futures · positioning",
  },
  {
    dept: "macro_research",
    tag: "Macro Research",
    question: "What is the rates market pricing for the next FOMC meeting?",
    sourceHint: "OIS · SOFR futures · dot plot",
  },
  {
    dept: "macro_research",
    tag: "Macro Research",
    question:
      "Walk me through the dollar wrecking ball in two paragraphs.",
    sourceHint: "DXY · EM FX · BIS",
  },
  // Portfolio
  {
    dept: "portfolio",
    tag: "Portfolio",
    question: "Which names in my book have >2% pre-market moves?",
    sourceHint: "14 holdings · LIA tracks",
  },
  {
    dept: "portfolio",
    tag: "Portfolio",
    question: "What is my current factor exposure vs the SPX?",
    sourceHint: "Barra-style · 14 holdings",
  },
  {
    dept: "portfolio",
    tag: "Portfolio",
    question: "Rank my positions by Sharpe over the last 90 days.",
    sourceHint: "daily returns · 14 holdings",
  },
  // Retail Sentiment
  {
    dept: "retail_sentiment",
    tag: "Retail Sentiment",
    question: "What's r/wallstreetbets piling into this week?",
    sourceHint: "1,284 threads · 24h",
  },
  {
    dept: "retail_sentiment",
    tag: "Retail Sentiment",
    question: "Which tickers spiked in mention velocity overnight?",
    sourceHint: "Reddit · StockTwits · 12h",
  },
  {
    dept: "retail_sentiment",
    tag: "Retail Sentiment",
    question: "Sentiment tilt on AAPL across retail forums this week.",
    sourceHint: "Reddit · StockTwits · 7d",
  },
];

const DEPT_ORDER: readonly SuggestionDept[] = [
  "earnings_update",
  "macro_research",
  "portfolio",
  "retail_sentiment",
];

function hashSeed(seed: string): number {
  let h = 0;
  for (let i = 0; i < seed.length; i++) {
    h = (h * 31 + seed.charCodeAt(i)) | 0;
  }
  return h;
}

/** Deterministic picker — selects one Suggestion per dept slot in
 *  `DEPT_ORDER`, indexed by `seed` so the same seed always yields the same
 *  4-card set. */
export function pickSuggestions(
  bank: readonly Suggestion[],
  seed: string,
): Suggestion[] {
  const out: Suggestion[] = [];
  const h = hashSeed(seed);
  for (let slot = 0; slot < DEPT_ORDER.length; slot++) {
    const dept = DEPT_ORDER[slot];
    const candidates = bank.filter((s) => s.dept === dept);
    if (candidates.length === 0) continue;
    // Shift hash per slot so different slots draw independently.
    const idx = ((h + slot * 7919) % candidates.length + candidates.length) %
      candidates.length;
    out.push(candidates[idx]);
  }
  return out;
}
