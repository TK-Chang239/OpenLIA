import { useEffect, useState } from "react";
import type { JSX } from "react";
import {
  fetchMarketIndices,
  type IndexQuote,
} from "../../api/markets";

const POLL_MS = 60_000;

function formatValue(value: number): string {
  // Yields/index-ish small numbers get 2 decimals; large index levels get
  // thousands separators and no decimals; BTC gets grouped integers.
  const digits = value >= 1000 ? 0 : 2;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatDelta(q: IndexQuote): { text: string; positive: boolean } | null {
  if (q.change_pct == null) return null;
  const positive = q.change_pct >= 0;
  const sign = positive ? "+" : "−"; // real minus sign
  return {
    text: `${sign}${Math.abs(q.change_pct).toFixed(2)}%`,
    positive,
  };
}

export function TickerStrip(): JSX.Element | null {
  const [quotes, setQuotes] = useState<IndexQuote[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { indices } = await fetchMarketIndices();
        if (!cancelled) setQuotes(indices);
      } catch {
        if (!cancelled) setQuotes([]);
      }
    };
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  // Hide the strip until it has real quotes (no EODHD key, empty, or error).
  if (!quotes || quotes.length === 0) return null;

  return (
    <div className="flex border border-border-subtle rounded-lg bg-bg-elevated overflow-hidden">
      {quotes.map((q, i) => {
        const delta = formatDelta(q);
        return (
          <div
            key={q.symbol}
            className={`flex-1 px-[14px] py-[10px] flex flex-col gap-[3px] transition-colors duration-normal ease-out hover:bg-surface-hover ${i < quotes.length - 1 ? "border-r border-border-subtle" : ""}`}
          >
            <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-text-tertiary">
              {q.label}
            </span>
            <span className="flex items-baseline gap-2">
              <span className="font-mono text-[14px] font-medium text-text-primary tabular-nums">
                {formatValue(q.value)}
              </span>
              {delta ? (
                <span
                  className={`font-mono text-[10px] tabular-nums ${delta.positive ? "text-feedback-success" : "text-feedback-error"}`}
                >
                  {delta.text}
                </span>
              ) : null}
            </span>
          </div>
        );
      })}
    </div>
  );
}
