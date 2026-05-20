import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { OilPanel } from "../../../lib/panic_thermometer/copy/types";
import { Crosshair, HoverTooltip, useChartHover } from "../_shared/hover";
import { PanelLineText, ParamsBlock, RulesBlock } from "../_shared/visuals";
import { PanelHead } from "./PanelHead";

interface Props {
  panel: OilPanel;
  onEditRules?: () => void;
}

export function OilSection({ panel, onEditRules }: Props): JSX.Element {
  const { t } = useTranslation();
  const { chart } = panel;
  const xMin = 40;
  const xMax = 690;
  const yMin = 20;
  const yMax = 220;
  const yRange = chart.yMax - chart.yMin;
  const viewWidth = 700;
  const viewHeight = 240;

  const toX = (i: number) =>
    xMin + ((xMax - xMin) * i) / (chart.series.length - 1);
  const toY = (price: number) =>
    yMax - ((price - chart.yMin) / yRange) * (yMax - yMin);

  const hover = useChartHover({
    points: chart.series,
    toX,
    toY: (p) => toY(p),
    label: (_p, i) => {
      const monthIdx = Math.min(
        chart.xLabels.length - 1,
        Math.floor((i / (chart.series.length - 1)) * (chart.xLabels.length - 1)),
      );
      return chart.xLabels[monthIdx];
    },
    value: (p) => `$${p.toFixed(2)}`,
    viewWidth,
    xMin,
    xMax,
  });

  const linePath = chart.series
    .map((p, i) => `${i === 0 ? "M" : "L"}${toX(i).toFixed(1)},${toY(p).toFixed(1)}`)
    .join(" ");
  const fillPath = `${linePath} L${xMax},${yMax} L${xMin},${yMax} Z`;
  const thresholdY = toY(chart.thresholdPrice);
  const lastIdx = chart.series.length - 1;

  return (
    <>
      <div className="pt-sec-label" id="oil">
        <span>{t("panic_thermometer.oil_section.title")}</span>
        <span className="pt-ln" />
        <span className="pt-count">{t("panic_thermometer.oil_section.meta")}</span>
      </div>

      <section className="pt-panel" aria-label={t("panic_thermometer.oil_section.aria")}>
        <PanelHead panel={panel} />
        <div className="pt-panel-body">
          <div className="pt-panel-chart">
            <div className="pt-bigval">
              <span className={`pt-v is-${panel.bigValueTone}`}>{panel.bigValue}</span>
              <span className="pt-unit">{panel.bigValueUnit}</span>
              <span className={`pt-stamp is-${panel.bigValueStamp.tone}`}>
                {panel.bigValueStamp.label}
              </span>
            </div>
            <PanelLineText line={panel.narrative} />

            <div className="pt-chart-host">
            <svg
              ref={hover.svgRef}
              className="pt-svg-chart"
              viewBox="0 0 700 240"
              preserveAspectRatio="none"
              aria-label={t("panic_thermometer.oil_section.chart_aria")}
              onMouseMove={hover.onMouseMove}
              onMouseLeave={hover.onMouseLeave}
            >
              <g className="pt-grid" opacity={0.6}>
                {[20, 60, 100, 140, 180, 220].map((y) => (
                  <line key={y} x1={40} y1={y} x2={690} y2={y} />
                ))}
              </g>
              <g className="pt-axis" textAnchor="end">
                {chart.yLabels.map((label, i) => (
                  <text key={label} x={35} y={24 + i * 40}>
                    {label}
                  </text>
                ))}
              </g>
              <g className="pt-axis" textAnchor="middle">
                {chart.xLabels.map((label, i) => (
                  <text
                    key={label}
                    x={80 + i * ((xMax - 80 - 60) / (chart.xLabels.length - 1))}
                    y={236}
                  >
                    {label}
                  </text>
                ))}
              </g>

              <rect
                className="pt-oil-band"
                x={xMin}
                y={yMin}
                width={xMax - xMin}
                height={thresholdY - yMin}
              />
              <line
                className="pt-oil-thresh"
                x1={xMin}
                y1={thresholdY}
                x2={xMax}
                y2={thresholdY}
              />
              <text
                x={xMax - 5}
                y={thresholdY - 4}
                className="pt-axis"
                textAnchor="end"
                fill="var(--color-feedback-error)"
              >
                {t("panic_thermometer.oil_section.user_threshold", { price: chart.thresholdPrice })}
              </text>

              {chart.streakStartIndex < chart.series.length - 1 ? (
                <>
                  <line
                    x1={toX(chart.streakStartIndex)}
                    y1={yMin}
                    x2={toX(chart.streakStartIndex)}
                    y2={yMax}
                    stroke="var(--color-feedback-error)"
                    strokeWidth={0.8}
                    strokeDasharray="2 3"
                    opacity={0.5}
                  />
                  <text
                    x={toX(chart.streakStartIndex) + 4}
                    y={yMin + 12}
                    className="pt-axis"
                    fill="var(--color-feedback-error)"
                  >
                    {chart.streakStartLabel}
                  </text>
                </>
              ) : null}

              <path className="pt-oil-line pt-anim-line" d={linePath} />
              <path d={fillPath} className="pt-oil-fill" />

              <circle
                cx={toX(lastIdx)}
                cy={toY(chart.series[lastIdx])}
                r={4}
                fill="var(--color-feedback-error)"
                stroke="var(--color-bg-elevated)"
                strokeWidth={1.5}
              />
              <text
                x={xMax - 5}
                y={toY(chart.series[lastIdx]) - 10}
                className="pt-axis"
                textAnchor="end"
                fill="var(--color-text-primary)"
                fontWeight={600}
              >
                {chart.currentLabel}
              </text>
              <Crosshair
                hovered={hover.hovered}
                xMin={xMin}
                xMax={xMax}
                yMin={yMin}
                yMax={yMax}
                lineColor="var(--color-feedback-error)"
                dotColor="var(--color-feedback-error)"
              />
            </svg>
            <HoverTooltip
              hovered={hover.hovered}
              hostRect={{ width: viewWidth, height: viewHeight }}
            />
            </div>

            <div className="pt-streak">
              <div className="pt-streak-head">
                <span className="pt-streak-label">
                  {t("panic_thermometer.oil_section.streak_progression")}
                </span>
                <span className="pt-streak-count">
                  {t("panic_thermometer.oil_section.streak_count", {
                    days: panel.streak.days,
                    target: panel.streak.targetDays,
                  })}
                </span>
              </div>
              <div className="pt-streak-track">
                {panel.streak.segments.map((s, i) => (
                  <div
                    key={i}
                    className={`pt-streak-seg is-${s.status}`}
                    style={{ left: `${s.leftPct}%`, width: `${s.widthPct}%` }}
                  />
                ))}
                <div
                  className="pt-streak-marker"
                  style={{ left: `${panel.streak.markerPct}%` }}
                />
              </div>
              <div className="pt-streak-foot">
                {panel.streak.foots.map((f, i) => (
                  <span key={i}>
                    {f.days}{" "}
                    <strong className={f.tone === "bad" ? "is-bad" : undefined}>
                      {f.label}
                    </strong>
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="pt-panel-side">
            <RulesBlock
              title={t("panic_thermometer.oil_section.rules_title")}
              rules={panel.rules}
              onEdit={onEditRules}
            />
            <ParamsBlock
              title={t("panic_thermometer.oil_section.params_title")}
              params={panel.params}
              presetLabel={panel.presetLabel}
            />
          </div>
        </div>
      </section>
    </>
  );
}
