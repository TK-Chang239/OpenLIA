import type {
  RecentReport,
  WatchlistEntry,
} from "../../api/earnings-update";

export function isDemoMode(): boolean {
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

function isoFuture(daysAhead: number, hour: number, minute = 0): string {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  d.setHours(hour, minute, 0, 0);
  return d.toISOString();
}

export function getDemoReports(): RecentReport[] {
  return [
    {
      id: "demo-aapl-q2",
      title: "Apple Inc. — Beat on Services, in-line on iPhone",
      subject: "AAPL",
      report_type: "earnings_update",
      created_at: isoOffset(0, 16, 30),
    },
    {
      id: "demo-meta-q1",
      title: "Q1 FY26 — Reality Labs narrows loss; Reels CPMs +18%",
      subject: "META",
      report_type: "earnings_update",
      created_at: isoOffset(0, 14, 32),
    },
    {
      id: "demo-sbux-q2",
      title: "Q2 FY26 — China comp -8%, full-year guide cut",
      subject: "SBUX",
      report_type: "earnings_update",
      created_at: isoOffset(0, 10, 8),
    },
    {
      id: "demo-qcom-fq2",
      title: "FQ2 — Auto +35%, IoT inflection; handset in-line",
      subject: "QCOM",
      report_type: "earnings_update",
      created_at: isoOffset(0, 7, 45),
    },
    {
      id: "demo-msft-fq3",
      title: "FQ3 — Azure +33% cc, AI capacity still constrained",
      subject: "MSFT",
      report_type: "earnings_update",
      created_at: isoOffset(2, 16, 5),
    },
    {
      id: "demo-googl-q1",
      title: "Q1 — Search resilient, Cloud op margin steps to 14%",
      subject: "GOOGL",
      report_type: "earnings_update",
      created_at: isoOffset(3, 16, 1),
    },
    {
      id: "demo-tsla-q1",
      title: "Q1 — Auto GM ex-credits 12.4%, robotaxi commentary in focus",
      subject: "TSLA",
      report_type: "earnings_update",
      created_at: isoOffset(4, 17, 5),
    },
  ];
}

export function getDemoWatchlist(): WatchlistEntry[] {
  return [
    {
      id: "demo-w-aapl",
      ticker: "AAPL",
      company_name: "Apple Inc.",
      next_earnings_date: null,
      release_timing: "post_market",
    },
    {
      id: "demo-w-msft",
      ticker: "MSFT",
      company_name: "Microsoft Corporation",
      next_earnings_date: null,
      release_timing: "post_market",
    },
    {
      id: "demo-w-nvda",
      ticker: "NVDA",
      company_name: "NVIDIA Corporation",
      next_earnings_date: "2026-05-21",
      release_timing: "post_market",
    },
    {
      id: "demo-w-googl",
      ticker: "GOOGL",
      company_name: "Alphabet Inc.",
      next_earnings_date: null,
      release_timing: "post_market",
    },
    {
      id: "demo-w-tsla",
      ticker: "TSLA",
      company_name: "Tesla, Inc.",
      next_earnings_date: null,
      release_timing: "post_market",
    },
    {
      id: "demo-w-amzn",
      ticker: "AMZN",
      company_name: "Amazon.com, Inc.",
      next_earnings_date: "2026-05-08",
      release_timing: "post_market",
    },
    {
      id: "demo-w-xom",
      ticker: "XOM",
      company_name: "Exxon Mobil Corporation",
      next_earnings_date: "2026-05-08",
      release_timing: "pre_market",
    },
  ];
}

export type Verdict = "beat" | "miss" | "mixed";

export interface DemoReportMeta {
  summary: string;
  verdict: Verdict;
  verdictLabel: string;
  revSurprise: string;
  epsSurprise: string;
  revPositive: boolean;
  epsPositive: boolean;
  afterHours?: string;
  afterHoursPositive?: boolean;
  liaSignal?: string;
}

export const DEMO_REPORT_META: Record<string, DemoReportMeta> = {
  "demo-aapl-q2": {
    summary:
      "Top-line +5.4% y/y at $94.2B, EPS $1.78 beats by $0.06. Services $26.8B reaccelerated to +15.2%. Q3 guide constructive — implies the Street stays put. Maintain Buy, $245 PT unchanged.",
    verdict: "beat",
    verdictLabel: "Beat · maintain",
    revSurprise: "+0.7%",
    epsSurprise: "+3.5%",
    revPositive: true,
    epsPositive: true,
    afterHours: "+1.65%",
    afterHoursPositive: true,
    liaSignal: "82 / 100",
  },
  "demo-meta-q1": {
    summary:
      "Family DAP 3.31B, ad impressions +9%. Capex guide raised to $48–52B for AI buildout. Stock +2.1% AH.",
    verdict: "beat",
    verdictLabel: "Beat · raise PT",
    revSurprise: "+1.4%",
    epsSurprise: "+5.2%",
    revPositive: true,
    epsPositive: true,
  },
  "demo-sbux-q2": {
    summary:
      "Global comp +1% below the +3% Street. Niccol commentary on \"back-to-Starbucks\" plan well-received but operationally still negative.",
    verdict: "miss",
    verdictLabel: "Miss · cut PT",
    revSurprise: "-2.8%",
    epsSurprise: "-6.4%",
    revPositive: false,
    epsPositive: false,
  },
  "demo-qcom-fq2": {
    summary:
      "Handset QCT $6.3B, Auto $960M beat. Q3 guide bracketed consensus midpoint. Mix story intact.",
    verdict: "mixed",
    verdictLabel: "Mixed · hold",
    revSurprise: "+0.4%",
    epsSurprise: "+1.8%",
    revPositive: true,
    epsPositive: true,
  },
  "demo-msft-fq3": {
    summary:
      "Commercial bookings +24%. Q4 guide implies ~$8B capex sequential step-up. Demand running ahead of supply.",
    verdict: "beat",
    verdictLabel: "Beat · raise PT",
    revSurprise: "+1.9%",
    epsSurprise: "+4.7%",
    revPositive: true,
    epsPositive: true,
  },
  "demo-googl-q1": {
    summary:
      "Search +11%, YouTube ads +15%. Capex of $24B in Q1; full-year unchanged at $96B.",
    verdict: "beat",
    verdictLabel: "Beat · maintain",
    revSurprise: "+1.1%",
    epsSurprise: "+3.0%",
    revPositive: true,
    epsPositive: true,
  },
  "demo-tsla-q1": {
    summary:
      "Deliveries 386k in-line. Energy storage record. Musk reiterated June Austin event timeline; FSD v13 attach inflecting.",
    verdict: "mixed",
    verdictLabel: "Mixed · hold",
    revSurprise: "-1.8%",
    epsSurprise: "-3.4%",
    revPositive: false,
    epsPositive: false,
  },
};

export interface DemoUpNext {
  id: string;
  timing: string;
  ticker: string;
  whenET: string;
  description: string;
  estEps: string;
  estRev: string;
}

export function getDemoUpNext(): DemoUpNext[] {
  void isoFuture;
  return [
    {
      id: "up-xom",
      timing: "Tomorrow · Pre-market",
      ticker: "XOM",
      whenET: "07:30 ET",
      description: "Q1 FY26 — Permian volumes vs guide, downstream margin reset.",
      estEps: "$1.92",
      estRev: "$87.4B",
    },
    {
      id: "up-amzn",
      timing: "Tomorrow · After-close",
      ticker: "AMZN",
      whenET: "16:00 ET",
      description: "Q1 FY26 — AWS reacceleration print, retail margin trajectory.",
      estEps: "$1.41",
      estRev: "$155.0B",
    },
    {
      id: "up-cvx",
      timing: "Tomorrow · After-close",
      ticker: "CVX",
      whenET: "16:30 ET",
      description: "Q1 FY26 — Hess close commentary, capex pacing for FY26.",
      estEps: "$2.36",
      estRev: "$48.1B",
    },
  ];
}

export interface DemoHeroStats {
  reportsThisWeek: number;
  beats: number;
  misses: number;
  avgSurprise: string;
  avgLatency: string;
}

export function getDemoHeroStats(): DemoHeroStats {
  return {
    reportsThisWeek: 7,
    beats: 4,
    misses: 1,
    avgSurprise: "+1.4%",
    avgLatency: "3m 42s",
  };
}
