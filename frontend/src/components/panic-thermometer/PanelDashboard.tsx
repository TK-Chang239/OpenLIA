import { type ReactNode, useState } from "react";
import type { PanelId, PanelResult } from "../../api/panic-thermometer";

interface Props {
  id: PanelId;
  title: string;
  result: PanelResult | undefined;
  generatedAt?: string;
  children: ReactNode;
  onOpenSettings?: (id: PanelId) => void;
}

export function PanelDashboard({
  id,
  title,
  result,
  generatedAt,
  children,
  onOpenSettings,
}: Props): JSX.Element {
  const [warnOpen, setWarnOpen] = useState<boolean>(false);
  const warnings = result?.warnings ?? [];

  return (
    <section
      id={`panel-${id}`}
      data-testid={`panel-dashboard-${id}`}
      style={{
        padding: "1rem",
        border: "1px solid var(--color-border-subtle)",
        borderRadius: 12,
        background: "var(--color-bg-elevated)",
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h3 style={{ margin: 0 }}>{title}</h3>
        <span style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          {generatedAt ? (
            <small style={{ color: "var(--color-text-secondary)" }}>
              {new Date(generatedAt).toLocaleTimeString()}
            </small>
          ) : null}
          <button
            type="button"
            data-testid={`panel-settings-${id}`}
            onClick={() => onOpenSettings?.(id)}
            aria-label={`Open settings for ${title}`}
          >
            ⚙
          </button>
        </span>
      </header>
      {warnings.length > 0 ? (
        <button
          type="button"
          data-testid={`panel-warnings-${id}`}
          onClick={() => setWarnOpen((v) => !v)}
          style={{
            color: "var(--color-feedback-warning)",
            textAlign: "left",
            background: "transparent",
            border: 0,
            padding: 0,
            cursor: "pointer",
          }}
        >
          {warnings.length} warning{warnings.length === 1 ? "" : "s"}
        </button>
      ) : null}
      {warnOpen ? (
        <ul style={{ margin: 0, paddingLeft: "1.25rem", fontSize: "0.85rem" }}>
          {warnings.map((w, i) => (
            <li key={i}>{w}</li>
          ))}
        </ul>
      ) : null}
      <div>{children}</div>
    </section>
  );
}
