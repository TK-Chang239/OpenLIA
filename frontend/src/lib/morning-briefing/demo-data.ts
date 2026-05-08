import type { RecentReport } from "../../api/morning-briefing";

export function isMbDemoMode(): boolean {
  if (typeof window === "undefined") return false;
  if (import.meta.env?.MODE === "test") return false;
  return true;
}

function isoOffset(daysAgo: number, hour: number, minute = 0): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

export type BriefingSlot = "pre_market" | "post_market";

export interface DemoBriefingMeta {
  slot: BriefingSlot;
  slotLabel: string;
  scheduleTime: string;
  summary: string;
}

export const DEMO_BRIEFING_META: Record<string, DemoBriefingMeta> = {
  "demo-mb-2026-05-08-pre": {
    slot: "pre_market",
    slotLabel: "Pre-Market",
    scheduleTime: "7:00 AM ET",
    summary:
      "Quiet tape into payrolls. NVDA Blackwell yields ahead of plan, UBER Q1 beats, PFE AdCom 13–2 against danuglipron.",
  },
  "demo-mb-2026-05-07-post": {
    slot: "post_market",
    slotLabel: "Post-Market",
    scheduleTime: "4:30 PM ET",
    summary:
      "Indices closed mixed; AMD beat with cautious DC commentary, SMCI guidance trimmed on margin pressure.",
  },
  "demo-mb-2026-05-07-pre": {
    slot: "pre_market",
    slotLabel: "Pre-Market",
    scheduleTime: "7:00 AM ET",
    summary:
      "Soft European data; 10Y auction strong. Two earnings calls into the open — UBER, BP.",
  },
  "demo-mb-2026-05-04-post": {
    slot: "post_market",
    slotLabel: "Post-Market",
    scheduleTime: "4:30 PM ET",
    summary:
      "Payrolls 158k vs 175k cons. Yields lower across the curve; SMH +1.8% led semis.",
  },
  "demo-mb-2026-05-04-pre": {
    slot: "pre_market",
    slotLabel: "Pre-Market",
    scheduleTime: "7:00 AM ET",
    summary:
      "Apple after-hours strong; cautious into payrolls. ISM mfg in focus.",
  },
  "demo-mb-2026-05-03-post": {
    slot: "post_market",
    slotLabel: "Post-Market",
    scheduleTime: "4:30 PM ET",
    summary:
      "FOMC held; Powell pushed back on June. Dot plot revised lower for '26.",
  },
  "demo-mb-2026-05-03-pre": {
    slot: "pre_market",
    slotLabel: "Pre-Market",
    scheduleTime: "7:00 AM ET",
    summary:
      "Pre-FOMC drift. ADP softer than consensus; refunding announcement balanced.",
  },
};

export function getDemoBriefings(): RecentReport[] {
  return [
    {
      id: "demo-mb-2026-05-08-pre",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(0, 7, 0),
    },
    {
      id: "demo-mb-2026-05-07-post",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(1, 16, 30),
    },
    {
      id: "demo-mb-2026-05-07-pre",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(1, 7, 0),
    },
    {
      id: "demo-mb-2026-05-04-post",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(4, 16, 30),
    },
    {
      id: "demo-mb-2026-05-04-pre",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(4, 7, 0),
    },
    {
      id: "demo-mb-2026-05-03-post",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(5, 16, 30),
    },
    {
      id: "demo-mb-2026-05-03-pre",
      title: "Morning Briefing",
      report_type: "morning_briefing",
      created_at: isoOffset(5, 7, 0),
    },
  ];
}

export interface DemoArchiveStats {
  totalReports: number;
  nextBriefing: string;
  activeSchedules: number;
}

export function getDemoArchiveStats(): DemoArchiveStats {
  return {
    totalReports: 42,
    nextBriefing: "7:00 AM ET · 4:30 PM ET",
    activeSchedules: 2,
  };
}
