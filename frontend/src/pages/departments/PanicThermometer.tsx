import { useMemo, useState } from "react";
import {
  exportConfig,
  importConfig,
  type PanelId,
} from "../../api/panic-thermometer";
import { CompositeBar } from "../../components/panic-thermometer/CompositeBar";
import { PanelGrid } from "../../components/panic-thermometer/PanelGrid";
import { SettingsDrawer } from "../../components/panic-thermometer/SettingsDrawer";
import { usePtConfig } from "../../hooks/usePtConfig";
import { usePtDashboard } from "../../hooks/usePtDashboard";
import { usePtPresets } from "../../hooks/usePtPresets";

const REFRESH_OPTIONS: Array<{ label: string; seconds: number | null }> = [
  { label: "Off", seconds: null },
  { label: "1 min", seconds: 60 },
  { label: "5 min", seconds: 300 },
  { label: "15 min", seconds: 900 },
];

export default function PanicThermometer(): JSX.Element {
  const [intervalSeconds, setIntervalSeconds] = useState<number | null>(300);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const dashboard = usePtDashboard(intervalSeconds);
  const cfg = usePtConfig();
  const presets = usePtPresets();

  const onPanelClick = (id: PanelId) => {
    const el = document.getElementById(`panel-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const onApplyPreset = async (id: string) => {
    await presets.apply(id);
    await cfg.refresh();
    await dashboard.refresh();
  };

  const onDeletePreset = async (id: string) => {
    await presets.remove(id);
  };

  const onExport = async () => {
    const payload = await exportConfig();
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "panic-thermometer-config.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const onImport = () => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const text = await file.text();
      try {
        const parsed: unknown = JSON.parse(text);
        await importConfig(parsed);
        await cfg.refresh();
        await dashboard.refresh();
      } catch (err) {
        console.error("pt import failed", err);
      }
    };
    input.click();
  };

  const composite = dashboard.data?.composite;
  const warnings = useMemo(() => dashboard.data?.warnings ?? [], [dashboard.data]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem", padding: "1rem" }}>
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <h1 style={{ margin: 0 }}>Panic Thermometer</h1>
        <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
          <label htmlFor="pt-refresh">Auto-refresh</label>
          <select
            id="pt-refresh"
            value={intervalSeconds ?? ""}
            onChange={(e) => {
              const val = e.target.value;
              setIntervalSeconds(val === "" ? null : Number(val));
            }}
          >
            {REFRESH_OPTIONS.map((opt) => (
              <option key={opt.label} value={opt.seconds ?? ""}>
                {opt.label}
              </option>
            ))}
          </select>
          <button type="button" onClick={() => setDrawerOpen((v) => !v)}>
            Settings
          </button>
        </div>
      </header>

      {dashboard.error ? (
        <div role="alert" style={{ color: "#eb5757" }}>
          Failed to load dashboard: {dashboard.error.message}
        </div>
      ) : null}

      {composite ? <CompositeBar composite={composite} /> : null}

      <PanelGrid dashboard={dashboard.data} onPanelClick={onPanelClick} />

      {warnings.length > 0 ? (
        <details>
          <summary>{warnings.length} warning(s)</summary>
          <ul>
            {warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </details>
      ) : null}

      <SettingsDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        config={cfg.config}
        presets={presets.presets}
        onApplyPreset={onApplyPreset}
        onDeletePreset={onDeletePreset}
        onExport={onExport}
        onImport={onImport}
      />
    </div>
  );
}
