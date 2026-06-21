// Surviving equity-research types shared by the v3 composer chrome.
//
// The v1/v2 equity-research engines (and their config/template REST helpers)
// were removed; v3 is the sole engine (see api/equity-research-v3.ts). Only
// these two enum types are still imported — by ErComposer.tsx and
// WelcomeStage.tsx for the report-mode / report-length pills.
export type ReportMode = "stock_initiation" | "stock_update" | "sector_research";
export type ReportLength = "concise" | "normal" | "elaborative";
