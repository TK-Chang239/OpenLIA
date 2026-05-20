import type { JSX } from "react";
import { useTranslation } from "react-i18next";

import type { InflationPanel } from "../../../lib/panic_thermometer/copy/types";
import { Crosshair, HoverTooltip, useChartHover } from "../_shared/hover";
import { PanelLineText, ParamsBlock, RulesBlock } from "../_shared/visuals";
import { PanelHead } from "./PanelHead";

interface Props {
  panel: InflationPanel;
  onEditRules?: () => void;
}

export function InflationSection({ panel, onEditRules }: Props): JSX.Element {
  const { t } = useTranslation();
  const { chart } = panel;
  const xMin = 40;
  const xMax = 690;
  const yMin = 20;
  const yMax = 220;
  const yPlot = yMax - yMin;

  const toY = (level: number) =>
    yMax - ((level - chart.yMin) / (chart.yMax - chart.yMin)) * yPlot;

  const tipMax = Math.max(...chart.tipSeries);
  const tipMin = Math.min(...chart.tipSeries);
  const tipRange = tipMax - tipMin || 1;
  const toTipY = (v: number) =>
    yMax - ((v - tipMin) / tipRange) * yPlot * 0.6 - yPlot * 0.2;

  const tipPath = chart.tipSeries
    .map((v, i) => {
      const x = xMin + ((xMax - xMin) * i) / (chart.tipSeries.length - 1);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${toTipY(v).toFixed(1)}`;
    })
    .join(" ");

  const michPath = chart.michiganDots
    .map((d, i) => `${i === 0 ? "M" : "L"}${d.x},${toY(d.y).toFixed(1)}`)
    .join(" ");

  const viewWidth = 700;
  const viewHeight = 240;
  const hover = useChartHover({
    points: chart.michiganDots,
    toX: (i) => chart.michiganDots[i].x,
    toY: (d) => toY(d.y),
    label: (_d, i) => chart.xLabels[i] ?? "",
    value: (d) => `Michigan ${d.y.toFixed(1)}%`,
    viewWidth,
    xMin,
    xMax,
  });

  return (
    <>
      <div className="pt-sec-label" id="inflation">
        <span>{t("panic_thermometer.inflation_section.title")}</span>
        <span className="pt-ln" />
        <span className="pt-count">{t("panic_thermometer.inflation_section.meta")}</span>
      </div>

      <section className="pt-panel" aria-label={t("panic_thermometer.inflation_section.aria")}>
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
              aria-label={t("panic_thermometer.inflation_section.chart_aria")}
              onMouseMove={hover.onMouseMove}
              onMouseLeave={hover.onMouseLeave}
            >
              {chart.bands.map((b, i) => {
                const yTop = yMin + (yPlot * b.yPct[0]) / 100;
                const yBottom = yMin + (yPlot * b.yPct[1]) / 100;
                return (
                  <rect
                    key={i}
                    className={`pt-infl-band-${b.tone}`}
                    x={xMin}
                    y={yTop}
                    width={xMax - xMin}
                    height={yBottom - yTop}
                  />
                );
              })}

              <g className="pt-grid" opacity={0.5}>
                {[60, 100, 150, 200].map((y) => (
                  <line key={y} x1={xMin} y1={y} x2={xMax} y2={y} />
                ))}
              </g>

              {chart.thresholds.map((t) => {
                const y = toY(t.level);
                return (
                  <g key={t.tone}>
                    <line
                      className={`pt-infl-thresh is-${t.tone}`}
                      x1={xMin}
                      y1={y}
                      x2={xMax}
                      y2={y}
                    />
                    <text
                      x={xMin + 4}
                      y={y - 4}
                      className="pt-axis"
                      fill={
                        t.tone === "dark"
                          ? "var(--pt-darkred)"
                          : t.tone === "red"
                          ? "var(--color-feedback-error)"
                          : "var(--color-feedback-warning)"
                      }
                    >
                      {t.label}
                    </text>
                  </g>
                );
              })}

              <g className="pt-axis" textAnchor="end">
                {chart.yLabels.map((label) => {
                  const value = parseFloat(label);
                  return (
                    <text key={label} x={xMin - 5} y={toY(value) + 4}>
                      {label}
                    </text>
                  );
                })}
              </g>
              <g className="pt-axis" textAnchor="middle">
                {chart.xLabels.map((label, i) => (
                  <text
                    key={label}
                    x={80 + i * ((xMax - 80 - 60) / (chart.xLabels.length - 1))}
                    y={232}
                  >
                    {label}
                  </text>
                ))}
              </g>

              <path className="pt-infl-tip-line pt-anim-line" d={tipPath} />
              <text
                x={xMax - 2}
                y={toTipY(chart.tipSeries[chart.tipSeries.length - 1]) - 4}
                className="pt-axis"
                textAnchor="end"
                fill="var(--color-text-primary)"
              >
                {chart.tipCurrentLabel}
              </text>

              <path className="pt-infl-mich-line" d={michPath} />
              {chart.michiganDots.map((d, i) => (
                <g key={i}>
                  <circle
                    className="pt-infl-mich-dot"
                    cx={d.x}
                    cy={toY(d.y)}
                    r={d.isCurrent ? 6 : 4.5}
                  />
                  {d.isCurrent && d.label ? (
                    <text
                      x={d.x}
                      y={toY(d.y) - 10}
                      className="pt-axis"
                      textAnchor="middle"
                      fill="var(--color-text-primary)"
                      fontWeight={600}
                    >
                      {d.label}
                    </text>
                  ) : null}
                </g>
              ))}
              <Crosshair
                hovered={hover.hovered}
                xMin={xMin}
                xMax={xMax}
                yMin={yMin}
                yMax={yMax}
                lineColor="var(--color-feedback-warning)"
                dotColor="var(--color-feedback-warning)"
                showDot={false}
              />
            </svg>
            <HoverTooltip
              hovered={hover.hovered}
              hostRect={{ width: viewWidth, height: viewHeight }}
            />
            </div>

            <div className="pt-infl-legend">
              <span>
                <span className="pt-legend-line" />
                {t("panic_thermometer.inflation_section.tip_left")}
              </span>
              <span>
                <span className="pt-legend-dot" />
                {t("panic_thermometer.inflation_section.michigan_monthly")}
              </span>
            </div>
          </div>

          <div className="pt-panel-side">
            <RulesBlock
              title={t("panic_thermometer.inflation_section.rules_title")}
              rules={panel.rules}
              onEdit={onEditRules}
            />
            <ParamsBlock
              title={t("panic_thermometer.inflation_section.params_title")}
              params={panel.params}
              presetLabel={panel.presetLabel}
            />
          </div>
        </div>
      </section>
    </>
  );
}
