import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  fetchAnalytics,
  fetchValueSeries,
  type AnalyticsResponse,
  type ValueSeriesResponse,
} from "../../api/portfolio";

// Tabs are real time windows; every one renders live value-series data (no
// synthetic paths, no benchmark overlay the backend can't source).
const TABS = [
  { id: "1D", tf: "1d" },
  { id: "1M", tf: "1m" },
  { id: "3M", tf: "3m" },
  { id: "1Y", tf: "1y" },
  { id: "ALL", tf: "all" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const VIEW_W = 800;
const VIEW_H = 110;
const PAD_Y = 10;

/** Map a numeric series onto the SVG viewBox, returning area + line paths. */
function buildPaths(values: number[]): { area: string; line: string } | null {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const n = values.length;
  const x = (i: number) => (i / (n - 1)) * VIEW_W;
  const y = (v: number) => PAD_Y + (1 - (v - min) / span) * (VIEW_H - 2 * PAD_Y);
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  return {
    line: `M${pts.join(" L")}`,
    area: `M0,${VIEW_H} L${pts.join(" L")} L${VIEW_W},${VIEW_H} Z`,
  };
}

function money(value: number, currency: string, fractionDigits: number): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    }).format(value);
  } catch {
    return `$${value.toLocaleString(undefined, {
      minimumFractionDigits: fractionDigits,
      maximumFractionDigits: fractionDigits,
    })}`;
  }
}

function shortDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Sum of per-position day P/L, or null when no position carries a day change. */
function todayChange(a: AnalyticsResponse): number | null {
  let sum = 0;
  let any = false;
  for (const p of a.positions) {
    if (p.day_change_abs != null) {
      const n = parseFloat(p.day_change_abs);
      if (!Number.isNaN(n)) {
        sum += n;
        any = true;
      }
    }
  }
  return any ? sum : null;
}

export function PortfolioGlanceCard(): JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabId>("3M");
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [series, setSeries] = useState<ValueSeriesResponse | null>(null);
  const seriesCache = useRef<Map<string, ValueSeriesResponse>>(new Map());

  useEffect(() => {
    let cancelled = false;
    fetchAnalytics()
      .then((a) => !cancelled && setAnalytics(a))
      .catch(() => !cancelled && setAnalytics(null));
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tf = TABS.find((x) => x.id === tab)!.tf;
    const cached = seriesCache.current.get(tf);
    if (cached) {
      setSeries(cached);
      return;
    }
    setSeries(null);
    fetchValueSeries(tf)
      .then((r) => {
        if (cancelled) return;
        seriesCache.current.set(tf, r);
        setSeries(r);
      })
      .catch(() => !cancelled && setSeries(null));
    return () => {
      cancelled = true;
    };
  }, [tab]);

  const currency = analytics?.display_currency || "USD";
  // total_market_value is null for a mixed-currency portfolio; guard the parse.
  const totalValue =
    analytics && analytics.total_market_value != null
      ? parseFloat(analytics.total_market_value)
      : null;
  const positionCount = analytics?.positions.length ?? 0;
  const isEmpty = analytics != null && positionCount === 0;

  const values = series?.points.map((p) => parseFloat(p.value)) ?? [];
  const paths = buildPaths(values);

  const dayAbs =
    analytics && !analytics.fx_unavailable ? todayChange(analytics) : null;
  const dayPct =
    dayAbs != null && totalValue != null && totalValue - dayAbs !== 0
      ? (dayAbs / (totalValue - dayAbs)) * 100
      : null;

  const periodPct = series?.period_return_pct
    ? parseFloat(series.period_return_pct)
    : null;

  return (
    <section className="bg-bg-elevated border border-border-subtle rounded-xl px-5 pt-[18px] pb-[14px]">
      <div className="flex items-baseline gap-[14px] mb-[14px]">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-text-tertiary">
            {t("home.portfolio_card_title")}
          </span>
          <span className="font-display text-[28px] font-semibold tracking-[-0.015em] text-text-primary leading-none">
            {totalValue == null ? (
              <span className="text-text-tertiary">—</span>
            ) : isEmpty ? (
              <span className="text-[18px] text-text-secondary">
                {t("home_cards.portfolio_empty")}
              </span>
            ) : (
              <>
                {money(Math.trunc(totalValue), currency, 0)}
                <small className="text-base text-text-secondary font-medium">
                  {Math.abs(totalValue - Math.trunc(totalValue))
                    .toFixed(2)
                    .slice(1)}
                </small>
              </>
            )}
          </span>
        </div>
        {dayAbs != null && dayPct != null ? (
          <span
            className={`ml-auto font-mono text-[11px] tracking-[0.04em] ${dayAbs >= 0 ? "text-feedback-success" : "text-feedback-error"}`}
          >
            {t("home_cards.portfolio_today", {
              change: `${dayAbs >= 0 ? "+" : ""}${money(dayAbs, currency, 0)} (${dayPct >= 0 ? "+" : ""}${dayPct.toFixed(2)}%)`,
            })}
          </span>
        ) : null}
      </div>

      <div className="flex gap-[14px] mb-2 items-center">
        {TABS.map((tabItem) => (
          <button
            key={tabItem.id}
            type="button"
            onClick={() => setTab(tabItem.id)}
            className={`font-mono text-[10px] tracking-[0.08em] cursor-pointer pb-1 border-b transition-colors duration-normal ease-out ${tab === tabItem.id ? "text-text-primary border-accent-primary" : "text-text-tertiary border-transparent hover:text-text-secondary"}`}
          >
            {tabItem.id}
          </button>
        ))}
        {series?.actual_span ? (
          <span className="ml-auto font-mono text-[10px] tracking-[0.08em] text-text-tertiary cursor-default">
            {shortDate(series.actual_span.start)} — {shortDate(series.actual_span.end)}
          </span>
        ) : null}
      </div>

      <div className="h-[110px]">
        <svg viewBox="0 0 800 110" preserveAspectRatio="none" className="w-full h-full block">
          <defs>
            <linearGradient id="homePfFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0.32 }} />
              <stop offset="100%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0 }} />
            </linearGradient>
          </defs>
          <g style={{ stroke: "var(--color-border-subtle)" }} strokeWidth="1" strokeDasharray="2 4">
            <line x1="0" y1="22" x2="800" y2="22" />
            <line x1="0" y1="55" x2="800" y2="55" />
            <line x1="0" y1="88" x2="800" y2="88" />
          </g>
          {paths ? (
            <>
              <path d={paths.area} fill="url(#homePfFill)" />
              <path
                d={paths.line}
                fill="none"
                style={{ stroke: "var(--yellow-600)" }}
                strokeWidth="1.6"
              />
            </>
          ) : null}
        </svg>
      </div>

      <div className="flex items-center gap-[14px] mt-3 pt-3 border-t border-border-subtle font-mono text-[10px] tracking-[0.06em] text-text-tertiary uppercase">
        <span>{t("home_cards.positions_count", { n: positionCount })}</span>
        {periodPct != null ? (
          <>
            <span>·</span>
            <span className={periodPct >= 0 ? "text-feedback-success" : "text-feedback-error"}>
              {t("home_cards.portfolio_return", {
                tf: tab,
                pct: `${periodPct >= 0 ? "+" : ""}${periodPct.toFixed(1)}%`,
              })}
            </span>
          </>
        ) : null}
        <Link
          to="/portfolio"
          className="ml-auto inline-flex items-center gap-[6px] px-[10px] py-1 rounded-md border border-border-subtle text-text-primary no-underline transition-colors duration-normal ease-out hover:bg-bg-base hover:border-border-strong"
        >
          {t("home_cards.open_portfolio")}
          <ArrowRight size={11} strokeWidth={2} />
        </Link>
      </div>
    </section>
  );
}
