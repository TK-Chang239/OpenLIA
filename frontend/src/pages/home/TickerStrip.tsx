import { useEffect, useState } from "react";
import type { JSX } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [quotes, setQuotes] = useState<IndexQuote[] | null>(null);
  // null = unknown (loading/error); false = server has no EODHD key configured.
  const [available, setAvailable] = useState<boolean | null>(null);
  const [asOf, setAsOf] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const res = await fetchMarketIndices();
        if (!cancelled) {
          setQuotes(res.indices);
          setAvailable(res.available);
          setAsOf(res.as_of ?? null);
        }
      } catch {
        // Transient fetch error: hide the strip, but do not claim EODHD is
        // unconfigured (leave `available` untouched).
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

  // Distinct states (audit 1.A.6): live quotes -> strip; server reports no EODHD
  // key -> a connect hint (the route's documented purpose); empty/error -> hidden.
  if (quotes && quotes.length > 0) {
    return renderStrip(quotes, asOf, t);
  }
  if (available === false) {
    return (
      <div className="flex border border-border-subtle rounded-lg bg-bg-elevated overflow-hidden">
        <div className="flex-1 px-[14px] py-[10px] font-mono text-[10px] tracking-[0.08em] uppercase text-text-tertiary">
          {t("home_cards.ticker_connect_eodhd")}
        </div>
      </div>
    );
  }
  return null;
}

function formatAsOf(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function renderStrip(
  quotes: IndexQuote[],
  asOf: string | null,
  t: (key: string, opts?: Record<string, unknown>) => string,
): JSX.Element {
  return (
    <div className="flex flex-col border border-border-subtle rounded-lg bg-bg-elevated overflow-hidden">
      <div className="flex">
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
      {asOf ? (
        <div className="px-[14px] py-[3px] border-t border-border-subtle font-mono text-[8.5px] tracking-[0.1em] uppercase text-text-tertiary text-right">
          {t("home_cards.ticker_source_as_of", { time: formatAsOf(asOf) })}
        </div>
      ) : null}
    </div>
  );
}
