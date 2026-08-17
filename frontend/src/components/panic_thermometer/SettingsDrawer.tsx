import type { JSX } from "react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  createPreset,
  exportConfig,
  importConfig,
  parseFormula,
  type CompositeSettings,
  type PanelConfig,
  type PanelId as PtBackendPanelId,
  type PanelStatus,
  type UserConfig,
} from "../../api/panic-thermometer";
import { usePtConfig } from "../../hooks/usePtConfig";
import { usePtPresets } from "../../hooks/usePtPresets";

type Tab = "presets" | "panels" | "composite" | "data";

type FocusSection = "rules" | "keywords" | "milestone" | "override";

export interface DrawerFocus {
  panelId: PtBackendPanelId;
  section?: FocusSection;
}

interface Props {
  open: boolean;
  onClose: () => void;
  refreshIntervalSeconds: number | null;
  onRefreshIntervalChange: (s: number | null) => void;
  focus?: DrawerFocus | null;
}

const REFRESH_OPTIONS: Array<{ key: string; value: number | null }> = [
  { key: "panic_thermometer.settings_drawer.refresh_off", value: null },
  { key: "panic_thermometer.settings_drawer.refresh_1", value: 60 },
  { key: "panic_thermometer.settings_drawer.refresh_5", value: 300 },
  { key: "panic_thermometer.settings_drawer.refresh_15", value: 900 },
];

const PANEL_TITLE_KEY: Record<PtBackendPanelId, string> = {
  oil: "panic_thermometer.settings_drawer.panel_oil",
  inflation: "panic_thermometer.settings_drawer.panel_inflation",
  fed_language: "panic_thermometer.settings_drawer.panel_fed",
  wage_growth: "panic_thermometer.settings_drawer.panel_wage",
  diplomacy: "panic_thermometer.settings_drawer.panel_diplomacy",
};

const STATUS_KEY: Record<string, string> = {
  green: "panic_thermometer.settings_drawer.status_green",
  amber: "panic_thermometer.settings_drawer.status_amber",
  red: "panic_thermometer.settings_drawer.status_red",
  dark_red: "panic_thermometer.settings_drawer.status_dark_red",
  disabled: "panic_thermometer.settings_drawer.status_disabled",
};

const OVERRIDE_STATUSES: PanelStatus[] = [
  "green",
  "amber",
  "red",
  "dark_red",
  "disabled",
];

/** Fed keyword lists live in panel params as plain string arrays. */
const FED_KEYWORD_FIELDS: Array<{ paramKey: string; labelKey: string }> = [
  { paramKey: "dovish_keywords", labelKey: "panic_thermometer.fed_section.tone_dovish" },
  { paramKey: "neutral_keywords", labelKey: "panic_thermometer.fed_section.tone_neutral" },
  { paramKey: "hawkish_keywords", labelKey: "panic_thermometer.fed_section.tone_hawkish" },
  { paramKey: "crisis_keywords", labelKey: "panic_thermometer.fed_section.tone_crisis" },
];

function paramStringList(params: Record<string, unknown>, key: string): string[] {
  const v = params[key];
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

export function SettingsDrawer({
  open,
  onClose,
  refreshIntervalSeconds,
  onRefreshIntervalChange,
  focus,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
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

  // When opened with a focus target, jump to the Panels tab and expand the
  // requested panel so its sub-editor is reachable.
  useEffect(() => {
    if (open && focus) {
      setTab("panels");
      setOpenPanelId(focus.panelId);
    }
  }, [open, focus]);

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
      setImportError(t("panic_thermometer.settings_drawer.invalid_json"));
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
          res.errors?.[0]?.message ??
            t("panic_thermometer.settings_drawer.formula_failed"),
        );
      } else {
        setFormulaError(
          `${t("panic_thermometer.settings_drawer.ok_prefix")}${
            (res.identifiers ?? []).join(", ") ||
            t("panic_thermometer.settings_drawer.no_identifiers")
          }`,
        );
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
        aria-label={t("panic_thermometer.settings_drawer.aria")}
      >
        <div className="pt-drawer-head">
          <h2>{t("panic_thermometer.settings_drawer.title")}</h2>
          <button
            type="button"
            className="pt-close"
            onClick={onClose}
            aria-label={t("panic_thermometer.settings_drawer.close_aria")}
          >
            ×
          </button>
        </div>

        <div className="pt-drawer-tabs" role="tablist">
          {([
            ["presets", "tab_presets"],
            ["panels", "tab_panels"],
            ["composite", "tab_composite"],
            ["data", "tab_data"],
          ] as const).map(([id, labelKey]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              className={`pt-drawer-tab ${tab === id ? "is-active" : ""}`}
              onClick={() => setTab(id)}
            >
              {t(`panic_thermometer.settings_drawer.${labelKey}`)}
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
              t={t}
            />
          ) : null}

          {tab === "panels" ? (
            <PanelsTab
              config={cfg.config}
              openPanelId={openPanelId}
              focus={focus ?? null}
              onTogglePanel={(id) =>
                setOpenPanelId((prev) => (prev === id ? null : id))
              }
              onSave={cfg.save}
              t={t}
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
              t={t}
            />
          ) : null}

          {tab === "data" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
              <div className="pt-drawer-row">
                <label htmlFor="pt-refresh-select">
                  {t("panic_thermometer.settings_drawer.auto_refresh")}
                </label>
                <select
                  id="pt-refresh-select"
                  value={refreshIntervalSeconds ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    onRefreshIntervalChange(v === "" ? null : Number(v));
                  }}
                >
                  {REFRESH_OPTIONS.map((opt) => (
                    <option key={opt.key} value={opt.value ?? ""}>
                      {t(opt.key)}
                    </option>
                  ))}
                </select>
              </div>

              <div className="pt-drawer-actions">
                <button type="button" className="pt-drawer-btn" onClick={onExport}>
                  {t("panic_thermometer.settings_drawer.export_config")}
                </button>
              </div>

              <div className="pt-drawer-row">
                <label htmlFor="pt-import-text">
                  {t("panic_thermometer.settings_drawer.import_config")}
                </label>
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
                    {t("panic_thermometer.settings_drawer.import")}
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
  t,
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
  t: (key: string, opts?: Record<string, unknown>) => string;
}): JSX.Element {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="pt-drawer-row">
        <label>{t("panic_thermometer.settings_drawer.available_presets")}</label>
        {presets.length === 0 ? (
          <span style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
            {t("panic_thermometer.settings_drawer.no_presets")}
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
                <span className="pt-preset-tag">
                  {t("panic_thermometer.settings_drawer.shipped")}
                </span>
              ) : null}
              <button
                type="button"
                className="pt-drawer-btn"
                onClick={() => void onApply(p.id)}
                disabled={p.id === activePresetId}
              >
                {p.id === activePresetId
                  ? t("panic_thermometer.settings_drawer.active")
                  : t("panic_thermometer.settings_drawer.apply")}
              </button>
              {!p.is_shipped ? (
                <button
                  type="button"
                  className="pt-drawer-btn is-danger"
                  onClick={() => {
                    const next = window.prompt(
                      t("panic_thermometer.settings_drawer.rename_prompt"),
                      p.name,
                    );
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
        <label htmlFor="pt-new-preset">
          {t("panic_thermometer.settings_drawer.save_as_preset")}
        </label>
        <input
          id="pt-new-preset"
          type="text"
          value={newPresetName}
          onChange={(e) => onNewPresetNameChange(e.target.value)}
          placeholder={t("panic_thermometer.settings_drawer.preset_name_placeholder")}
        />
        <div className="pt-drawer-actions">
          <button
            type="button"
            className="pt-drawer-btn is-primary"
            onClick={() => void onSaveAs()}
            disabled={!newPresetName.trim()}
          >
            {t("panic_thermometer.settings_drawer.save_as_button")}
          </button>
        </div>
      </div>
    </div>
  );
}

function PanelsTab({
  config,
  openPanelId,
  focus,
  onTogglePanel,
  onSave,
  t,
}: {
  config: UserConfig | null;
  openPanelId: PtBackendPanelId | null;
  focus: DrawerFocus | null;
  onTogglePanel: (id: PtBackendPanelId) => void;
  onSave: (
    next: Pick<UserConfig, "panel_config" | "composite_settings">,
  ) => Promise<void>;
  t: (key: string, opts?: Record<string, unknown>) => string;
}): JSX.Element {
  if (!config) {
    return (
      <div style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
        {t("panic_thermometer.settings_drawer.loading_config")}
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
              <span>{t(PANEL_TITLE_KEY[p.panel_id])}</span>
              <span className="pt-acc-status">
                {p.enabled === false
                  ? t("panic_thermometer.settings_drawer.panel_off")
                  : t("panic_thermometer.settings_drawer.panel_on")}
              </span>
            </button>
            {isOpen ? (
              <div className="pt-panel-acc-body">
                <PanelEditor
                  panel={p}
                  focusSection={
                    focus && focus.panelId === p.panel_id
                      ? focus.section ?? null
                      : null
                  }
                  t={t}
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
  focusSection,
  onChange,
  t,
}: {
  panel: PanelConfig;
  focusSection: FocusSection | null;
  onChange: (next: PanelConfig) => Promise<void>;
  t: (key: string, opts?: Record<string, unknown>) => string;
}): JSX.Element {
  const [draft, setDraft] = useState<PanelConfig>(panel);
  const keywordsRef = useRef<HTMLDivElement>(null);
  const milestoneRef = useRef<HTMLDivElement>(null);
  const overrideRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setDraft(panel);
  }, [panel]);

  // Scroll the requested sub-editor into view when the drawer opens focused.
  useEffect(() => {
    if (!focusSection) return;
    const target =
      focusSection === "keywords"
        ? keywordsRef.current
        : focusSection === "milestone"
          ? milestoneRef.current
          : focusSection === "override"
            ? overrideRef.current
            : null;
    if (target && typeof target.scrollIntoView === "function") {
      target.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [focusSection]);

  const dirty = JSON.stringify(draft) !== JSON.stringify(panel);

  return (
    <>
      <div className="pt-drawer-row">
        <label>{t("panic_thermometer.settings_drawer.rules")}</label>
        {draft.rules.length === 0 ? (
          <span style={{ color: "var(--color-text-tertiary)", fontSize: 12 }}>
            {t("panic_thermometer.settings_drawer.no_rules")}
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
                {STATUS_KEY[r.status] ? t(STATUS_KEY[r.status]) : r.status}
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
        <label>{t("panic_thermometer.settings_drawer.streak_condition")}</label>
        <input
          type="text"
          value={draft.streak_condition ?? ""}
          onChange={(e) =>
            setDraft({
              ...draft,
              streak_condition: e.target.value || null,
            })
          }
          placeholder={t("panic_thermometer.settings_drawer.streak_optional")}
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
          {t("panic_thermometer.settings_drawer.enabled")}
        </label>
      </div>

      {draft.panel_id === "fed_language" ? (
        <div className="pt-drawer-row" ref={keywordsRef}>
          <label>{t("panic_thermometer.settings_drawer.keywords")}</label>
          {FED_KEYWORD_FIELDS.map((f) => (
            <div
              key={f.paramKey}
              style={{
                display: "grid",
                gridTemplateColumns: "80px 1fr",
                gap: 6,
                fontFamily: "var(--font-mono)",
                fontSize: 11,
              }}
            >
              <span style={{ color: "var(--color-text-tertiary)" }}>
                {t(f.labelKey)}
              </span>
              <input
                type="text"
                value={paramStringList(draft.params, f.paramKey).join(", ")}
                onChange={(e) => {
                  const list = e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                  setDraft({
                    ...draft,
                    params: { ...draft.params, [f.paramKey]: list },
                  });
                }}
              />
            </div>
          ))}
        </div>
      ) : null}

      <div className="pt-drawer-row" ref={milestoneRef}>
        <label htmlFor={`pt-milestone-${draft.panel_id}`}>
          {t("panic_thermometer.settings_drawer.milestone_date")}
        </label>
        <input
          id={`pt-milestone-${draft.panel_id}`}
          type="date"
          value={draft.milestone_date ?? ""}
          onChange={(e) =>
            setDraft({ ...draft, milestone_date: e.target.value || null })
          }
        />
      </div>

      <div className="pt-drawer-row" ref={overrideRef}>
        <label htmlFor={`pt-override-${draft.panel_id}`}>
          {t("panic_thermometer.settings_drawer.status_override")}
        </label>
        <select
          id={`pt-override-${draft.panel_id}`}
          value={draft.manual_override?.status ?? ""}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "") {
              setDraft({ ...draft, manual_override: null });
            } else {
              setDraft({
                ...draft,
                manual_override: {
                  status: v as PanelStatus,
                  note: draft.manual_override?.note ?? null,
                  set_at: new Date().toISOString(),
                },
              });
            }
          }}
        >
          <option value="">
            {t("panic_thermometer.settings_drawer.override_none")}
          </option>
          {OVERRIDE_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(STATUS_KEY[s])}
            </option>
          ))}
        </select>
        <input
          type="text"
          value={draft.manual_override?.note ?? ""}
          disabled={!draft.manual_override}
          placeholder={t("panic_thermometer.settings_drawer.override_note")}
          onChange={(e) => {
            if (!draft.manual_override) return;
            setDraft({
              ...draft,
              manual_override: {
                ...draft.manual_override,
                note: e.target.value || null,
              },
            });
          }}
        />
      </div>

      <div className="pt-drawer-actions">
        <button
          type="button"
          className="pt-drawer-btn is-primary"
          onClick={() => void onChange(draft)}
          disabled={!dirty}
        >
          {t("panic_thermometer.settings_drawer.save")}
        </button>
        <button
          type="button"
          className="pt-drawer-btn"
          onClick={() => setDraft(panel)}
          disabled={!dirty}
        >
          {t("panic_thermometer.settings_drawer.reset")}
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
  t,
}: {
  config: UserConfig | null;
  onSave: (next: Pick<UserConfig, "panel_config" | "composite_settings">) => Promise<void>;
  formulaText: string;
  onFormulaTextChange: (v: string) => void;
  onTestFormula: () => Promise<void>;
  formulaError: string | null;
  t: (key: string, opts?: Record<string, unknown>) => string;
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
        {t("panic_thermometer.settings_drawer.loading_config")}
      </div>
    );
  }

  const dirty =
    JSON.stringify(draft) !== JSON.stringify(config.composite_settings);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="pt-drawer-row">
        <label htmlFor="pt-mode">
          {t("panic_thermometer.settings_drawer.composite_mode")}
        </label>
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
        <label htmlFor="pt-red-threshold">
          {t("panic_thermometer.settings_drawer.red_threshold")}
        </label>
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
          {t("panic_thermometer.settings_drawer.save_composite")}
        </button>
        <button
          type="button"
          className="pt-drawer-btn"
          onClick={() => setDraft(config.composite_settings)}
          disabled={!dirty}
        >
          {t("panic_thermometer.settings_drawer.reset")}
        </button>
      </div>

      <div className="pt-drawer-row">
        <label htmlFor="pt-formula-text">
          {t("panic_thermometer.settings_drawer.test_formula")}
        </label>
        <textarea
          id="pt-formula-text"
          value={formulaText}
          onChange={(e) => onFormulaTextChange(e.target.value)}
          placeholder={t("panic_thermometer.settings_drawer.formula_placeholder")}
        />
        <div className="pt-drawer-actions">
          <button
            type="button"
            className="pt-drawer-btn"
            onClick={() => void onTestFormula()}
            disabled={!formulaText.trim()}
          >
            {t("panic_thermometer.settings_drawer.parse")}
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
