import {
  Home,
  FolderOpen,
  MessageSquare,
  TrendingUp,
  ClipboardList,
  Sun,
  BarChart2,
  Globe,
  Thermometer,
  type LucideIcon,
} from "lucide-react";

export interface NavEntry {
  id: string;
  label: string;
  icon: LucideIcon;
  path: string;
  /** Department id used to correlate with /notifications/unread.by_department. null for core pages. */
  departmentId: string | null;
}

export const CORE_NAV: readonly NavEntry[] = [
  { id: "home", label: "Home", icon: Home, path: "/", departmentId: null },
  {
    id: "repository",
    label: "Repository",
    icon: FolderOpen,
    path: "/repository",
    departmentId: null,
  },
];

export const DEPARTMENT_NAV: readonly NavEntry[] = [
  {
    id: "secretary",
    label: "Secretary",
    icon: MessageSquare,
    path: "/secretary",
    departmentId: "secretary",
  },
  {
    id: "equity_research",
    label: "Equity Research",
    icon: TrendingUp,
    path: "/equity-research",
    departmentId: "equity_research",
  },
  {
    id: "earnings_update",
    label: "Earnings Update",
    icon: ClipboardList,
    path: "/earnings-update",
    departmentId: "earnings_update",
  },
  {
    id: "morning_briefing",
    label: "Morning Briefing",
    icon: Sun,
    path: "/morning-briefing",
    departmentId: "morning_briefing",
  },
  {
    id: "retail_sentiment",
    label: "Retail Sentiment",
    icon: BarChart2,
    path: "/retail-sentiment",
    departmentId: "retail_sentiment",
  },
  {
    id: "macro_research",
    label: "Macro Research",
    icon: Globe,
    path: "/macro-research",
    departmentId: "macro_research",
  },
  {
    id: "panic_thermometer",
    label: "Panic Thermometer",
    icon: Thermometer,
    path: "/panic-thermometer",
    departmentId: "panic_thermometer",
  },
];
