import type {
  DashboardPayload,
  PanelId,
} from "../../api/panic-thermometer";
import { PANEL_CATALOG } from "../../lib/panic-thermometer/panel-catalog";
import { PanelCard } from "./PanelCard";

interface Props {
  dashboard: DashboardPayload | null;
  onPanelClick?: (id: PanelId) => void;
}

export function PanelGrid({ dashboard, onPanelClick }: Props): JSX.Element {
  return (
    <div
      data-testid="pt-panel-grid"
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
        gap: "0.75rem",
      }}
    >
      {PANEL_CATALOG.map((entry) => (
        <PanelCard
          key={entry.id}
          entry={entry}
          result={dashboard?.panels[entry.id]}
          onClick={onPanelClick}
        />
      ))}
    </div>
  );
}
