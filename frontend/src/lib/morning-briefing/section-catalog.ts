export interface SectionCatalogEntry {
  title: string;
  hint: string;
  topicPlaceholder: string;
  hasTopics: boolean;
  hasReferencePortfolioToggle?: boolean;
}

export const MB_SECTION_CATALOG: Record<string, SectionCatalogEntry> = {
  executive_summary: {
    title: "Executive Summary",
    hint: "Always included as a summary of the full briefing.",
    topicPlaceholder: "",
    hasTopics: false,
  },
  global_macro: {
    title: "Global Macro News",
    hint: "Add macro topics to cover (e.g., War, Politics, Energy).",
    topicPlaceholder: "Add topic",
    hasTopics: true,
  },
  country_news: {
    title: "Country News",
    hint: "Add countries to cover (e.g., US, Taiwan, Japan).",
    topicPlaceholder: "Add country",
    hasTopics: true,
  },
  market_news: {
    title: "Market News",
    hint: "Add markets to cover (e.g., Bonds, Gold, Oil).",
    topicPlaceholder: "Add market",
    hasTopics: true,
  },
  sector_news: {
    title: "Sector News",
    hint: "Add sectors or industries to cover.",
    topicPlaceholder: "Add sector",
    hasTopics: true,
  },
  stock_news: {
    title: "Stock News",
    hint: "Add tickers to cover (e.g., AAPL, TSLA).",
    topicPlaceholder: "Add stock",
    hasTopics: true,
  },
  upcoming_preview: {
    title: "Upcoming Preview",
    hint: "Covers major upcoming events for the next few sessions.",
    topicPlaceholder: "Add topic",
    hasTopics: true,
    hasReferencePortfolioToggle: true,
  },
};

export const DEFAULT_MB_SECTIONS: readonly string[] = [
  "executive_summary",
  "global_macro",
  "country_news",
  "market_news",
  "sector_news",
  "stock_news",
  "upcoming_preview",
];
