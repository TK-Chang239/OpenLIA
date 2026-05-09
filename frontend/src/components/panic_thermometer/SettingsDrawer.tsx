import type { JSX } from "react";
import { useEffect, useState } from "react";
import {
  createPreset,
  exportConfig,
  importConfig,
  parseFormula,
  type CompositeSettings,
  type PanelConfig,
  type PanelId as PtBackendPanelId,
  type UserConfig,
} from "../../api/panic-thermometer";
import { usePtConfig } from "../../hooks/usePtConfig";
import { usePtPresets } from "../../hooks/usePtPresets";

type Tab = "presets" | "panels" | "composite" | "data";

interface Props {
  open: boolean;
  onClose: () => void;
  refreshIntervalSeconds: number | null;
  onRefreshIntervalChange: (s: number | null) => void;
}

const REFRESH_OPTIONS: Array<{ label: string; value: number | null }> = [
  { label: "Auto-refresh · Off", value: null },
  { label: "Auto-refresh · 1 min", value: 60 },
  { label: "Auto-refresh · 5 min", value: 300 },
  { label: "Auto-refresh · 15 min", value: 900 },
];

const PANEL_TITLES: Record<PtBackendPanelId, string> = {
  oil: "D1 · Oil price duration",
  inflation: "D2 · Inflation expectations",
  fed_language: "D3 · Fed language tracker",
  wage_growth: "D4 · Wage growth",
  diplomacy: "D5 · Diplomatic progress",
};

const STATUS_LABEL: Record<string, string> = {
  green: "Green",
  amber: "Amber",
  red: "Red",
  dark_red: "Dark red",
  disabled: "Off",
};

export function SettingsDrawer({
  open,
  onClose,
  refreshIntervalSeconds,
  onRefreshIntervalChange,
}: Props): JSX.Element | null {
  const cfg = usePtConfig();
  const presets = usePtPresets();
  const [tab, setTab] = useState<Tab>("presets");
  const [importText, setImportText] = useState<string>("");
  const [importError, setImportError] = useState<string | null>(null);
  const [newPresetName, setNewPresetName] = useState<string>("");
  const [openPanelId, setOpenPanelId] = useState<PtBackendPanelId | null>(null);
  const [formulaText, setFormulaText] = useState<string>("");
  const [formulaError, setFormulaError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setImportText("");
      setImportError(null);
      setNewPresetName("");
      setFormulaError(null);
    }
  }, [open]);

  if (!open) return null;

  const onApplyPreset = async (id: string) => {
    await presets.apply(id);
    await cfg.refresh();
  };

  const onSaveAsPreset = async () => {
    if (!newPresetName.trim()) return;
    await createPreset(newPresetName.trim(), null);
    await presets.refresh();
    setNewPresetName("");
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

  const onImport = async () => {
    setImportError(null);
    let parsed: unknown;
    try {
      parsed = JSON.parse(importText);
    } catch {
      setImportError("Invalid JSON");
      return;
    }
    try {
      await importConfig(parsed);
      await cfg.refresh();
      setImportText("");
    } catch (err) {
      setImportError(err instanceof Error ? err.message : String(err));
    }
  };

  const onTestFormula = async () => {
    setFormulaError(null);
    try {
      const res = await parseFormula(formulaText, "oil");
      if (!res.ok) {
        setFormulaError(
          res.errors?.[0]?.message ?? "Formula failed to parse",
        );
      } else {
        setFormulaError(`OK — ${(res.identifiers ?? []).join(", ") || "no identifiers"}`);
      }
    } catch (err) {
      setFormulaError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <>
      <div
        className="pt-drawer-backdrop"
        onClick={onClose}
        aria-hidden="true"
      />
      <aside
        className="pt-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Panic Thermometer settings"
      >
        <div className="pt-drawer-head">
          <h2>Settings</h2>
          <button
            type="button"
            className="pt-close"
            onClick={onClose}
            aria-label="Close settings"
          >
            ×
          </button>
        </div>

        <div className="pt-drawer-tabs" role="tablist">
          {([
            ["presets", "Presets"],
            ["panels", "Panels"],
            ["composite", "Composite"],
            ["data", "Data"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`pt-drawer-tab ${tab === id ? "is-active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="pt-drawer-body" role="tabpanel">
          {tab === "presets" ? (
            <PresetsTab
              presets={presets.presets}
              activePresetId={cfg.config?.active_preset_id ?? null}
              onApply={onApplyPreset}
              onRename={(id, name) =>
                presets.rename(id, { name, description: null }).then(() => undefined)
              }
              onRemove={presets.remove}
              newPresetName={newPresetName}
              onNewPresetNameChange={setNewPresetName}
              onSaveAs={onSaveAsPreset}
            />
          ) : null}

          {tab === "panels" ? (
            <PanelsTab
              config={cfg.config}
              openPanelId={openPanelId}
              onTogglePanel={(id) =>
                setOpenPanelId((prev) => (prev === id ? null : id))
              }
              onSave={cfg.save}
            />
          ) : null}

          {tab === "composite" ? (
            <CompositeTab
              config={cfg.config}
              onSave={cfg.save}
              formulaText={formulaText}
              onFormulaTextChange={setFormulaText}
              onTestFormula={onTestFormula}
              formulaError={formulaError}
            />
          ) : null}

          {tab === "data" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="pt-drawer-row">
                <label htmlFor="pt-refresh-select">Auto-refresh interval</label>
                <select
                  id="pt-refresh-select"
                  value={refreshIntervalSeconds ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    onRefreshIntervalChange(v === "" ? null : Number(v));
                  }}
                >
                  {REFRESH_OPTIONS.map((opt) => (
                    <option key={opt.label} value={opt.value ?? ""}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-drawer-actions">
                <button type="button" className="pt-drawer-btn" onClick={onExport}>
                  Export config
                </button>
              </div>

              <div className="pt-drawer-row">
                <label htmlFor="pt-import-text">Import config (JSON)</label>
                <textarea
                  id="pt-import-text"
                  value={importText}
                  onChange={(e) => setImportText(e.target.value)}
                  placeholder='{"version": 1, ...}'
                />
                {importError ? (
                  <div className="pt-drawer-error" role="alert">
                    {importError}
                  </div>
                ) : null}
                <div className="pt-drawer-actions">
                  <button
                    type="button"
                    className="pt-drawer-btn is-primary"
                    onClick={onImport}
                    disabled={!importText.trim()}
                  >
                    Import
                  </button>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </aside>
    </>
  );
}

function PresetsTab({
  presets,
  activePresetId,
  onApply,
  onRename,
  onRemove,
  newPresetName,
  onNewPresetNameChange,
  onSaveAs,
}: {
  presets: ReadonlyArray<{
    id: string;
    name: string;
    is_shipped: boolean;
  }>;
  activePresetId: string | null;
  onApply: (id: string) => Promise<void>;
  onRename: (id: string, name: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  newPresetName: string;
  onNewPresetNameChange: (v: string) => void;
  onSaveAs: () => Promise<void>;
}): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="pt-drawer-row">
        <label>Available presets</label>
        {presets.length === 0 ? (
          <span style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
            No presets yet
          </span>
        ) : (
          presets.map((p) => (
            <div
              key={p.id}
              className={`pt-preset-row ${
                p.id === activePresetId ? "is-active" : ""
              }`}
            >
              <span className="pt-preset-name">{p.name}</span>
              {p.is_shipped ? (
                <span className="pt-preset-tag">shipped</span>
              ) : null}
              <button
                type="button"
                className="pt-drawer-btn"
                onClick={() => void onApply(p.id)}
                disabled={p.id === activePresetId}
              >
                {p.id === activePresetId ? "Active" : "Apply"}
              </button>
              {!p.is_shipped ? (
                <button
                  type="button"
                  className="pt-drawer-btn is-danger"
                  onClick={() => {
                    const next = window.prompt("Rename preset", p.name);
                    if (next && next.trim() && next.trim() !== p.name) {
                      void onRename(p.id, next.trim());
                    } else {
                      void onRemove(p.id);
                    }
                  }}
                >
                  ⋯
                </button>
              ) : null}
            </div>
          ))
        )}
      </div>

      <div className="pt-drawer-row">
        <label htmlFor="pt-new-preset">Save current config as preset</label>
        <input
          id="pt-new-preset"
          type="text"
          value={newPresetName}
          onChange={(e) => onNewPresetNameChange(e.target.value)}
          placeholder="e.g. Recession-watch"
        />
        <div className="pt-drawer-actions">
          <button
            type="button"
            className="pt-drawer-btn is-primary"
            onClick={() => void onSaveAs()}
            disabled={!newPresetName.trim()}
          >
            Save as preset
          </button>
        </div>
      </div>
    </div>
  );
}

function PanelsTab({
  config,
  openPanelId,
  onTogglePanel,
  onSave,
}: {
  config: UserConfig | null;
  openPanelId: PtBackendPanelId | null;
  onTogglePanel: (id: PtBackendPanelId) => void;
  onSave: (
    next: Pick<UserConfig, "panel_config" | "composite_settings">,
  ) => Promise<void>;
}): JSX.Element {
  if (!config) {
    return (
      <div style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
        Loading config…
      </div>
    );
  }

  const panels = config.panel_config;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {panels.map((p) => {
        const isOpen = p.panel_id === openPanelId;
        return (
          <div key={p.panel_id} className="pt-panel-acc">
            <button
              type="button"
              className="pt-panel-acc-head"
              onClick={() => onTogglePanel(p.panel_id)}
              aria-expanded={isOpen}
            >
              <span className="pt-acc-num">{p.panel_id.toUpperCase()}</span>
              <span>{PANEL_TITLES[p.panel_id]}</span>
              <span className="pt-acc-status">
                {p.enabled === false ? "Off" : "On"}
              </span>
            </button>
            {isOpen ? (
              <div className="pt-panel-acc-body">
                <PanelEditor
                  panel={p}
                  onChange={async (next) => {
                    const updated = panels.map((q) =>
                      q.panel_id === p.panel_id ? next : q,
                    );
                    await onSave({
                      panel_config: updated,
                      composite_settings: config.composite_settings,
                    });
                  }}
                />
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

function PanelEditor({
  panel,
  onChange,
}: {
  panel: PanelConfig;
  onChange: (next: PanelConfig) => Promise<void>;
}): JSX.Element {
  const [draft, setDraft] = useState<PanelConfig>(panel);

  useEffect(() => {
    setDraft(panel);
  }, [panel]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(panel);

  return (
    <>
      <div className="pt-drawer-row">
        <label>Rules</label>
        {draft.rules.length === 0 ? (
          <span style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
            No rules
          </span>
        ) : (
          draft.rules.map((r, i) => (
            <div
              key={i}
              style={{
                display: "grid",
                gridTemplateColumns: "80px 1fr",
                gap: 6,
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              <span style={{ color: "var(--color-text-tertiary)" }}>
                {STATUS_LABEL[r.status] ?? r.status}
              </span>
              <input
                type="text"
                value={r.formula}
                onChange={(e) => {
                  const rules = draft.rules.map((rr, j) =>
                    j === i ? { ...rr, formula: e.target.value } : rr,
                  );
                  setDraft({ ...draft, rules });
                }}
              />
            </div>
          ))
        )}
      </div>

      <div className="pt-drawer-row">
        <label>Streak condition</label>
        <input
          type="text"
          value={draft.streak_condition ?? ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              streak_condition: e.target.value || null,
            })
          }
          placeholder="(optional)"
        />
      </div>

      <div className="pt-drawer-row">
        <label>
          <input
            type="checkbox"
            checked={draft.enabled !== false}
            onChange={(e) =>
              setDraft({ ...draft, enabled: e.target.checked })
            }
            style={{ marginRight: 8 }}
          />
          Enabled
        </label>
      </div>

      <div className="pt-drawer-actions">
        <button
          type="button"
          className="pt-drawer-btn is-primary"
          onClick={() => void onChange(draft)}
          disabled={!dirty}
        >
          Save
        </button>
        <button
          type="button"
          className="pt-drawer-btn"
          onClick={() => setDraft(panel)}
          disabled={!dirty}
        >
          Reset
        </button>
      </div>
    </>
  );
}

function CompositeTab({
  config,
  onSave,
  formulaText,
  onFormulaTextChange,
  onTestFormula,
  formulaError,
}: {
  config: UserConfig | null;
  onSave: (next: Pick<UserConfig, "panel_config" | "composite_settings">) => Promise<void>;
  formulaText: string;
  onFormulaTextChange: (v: string) => void;
  onTestFormula: () => Promise<void>;
  formulaError: string | null;
}): JSX.Element {
  const [draft, setDraft] = useState<CompositeSettings | null>(
    config?.composite_settings ?? null,
  );

  useEffect(() => {
    setDraft(config?.composite_settings ?? null);
  }, [config]);

  if (!config || !draft) {
    return (
      <div style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
        Loading config…
      </div>
    );
  }

  const dirty =
    JSON.stringify(draft) !== JSON.stringify(config.composite_settings);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="pt-drawer-row">
        <label htmlFor="pt-mode">Composite mode</label>
        <select
          id="pt-mode"
          value={draft.mode}
          onChange={(e) =>
            setDraft({ ...draft, mode: e.target.value as "count" | "weighted" })
          }
        >
          <option value="count">count</option>
          <option value="weighted">weighted</option>
        </select>
      </div>

      <div className="pt-drawer-row">
        <label htmlFor="pt-red-threshold">Red threshold</label>
        <input
          id="pt-red-threshold"
          type="number"
          step={0.1}
          value={draft.red_threshold ?? ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              red_threshold: e.target.value === "" ? undefined : Number(e.target.value),
            })
          }
        />
      </div>

      <div className="pt-drawer-actions">
        <button
          type="button"
          className="pt-drawer-btn is-primary"
          onClick={() =>
            void onSave({
              panel_config: config.panel_config,
              composite_settings: draft,
            })
          }
          disabled={!dirty}
        >
          Save composite
        </button>
        <button
          type="button"
          className="pt-drawer-btn"
          onClick={() => setDraft(config.composite_settings)}
          disabled={!dirty}
        >
          Reset
        </button>
      </div>

      <div className="pt-drawer-row">
        <label htmlFor="pt-formula-text">Test panel formula</label>
        <textarea
          id="pt-formula-text"
          value={formulaText}
          onChange={(e) => onFormulaTextChange(e.target.value)}
          placeholder="e.g. streak_days >= streak_red"
        />
        <div className="pt-drawer-actions">
          <button
            type="button"
            className="pt-drawer-btn"
            onClick={() => void onTestFormula()}
            disabled={!formulaText.trim()}
          >
            Parse
          </button>
        </div>
        {formulaError ? (
          <div className="pt-drawer-error" role="alert">
            {formulaError}
          </div>
        ) : null}
      </div>
    </div>
  );
}
