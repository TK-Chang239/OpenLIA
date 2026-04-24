import type { ReportMode } from "../../api/equity-research";

export interface SectionEntry {
  id: string;
  title: string;
}

export const SECTION_CATALOG: Record<ReportMode, SectionEntry[]> = {
  stock_initiation: [
    { id: "company_overview", title: "Company Overview" },
    { id: "industry_overview", title: "Industry Overview" },
    { id: "products_and_services", title: "Products and Services" },
    { id: "business_model", title: "Business Model" },
    { id: "competitive_analysis", title: "Competitive Analysis" },
    { id: "management_team", title: "Management Team" },
    { id: "competitive_advantages", title: "Competitive Advantages and Weaknesses" },
    { id: "risk_analysis", title: "Risk Analysis" },
    { id: "historical_financials", title: "Historical Financial Data" },
    { id: "financial_analysis", title: "Financial Analysis" },
    { id: "financial_projections", title: "Financial Projections" },
    { id: "valuation_analysis", title: "Valuation Analysis" },
    { id: "investment_recommendation", title: "Investment Recommendation" },
  ],
  stock_update: [
    { id: "investment_thesis", title: "Investment Thesis / Key Takeaway" },
    { id: "event_analysis", title: "Event Analysis" },
    { id: "financial_results", title: "Financial Results Summary" },
    { id: "estimate_revisions", title: "Estimate Revisions" },
    { id: "valuation_and_target", title: "Valuation and Price Target" },
    { id: "scenarios", title: "Bull / Bear / Base Scenarios" },
    { id: "risks", title: "Risks" },
  ],
  sector_research: [
    { id: "sector_thesis", title: "Sector Thesis / Key Takeaway" },
    { id: "industry_overview", title: "Industry Overview and Market Sizing" },
    { id: "key_drivers", title: "Key Drivers and Trends" },
    { id: "data_analysis", title: "Market Data and Analysis" },
    { id: "competitive_landscape", title: "Competitive Landscape and Value Chain" },
    { id: "company_analysis", title: "Company Analysis and Stock Implications" },
    { id: "valuation", title: "Valuation" },
    { id: "risks", title: "Risks" },
  ],
};

export function titleOf(mode: ReportMode, id: string): string {
  const entry = SECTION_CATALOG[mode].find((s) => s.id === id);
  return entry?.title ?? id;
}
