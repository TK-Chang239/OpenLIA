import { useEffect, useMemo, useState } from "react";
import {
  createPreset,
  exportConfig,
  importConfig,
  saveConfig,
  updatePreset,
  type PanelId,
} from "../../api/panic-thermometer";
import { CompositeBar } from "../../components/panic-thermometer/CompositeBar";
import { DiplomacyDashboard } from "../../components/panic-thermometer/DiplomacyDashboard";
import { FedLanguageDashboard } from "../../components/panic-thermometer/FedLanguageDashboard";
import { ImportExportModal } from "../../components/panic-thermometer/ImportExportModal";
import { InflationDashboard } from "../../components/panic-thermometer/InflationDashboard";
import { OilDashboard } from "../../components/panic-thermometer/OilDashboard";
import { PanelDashboard } from "../../components/panic-thermometer/PanelDashboard";
import { PanelGrid } from "../../components/panic-thermometer/PanelGrid";
import { SettingsDrawer } from "../../components/panic-thermometer/SettingsDrawer";
import { WageGrowthDashboard } from "../../components/panic-thermometer/WageGrowthDashboard";
import { usePtConfig } from "../../hooks/usePtConfig";
import { usePtDashboard } from "../../hooks/usePtDashboard";
import { usePtPresets } from "../../hooks/usePtPresets";
import { readShareLinkFromUrl } from "../../lib/panic-thermometer/share-link";

const REFRESH_OPTIONS: Array<{ label: string; seconds: number | null }> = [
  { label: "Off", seconds: null },
  { label: "1 min", seconds: 60 },
  { label: "5 min", seconds: 300 },
  { label: "15 min", seconds: 900 },
];

const PANEL_TITLES: Record<PanelId, string> = {
  oil: "Oil Price Duration",
  inflation: "Inflation Expectations",
  fed_language: "Fed Language Tracker",
  wage_growth: "Wage Growth",
  diplomacy: "Diplomatic Progress",
};

export default function PanicThermometer(): JSX.Element {
  const [intervalSeconds, setIntervalSeconds] = useState<number | null>(300);
  const [drawerOpen, setDrawerOpen] = useState<boolean>(false);
  const [importOpen, setImportOpen] = useState<boolean>(false);
  const dashboard = usePtDashboard(intervalSeconds);
  const cfg = usePtConfig();
  const presets = usePtPresets();

  // Hydrate from share-link on mount.
  useEffect(() => {
    const shared = readShareLinkFromUrl();
    if (shared && typeof shared === "object") {
      void importConfig(shared).then(() => {
        void cfg.refresh();
        void dashboard.refresh();
      });
    }
    // Run only once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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

  const onSaveAsPreset = async (name: string) => {
    await createPreset(name, null);
    await presets.refresh();
  };

  const onRenamePreset = async (id: string, name: string) => {
    await updatePreset(id, { name, description: null });
    await presets.refresh();
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

  const onImport = () => setImportOpen(true);
  const onImportSubmit = async (payload: unknown) => {
    await importConfig(payload);
    await cfg.refresh();
    await dashboard.refresh();
  };

  const onSaveConfig = async (
    next: Pick<typeof cfg.config & {}, "panel_config" | "composite_settings">,
  ) => {
    await saveConfig(next);
    await cfg.refresh();
    await dashboard.refresh();
  };

  const composite = dashboard.data?.composite;
  const warnings = useMemo(() => dashboard.data?.warnings ?? [], [dashboard.data]);
  const panels = dashboard.data?.panels;

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
        <div role="alert" style={{ color: "var(--color-feedback-error)" }}>
          Failed to load dashboard: {dashboard.error.message}
        </div>
      ) : null}

      {composite ? <CompositeBar composite={composite} /> : null}

      <PanelGrid dashboard={dashboard.data} onPanelClick={onPanelClick} />

      <PanelDashboard
        id="oil"
        title={PANEL_TITLES.oil}
        result={panels?.oil}
        generatedAt={dashboard.data?.generated_at}
        onOpenSettings={() => setDrawerOpen(true)}
      >
        <OilDashboard result={panels?.oil} />
      </PanelDashboard>

      <PanelDashboard
        id="inflation"
        title={PANEL_TITLES.inflation}
        result={panels?.inflation}
        generatedAt={dashboard.data?.generated_at}
        onOpenSettings={() => setDrawerOpen(true)}
      >
        <InflationDashboard result={panels?.inflation} />
      </PanelDashboard>

      <PanelDashboard
        id="fed_language"
        title={PANEL_TITLES.fed_language}
        result={panels?.fed_language}
        generatedAt={dashboard.data?.generated_at}
        onOpenSettings={() => setDrawerOpen(true)}
      >
        <FedLanguageDashboard result={panels?.fed_language} />
      </PanelDashboard>

      <PanelDashboard
        id="wage_growth"
        title={PANEL_TITLES.wage_growth}
        result={panels?.wage_growth}
        generatedAt={dashboard.data?.generated_at}
        onOpenSettings={() => setDrawerOpen(true)}
      >
        <WageGrowthDashboard result={panels?.wage_growth} />
      </PanelDashboard>

      <PanelDashboard
        id="diplomacy"
        title={PANEL_TITLES.diplomacy}
        result={panels?.diplomacy}
        generatedAt={dashboard.data?.generated_at}
        onOpenSettings={() => setDrawerOpen(true)}
      >
        <DiplomacyDashboard result={panels?.diplomacy} />
      </PanelDashboard>

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
        onSaveConfig={onSaveConfig}
        onSaveAsPreset={onSaveAsPreset}
        onRenamePreset={onRenamePreset}
      />

      <ImportExportModal
        open={importOpen}
        onClose={() => setImportOpen(false)}
        onImport={onImportSubmit}
        exportPayload={cfg.config}
      />
    </div>
  );
}
