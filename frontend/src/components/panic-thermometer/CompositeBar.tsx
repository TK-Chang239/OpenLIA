import type { CompositeResult } from "../../api/panic-thermometer";

const LEVELS = ["calm", "elevated", "high", "severe", "crisis"] as const;

const LEVEL_COLORS: Record<(typeof LEVELS)[number], string> = {
  calm: "var(--color-feedback-success)",
  elevated: "var(--color-feedback-warning)",
  high: "var(--color-feedback-warning)",
  severe: "var(--color-feedback-error)",
  crisis: "var(--color-border-error)",
};

interface Props {
  composite: CompositeResult;
}

export function CompositeBar({ composite }: Props): JSX.Element {
  const activeIdx = LEVELS.indexOf(composite.level);
  return (
    <div
      role="status"
      aria-label={`Composite threat level: ${composite.level}`}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "0.5rem 1rem",
        borderRadius: "9999px",
        background: "var(--color-bg-elevated)",
      }}
    >
      <div style={{ display: "flex", gap: "4px", flex: 1 }}>
        {LEVELS.map((lvl, idx) => (
          <div
            key={lvl}
            data-testid={`composite-stop-${lvl}`}
            style={{
              flex: 1,
              height: "12px",
              borderRadius: "4px",
              background: idx <= activeIdx ? LEVEL_COLORS[lvl] : "var(--color-border-subtle)",
            }}
          />
        ))}
      </div>
      <div
        style={{
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: "0.08em",
          minWidth: "5rem",
          textAlign: "right",
        }}
      >
        {composite.level}
      </div>
      <div
        style={{
          fontVariantNumeric: "tabular-nums",
          color: "var(--color-text-secondary)",
        }}
      >
        {composite.red_count}/5 red
      </div>
    </div>
  );
}
