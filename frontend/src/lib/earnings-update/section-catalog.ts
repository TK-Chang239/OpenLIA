export interface SectionCatalogEntry {
  title: string;
  description: string;
}

export const EU_SECTION_CATALOG: Record<string, SectionCatalogEntry> = {
  quick_take: {
    title: "Quick Take",
    description:
      "1–3 sentence verdict and investment implication.",
  },
  market_reaction: {
    title: "Post-Earnings Market Reaction",
    description:
      "Price change, volume, and immediate analyst response.",
  },
  key_financials: {
    title: "Key Financials vs Consensus",
    description:
      "Revenue, EPS, and margins vs estimate, prior quarter, and year ago.",
  },
  operational_highlights: {
    title: "Operational Highlights and Drivers",
    description:
      "Beats, misses, watch items, and segment breakdown.",
  },
  forward_guidance: {
    title: "Forward Guidance",
    description:
      "New vs prior guidance, vs street, and guidance quality.",
  },
  earnings_call: {
    title: "Earnings Call Key Points",
    description:
      "Management commentary, Q&A highlights, and tone.",
  },
  risk_assessment: {
    title: "Risk Assessment",
    description:
      "Upside and downside risks specific to this quarter.",
  },
  thesis_check: {
    title: "Investment Thesis Check",
    description:
      "How this quarter affects each thesis pillar and the rating.",
  },
};

export const DEFAULT_EU_SECTIONS: readonly string[] = [
  "quick_take",
  "market_reaction",
  "key_financials",
  "operational_highlights",
  "forward_guidance",
  "earnings_call",
  "risk_assessment",
  "thesis_check",
] as const;

export function euTitleOf(id: string): string {
  return EU_SECTION_CATALOG[id]?.title ?? id;
}
