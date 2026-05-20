import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { DiplomacyPanel } from "../../../lib/panic_thermometer/copy/types";
import {
  HeadlineText,
  ParamsBlock,
  RulesBlock,
} from "../_shared/visuals";
import { PanelHead } from "./PanelHead";

interface Props {
  panel: DiplomacyPanel;
  onEditRules?: () => void;
  onMarkMilestone?: () => void;
  onOverrideStatus?: () => void;
}

export function DiplomacySection({
  panel,
  onEditRules,
  onMarkMilestone,
  onOverrideStatus,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const { countdown, signals } = panel;

  return (
    <>
      <div className="pt-sec-label" id="diplomacy">
        <span>{t("panic_thermometer.diplomacy_section.title")}</span>
        <span className="pt-ln" />
        <span className="pt-count">{t("panic_thermometer.diplomacy_section.meta")}</span>
      </div>

      <section className="pt-panel" aria-label={t("panic_thermometer.diplomacy_section.aria")}>
        <PanelHead panel={panel} />
        <div className="pt-panel-body is-full">
          <div
            className="pt-panel-chart"
            style={{ borderRight: 0, borderBottom: "var(--pt-rule)" }}
          >
            <div className="pt-dipl-row">
              <div>
                <div className="pt-countdown">
                  <div className="pt-countdown-num">
                    <span className="pt-v">{countdown.elapsed}</span>
                    <span className="pt-of">
                      {t("panic_thermometer.diplomacy_section.days_elapsed", {
                        total: countdown.total,
                      })}
                    </span>
                    <span className="pt-lbl">
                      {t("panic_thermometer.diplomacy_section.days_remaining", {
                        days: countdown.remaining,
                      })}
                    </span>
                  </div>
                  <div className="pt-countdown-bar">
                    <div
                      className="pt-fill"
                      style={{ width: `${countdown.progressPct}%` }}
                    />
                    <div
                      className="pt-marker"
                      style={{ left: `${countdown.progressPct}%` }}
                    />
                  </div>
                  <div className="pt-countdown-foot">
                    <span>
                      <strong>{t("panic_thermometer.diplomacy_section.day0_strong")}</strong>{" "}
                      · {countdown.startLabel.replace(/^Day 0 · /, "")}
                    </span>
                    <span>
                      <strong>
                        {t("panic_thermometer.diplomacy_section.day_total_strong", {
                          total: countdown.total,
                        })}
                      </strong>{" "}
                      ·{" "}
                      {countdown.endLabel.replace(new RegExp(`^Day ${countdown.total} · `), "")}
                    </span>
                  </div>
                </div>

                <div className="pt-dipl-actions">
                  <button
                    type="button"
                    className="pt-reset-btn"
                    onClick={onMarkMilestone}
                  >
                    {t("panic_thermometer.diplomacy_section.mark_milestone")}
                  </button>
                  <button
                    type="button"
                    className="pt-reset-btn is-warn"
                    onClick={onOverrideStatus}
                  >
                    {t("panic_thermometer.diplomacy_section.override_status")}
                  </button>
                </div>

                <div className="pt-dipl-signals">
                  <div className="pt-dipl-signal">
                    <div className="pt-dipl-signal-k">
                      {t("panic_thermometer.diplomacy_section.progress_signals")}
                    </div>
                    <div className="pt-dipl-signal-v">
                      {signals.progress}{" "}
                      <small>{t("panic_thermometer.diplomacy_section.in_news_30d")}</small>
                    </div>
                  </div>
                  <div className="pt-dipl-signal">
                    <div className="pt-dipl-signal-k">
                      {t("panic_thermometer.diplomacy_section.escalation_signals")}
                    </div>
                    <div className="pt-dipl-signal-v">
                      {signals.escalation}{" "}
                      <small>{t("panic_thermometer.diplomacy_section.in_news_30d")}</small>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div className="pt-fed-news-head">
                  <span className="pt-fed-news-title">
                    {t("panic_thermometer.diplomacy_section.news_feed", {
                      count: panel.headlines.length,
                    })}
                  </span>
                  <span className="pt-fed-news-meta">
                    {t("panic_thermometer.diplomacy_section.news_meta")}
                  </span>
                </div>
                <div className="pt-fed-news">
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
            </div>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 12,
              padding: "16px 20px",
            }}
          >
            <RulesBlock
              title={t("panic_thermometer.diplomacy_section.rules_title")}
              rules={panel.rules}
              onEdit={onEditRules}
            />
            <ParamsBlock
              title={t("panic_thermometer.diplomacy_section.params_title")}
              params={panel.params}
              presetLabel={panel.presetLabel}
            />
          </div>
        </div>
      </section>
    </>
  );
}
