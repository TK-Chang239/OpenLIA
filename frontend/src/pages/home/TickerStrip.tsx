import type { JSX } from "react";

interface Cell {
  label: string;
  value: string;
  delta: string;
  positive: boolean;
}

const CELLS: Cell[] = [
  { label: "S&P FUT", value: "5,891.25", delta: "+0.34%", positive: true },
  { label: "NASDAQ", value: "20,142", delta: "+0.52%", positive: true },
  { label: "VIX", value: "14.2", delta: "−1.8%", positive: false },
  { label: "10Y", value: "4.28", delta: "−2bp", positive: false },
  { label: "DXY", value: "103.1", delta: "+0.11%", positive: true },
  { label: "BTC", value: "94,820", delta: "+1.42%", positive: true },
];

export function TickerStrip(): JSX.Element {
  return (
    <div className="flex border border-border-subtle rounded-lg bg-bg-elevated overflow-hidden">
      {CELLS.map((c, i) => (
        <div
          key={c.label}
          className={`flex-1 px-[14px] py-[10px] flex flex-col gap-[3px] ${i < CELLS.length - 1 ? "border-r border-border-subtle" : ""}`}
        >
          <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-text-tertiary">
            {c.label}
          </span>
          <span className="flex items-baseline gap-2">
            <span className="font-mono text-[14px] font-medium text-text-primary tabular-nums">
              {c.value}
            </span>
            <span
              className={`font-mono text-[10px] tabular-nums ${c.positive ? "text-feedback-success" : "text-feedback-error"}`}
            >
              {c.delta}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}
