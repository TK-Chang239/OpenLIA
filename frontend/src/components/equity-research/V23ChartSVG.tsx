/**
 * V23ChartSVG — render one v2.3 ChartSpec as an inline SVG chart.
 *
 * Why inline SVG (recharts) and not canvas: the same DOM has to look
 * good on screen (interactive hover) AND crisp when printed to PDF
 * via a headless browser (vector, CSS-controllable). Canvas can't do
 * both. See report_output_rendering_spec.md §5.
 *
 * The component is a thin mapping layer: it pulls the fact values out
 * of the bundle the parent passed and shapes them into the row format
 * recharts wants. ChartSpec.value_fact_ids may reference either a
 * scalar fact (one data point) or a time-series fact (an array of
 * points keyed by period).
 */
import { type JSX, useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type {
  V23BundleFact,
  V23BundleSeriesPoint,
  V23ChartSpec,
} from "../../api/equity-research-v2-3";

interface Props {
  spec: V23ChartSpec;
  bundleFacts: Record<string, V23BundleFact>;
  figureLabel?: number;
}

/** Color palette is sourced from theme tokens (no hex literals in
 *  component code — keeps a single dark/light source of truth in
 *  tokens.css). Recharts accepts any valid CSS color string. */
const PALETTE = [
  "var(--color-accent-primary)",
  "var(--color-feedback-warning)",
  "var(--color-feedback-success)",
  "var(--color-feedback-danger)",
  "var(--color-text-secondary)",
  "var(--color-text-tertiary)",
];

interface ChartRow {
  category: string;
  [seriesName: string]: string | number;
}

/** Build a [{category, "Series A": 1.2, "Series B": 3.4}, …] table that
 *  every recharts cartesian chart understands. The category column is
 *  driven by spec.category_labels; each series column is named after the
 *  series and populated from the referenced fact's value(s). */
function buildRows(
  spec: V23ChartSpec,
  facts: Record<string, V23BundleFact>,
): ChartRow[] {
  const rows: ChartRow[] = spec.category_labels.map((cat) => ({ category: cat }));
  for (const series of spec.series) {
    for (let i = 0; i < spec.category_labels.length; i++) {
      const factId = series.value_fact_ids[i] ?? series.value_fact_ids[0];
      const fact = facts[factId];
      const numeric = resolveValueForCategory(fact, spec.category_labels[i], i);
      if (numeric !== null) {
        rows[i][series.name] = numeric;
      }
    }
  }
  return rows;
}

function resolveValueForCategory(
  fact: V23BundleFact | undefined,
  category: string,
  index: number,
): number | null {
  if (!fact) return null;
  const v = fact.value;
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  if (Array.isArray(v)) {
    const points = v as V23BundleSeriesPoint[];
    const hit = points.find((p) => p.period === category);
    if (hit) return hit.value;
    if (points[index]) return points[index].value;
    return null;
  }
  return null;
}

export function V23ChartSVG({ spec, bundleFacts, figureLabel }: Props): JSX.Element {
  const rows = useMemo(() => buildRows(spec, bundleFacts), [spec, bundleFacts]);
  const isHorizontal = spec.chart_type === "bar";
  const showPie = spec.chart_type === "pie";
  const caption =
    figureLabel !== undefined ? `Figure ${figureLabel}. ${spec.title}` : spec.title;

  const renderCartesian = () => {
    const seriesNames = spec.series.map((s) => s.name);
    const commonAxes = (
      <>
        <CartesianGrid stroke="rgba(0,0,0,0.06)" />
        <Tooltip />
        <Legend />
      </>
    );
    const categoryAxis = (
      <XAxis
        dataKey="category"
        tick={{ fontSize: 11 }}
        label={
          spec.x_axis_label
            ? { value: spec.x_axis_label, position: "insideBottom", offset: -2, fontSize: 11 }
            : undefined
        }
      />
    );
    const valueAxis = (
      <YAxis
        tick={{ fontSize: 11 }}
        label={
          spec.y_axis_label
            ? { value: spec.y_axis_label, angle: -90, position: "insideLeft", fontSize: 11 }
            : undefined
        }
      />
    );

    if (spec.chart_type === "line") {
      return (
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
          {commonAxes}
          {categoryAxis}
          {valueAxis}
          {seriesNames.map((name, i) => (
            <Line
              key={name}
              dataKey={name}
              stroke={PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={{ r: 3 }}
            />
          ))}
        </LineChart>
      );
    }
    if (spec.chart_type === "area") {
      return (
        <AreaChart data={rows} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
          {commonAxes}
          {categoryAxis}
          {valueAxis}
          {seriesNames.map((name, i) => (
            <Area
              key={name}
              dataKey={name}
              stroke={PALETTE[i % PALETTE.length]}
              fill={PALETTE[i % PALETTE.length]}
              fillOpacity={0.18}
            />
          ))}
        </AreaChart>
      );
    }
    if (spec.chart_type === "scatter") {
      return (
        <ScatterChart data={rows} margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
          {commonAxes}
          {categoryAxis}
          {valueAxis}
          {seriesNames.map((name, i) => (
            <Scatter key={name} dataKey={name} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </ScatterChart>
      );
    }
    // column / bar share the BarChart engine; bar charts swap axis orientation.
    return (
      <BarChart
        data={rows}
        layout={isHorizontal ? "vertical" : "horizontal"}
        margin={{ top: 8, right: 16, bottom: 24, left: 8 }}
      >
        {commonAxes}
        {isHorizontal ? (
          <>
            <XAxis type="number" tick={{ fontSize: 11 }} />
            <YAxis type="category" dataKey="category" tick={{ fontSize: 11 }} />
          </>
        ) : (
          <>
            {categoryAxis}
            {valueAxis}
          </>
        )}
        {seriesNames.map((name, i) => (
          <Bar key={name} dataKey={name} fill={PALETTE[i % PALETTE.length]} />
        ))}
      </BarChart>
    );
  };

  const renderPie = () => {
    const seriesName = spec.series[0]?.name ?? "value";
    return (
      <PieChart>
        <Tooltip />
        <Legend />
        <Pie
          data={rows}
          dataKey={seriesName}
          nameKey="category"
          cx="50%"
          cy="50%"
          outerRadius="70%"
          label={{ fontSize: 11 }}
        >
          {rows.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
      </PieChart>
    );
  };

  return (
    <figure
      data-testid={`er-v2-3-chart-${spec.id}`}
      className="my-4 break-inside-avoid rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 pt-3 pb-2"
    >
      <div style={{ width: "100%", height: 280 }}>
        <ResponsiveContainer width="100%" height="100%">
          {showPie ? renderPie() : renderCartesian()}
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-[11.5px] text-[--color-text-secondary]">
        {caption}
        {spec.claim ? (
          <span className="ml-1 text-[--color-text-tertiary]">— {spec.claim}</span>
        ) : null}
      </figcaption>
    </figure>
  );
}
