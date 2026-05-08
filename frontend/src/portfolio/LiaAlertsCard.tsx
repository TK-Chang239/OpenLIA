import type { JSX } from "react";
import { Link } from "react-router-dom";

export interface LiaAlertsCardProps {
  readonly hasHoldings: boolean;
}

interface PlaceholderAlert {
  tone: "warn" | "accent" | "info";
  meta: string;
  body: JSX.Element;
  ctaLabel: string;
  prompt: string;
}

const ALERTS: PlaceholderAlert[] = [
  {
    tone: "warn",
    meta: "PLTR · 07:42 UTC · RISK",
    body: (
      <>
        <strong>PLTR</strong> 14-day vol crossed the 35% threshold —
        position contributing 28% of book risk.
      </>
    ),
    ctaLabel: "Review hedging options",
    prompt: "Review hedging options for PLTR.",
  },
  {
    tone: "accent",
    meta: "NVDA · 06:18 UTC · CATALYST",
    body: (
      <>
        Q4 guide $37.5B beat consensus by <strong>+4.2pt</strong>. Sell-side
        raising PTs into open.
      </>
    ),
    ctaLabel: "Open earnings briefing",
    prompt: "Brief me on NVDA earnings.",
  },
  {
    tone: "info",
    meta: "PORTFOLIO · 05:30 UTC · DRIFT",
    body: (
      <>
        Tech tilt at <strong>62%</strong> vs target 48%. Drift threshold hit
        9 days ago.
      </>
    ),
    ctaLabel: "See rebalance plan",
    prompt: "Suggest a rebalance plan for my portfolio.",
  },
];

const DOT_CLASS: Record<PlaceholderAlert["tone"], string> = {
  warn: "bg-[--color-feedback-warning] shadow-[0_0_6px_rgba(249,115,22,0.5)]",
  accent: "bg-[--color-accent-primary] shadow-[0_0_6px_rgba(212,255,0,0.6)]",
  info: "bg-[--color-text-tertiary]",
};

export function LiaAlertsCard({ hasHoldings }: LiaAlertsCardProps): JSX.Element {
  return (
    <section
      aria-label="LIA alerts"
      className="rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[18px] py-[14px]"
      data-testid="lia-alerts-card"
    >
      <div className="mb-[10px] flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        <span className="text-[--color-text-primary]">LIA alerts</span>
        <span>{hasHoldings ? `${ALERTS.length} PLACEHOLDER` : ""}</span>
      </div>

      {hasHoldings ? (
        <div className="flex flex-col">
          {ALERTS.map((a, i) => (
            <div
              key={`${a.meta}-${i}`}
              className={`flex gap-[10px] py-[10px] ${i < ALERTS.length - 1 ? "border-b border-dashed border-[--color-border-subtle]" : ""}`}
              data-testid={`alert-row-${i}`}
            >
              <span
                aria-hidden="true"
                className={`mt-[7px] h-[6px] w-[6px] flex-shrink-0 rounded-full ${DOT_CLASS[a.tone]}`}
              />
              <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
                <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                  {a.meta}
                </span>
                <span className="text-[12.5px] leading-[1.45] text-[--color-text-primary]">
                  {a.body}
                </span>
                <Link
                  to={`/secretary?prompt=${encodeURIComponent(a.prompt)}`}
                  className="mt-[2px] font-mono text-[10px] tracking-[0.06em] text-[--color-feedback-success] no-underline hover:underline"
                >
                  → {a.ctaLabel}
                </Link>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="py-2 text-center text-[12px] text-[--color-text-tertiary]">
          No alerts
        </p>
      )}
    </section>
  );
}
