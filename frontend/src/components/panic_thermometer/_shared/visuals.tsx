import type { JSX } from "react";
import type {
  HeadlineFragment,
  PanelLine,
  PanelStatus,
  RuleRow,
  ParamRow,
  ScorecardEntry,
  Severity,
  Tone,
} from "../../../lib/panic_thermometer/copy/types";

export const SEVERITY_PILL_CLASS: Record<Severity, string> = {
  calm: "is-calm",
  elevated: "is-elevated",
  high: "is-high",
  severe: "is-severe",
  crisis: "is-crisis",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  calm: "Calm",
  elevated: "Elevated",
  high: "High",
  severe: "Severe",
  crisis: "Crisis",
};

export const STATUS_CLASS: Record<PanelStatus, string> = {
  green: "is-green",
  amber: "is-amber",
  red: "is-red",
  darkred: "is-darkred",
};

export const TONE_CLASS: Record<Tone, string> = {
  dovish: "is-dovish",
  neutral: "is-neutral",
  hawkish: "is-hawkish",
  crisis: "is-crisis",
};

export function PanelLineText({ line }: { line: PanelLine }): JSX.Element {
  return (
    <p className="pt-line">
      {line.parts.map((part, i) =>
        part.kind === "text" ? (
          <span key={i}>{part.value}</span>
        ) : (
          <strong key={i} className={part.tone ? `is-${part.tone}` : undefined}>
            {part.value}
          </strong>
        ),
      )}
    </p>
  );
}

export function HeadlineText({
  fragments,
}: {
  fragments: HeadlineFragment[];
}): JSX.Element {
  return (
    <span>
      {fragments.map((f, i) =>
        f.kind === "text" ? (
          <span key={i}>{f.value}</span>
        ) : (
          <mark key={i} className={`pt-mark ${TONE_CLASS[f.tone]}`}>
            {f.value}
          </mark>
        ),
      )}
    </span>
  );
}

export function RulesBlock({
  title,
  rules,
  onEdit,
}: {
  title: string;
  rules: RuleRow[];
  onEdit?: () => void;
}): JSX.Element {
  return (
    <div className="pt-rules" aria-label={title}>
      <div className="pt-rules-head">
        <span>{title}</span>
        {onEdit ? (
          <button type="button" className="pt-edit-link" onClick={onEdit}>
            + Edit
          </button>
        ) : null}
      </div>
      {rules.map((r, i) => (
        <div
          key={i}
          className={`pt-rule-row ${r.matched ? "is-match" : ""}`}
        >
          <span className={`pt-dot ${STATUS_CLASS[r.status]}`} />
          <span className="pt-formula">
            {r.formulaParts.map((p, j) => {
              if (p.kind === "var") return <b key={j}>{p.value}</b>;
              if (p.kind === "lit")
                return (
                  <em key={j}>
                    {p.value}
                    {p.gloss ? ` ${p.gloss}` : ""}
                  </em>
                );
              if (p.kind === "op") return <span key={j}> {p.value} </span>;
              return <span key={j}>{p.value}</span>;
            })}
          </span>
          <span className="pt-check">{r.check}</span>
        </div>
      ))}
    </div>
  );
}

export function ParamsBlock({
  title,
  params,
  presetLabel,
}: {
  title: string;
  params: ParamRow[];
  presetLabel?: string;
}): JSX.Element {
  return (
    <div className="pt-params">
      <div className="pt-params-head">
        <span>{title}</span>
        {presetLabel ? <span>{presetLabel}</span> : null}
      </div>
      {params.map((p) => (
        <div key={p.key} className="pt-param-row">
          <span className="pt-k">{p.key}</span>
          <span className="pt-vv">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

/** Generic area-spark used by simple scorecards. */
export function MiniSparkArea({
  points,
  threshold,
  stroke,
  fill,
}: {
  points: number[];
  threshold?: number;
  stroke: string;
  fill: string;
}): JSX.Element {
  if (points.length === 0) {
    return <svg className="pt-mini" viewBox="0 0 100 28" preserveAspectRatio="none" />;
  }
  const stepX = 100 / (points.length - 1);
  const path = points
    .map((y, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(1)},${y}`)
    .join(" ");
  const fillPath = `${path} L100,28 L0,28 Z`;
  return (
    <svg className="pt-mini" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
      <path d={fillPath} fill={fill} />
      <path
        className="pt-mini-line"
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth={1.4}
      />
      {threshold !== undefined ? (
        <line
          x1={0}
          y1={threshold}
          x2={100}
          y2={threshold}
          stroke={stroke}
          strokeWidth={0.6}
          strokeDasharray="2 2"
          opacity={0.7}
        />
      ) : null}
    </svg>
  );
}

export function MiniBars({
  bars,
  threshold,
  thresholdStroke,
}: {
  bars: NonNullable<ScorecardEntry["miniChart"]["bars"]>;
  threshold?: number;
  thresholdStroke?: string;
}): JSX.Element {
  const colorMap: Record<PanelStatus, string> = {
    green: "var(--color-feedback-success)",
    amber: "var(--color-feedback-warning)",
    red: "var(--color-feedback-error)",
    darkred: "var(--pt-darkred)",
  };
  const stepX = 100 / bars.length;
  return (
    <svg className="pt-mini" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
      {bars.map((b, i) => (
        <rect
          key={i}
          x={i * stepX + 0.5}
          y={28 - b.value}
          width={stepX - 1}
          height={b.value}
          fill={colorMap[b.status]}
        />
      ))}
      {threshold !== undefined ? (
        <line
          x1={0}
          y1={threshold}
          x2={100}
          y2={threshold}
          stroke={thresholdStroke ?? "var(--color-feedback-error)"}
          strokeWidth={0.6}
          strokeDasharray="2 2"
        />
      ) : null}
    </svg>
  );
}

export function MiniStripes({
  stripes,
}: {
  stripes: NonNullable<ScorecardEntry["miniChart"]["stripes"]>;
}): JSX.Element {
  const colorMap: Record<string, string> = {
    green: "var(--color-feedback-success)",
    amber: "var(--color-feedback-warning)",
    red: "var(--color-feedback-error)",
    darkred: "var(--pt-darkred)",
    neutral: "var(--color-text-secondary)",
  };
  return (
    <div
      style={{ display: "flex", gap: 4, paddingTop: 4 }}
      aria-hidden="true"
    >
      {stripes.map((s, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: 4,
            background: colorMap[s.status] ?? "var(--color-text-secondary)",
            opacity: s.intensity ?? 1,
            borderRadius: 1,
          }}
        />
      ))}
    </div>
  );
}

export function MiniProgress({
  pct,
}: {
  pct: number;
}): JSX.Element {
  return (
    <div
      style={{
        height: 8,
        background: "var(--color-bg-code)",
        borderRadius: 4,
        position: "relative",
        overflow: "hidden",
      }}
      aria-hidden="true"
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          bottom: 0,
          width: `${pct}%`,
          background:
            "linear-gradient(90deg, var(--color-feedback-success) 0%, var(--color-feedback-warning) 100%)",
          borderRadius: 4,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: `${pct}%`,
          top: -2,
          bottom: -2,
          width: 2,
          background: "var(--color-text-primary)",
          borderRadius: 1,
        }}
      />
    </div>
  );
}
