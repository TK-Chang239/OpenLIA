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
  Briefcase,
  Brain,
  type LucideIcon,
} from "lucide-react";

export interface NavEntry {
  id: string;
  /** Fallback English label. UI should translate via the matching `nav.<id>` key. */
  label: string;
  /** i18n key (`nav.home`, `nav.equity_research`, etc.). */
  labelKey: string;
  icon: LucideIcon;
  path: string;
  /** Department id used to correlate with /notifications/unread.by_department. null for core pages. */
  departmentId: string | null;
}

export const CORE_NAV: readonly NavEntry[] = [
  {
    id: "home",
    label: "Home",
    labelKey: "nav.home",
    icon: Home,
    path: "/",
    departmentId: null,
  },
  {
    id: "secretary",
    label: "Secretary",
    labelKey: "nav.secretary",
    icon: MessageSquare,
    path: "/secretary",
    departmentId: "secretary",
  },
  {
    id: "portfolio",
    label: "Portfolio",
    labelKey: "nav.portfolio",
    icon: Briefcase,
    path: "/portfolio",
    departmentId: null,
  },
  {
    id: "repository",
    label: "Repository",
    labelKey: "nav.repository",
    icon: FolderOpen,
    path: "/repository",
    departmentId: null,
  },
  {
    id: "memory",
    label: "Memory",
    labelKey: "nav.memory",
    icon: Brain,
    path: "/memory",
    departmentId: null,
  },
];

export const DEPARTMENT_NAV: readonly NavEntry[] = [
  {
    id: "equity_research",
    label: "Equity Research",
    labelKey: "nav.equity_research",
    icon: TrendingUp,
    // v3 is the active engine. The /equity-research route (v1/v2.3
    // monolith) is still reachable by direct link until those
    // engines get removed; the sidebar always sends users to v3.
    path: "/equity-research-v3",
    departmentId: "equity_research",
  },
  {
    id: "earnings_update",
    label: "Earnings Update",
    labelKey: "nav.earnings_update",
    icon: ClipboardList,
    path: "/earnings-update",
    departmentId: "earnings_update",
  },
  {
    id: "morning_briefing",
    label: "Morning Briefing",
    labelKey: "nav.morning_briefing",
    icon: Sun,
    path: "/morning-briefing",
    departmentId: "morning_briefing",
  },
  {
    id: "retail_sentiment",
    label: "Retail Sentiment",
    labelKey: "nav.retail_sentiment",
    icon: BarChart2,
    path: "/retail-sentiment",
    departmentId: "retail_sentiment",
  },
  {
    id: "macro_research",
    label: "Macro Research",
    labelKey: "nav.macro_research",
    icon: Globe,
    path: "/macro-research",
    departmentId: "macro_research",
  },
  {
    id: "panic_thermometer",
    label: "Panic Thermometer",
    labelKey: "nav.panic_thermometer",
    icon: Thermometer,
    path: "/panic-thermometer",
    departmentId: "panic_thermometer",
  },
];
