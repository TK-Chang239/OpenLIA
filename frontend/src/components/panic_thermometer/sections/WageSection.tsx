import type { JSX } from "react";
import { useState } from "react";
import type { WagePanel } from "../../../lib/panic_thermometer/copy/types";
import { PanelLineText, ParamsBlock, RulesBlock } from "../_shared/visuals";
import { PanelHead } from "./PanelHead";

interface Props {
  panel: WagePanel;
  onEditRules?: () => void;
}

export function WageSection({ panel, onEditRules }: Props): JSX.Element {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const xMin = 40;
  const xMax = 690;
  const yMin = 0;
  const yMax = 200;
  const yPlot = yMax - yMin;
  const yScale = (v: number) => yMax - (v / panel.yMax) * yPlot;

  const barWidth = 36;
  const slotWidth = (xMax - xMin) / panel.bars.length;

  return (
    <>
      <div className="pt-sec-label" id="wage">
        <span>D4 · Wage growth</span>
        <span className="pt-ln" />
        <span className="pt-count">EODHD · economic_events · AHE MoM</span>
      </div>

      <section className="pt-panel" aria-label="Wage growth panel">
        <PanelHead panel={panel} />
        <div className="pt-panel-body">
          <div className="pt-panel-chart">
            <div className="pt-bigval">
              <span className="pt-v is-bad">{panel.bigValue}</span>
              <span className="pt-unit">{panel.bigValueUnit}</span>
              <span className={`pt-stamp is-${panel.bigValueStamp.tone}`}>
                {panel.bigValueStamp.label}
              </span>
            </div>
            <PanelLineText line={panel.narrative} />

            <div className="pt-chart-host">
            <svg
              className="pt-svg-chart pt-wage-svg"
              viewBox="0 0 700 200"
              preserveAspectRatio="none"
              aria-label="Monthly AHE bars"
              style={{ cursor: "default" }}
            >
              <g className="pt-grid" opacity={0.5}>
                {[20, 60, 100, 140, 180].map((y) => (
                  <line key={y} x1={xMin} y1={y} x2={xMax} y2={y} />
                ))}
              </g>
              <g className="pt-axis" textAnchor="end">
                {[0, 0.2, 0.4, 0.6, 0.8].map((v) => (
                  <text key={v} x={xMin - 5} y={yScale(v) + 4}>
                    {v.toFixed(1)}
                  </text>
                ))}
              </g>

              <line
                className="pt-wage-thresh-amber"
                x1={xMin}
                y1={yScale(panel.thresholds.amber)}
                x2={xMax}
                y2={yScale(panel.thresholds.amber)}
              />
              <text
                x={xMax - 5}
                y={yScale(panel.thresholds.amber) - 4}
                className="pt-axis"
                textAnchor="end"
                fill="var(--color-feedback-warning)"
              >
                {panel.thresholds.amber}% — amber
              </text>
              <line
                className="pt-wage-thresh-red"
                x1={xMin}
                y1={yScale(panel.thresholds.red)}
                x2={xMax}
                y2={yScale(panel.thresholds.red)}
              />
              <text
                x={xMax - 5}
                y={yScale(panel.thresholds.red) - 4}
                className="pt-axis"
                textAnchor="end"
                fill="var(--color-feedback-error)"
              >
                {panel.thresholds.red}% — red
              </text>

              {panel.bars.map((b, i) => {
                const slotLeft = xMin + i * slotWidth + (slotWidth - barWidth) / 2;
                const yTop = yScale(b.value);
                return (
                  <rect
                    key={`${b.month}-${i}`}
                    className={`pt-wage-bar is-${b.status} pt-anim-bar`}
                    x={slotLeft}
                    y={yTop}
                    width={barWidth}
                    height={yMax - yTop}
                    style={{ animationDelay: `${200 + i * 40}ms` }}
                    onMouseEnter={() => setHoverIdx(i)}
                    onMouseLeave={() => setHoverIdx(null)}
                  >
                    <title>
                      {b.month}: {b.value.toFixed(2)}% MoM
                    </title>
                  </rect>
                );
              })}

              <g className="pt-axis" textAnchor="middle">
                {panel.bars.map((b, i) => {
                  const cx = xMin + i * slotWidth + slotWidth / 2;
                  return (
                    <text
                      key={`${b.month}-${i}-x`}
                      x={cx}
                      y={196}
                      fill={
                        b.isCurrent || i === panel.consecutiveBracket.startIndex
                          ? "var(--color-text-primary)"
                          : undefined
                      }
                      fontWeight={
                        b.isCurrent || i === panel.consecutiveBracket.startIndex
                          ? 600
                          : 400
                      }
                    >
                      {b.month}
                    </text>
                  );
                })}
              </g>

              {hoverIdx !== null ? (() => {
                const b = panel.bars[hoverIdx];
                const cx = xMin + hoverIdx * slotWidth + slotWidth / 2;
                const yTop = yScale(b.value);
                return (
                  <line
                    x1={cx}
                    y1={yMin}
                    x2={cx}
                    y2={yTop - 4}
                    stroke="var(--color-text-primary)"
                    strokeWidth={0.6}
                    strokeDasharray="2 2"
                    opacity={0.5}
                    pointerEvents="none"
                  />
                );
              })() : null}

              {(() => {
                const startCx =
                  xMin +
                  panel.consecutiveBracket.startIndex * slotWidth +
                  slotWidth / 2;
                const endCx =
                  xMin +
                  panel.consecutiveBracket.endIndex * slotWidth +
                  slotWidth / 2;
                const midCx = (startCx + endCx) / 2;
                return (
                  <g>
                    <line
                      x1={startCx}
                      y1={48}
                      x2={startCx}
                      y2={55}
                      stroke="var(--pt-darkred)"
                      strokeWidth={1}
                    />
                    <line
                      x1={startCx}
                      y1={48}
                      x2={endCx}
                      y2={48}
                      stroke="var(--pt-darkred)"
                      strokeWidth={1}
                    />
                    <line
                      x1={endCx}
                      y1={48}
                      x2={endCx}
                      y2={55}
                      stroke="var(--pt-darkred)"
                      strokeWidth={1}
                    />
                    <text
                      x={midCx}
                      y={42}
                      className="pt-axis"
                      textAnchor="middle"
                      fill="var(--pt-darkred)"
                      fontWeight={600}
                    >
                      {panel.consecutiveBracket.label}
                    </text>
                  </g>
                );
              })()}
            </svg>
            {hoverIdx !== null ? (() => {
              const b = panel.bars[hoverIdx];
              const cxPct = ((xMin + hoverIdx * slotWidth + slotWidth / 2) / 700) * 100;
              const cyPct = (yScale(b.value) / 200) * 100;
              const flipX = cxPct > 75;
              const toneClass =
                b.status === "darkred" || b.status === "red" ? "is-bad"
                : b.status === "amber" ? "is-warn"
                : "is-ok";
              return (
                <div
                  className="pt-tooltip"
                  role="tooltip"
                  style={{
                    position: "absolute",
                    left: `${cxPct}%`,
                    top: `${cyPct}%`,
                    transform: `translate(${flipX ? "calc(-100% - 12px)" : "12px"}, -100%)`,
                    pointerEvents: "none",
                  }}
                >
                  <div className="pt-tooltip-label">{b.month}</div>
                  <div className={`pt-tooltip-value ${toneClass}`}>
                    {b.value > 0 ? "+" : ""}{b.value.toFixed(2)}% MoM
                  </div>
                </div>
              );
            })() : null}
            </div>
          </div>

          <div className="pt-panel-side">
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
