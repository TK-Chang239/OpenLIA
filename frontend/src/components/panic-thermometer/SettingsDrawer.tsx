import type { PtPreset, UserConfig } from "../../api/panic-thermometer";
import { PresetLibrary } from "./PresetLibrary";

interface Props {
  open: boolean;
  onClose: () => void;
  config: UserConfig | null;
  presets: PtPreset[];
  onApplyPreset: (id: string) => void;
  onDeletePreset: (id: string) => void;
  onExport: () => void;
  onImport: () => void;
}

export function SettingsDrawer({
  open,
  onClose,
  config,
  presets,
  onApplyPreset,
  onDeletePreset,
  onExport,
  onImport,
}: Props): JSX.Element | null {
  if (!open) return null;
  return (
    <aside
      role="dialog"
      aria-label="Panic Thermometer settings"
      data-testid="pt-settings-drawer"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "min(420px, 100%)",
        height: "100vh",
        background: "var(--color-surface, #111)",
        borderLeft: "1px solid var(--color-border, #2a2a2a)",
        padding: "1rem",
        overflowY: "auto",
        zIndex: 40,
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h3>Settings</h3>
        <button type="button" onClick={onClose}>
          Close
        </button>
      </div>
      <hr />
      <div>
        Composite mode:{" "}
        <strong>{config?.composite_settings.mode ?? "count"}</strong>
      </div>
      <hr />
      <PresetLibrary
        presets={presets}
        onApply={onApplyPreset}
        onDelete={onDeletePreset}
      />
      <hr />
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="button" onClick={onExport}>
          Export JSON
        </button>
        <button type="button" onClick={onImport}>
          Import JSON
        </button>
      </div>
    </aside>
  );
}
