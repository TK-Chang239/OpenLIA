import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { FedPanel, Tone } from "../../../lib/panic_thermometer/copy/types";
import {
  HeadlineText,
  PanelLineText,
  ParamsBlock,
  RulesBlock,
} from "../_shared/visuals";
import { PanelHead } from "./PanelHead";

interface Props {
  panel: FedPanel;
  onEditRules?: () => void;
  onEditKeywords?: () => void;
}

const TONE_FILL: Record<Tone, string> = {
  dovish: "var(--color-feedback-success)",
  neutral: "var(--color-text-secondary)",
  hawkish: "var(--color-feedback-error)",
  crisis: "var(--pt-darkred)",
};
const TONE_KEY: Record<Tone, string> = {
  dovish: "panic_thermometer.fed_section.tone_dovish",
  neutral: "panic_thermometer.fed_section.tone_neutral",
  hawkish: "panic_thermometer.fed_section.tone_hawkish",
  crisis: "panic_thermometer.fed_section.tone_crisis",
};

export function FedSection({ panel, onEditRules, onEditKeywords }: Props): JSX.Element {
  const { t } = useTranslation();
  const xMin = 30;
  const xMax = 690;
  const xStep = (xMax - xMin) / Math.max(1, panel.postureTimeline.length - 1);

  return (
    <>
      <div className="pt-sec-label" id="fed">
        <span>{t("panic_thermometer.fed_section.title")}</span>
        <span className="pt-ln" />
        <span className="pt-count">{t("panic_thermometer.fed_section.meta")}</span>
      </div>

      <section className="pt-panel" aria-label={t("panic_thermometer.fed_section.aria")}>
        <PanelHead panel={panel} />
        <div className="pt-panel-body">
          <div className="pt-panel-chart">
            <div className="pt-bigval">
              <span className="pt-v is-bad is-quote">{panel.bigQuote}</span>
            </div>
            <PanelLineText line={panel.narrative} />

            <div className="pt-fed-timeline">
              <div className="pt-fed-tl-head">
                <span className="pt-fed-tl-title">
                  {t("panic_thermometer.fed_section.posture_title")}
                </span>
                <span className="pt-fed-tl-meta">
                  {t("panic_thermometer.fed_section.posture_meta", {
                    count: panel.postureTimeline.length,
                  })}
                </span>
              </div>
              <svg
                className="pt-fed-tl-svg"
                viewBox="0 0 700 96"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <line
                  x1={xMin}
                  y1={48}
                  x2={xMax}
                  y2={48}
                  stroke="var(--color-border-strong)"
                  strokeWidth={0.8}
                />
                {panel.postureTimeline.map((m, i) => {
                  const cx = xMin + i * xStep;
                  return (
                    <g key={i}>
                      <circle
                        cx={cx}
                        cy={48}
                        r={m.isCurrent ? 11 : 8}
                        fill={TONE_FILL[m.tone]}
                        stroke={
                          m.isCurrent ? "var(--pt-darkred)" : "transparent"
                        }
                        strokeWidth={m.isCurrent ? 1.5 : 0}
                        style={{ animationDelay: `${300 + i * 60}ms` }}
                      >
                        <title>
                          {m.label}: {t(TONE_KEY[m.tone])}
                          {m.isCurrent ? t("panic_thermometer.fed_section.current_suffix") : ""}
                        </title>
                      </circle>
                      <text
                        x={cx}
                        y={74}
                        className="pt-fed-tl-axis"
                        textAnchor="middle"
                        fill={
                          m.isCurrent
                            ? "var(--color-text-primary)"
                            : "var(--color-text-tertiary)"
                        }
                        fontWeight={m.isCurrent ? 600 : 400}
                      >
                        {m.label}
                      </text>
                      <text
                        x={cx}
                        y={m.isCurrent ? 22 : 32}
                        className="pt-fed-tl-axis"
                        textAnchor="middle"
                        fill={TONE_FILL[m.tone]}
                        fontWeight={m.isCurrent ? 600 : 400}
                        fontSize={8}
                      >
                        {t(TONE_KEY[m.tone])}
                        {m.isCurrent ? " ●" : ""}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>

            <div className="pt-fed-news">
              <div className="pt-fed-news-head">
                <span className="pt-fed-news-title">
                  {t("panic_thermometer.fed_section.news_title", {
                    count: panel.headlines.length,
                  })}
                </span>
                <span className="pt-fed-news-meta">
                  {t("panic_thermometer.fed_section.news_meta")}
                </span>
              </div>
              {panel.headlines.map((h, i) => (
                <div key={i} className="pt-fed-item">
                  <span className="pt-when">
                    {h.when}
                    <br />
                    {h.time}
                  </span>
                  <div>
                    <div className="pt-headline">
                      <HeadlineText fragments={h.body} />
                    </div>
                    <div className="pt-src">{h.source}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="pt-panel-side">
            <div className="pt-kw">
              <div className="pt-kw-head">
                {t("panic_thermometer.fed_section.keywords_head")}
              </div>
              {(["dovish", "neutral", "hawkish", "crisis"] as Tone[]).map((tone) => {
                const kw = panel.keywords[tone];
                return (
                  <div key={tone} className="pt-kw-row">
                    <span className={`pt-lbl is-${tone}`}>{t(TONE_KEY[tone])}</span>
                    <div className="pt-kw-chips">
                      {kw.matches.map((m) => (
                        <span key={`m-${m}`} className="pt-kw-chip is-match">
                          {m}
                        </span>
                      ))}
                      {kw.standard.map((s) => (
                        <span key={`s-${s}`} className="pt-kw-chip">
                          {s}
                        </span>
                      ))}
                      <button
                        type="button"
                        className="pt-kw-chip"
                        style={{
                          color: "var(--color-text-tertiary)",
                          borderStyle: "dashed",
                          cursor: "pointer",
                        }}
                        onClick={onEditKeywords}
                      >
                        +
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>

            <RulesBlock
              title={t("panic_thermometer.fed_section.rules_title")}
              rules={panel.rules}
              onEdit={onEditRules}
            />
            <ParamsBlock
              title={t("panic_thermometer.fed_section.params_title")}
              params={panel.params}
            />
          </div>
        </div>
      </section>
    </>
  );
}
