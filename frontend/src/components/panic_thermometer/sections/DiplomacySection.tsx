import type { JSX } from "react";
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
  const { countdown, signals } = panel;

  return (
    <>
      <div className="pt-sec-label" id="diplomacy">
        <span>D5 · Diplomatic progress</span>
        <span className="pt-ln" />
        <span className="pt-count">EODHD · company_news · ceasefire / Hormuz / Iran</span>
      </div>

      <section className="pt-panel" aria-label="Diplomatic progress panel">
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
                    <span className="pt-of">/ {countdown.total} days elapsed</span>
                    <span className="pt-lbl">{countdown.remaining} days remaining</span>
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
                      <strong>Day 0</strong> · {countdown.startLabel.replace(/^Day 0 · /, "")}
                    </span>
                    <span>
                      <strong>Day {countdown.total}</strong> ·{" "}
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
                    + Mark new milestone
                  </button>
                  <button
                    type="button"
                    className="pt-reset-btn is-warn"
                    onClick={onOverrideStatus}
                  >
                    ⚑ Override status
                  </button>
                </div>

                <div className="pt-dipl-signals">
                  <div className="pt-dipl-signal">
                    <div className="pt-dipl-signal-k">Progress signals</div>
                    <div className="pt-dipl-signal-v">
                      {signals.progress} <small>in news (30d)</small>
                    </div>
                  </div>
                  <div className="pt-dipl-signal">
                    <div className="pt-dipl-signal-k">Escalation signals</div>
                    <div className="pt-dipl-signal-v">
                      {signals.escalation} <small>in news (30d)</small>
                    </div>
                  </div>
                </div>
              </div>

              <div>
                <div className="pt-fed-news-head">
                  <span className="pt-fed-news-title">
                    News feed · last {panel.headlines.length}
                  </span>
                  <span className="pt-fed-news-meta">progress / escalation tags</span>
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
            <RulesBlock title="Rule set" rules={panel.rules} onEdit={onEditRules} />
            <ParamsBlock
              title="Params"
              params={panel.params}
              presetLabel={panel.presetLabel}
            />
          </div>
        </div>
      </section>
    </>
  );
}
