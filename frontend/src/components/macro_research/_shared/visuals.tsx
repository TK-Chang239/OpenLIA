import { useMemo } from "react";
import * as echarts from "echarts/core";
import { LineChart, PieChart } from "echarts/charts";
import {
  GraphicComponent,
  GridComponent,
  MarkPointComponent,
  TooltipComponent,
} from "echarts/components";
import { SVGRenderer } from "echarts/renderers";
import EChartsReactCore from "echarts-for-react/lib/core";

import type { Status } from "../../../lib/macro_research/dalio_copy/types";

/* Tree-shaken ECharts setup. We register only what the four macro charts
   actually use (line + pie series, grid + tooltip + mark-point + graphic
   components, SVG renderer). The umbrella `echarts-for-react` default
   import would pull in the full library — ~400KB gz. */
echarts.use([
  LineChart,
  PieChart,
  GridComponent,
  TooltipComponent,
  MarkPointComponent,
  GraphicComponent,
  SVGRenderer,
]);

/* Resolve OpenLIA design tokens at chart mount time. ECharts mostly
   passes color strings straight through to SVG attributes (fill,
   stroke, stop-color), where the browser resolves `var(--*)`. Reading
   them off the document root once gives us real values to pass into
   ECharts internals (gradient interpolation, hover-state color
   manipulation) where var() strings would fail to parse. */
function useChartTokens() {
  return useMemo(() => {
    if (typeof window === "undefined" || typeof document === "undefined") {
      return {
        accent: "var(--color-accent-primary)",
        accentOn: "var(--color-accent-on)",
        textPrimary: "var(--color-text-primary)",
        textSecondary: "var(--color-text-secondary)",
        textTertiary: "var(--color-text-tertiary)",
        borderSubtle: "var(--color-border-subtle)",
        bgElevated: "var(--color-bg-elevated)",
        bgCode: "var(--color-bg-code)",
        bgBase: "var(--color-bg-base)",
        error: "var(--color-feedback-error)",
        warning: "var(--color-feedback-warning)",
        success: "var(--color-feedback-success)",
        fontMono: "var(--font-mono)",
      };
    }
    const cs = getComputedStyle(document.documentElement);
    function read(varName: string): string {
      return cs.getPropertyValue(varName).trim() || `var(${varName})`;
    }
    return {
      accent: read("--color-accent-primary"),
      accentOn: read("--color-accent-on"),
      textPrimary: read("--color-text-primary"),
      textSecondary: read("--color-text-secondary"),
      textTertiary: read("--color-text-tertiary"),
      borderSubtle: read("--color-border-subtle"),
      bgElevated: read("--color-bg-elevated"),
      bgCode: read("--color-bg-code"),
      bgBase: read("--color-bg-base"),
      error: read("--color-feedback-error"),
      warning: read("--color-feedback-warning"),
      success: read("--color-feedback-success"),
      fontMono: read("--font-mono"),
    };
  }, []);
}

/* ============================================================
   Inline SVG primitives — pure SVG, no chart library.
   Used across all 6 macro tabs. Static / paint-only; no
   interactivity beyond CSS hover states.
   ============================================================ */

function statusStroke(status: Status): string {
  switch (status) {
    case "bad":  return "var(--color-feedback-error)";
    case "warn": return "var(--color-feedback-warning)";
    case "ok":
    case "info": return "var(--color-feedback-success)";
    case "acid": return "var(--color-accent-primary)";
    case "flat": return "var(--color-text-tertiary)";
  }
}

/* === Mini bars (T1 framework card thumbnail) === */

export function MiniBars({ values, status = "warn" }: { values: number[]; status?: Status }): JSX.Element {
  const max = Math.max(...values, 1);
  return (
    <svg viewBox="0 0 80 32" width={80} height={32} role="img" aria-label="indicator bars">
      {values.map((v, i) => {
        const h = (v / max) * 28;
        const x = i * (76 / values.length) + 2;
        const w = 76 / values.length - 2;
        return (
          <rect
            key={i}
            x={x}
            y={32 - h}
            width={w}
            height={h}
            fill={statusStroke(status)}
            rx={1}
          />
        );
      })}
    </svg>
  );
}

/* === Mini ring (T3 framework card thumbnail) === */

export function MiniRing({ values }: { values: number[] }): JSX.Element {
  const r = 12;
  const c = 2 * Math.PI * r;
  const total = values.reduce((s, v) => s + v, 0) || 1;
  let cum = 0;
  const palette = [
    "var(--color-accent-primary)",
    "var(--color-feedback-success)",
    "var(--color-feedback-warning)",
    "var(--color-feedback-error)",
    "var(--color-text-tertiary)",
  ];
  return (
    <svg viewBox="0 0 32 32" width={32} height={32} role="img" aria-label="allocation ring">
      <g transform="rotate(-90 16 16)">
        {values.map((v, i) => {
          const len = (v / total) * c;
          const offset = -((cum / total) * c);
          cum += v;
          return (
            <circle
              key={i}
              cx={16}
              cy={16}
              r={r}
              fill="none"
              stroke={palette[i % palette.length]}
              strokeWidth={4}
              strokeDasharray={`${len} ${c - len}`}
              strokeDashoffset={offset}
            />
          );
        })}
      </g>
    </svg>
  );
}

/* === Mini quadrant (T2 framework card thumbnail) === */

export function MiniQuadrant({ active }: { active: { active: boolean; index?: number } }): JSX.Element {
  const cells: { x: number; y: number }[] = [
    { x: 0, y: 0 },
    { x: 16, y: 0 },
    { x: 0, y: 16 },
    { x: 16, y: 16 },
  ];
  const idx = active.index ?? 3;
  return (
    <svg viewBox="0 0 32 32" width={32} height={32} role="img" aria-label="regime quadrant">
      {cells.map((c, i) => (
        <rect
          key={i}
          x={c.x}
          y={c.y}
          width={16}
          height={16}
          fill={i === idx && active.active ? "var(--color-accent-primary)" : "var(--color-bg-code)"}
          stroke="var(--color-border-subtle)"
          strokeWidth={0.5}
        />
      ))}
    </svg>
  );
}

/* === Mini stage strip (T4 framework card thumbnail) === */

export function MiniStage({ active }: { active: { active: boolean; index?: number } }): JSX.Element {
  const idx = active.index ?? 4;
  return (
    <svg viewBox="0 0 80 14" width={80} height={14} role="img" aria-label="empire stage strip">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <rect
          key={i}
          x={i * 13 + 1}
          y={2}
          width={11}
          height={10}
          rx={2}
          fill={i === idx ? "var(--color-feedback-warning)" : i < idx ? "var(--color-text-tertiary)" : "var(--color-bg-code)"}
          opacity={i === idx ? 1 : i < idx ? 0.5 : 0.7}
        />
      ))}
    </svg>
  );
}

/* === Mini forces (T5 framework card thumbnail) === */

export function MiniForces({ values }: { values: number[] }): JSX.Element {
  return (
    <svg viewBox="0 0 100 32" width={100} height={32} role="img" aria-label="five forces">
      {values.map((v, i) => {
        const h = (v / 100) * 26;
        const x = i * 19 + 4;
        const fill = v >= 70 ? "var(--color-feedback-error)" : v >= 50 ? "var(--color-feedback-warning)" : "var(--color-feedback-success)";
        return (
          <g key={i}>
            <rect x={x} y={3} width={14} height={26} fill="var(--color-bg-code)" rx={1} />
            <rect x={x} y={29 - h} width={14} height={h} fill={fill} rx={1} />
          </g>
        );
      })}
    </svg>
  );
}

/* === T1 spotlight area chart (interactive: hover tooltip) === */

export interface SpotlightChart {
  yLabel: string;
  yUnit?: string;
  yMin?: number;
  yMax?: number;
  data: { year: number; value: number }[];
  current: { year: number; value: number };
}

export function SpotlightAreaChart({ data }: { data: SpotlightChart }): JSX.Element {
  const t = useChartTokens();
  const unit = data.yUnit ?? "";
  const option = {
    animation: false,
    grid: { top: 16, right: 12, bottom: 22, left: 40 },
    tooltip: {
      trigger: "axis",
      backgroundColor: t.bgElevated,
      borderColor: t.borderSubtle,
      textStyle: { color: t.textPrimary, fontSize: 11, fontFamily: t.fontMono },
      formatter: (params: { axisValueLabel: string; data: [number, number] }[]) => {
        if (!params || params.length === 0) return "";
        const p = params[0];
        const [year, value] = p.data;
        return `<span style="color:${t.textTertiary};font-size:10px;letter-spacing:0.06em">${year}</span><br/><strong>${value.toFixed(1)}${unit}</strong>`;
      },
    },
    xAxis: {
      type: "value",
      min: data.data[0].year,
      max: data.data[data.data.length - 1].year,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        fontSize: 9,
        fontFamily: t.fontMono,
        color: t.textTertiary,
        formatter: (v: number) => `'${String(v).slice(2)}`,
      },
    },
    yAxis: {
      type: "value",
      min: data.yMin,
      max: data.yMax,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: t.borderSubtle, type: "dashed", opacity: 0.6 } },
      axisLabel: {
        fontSize: 9,
        fontFamily: t.fontMono,
        color: t.textTertiary,
        formatter: (v: number) => `${v}${unit}`,
      },
    },
    series: [
      {
        type: "line",
        smooth: 0.18,
        symbol: "none",
        data: data.data.map((d) => [d.year, d.value]),
        lineStyle: { color: t.textPrimary, width: 1.6 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(var(--color-accent-primary-rgb), 0.7)" },
              { offset: 1, color: "rgba(var(--color-accent-primary-rgb), 0)" },
            ],
          },
        },
        markPoint: {
          symbol: "circle",
          symbolSize: 12,
          data: [
            {
              coord: [data.current.year, data.current.value],
              itemStyle: { color: t.accent, borderColor: t.accentOn, borderWidth: 1.4 },
              label: {
                show: true,
                position: "top",
                formatter: `${data.current.value.toFixed(1)}${unit}`,
                color: t.textPrimary,
                fontFamily: t.fontMono,
                fontSize: 9,
                fontWeight: 600,
              },
            },
          ],
        },
      },
    ],
  };
  return (
    <EChartsReactCore echarts={echarts}
      option={option}
      opts={{ renderer: "svg" }}
      style={{ height: 110, width: "100%" }}
      notMerge
    />
  );
}

/* === Dependency map (Summary cross-framework) === */

export interface DepMapNode {
  id: string;
  tcode: string;
  name: string;
  status: Status;
  statusLabel: string;
  /** "left" | "center" | "right" */
  position: "left-top" | "left-mid" | "left-bot" | "center" | "right";
}

export interface DepMapEdge {
  from: string;
  to: string;
  label: string;
  variant: "solid" | "dashed" | "accent";
}

export function DepMap({ nodes, edges }: { nodes: DepMapNode[]; edges: DepMapEdge[] }): JSX.Element {
  const positions: Record<DepMapNode["position"], { x: number; y: number; w: number; h: number; isCenter?: boolean; isRight?: boolean }> = {
    "left-top": { x: 40, y: 60, w: 110, h: 60 },
    "left-mid": { x: 40, y: 140, w: 110, h: 60 },
    "left-bot": { x: 40, y: 220, w: 110, h: 60 },
    center:    { x: 420, y: 120, w: 120, h: 80, isCenter: true },
    right:     { x: 720, y: 100, w: 120, h: 80, isRight: true },
  };

  const nodeMap: Record<string, DepMapNode & { pos: typeof positions[DepMapNode["position"]] }> = {};
  for (const n of nodes) nodeMap[n.id] = { ...n, pos: positions[n.position] };

  function anchor(id: string, side: "right" | "left"): { x: number; y: number } {
    const n = nodeMap[id];
    const cx = n.pos.x + (side === "right" ? n.pos.w : 0);
    const cy = n.pos.y + n.pos.h / 2;
    return { x: cx, y: cy };
  }

  return (
    <svg viewBox="0 0 880 290" aria-label="cross-framework dependency map">
      <defs>
        <marker id="mr-arr-solid" viewBox="0 0 8 8" refX={7} refY={4} markerWidth={6} markerHeight={6} orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-text-primary)" />
        </marker>
        <marker id="mr-arr-dashed" viewBox="0 0 8 8" refX={7} refY={4} markerWidth={6} markerHeight={6} orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-text-secondary)" />
        </marker>
        <marker id="mr-arr-accent" viewBox="0 0 8 8" refX={7} refY={4} markerWidth={6} markerHeight={6} orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-feedback-success)" />
        </marker>
        <pattern id="mr-depg" x={0} y={0} width={14} height={14} patternUnits="userSpaceOnUse">
          <circle cx={1} cy={1} r={0.55} fill="var(--color-text-tertiary)" opacity={0.3} />
        </pattern>
      </defs>
      <rect x={0} y={0} width={880} height={290} fill="url(#mr-depg)" opacity={0.55} />
      {edges.map((e, i) => {
        const from = anchor(e.from, "right");
        const to = anchor(e.to, "left");
        const midX = (from.x + to.x) / 2;
        const dPath = `M${from.x},${from.y} C ${midX},${from.y} ${midX},${to.y} ${to.x},${to.y}`;
        const stroke =
          e.variant === "accent" ? "var(--color-feedback-success)" :
          e.variant === "dashed" ? "var(--color-text-secondary)" :
          "var(--color-text-primary)";
        const dash = e.variant === "dashed" ? "3 3" : undefined;
        const marker =
          e.variant === "accent" ? "url(#mr-arr-accent)" :
          e.variant === "dashed" ? "url(#mr-arr-dashed)" :
          "url(#mr-arr-solid)";
        const labelY = from.y - 10 + (i % 3) * 4;
        return (
          <g key={`${e.from}-${e.to}-${i}`}>
            <path
              d={dPath}
              fill="none"
              stroke={stroke}
              strokeWidth={e.variant === "accent" ? 2 : 1.5}
              strokeDasharray={dash}
              markerEnd={marker}
            />
            <text
              x={midX}
              y={labelY}
              fontFamily="var(--font-mono)"
              fontSize={10}
              fill={stroke}
              fontWeight={e.variant === "accent" ? 600 : 400}
              letterSpacing="0.04em"
              textAnchor="middle"
            >
              {e.label}
            </text>
          </g>
        );
      })}
      {nodes.map((n) => {
        const pos = positions[n.position];
        const fill = pos.isCenter ? "var(--color-text-primary)" : "var(--color-bg-elevated)";
        const stroke = pos.isRight
          ? "var(--color-feedback-success)"
          : "var(--color-text-primary)";
        const strokeW = pos.isRight ? 2 : 1.6;
        const tcodeFill = pos.isCenter ? "var(--color-bg-base)" : "var(--color-text-primary)";
        const nameFill = pos.isCenter ? "var(--color-bg-base)" : "var(--color-text-primary)";
        const statusFill =
          pos.isCenter ? "var(--color-accent-primary)" :
          pos.isRight ? "var(--color-feedback-success)" :
          n.status === "bad" ? "var(--color-feedback-error)" :
          n.status === "warn" ? "var(--color-feedback-warning)" :
          "var(--color-feedback-success)";
        const cx = pos.x + pos.w / 2;
        const tcodeY = pos.isCenter ? pos.y + 26 : pos.y + 25;
        const nameY = pos.isCenter ? pos.y + 44 : pos.y + 40;
        const statusY = pos.isCenter ? pos.y + 63 : pos.y + 53;
        const tcodeText = pos.isCenter
          ? `${n.tcode} · AGGREGATOR`
          : pos.isRight
          ? `${n.tcode} · IMPLEMENT`
          : n.tcode;
        return (
          <g key={n.id}>
            <rect
              x={pos.x}
              y={pos.y}
              width={pos.w}
              height={pos.h}
              rx={10}
              fill={fill}
              stroke={stroke}
              strokeWidth={strokeW}
            />
            <text
              x={cx}
              y={tcodeY}
              fontFamily="var(--font-mono)"
              fontSize={11}
              fontWeight={600}
              letterSpacing="0.12em"
              textAnchor="middle"
              fill={tcodeFill}
            >
              {tcodeText}
            </text>
            <text
              x={cx}
              y={nameY}
              fontFamily="var(--font-display)"
              fontSize={pos.isCenter || pos.isRight ? 12 : 11}
              textAnchor="middle"
              fill={nameFill}
            >
              {n.name}
            </text>
            <text
              x={cx}
              y={statusY}
              fontFamily="var(--font-mono)"
              fontSize={pos.isCenter || pos.isRight ? 10 : 9}
              fill={statusFill}
              textAnchor="middle"
              letterSpacing="0.06em"
              fontWeight={pos.isCenter ? 500 : 400}
            >
              {n.statusLabel}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/* === Donut (T3 portfolio comparison · interactive: hover slice) === */

export interface DonutSlice {
  label: string;
  pct: number;
  tone: "accent" | "olive" | "neutral" | "amber" | "rust";
}

export function Donut({ slices }: { slices: DonutSlice[] }): JSX.Element {
  const t = useChartTokens();
  const sliceColor: Record<DonutSlice["tone"], string> = {
    accent: t.accent,
    olive: t.success,
    amber: t.warning,
    rust: t.error,
    neutral: t.textSecondary,
  };
  const total = slices.reduce((s, x) => s + x.pct, 0);
  const option = {
    animation: false,
    tooltip: {
      trigger: "item",
      backgroundColor: t.bgElevated,
      borderColor: t.borderSubtle,
      textStyle: { color: t.textPrimary, fontSize: 11, fontFamily: t.fontMono },
      formatter: (p: { name: string; value: number; percent: number }) =>
        `<span style="color:${t.textTertiary};font-size:10px">${p.name}</span><br/><strong>${p.value}%</strong> <span style="color:${t.textTertiary}">(${p.percent.toFixed(1)}% of total)</span>`,
    },
    series: [
      {
        type: "pie",
        radius: ["55%", "82%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: false,
        label: { show: false },
        labelLine: { show: false },
        emphasis: {
          scale: true,
          scaleSize: 4,
          itemStyle: { shadowBlur: 6, shadowColor: "rgba(0,0,0,0.12)" },
        },
        data: slices.map((s) => ({
          name: s.label,
          value: s.pct,
          itemStyle: {
            color: sliceColor[s.tone],
            borderColor: t.bgElevated,
            borderWidth: 2,
          },
        })),
      },
    ],
    graphic: {
      type: "text",
      left: "center",
      top: "center",
      style: {
        text: `${total}%`,
        fontFamily: t.fontMono,
        fontSize: 18,
        fontWeight: 600,
        fill: t.textPrimary,
      },
    },
  };
  return (
    <EChartsReactCore echarts={echarts}
      option={option}
      opts={{ renderer: "svg" }}
      style={{ height: 160, width: 160 }}
      notMerge
    />
  );
}

/* === Reserve composition multi-line chart (T4 · interactive) === */

export interface ReserveLineSeries {
  label: string;
  values: number[];
  isPrimary?: boolean;
}

export function ReserveLineChart({
  years,
  series,
  yMax = 80,
}: {
  years: number[];
  series: ReserveLineSeries[];
  yMax?: number;
}): JSX.Element {
  const t = useChartTokens();
  const colorOf: Record<string, string> = {
    USD: t.error,
    EUR: t.textSecondary,
    JPY: t.warning,
    CNY: t.success,
    Other: t.textTertiary,
  };
  const option = {
    animation: false,
    tooltip: {
      trigger: "axis",
      backgroundColor: t.bgElevated,
      borderColor: t.borderSubtle,
      textStyle: { color: t.textPrimary, fontSize: 11, fontFamily: t.fontMono },
      axisPointer: { type: "line", lineStyle: { color: t.textTertiary, type: "dashed" } },
      formatter: (params: { axisValueLabel: string; seriesName: string; value: number; color: string }[]) => {
        if (!params || params.length === 0) return "";
        const sorted = [...params].sort((a, b) => b.value - a.value);
        const head = `<div style="color:${t.textTertiary};font-size:10px;letter-spacing:0.06em;margin-bottom:4px">${params[0].axisValueLabel}</div>`;
        const rows = sorted
          .map(
            (p) =>
              `<div style="display:flex;align-items:center;gap:6px;font-size:11px"><span style="display:inline-block;width:8px;height:2px;background:${p.color}"></span><span style="color:${t.textSecondary};min-width:36px">${p.seriesName}</span><strong>${p.value.toFixed(1)}%</strong></div>`,
          )
          .join("");
        return head + rows;
      },
    },
    legend: { show: false },
    grid: { top: 12, right: 16, bottom: 28, left: 40 },
    xAxis: {
      type: "category",
      data: years.map((y) => String(y)),
      axisLine: { lineStyle: { color: t.borderSubtle } },
      axisTick: { show: false },
      axisLabel: {
        fontFamily: t.fontMono,
        fontSize: 10,
        color: t.textTertiary,
        interval: Math.max(0, Math.floor(years.length / 6) - 1),
      },
    },
    yAxis: {
      type: "value",
      min: 0,
      max: yMax,
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: t.borderSubtle, type: "dashed", opacity: 0.6 } },
      axisLabel: {
        fontFamily: t.fontMono,
        fontSize: 10,
        color: t.textTertiary,
        formatter: (v: number) => `${v}%`,
      },
    },
    series: series.map((s) => {
      const color = colorOf[s.label] ?? t.textTertiary;
      return {
        name: s.label,
        type: "line",
        data: s.values,
        smooth: 0.25,
        showSymbol: false,
        emphasis: { focus: "series" },
        lineStyle: {
          color,
          width: s.isPrimary ? 2.4 : 1.5,
          type: s.isPrimary ? "solid" : "dashed",
        },
        itemStyle: { color },
      };
    }),
  };
  return (
    <EChartsReactCore echarts={echarts}
      option={option}
      opts={{ renderer: "svg" }}
      style={{ height: 220, width: "100%" }}
      notMerge
    />
  );
}
