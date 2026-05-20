import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { HeroCopy, SummaryStats } from "../../../lib/panic_thermometer/copy/types";

interface Props {
  hero: HeroCopy;
  stats: SummaryStats;
  mode: "count" | "weighted";
  onModeChange: (mode: "count" | "weighted") => void;
}

export function Hero({ hero, stats, mode, onModeChange }: Props): JSX.Element {
  const { t } = useTranslation();
  const tubeY1 = 10;
  const tubeY2 = 190;
  const tubeHeight = tubeY2 - tubeY1;
  const fillTopY = tubeY2 - (tubeHeight * hero.thermBulbFillPct) / 100;

  return (
    <section className="pt-hero" aria-labelledby="pt-hero-headline">
      <div className="pt-hero-lhs">
        <span className="pt-eyebrow">{hero.eyebrowTime}</span>
        <h1 id="pt-hero-headline">
          {hero.headline} <span className="pt-accent">{hero.accent}</span>
        </h1>
        <p className="pt-lede">
          {hero.ledeFragments.map((f, i) => {
            if (f.kind === "text") return <span key={i}>{f.value}</span>;
            if (f.kind === "strong") return <strong key={i}>{f.value}</strong>;
            if (f.kind === "hot") return <span key={i} className="pt-hot">{f.value}</span>;
            return <span key={i} className="pt-warm">{f.value}</span>;
          })}
        </p>
        <div className="pt-stats">
          <div className="pt-stat">
            <span className="pt-k">{t("panic_thermometer.hero.composite")}</span>
            <span className="pt-v is-bad">{stats.composite.toUpperCase()}</span>
          </div>
          <div className="pt-stat">
            <span className="pt-k">{t("panic_thermometer.hero.score")}</span>
            <span className="pt-v is-bad">
              {stats.scoreOutOf5.toFixed(1)} / 5.0
            </span>
          </div>
          <div className="pt-stat">
            <span className="pt-k">{t("panic_thermometer.hero.delta_7day")}</span>
            <span className="pt-v is-warn">
              {stats.delta7day > 0 ? `+${stats.delta7day}` : stats.delta7day}{" "}
              {t("panic_thermometer.hero.panels", {
                count: Math.abs(stats.delta7day),
              })}
            </span>
          </div>
          <div className="pt-stat">
            <span className="pt-k">{t("panic_thermometer.hero.last_refresh")}</span>
            <span className="pt-v">{stats.lastRefreshLabel}</span>
          </div>
        </div>
      </div>

      <div className="pt-therm-card">
        <div className="pt-therm-col">
          <div
            className="pt-therm-bulb"
            aria-label={t("panic_thermometer.hero.composite_aria", { level: stats.composite })}
          >
            <svg viewBox="0 0 56 240" preserveAspectRatio="xMidYMid meet">
              <rect
                x={20}
                y={tubeY1}
                width={16}
                height={tubeHeight}
                rx={8}
                fill="var(--color-bg-code)"
                stroke="var(--color-border-strong)"
                strokeWidth={0.8}
              />
              <defs>
                <clipPath id="pt-tube-clip">
                  <rect x={20} y={tubeY1} width={16} height={tubeHeight} rx={8} />
                </clipPath>
                <linearGradient id="pt-merc" x1="0" y1="1" x2="0" y2="0">
                  <stop offset="0%" stopColor="var(--pt-darkred)" />
                  <stop offset="20%" stopColor="var(--color-feedback-error)" />
                  <stop offset="55%" stopColor="var(--color-feedback-warning)" />
                  <stop offset="80%" stopColor="var(--yellow-600)" />
                  <stop offset="100%" stopColor="var(--color-feedback-success)" />
                </linearGradient>
              </defs>
              <g clipPath="url(#pt-tube-clip)">
                <rect
                  className="pt-mercury-rect"
                  x={20}
                  y={fillTopY}
                  width={16}
                  height={tubeY2 - fillTopY}
                  fill="url(#pt-merc)"
                />
              </g>
              <circle
                cx={28}
                cy={208}
                r={18}
                fill="var(--pt-darkred)"
                stroke="var(--color-bg-base)"
                strokeWidth={0.8}
              />
              <circle cx={22} cy={202} r={4} fill="var(--color-feedback-error)" opacity={0.6} />
              <g stroke="var(--color-text-tertiary)" strokeWidth={0.6} opacity={0.7}>
                <line x1={36} y1={22} x2={44} y2={22} />
                <line x1={36} y1={58} x2={44} y2={58} />
                <line x1={36} y1={94} x2={44} y2={94} />
                <line x1={36} y1={130} x2={44} y2={130} />
                <line x1={36} y1={166} x2={44} y2={166} />
              </g>
              <line
                x1={14}
                y1={fillTopY}
                x2={42}
                y2={fillTopY}
                stroke="var(--color-text-primary)"
                strokeWidth={1.4}
              />
              <polygon
                points={`10,${fillTopY} 14,${fillTopY - 4} 14,${fillTopY + 4}`}
                fill="var(--color-text-primary)"
              />
            </svg>
          </div>
          <span className="pt-therm-date">04 May</span>
        </div>

        <div className="pt-therm-side">
          <div className="pt-therm-row1">
            <span className="pt-therm-label">
              {t("panic_thermometer.hero.composite_reading")}
            </span>
            <div className="pt-mode" role="group" aria-label={t("panic_thermometer.hero.composite_mode_aria")}>
              <button
                type="button"
                className={mode === "count" ? "is-on" : ""}
                onClick={() => onModeChange("count")}
              >
                {t("panic_thermometer.hero.mode_count")}
              </button>
              <button
                type="button"
                className={mode === "weighted" ? "is-on" : ""}
                onClick={() => onModeChange("weighted")}
              >
                {t("panic_thermometer.hero.mode_weighted")}
              </button>
            </div>
          </div>

          <div className="pt-therm-level">
            <span className="pt-nm">
              {stats.composite.charAt(0).toUpperCase() + stats.composite.slice(1)}
            </span>
            <span className="pt-sub">
              <strong>
                {t("panic_thermometer.hero.red_of_total_strong", {
                  red: stats.redCount,
                  total: stats.totalPanels,
                })}
              </strong>{" "}
              {t("panic_thermometer.hero.red_score", {
                score: stats.scoreOutOf5.toFixed(1),
                trend: stats.trend,
              })}
            </span>
          </div>

          <div className="pt-scale-list">
            {hero.scale.map((row) => (
              <div
                key={row.severity}
                className={`pt-scale-row ${row.isCurrent ? "is-current" : ""}`}
              >
                <span className={`pt-sw is-${row.severity}`} />
                <span className="pt-nm">{row.label}</span>
                <span className="pt-det">{row.detail}</span>
                <span className="pt-ct">{row.reachedOn ?? "—"}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
