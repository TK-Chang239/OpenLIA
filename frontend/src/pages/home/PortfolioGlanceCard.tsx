import { useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "react-i18next";

const TABS = ["NAV", "vs SPX", "Drawdown", "Exposure"] as const;
type Tab = (typeof TABS)[number];

const TAB_I18N: Record<Tab, string> = {
  NAV: "home.nav",
  "vs SPX": "home.vs_spx",
  Drawdown: "home.drawdown",
  Exposure: "home.exposure",
};

/** Synthetic chart paths — visual stub until backend exposes a portfolio
 *  timeseries endpoint. The "selected tab" only swaps the area path so the
 *  card feels alive without lying about real values. */
const PATHS: Record<Tab, { area: string; line: string; bench: string }> = {
  NAV: {
    area:
      "M0,90 L40,86 L80,82 L120,88 L160,72 L200,76 L240,64 L280,68 L320,52 L360,58 L400,44 L440,48 L480,38 L520,42 L560,30 L600,34 L640,24 L680,28 L720,16 L760,18 L800,10 L800,110 L0,110 Z",
    line:
      "M0,90 L40,86 L80,82 L120,88 L160,72 L200,76 L240,64 L280,68 L320,52 L360,58 L400,44 L440,48 L480,38 L520,42 L560,30 L600,34 L640,24 L680,28 L720,16 L760,18 L800,10",
    bench:
      "M0,92 L40,90 L80,88 L120,90 L160,82 L200,84 L240,78 L280,80 L320,72 L360,74 L400,66 L440,68 L480,62 L520,64 L560,56 L600,58 L640,50 L680,52 L720,42 L760,44 L800,36",
  },
  "vs SPX": {
    area:
      "M0,80 L80,78 L160,68 L240,70 L320,58 L400,62 L480,46 L560,50 L640,32 L720,28 L800,18 L800,110 L0,110 Z",
    line:
      "M0,80 L80,78 L160,68 L240,70 L320,58 L400,62 L480,46 L560,50 L640,32 L720,28 L800,18",
    bench:
      "M0,84 L80,84 L160,80 L240,82 L320,76 L400,74 L480,68 L560,68 L640,60 L720,58 L800,50",
  },
  Drawdown: {
    area:
      "M0,30 L80,38 L160,46 L240,42 L320,58 L400,54 L480,72 L560,68 L640,82 L720,76 L800,86 L800,110 L0,110 Z",
    line:
      "M0,30 L80,38 L160,46 L240,42 L320,58 L400,54 L480,72 L560,68 L640,82 L720,76 L800,86",
    bench:
      "M0,40 L80,46 L160,52 L240,50 L320,62 L400,60 L480,72 L560,70 L640,80 L720,78 L800,86",
  },
  Exposure: {
    area:
      "M0,60 L80,56 L160,64 L240,52 L320,58 L400,46 L480,50 L560,38 L640,44 L720,30 L800,36 L800,110 L0,110 Z",
    line:
      "M0,60 L80,56 L160,64 L240,52 L320,58 L400,46 L480,50 L560,38 L640,44 L720,30 L800,36",
    bench:
      "M0,68 L80,66 L160,72 L240,62 L320,66 L400,58 L480,60 L560,50 L640,54 L720,44 L800,48",
  },
};

export function PortfolioGlanceCard(): JSX.Element {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("NAV");
  const p = PATHS[tab];
  return (
    <section className="bg-bg-elevated border border-border-subtle rounded-xl px-5 pt-[18px] pb-[14px]">
      <div className="flex items-baseline gap-[14px] mb-[14px]">
        <div className="flex flex-col gap-1">
          <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-text-tertiary">
            {t("home.portfolio_card_title")}
          </span>
          <span className="font-display text-[28px] font-semibold tracking-[-0.015em] text-text-primary leading-none">
            $2,184,920
            <small className="text-base text-text-secondary font-medium">
              .18
            </small>
          </span>
        </div>
        <span className="ml-auto font-mono text-[11px] tracking-[0.04em] text-feedback-success">
          {t("home_cards.today_change")}
        </span>
      </div>

      <div className="flex gap-[14px] mb-2 items-center">
        {TABS.map((tabItem) => (
          <button
            key={tabItem}
            type="button"
            onClick={() => setTab(tabItem)}
            className={`font-mono text-[10px] tracking-[0.08em] cursor-pointer pb-1 border-b transition-colors duration-normal ease-out ${tab === tabItem ? "text-text-primary border-accent-primary" : "text-text-tertiary border-transparent hover:text-text-secondary"}`}
          >
            {t(TAB_I18N[tabItem])}
          </button>
        ))}
        <span className="ml-auto font-mono text-[10px] tracking-[0.08em] text-text-tertiary cursor-default">
          JAN 2 — TUE 08:14
        </span>
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
          <path d={p.area} fill="url(#homePfFill)" />
          <path
            d={p.line}
            fill="none"
            style={{ stroke: "var(--yellow-600)" }}
            strokeWidth="1.6"
          />
          <path
            d={p.bench}
            fill="none"
            style={{ stroke: "var(--neutral-400)" }}
            strokeWidth="1.2"
            strokeDasharray="3 3"
          />
        </svg>
      </div>

      <div className="flex items-center gap-[14px] mt-3 pt-3 border-t border-border-subtle font-mono text-[10px] tracking-[0.06em] text-text-tertiary uppercase">
        <span>{t("home_cards.positions_count", { n: 14 })}</span>
        <span>·</span>
        <span>{t("home_cards.ytd")}</span>
        <span>·</span>
        <span>{t("home_cards.sharpe")}</span>
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
