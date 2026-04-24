import type { PanelId } from "../../api/panic-thermometer";

export interface PanelCatalogEntry {
  id: PanelId;
  displayName: string;
  shortLabel: string;
  sparklineKey: string;
}

export const PANEL_CATALOG: PanelCatalogEntry[] = [
  {
    id: "oil",
    displayName: "Oil Price Duration",
    shortLabel: "Oil",
    sparklineKey: "price",
  },
  {
    id: "inflation",
    displayName: "Inflation Expectations",
    shortLabel: "Inflation",
    sparklineKey: "tip_price",
  },
  {
    id: "fed_language",
    displayName: "Fed Language Tracker",
    shortLabel: "Fed",
    sparklineKey: "",
  },
  {
    id: "wage_growth",
    displayName: "Wage Growth",
    shortLabel: "Wages",
    sparklineKey: "value",
  },
  {
    id: "diplomacy",
    displayName: "Diplomatic Progress",
    shortLabel: "Diplomacy",
    sparklineKey: "",
  },
];

export const PANEL_IDS: PanelId[] = PANEL_CATALOG.map((p) => p.id);
