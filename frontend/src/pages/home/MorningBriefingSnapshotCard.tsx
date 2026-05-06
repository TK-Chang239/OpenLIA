import type { JSX } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, MessageSquare } from "lucide-react";

/** Compact snapshot of today's Morning Briefing rendered on the Home page.
 *  All numbers are placeholder per Q1=A; replace with the snapshot API once
 *  the morning-briefing department exposes a /today endpoint. See
 *  planning/dev-backlog/home.md for the full backlog list. */

interface MacroEvent {
  time: string;
  region: string;
  headline: string;
  detail: JSX.Element;
}

interface WatchEntry {
  ticker: string;
  importance: "high" | "med" | "low";
  preMarket: string;
  preMarketPos: boolean;
  blurb: string;
}

interface CalendarEntry {
  time: string;
  day: string;
  tag: string;
  event: string;
  estimate: JSX.Element;
}

const MACRO: MacroEvent[] = [
  {
    time: "06:42",
    region: "EU",
    headline: "German IFO misses; expectations component drags",
    detail: (
      <>
        86.3 vs <strong>87.1</strong> cons ·{" "}
        <strong className="text-feedback-error">−0.92σ</strong>
      </>
    ),
  },
  {
    time: "05:08",
    region: "US",
    headline: "10Y auction tails 0.2bp; indirect bid steady",
    detail: (
      <>
        stop <strong>4.293</strong> · BTC <strong>2.58</strong>
      </>
    ),
  },
  {
    time: "02:14",
    region: "JP",
    headline: "Tokyo CPI ex-fresh-food prints 2.2%, in line",
    detail: (
      <>
        core <strong>2.2%</strong> · svcs <strong>1.8%</strong>
      </>
    ),
  },
];

const WATCH: WatchEntry[] = [
  {
    ticker: "NVDA",
    importance: "high",
    preMarket: "+2.4% PM",
    preMarketPos: true,
    blurb: "Hyperscaler capex chatter lifts AI names; Q3 print Wed AMC.",
  },
  {
    ticker: "AAPL",
    importance: "med",
    preMarket: "+1.1% PM",
    preMarketPos: true,
    blurb:
      "Services beat from Q2 still bid; PT chatter from two sell-side desks.",
  },
  {
    ticker: "SBUX",
    importance: "high",
    preMarket: "−3.2% PM",
    preMarketPos: false,
    blurb: "China comp −8% guide cut still weighing; downgrade from MS overnight.",
  },
];

const CAL: CalendarEntry[] = [
  {
    time: "08:30",
    day: "Today",
    tag: "US · DATA",
    event: "JOLTS job openings",
    estimate: (
      <>
        cons <strong>8.10M</strong> · prior 8.49M
      </>
    ),
  },
  {
    time: "16:00",
    day: "Today",
    tag: "EARN",
    event: "AMZN · Q1 FY26 AMC",
    estimate: (
      <>
        EPS <strong>$1.41</strong> · Rev <strong>$155.0B</strong>
      </>
    ),
  },
  {
    time: "08:30",
    day: "Fri",
    tag: "US · DATA",
    event: "Non-farm payrolls",
    estimate: (
      <>
        cons <strong>165k</strong> · UR <strong>3.9%</strong>
      </>
    ),
  },
];

const IMPORTANCE_CLASS: Record<WatchEntry["importance"], string> = {
  high: "bg-[rgba(224,92,48,0.14)] text-feedback-error",
  med: "bg-[rgba(220,150,20,0.16)] text-feedback-warning",
  low: "bg-[rgba(107,130,0,0.14)] text-feedback-success",
};

export function MorningBriefingSnapshotCard(): JSX.Element {
  return (
    <article
      aria-label="Morning briefing snapshot"
      className="rounded-xl border border-border-subtle bg-bg-elevated overflow-hidden"
    >
      <header className="flex items-center gap-[10px] px-[18px] py-[14px] border-b border-border-subtle">
        <span
          aria-hidden="true"
          className="inline-flex items-center justify-center w-[22px] h-[22px] rounded-[5px] bg-accent-primary text-[--color-accent-on] font-mono text-[9px] font-bold shadow-[0_0_8px_rgba(212,255,0,0.35)]"
        >
          LIA
        </span>
        <span className="text-[13.5px] font-semibold text-text-primary tracking-[-0.005em]">
          Morning Briefing · Edition No. 218
        </span>
        <span className="ml-auto flex items-center gap-2 font-mono text-[9.5px] tracking-[0.1em] uppercase text-text-tertiary">
          <span>TUE 02 MAY</span>
          <span className="w-[3px] h-[3px] rounded-full bg-text-tertiary" />
          <span className="text-feedback-success">
            Pre-open · 2h 14m to bell
          </span>
        </span>
        <Link
          to="/morning-briefing"
          className="ml-3 inline-flex items-center gap-[6px] px-[10px] py-1 rounded-md border border-border-subtle bg-bg-base font-mono text-[10px] tracking-[0.06em] text-text-primary no-underline transition-colors duration-normal ease-out hover:border-border-strong hover:bg-surface-hover"
        >
          Open briefing
          <ArrowRight size={11} strokeWidth={2} />
        </Link>
      </header>

      <div className="grid grid-cols-[28px_1fr] gap-3 px-[18px] py-[14px] pb-[14px] border-b border-border-subtle">
        <span
          aria-hidden="true"
          className="self-start mt-[2px] inline-flex items-center justify-center w-[22px] h-[22px] rounded-[5px] bg-accent-primary text-[--color-accent-on] font-mono text-[9px] font-bold"
        >
          LIA
        </span>
        <div className="flex flex-col gap-[6px] min-w-0">
          <div className="flex items-center gap-2 font-mono text-[9.5px] tracking-[0.12em] uppercase text-text-tertiary">
            <span>Today's read</span>
            <span className="w-[3px] h-[3px] rounded-full bg-text-tertiary" />
            <span>Confidence 78 / 100</span>
            <span className="w-[3px] h-[3px] rounded-full bg-text-tertiary" />
            <span>12 sources</span>
          </div>
          <p className="m-0 text-[16px] leading-[1.4] font-medium text-text-primary tracking-[-0.005em]">
            Payrolls Friday is the only chart that matters this week — and the
            market is{" "}
            <em className="not-italic text-feedback-success">
              positioned for a soft print
            </em>
            .
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3">
        <Column heading="Overnight macro" count="3 of 12">
          <div className="flex flex-col gap-2">
            {MACRO.map((m) => (
              <div
                key={`${m.time}-${m.region}`}
                className="grid grid-cols-[38px_1fr] gap-[10px] items-start"
              >
                <div className="font-mono text-[9.5px] text-text-tertiary leading-[1.3] tracking-[0.04em] pt-[1px]">
                  {m.time}
                  <span className="block text-feedback-success mt-[1px] text-[8.5px] tracking-[0.1em]">
                    {m.region}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="m-0 mb-[2px] text-[12.5px] leading-[1.4] font-medium text-text-primary">
                    {m.headline}
                  </p>
                  <p className="m-0 font-mono text-[10px] text-text-tertiary tabular-nums tracking-[0.02em]">
                    {m.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Column>

        <Column heading="Your watchlist" count="3 matter" border>
          <div className="flex flex-col gap-2">
            {WATCH.map((w, i) => (
              <div
                key={w.ticker}
                className={`flex flex-col gap-[3px] ${i < WATCH.length - 1 ? "pb-2 border-b border-dashed border-border-subtle" : ""}`}
              >
                <div className="flex items-center gap-[6px]">
                  <span className="font-mono text-[10.5px] font-semibold text-text-primary px-[5px] py-[1px] rounded-[3px] bg-[--color-bg-code] tracking-[0.02em]">
                    {w.ticker}
                  </span>
                  <span
                    className={`font-mono text-[8.5px] tracking-[0.1em] uppercase px-[5px] py-[1px] rounded-[3px] ${IMPORTANCE_CLASS[w.importance]}`}
                  >
                    {w.importance === "high"
                      ? "High"
                      : w.importance === "med"
                        ? "Med"
                        : "Low"}
                  </span>
                  <span
                    className={`ml-auto font-mono text-[10px] tabular-nums ${w.preMarketPos ? "text-feedback-success" : "text-feedback-error"}`}
                  >
                    {w.preMarket}
                  </span>
                </div>
                <p className="m-0 text-[12.5px] leading-[1.4] text-text-primary">
                  {w.blurb}
                </p>
              </div>
            ))}
          </div>
        </Column>

        <Column heading="Today & ahead" count="Next 72h">
          <div className="flex flex-col gap-2">
            {CAL.map((c, i) => (
              <div
                key={`${c.time}-${c.day}-${c.event}`}
                className={`grid grid-cols-[50px_1fr] gap-[10px] items-start ${i < CAL.length - 1 ? "pb-2 border-b border-dashed border-border-subtle" : ""}`}
              >
                <div className="font-mono text-[10px] text-text-primary tabular-nums pt-[1px]">
                  {c.time}
                  <span className="block text-text-tertiary text-[8.5px] tracking-[0.1em] mt-[1px] uppercase">
                    {c.day}
                  </span>
                </div>
                <div className="min-w-0">
                  <p className="m-0 mb-[2px] text-[12.5px] leading-[1.4] text-text-primary">
                    <span className="inline-block font-mono text-[8.5px] tracking-[0.1em] uppercase text-text-tertiary mr-[6px]">
                      {c.tag}
                    </span>
                    {c.event}
                  </p>
                  <p className="m-0 font-mono text-[9.5px] text-text-tertiary tabular-nums tracking-[0.02em]">
                    {c.estimate}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Column>
      </div>

      <div className="flex items-center gap-[14px] px-[18px] py-[10px] border-t border-border-subtle bg-bg-base font-mono text-[10px] tracking-[0.06em] text-text-tertiary uppercase">
        <span className="inline-flex items-center gap-[6px] before:content-[''] before:w-[4px] before:h-[4px] before:bg-accent-primary before:rounded-full">
          5 watchlist names {">"}2% PM
        </span>
        <span>·</span>
        <span>3 earnings on book</span>
        <span>·</span>
        <span>Updated 07:16 ET</span>
        <Link
          to={`/secretary?prompt=${encodeURIComponent("Brief me on today.")}`}
          className="ml-auto inline-flex items-center gap-[6px] px-[10px] py-[3px] rounded-md border border-border-subtle text-text-primary no-underline transition-colors duration-normal ease-out hover:bg-surface-hover hover:border-border-strong"
        >
          Ask LIA to brief me
          <MessageSquare size={11} strokeWidth={2} />
        </Link>
      </div>
    </article>
  );
}

function Column({
  heading,
  count,
  border,
  children,
}: {
  heading: string;
  count: string;
  border?: boolean;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div
      className={`flex flex-col gap-[10px] px-[18px] py-[14px] min-w-0 ${border ? "md:border-l md:border-r border-border-subtle" : ""}`}
    >
      <div className="flex items-center justify-between font-mono text-[9px] tracking-[0.14em] uppercase text-text-tertiary">
        <span className="text-text-primary">{heading}</span>
        <span>{count}</span>
      </div>
      {children}
    </div>
  );
}
