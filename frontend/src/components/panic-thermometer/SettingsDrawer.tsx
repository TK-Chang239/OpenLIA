import { useState } from "react";
import type {
  PanelConfig,
  PanelId,
  PtPreset,
  UserConfig,
} from "../../api/panic-thermometer";
import { PanelSettingsPane } from "./PanelSettingsPane";
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
  onSaveConfig?: (cfg: Pick<UserConfig, "panel_config" | "composite_settings">) => void;
  onSaveAsPreset?: (name: string) => void;
  onRenamePreset?: (id: string, name: string) => void;
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
  onSaveConfig,
  onSaveAsPreset,
  onRenamePreset,
}: Props): JSX.Element | null {
  const [active, setActive] = useState<PanelId>("oil");

  if (!open) return null;

  const panelConfig = config?.panel_config.find((p) => p.panel_id === active) ?? null;
  const updatePanel = (next: PanelConfig) => {
    if (!config || !onSaveConfig) return;
    const merged = config.panel_config.map((p) =>
      p.panel_id === next.panel_id ? next : p,
    );
    onSaveConfig({ panel_config: merged, composite_settings: config.composite_settings });
  };

  return (
    <aside
      role="dialog"
      aria-label="Panic Thermometer settings"
      data-testid="pt-settings-drawer"
      style={{
        position: "fixed",
        top: 0,
        right: 0,
        width: "min(560px, 100%)",
        height: "100vh",
        background: "var(--color-bg-elevated)",
        borderLeft: "1px solid var(--color-border-subtle)",
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
      <div style={{ display: "flex", gap: "0.25rem", flexWrap: "wrap" }}>
        {(["oil", "inflation", "fed_language", "wage_growth", "diplomacy"] as PanelId[]).map(
          (id) => (
            <button
              key={id}
              type="button"
              data-testid={`tab-${id}`}
              onClick={() => setActive(id)}
              style={{
                fontWeight: active === id ? 600 : 400,
                background:
                  active === id ? "var(--color-bg-default)" : "transparent",
              }}
            >
              {id}
            </button>
          ),
        )}
      </div>
      <hr />
      {panelConfig ? (
        <PanelSettingsPane
          config={panelConfig}
          presets={presets}
          onChange={updatePanel}
          onApplyPreset={onApplyPreset}
        />
      ) : (
        <div>Loading panel config…</div>
      )}
      <hr />
      <PresetLibrary
        presets={presets}
        onApply={onApplyPreset}
        onDelete={onDeletePreset}
        onSaveAs={onSaveAsPreset}
        onRename={onRenamePreset}
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
