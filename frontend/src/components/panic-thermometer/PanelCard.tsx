import type {
  PanelId,
  PanelResult,
  PanelStatus,
} from "../../api/panic-thermometer";
import type { PanelCatalogEntry } from "../../lib/panic-thermometer/panel-catalog";

const STATUS_COLORS: Record<PanelStatus, string> = {
  green: "#1f9d55",
  amber: "#f2c94c",
  red: "#eb5757",
  dark_red: "#7a1f1f",
  disabled: "#4a4a4a",
};

interface Props {
  entry: PanelCatalogEntry;
  result: PanelResult | undefined;
  onClick?: (id: PanelId) => void;
}

export function PanelCard({ entry, result, onClick }: Props): JSX.Element {
  const status: PanelStatus = result?.status ?? "disabled";
  return (
    <button
      type="button"
      data-testid={`pt-panel-card-${entry.id}`}
      onClick={() => onClick?.(entry.id)}
      style={{
        display: "flex",
        flexDirection: "column",
        gap: "0.5rem",
        padding: "1rem",
        borderRadius: "12px",
        background: "var(--color-surface, #161617)",
        border: "1px solid var(--color-border, #2a2a2a)",
        color: "inherit",
        textAlign: "left",
        cursor: "pointer",
        minHeight: "120px",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontWeight: 600 }}>{entry.displayName}</span>
        <span
          data-testid={`pt-panel-status-${entry.id}`}
          style={{
            fontSize: "0.75rem",
            padding: "2px 8px",
            borderRadius: "9999px",
            background: STATUS_COLORS[status],
            textTransform: "uppercase",
            letterSpacing: "0.08em",
          }}
        >
          {status}
        </span>
      </div>
      <div style={{ color: "var(--color-text-muted, #9a9a9a)", fontSize: "0.85rem" }}>
        {result?.label ?? "(no data yet)"}
      </div>
    </button>
  );
}
