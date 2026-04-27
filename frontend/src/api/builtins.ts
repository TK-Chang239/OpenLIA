import type { Category } from "./connectors";

export interface BuiltinEntry {
  template_id: string;
  display_name: string;
  category: Category;
  api_key_env_var: string;
}

export const BUILT_IN_CATALOG: BuiltinEntry[] = [
  {
    template_id: "eodhd",
    display_name: "EODHD",
    category: "financial",
    api_key_env_var: "EODHD_API_KEY",
  },
  {
    template_id: "fmp",
    display_name: "Financial Modeling Prep",
    category: "financial",
    api_key_env_var: "FMP_API_KEY",
  },
  {
    template_id: "newsapi_ai",
    display_name: "NewsAPI.ai",
    category: "news",
    api_key_env_var: "NEWSAPI_AI_KEY",
  },
];

export function builtinsForCategory(c: Category): BuiltinEntry[] {
  return BUILT_IN_CATALOG.filter((b) => b.category === c);
}
