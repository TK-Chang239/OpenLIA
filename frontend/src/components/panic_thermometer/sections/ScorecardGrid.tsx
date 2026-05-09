import type { JSX } from "react";
import type { ScorecardEntry } from "../../../lib/panic_thermometer/copy/types";
import {
  MiniBars,
  MiniProgress,
  MiniSparkArea,
  MiniStripes,
  STATUS_CLASS,
} from "../_shared/visuals";

interface Props {
  entries: ScorecardEntry[];
}

const SPARK_COLORS: Record<string, { stroke: string; fill: string }> = {
  red: { stroke: "var(--color-feedback-error)", fill: "rgba(var(--pt-feedback-error-rgb),0.12)" },
  amber: {
    stroke: "var(--color-feedback-warning)",
    fill: "rgba(var(--pt-feedback-warning-rgb),0.14)",
  },
  green: {
    stroke: "var(--color-feedback-success)",
    fill: "rgba(var(--pt-feedback-success-rgb),0.14)",
  },
  darkred: {
    stroke: "var(--pt-darkred)",
    fill: "rgba(var(--pt-darkred-rgb),0.14)",
  },
};

export function ScorecardGrid({ entries }: Props): JSX.Element {
  return (
    <>
      <div className="pt-sec-label is-first">
        <span>Indicator scorecards</span>
        <span className="pt-ln" />
        <span className="pt-count">{entries.length} panels · click to drill in</span>
      </div>

      <div className="pt-grid5" role="list">
        {entries.map((e) => (
          <a
            key={e.panelId}
            className={`pt-pcard ${STATUS_CLASS[e.status]}`}
            href={`#${e.panelId}`}
            role="listitem"
            data-testid={`pt-scorecard-${e.panelId}`}
          >
            <div className="pt-pcard-head">
              <span className="pt-ix">{e.index}</span>
              <span className="pt-stamp">{e.stampLabel}</span>
            </div>
            <div className="pt-nm">{e.title}</div>
            <div className="pt-v">
              {e.primaryValue}
              {e.primaryUnit ? <small>{e.primaryUnit}</small> : null}
            </div>
            {renderMini(e)}
            <div className="pt-det">
              {e.detail.map((part, i) =>
                part.kind === "text" ? (
                  <span key={i}>{part.value}</span>
                ) : (
                  <strong key={i} className={part.tone ? `is-${part.tone}` : undefined}>
                    {part.value}
                  </strong>
                ),
              )}
            </div>
          </a>
        ))}
      </div>
    </>
  );
}

function renderMini(e: ScorecardEntry): JSX.Element {
  const colors = SPARK_COLORS[e.status] ?? SPARK_COLORS.red;
  if (e.miniChart.kind === "spark-area" && e.miniChart.points) {
    return (
      <MiniSparkArea
        points={e.miniChart.points}
        threshold={e.miniChart.threshold}
        stroke={colors.stroke}
        fill={colors.fill}
      />
    );
  }
  if (e.miniChart.kind === "bars" && e.miniChart.bars) {
    return <MiniBars bars={e.miniChart.bars} threshold={e.miniChart.threshold} />;
  }
  if (e.miniChart.kind === "stripe-bars" && e.miniChart.stripes) {
    return <MiniStripes stripes={e.miniChart.stripes} />;
  }
  if (e.miniChart.kind === "progress" && e.miniChart.progressPct !== undefined) {
    return <MiniProgress pct={e.miniChart.progressPct} />;
  }
  return <div />;
}
