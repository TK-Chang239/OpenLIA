import type { JSX } from "react";

export interface LiaAlertsCardProps {
  readonly hasHoldings: boolean;
}

export function LiaAlertsCard(_props: LiaAlertsCardProps): JSX.Element {
  return (
    <section
      aria-label="LIA alerts"
      className="rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[18px] py-[14px]"
      data-testid="lia-alerts-card"
    >
      <div className="mb-[10px] flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        <span className="text-[--color-text-primary]">LIA alerts</span>
      </div>
      <p className="py-2 text-center text-[12px] text-[--color-text-tertiary]">
        No alerts
      </p>
    </section>
  );
}
