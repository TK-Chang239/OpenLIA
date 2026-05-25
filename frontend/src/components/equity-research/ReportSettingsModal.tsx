import * as Dialog from "@radix-ui/react-dialog";
import { Check, Plus, X } from "lucide-react";
import { type JSX, useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type CustomSection,
  type ErConfig,
  type ErConfigPatch,
  type ErTemplate,
  type ReportLength,
  type ReportMode,
  type ReportReasoningEffort,
  WEB_SEARCH_BUDGET_DEFAULTS,
} from "../../api/equity-research";
import { useCurrentUser } from "../../auth/useCurrentUser";
import { SECTION_CATALOG } from "../../lib/equity-research/section-catalog";
import { CustomSectionRow } from "./CustomSectionRow";
import { TemplateInfoCard, TemplatePickerSection } from "./TemplatePickerSection";

const MODE_KEY: Record<ReportMode, string> = {
  stock_initiation: "equity_research.mode_stock_initiation",
  stock_update: "equity_research.mode_stock_update",
  sector_research: "equity_research.mode_sector_research",
};
const MODE_FULL_KEY: Record<ReportMode, string> = {
  stock_initiation: "equity_research.mode_full_stock_initiation",
  stock_update: "equity_research.mode_full_stock_update",
  sector_research: "equity_research.mode_full_sector_research",
};
const LENGTH_KEY: Record<ReportLength, string> = {
  concise: "equity_research.length_concise",
  normal: "equity_research.length_normal",
  elaborative: "equity_research.length_elaborative",
};
const REASONING_KEY: Record<ReportReasoningEffort, string> = {
  off: "equity_research.reasoning_off",
  medium: "equity_research.reasoning_medium",
  high: "equity_research.reasoning_high",
};

interface Props {
  open: boolean;
  config: ErConfig;
  onClose: () => void;
  onSave: (patch: ErConfigPatch) => Promise<void>;
  // Optional ephemeral toggle (v2.2 engine): bypass cached documents
  // on the next report dispatch. Caller owns the state; absent props
  // hide the section entirely so older callers stay unaffected.
  forceCacheRefresh?: boolean;
  onForceCacheRefreshChange?: (next: boolean) => void;
  // Feature-flag: routes the next report through the v2.2 pipeline
  // (Clarifier → ResearchPlan → … → assemble). Absent props hide the
  // section so older callers stay unaffected.
  engineV2Enabled?: boolean;
  onEngineV2EnabledChange?: (next: boolean) => void;
}

interface SegmentedProps<T extends string> {
  ariaLabel: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (next: T) => void;
}

function Segmented<T extends string>({
  ariaLabel,
  value,
  options,
  onChange,
}: SegmentedProps<T>): JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={[
              "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
              active
                ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

export function ReportSettingsModal({
  open,
  config,
  onClose,
  onSave,
  forceCacheRefresh,
  onForceCacheRefreshChange,
  engineV2Enabled,
  onEngineV2EnabledChange,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [mode, setMode] = useState<ReportMode>(config.report_mode);
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [reasoningEffort, setReasoningEffort] = useState<ReportReasoningEffort>(
    config.report_reasoning_effort ?? "off",
  );
  const [sections, setSections] = useState(config.sections_by_mode);
  const [customs, setCustoms] = useState(config.custom_sections_by_mode);
  const [pendingCustom, setPendingCustom] = useState<CustomSection | null>(null);
  const [selectedTemplateByMode, setSelectedTemplateByMode] = useState<
    Record<ReportMode, string>
  >(() => normalizeSelected(config.selected_template_id_by_mode));
  // Per-mode override map. Stored as strings so the empty input maps
  // cleanly to "use framework default" without juggling NaN. Parsed
  // and validated at save-time.
  const [budgetInputs, setBudgetInputs] = useState<Record<ReportMode, string>>(
    () => normalizeBudgetInputs(config.web_search_budgets_by_mode),
  );
  const [activeTemplate, setActiveTemplate] = useState<ErTemplate | null>(null);
  const currentUser = useCurrentUser();
  const isAdmin = currentUser?.role === "admin";
  const handleActiveTemplateChange = useCallback(
    (t: ErTemplate | null) => setActiveTemplate(t),
    [],
  );

  useEffect(() => {
    if (!open) return;
    setMode(config.report_mode);
    setLength(config.report_length);
    setReasoningEffort(config.report_reasoning_effort ?? "off");
    setSections(config.sections_by_mode);
    setCustoms(config.custom_sections_by_mode);
    setPendingCustom(null);
    setSelectedTemplateByMode(normalizeSelected(config.selected_template_id_by_mode));
    setBudgetInputs(normalizeBudgetInputs(config.web_search_budgets_by_mode));
  }, [open, config]);

  const templateActive = (selectedTemplateByMode[mode] ?? "default") !== "default";

  const toggleSection = (id: string) => {
    const current = new Set(sections[mode]);
    if (current.has(id)) current.delete(id);
    else current.add(id);
    const ordered = SECTION_CATALOG[mode]
      .map((s) => s.id)
      .filter((sid) => current.has(sid));
    setSections({ ...sections, [mode]: ordered });
  };

  const addCustom = () => {
    if (!pendingCustom?.title) return;
    const id = `custom_${pendingCustom.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .slice(0, 32)}_${Math.random().toString(36).slice(2, 6)}`;
    setCustoms({
      ...customs,
      [mode]: [...customs[mode], { ...pendingCustom, id }],
    });
    setPendingCustom(null);
  };

  const save = async () => {
    const budgets: Partial<Record<ReportMode, number>> = {};
    for (const m of Object.keys(WEB_SEARCH_BUDGET_DEFAULTS) as ReportMode[]) {
      const raw = budgetInputs[m].trim();
      if (!raw) continue; // empty = use framework default; don't send.
      const n = Number(raw);
      if (Number.isInteger(n) && n > 0) {
        budgets[m] = n;
      }
    }
    await onSave({
      report_mode: mode,
      report_length: length,
      report_reasoning_effort: reasoningEffort,
      sections_by_mode: sections,
      custom_sections_by_mode: customs,
      selected_template_id_by_mode: selectedTemplateByMode,
      web_search_budgets_by_mode: budgets,
    });
    onClose();
  };

  const setBudget = (m: ReportMode, raw: string) => {
    // Coerce: blank, or digits only. Anything else is rejected at the
    // input boundary so the field never holds invalid state.
    if (raw === "" || /^\d+$/.test(raw)) {
      setBudgetInputs({ ...budgetInputs, [m]: raw });
    }
  };

  const modeOptions = (Object.keys(MODE_KEY) as ReportMode[]).map((v) => ({
    value: v,
    label: t(MODE_KEY[v]),
  }));
  const lengthOptions = (Object.keys(LENGTH_KEY) as ReportLength[]).map(
    (v) => ({ value: v, label: t(LENGTH_KEY[v]) }),
  );
  const reasoningOptions = (Object.keys(REASONING_KEY) as ReportReasoningEffort[]).map(
    (v) => ({ value: v, label: t(REASONING_KEY[v]) }),
  );

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-full max-w-[520px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]">
          <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <Dialog.Title className="m-0 text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
              {t("equity_research.settings.title")}
            </Dialog.Title>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("equity_research.settings.close_aria")}
              className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                {t("equity_research.settings.section_report_mode")}
              </span>
              <Segmented
                ariaLabel={t("equity_research.settings.section_report_mode")}
                value={mode}
                options={modeOptions}
                onChange={setMode}
              />
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                {t("equity_research.settings.section_report_length")}
              </span>
              <Segmented
                ariaLabel={t("equity_research.settings.section_report_length")}
                value={length}
                options={lengthOptions}
                onChange={setLength}
              />
            </section>

            <section
              className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
              data-testid="er-reasoning-effort"
            >
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                {t("equity_research.settings.section_reasoning_effort")}
              </span>
              <Segmented
                ariaLabel={t("equity_research.settings.section_reasoning_effort")}
                value={reasoningEffort}
                options={reasoningOptions}
                onChange={setReasoningEffort}
              />
              <p className="mt-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
                {t("equity_research.settings.reasoning_help")}
              </p>
            </section>

            <TemplatePickerSection
              mode={mode}
              selectedId={selectedTemplateByMode[mode] ?? "default"}
              onSelectedIdChange={(id) =>
                setSelectedTemplateByMode({
                  ...selectedTemplateByMode,
                  [mode]: id,
                })
              }
              isAdmin={isAdmin}
              onActiveTemplateChange={handleActiveTemplateChange}
            />

            {templateActive && activeTemplate ? (
              <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
                <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                  {t("equity_research.settings.section_template_structure")}
                </span>
                <TemplateInfoCard template={activeTemplate} />
              </section>
            ) : (
              <>
                <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
                  <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                    {t("equity_research.settings.section_sections")} ·{" "}
                    <strong className="font-medium text-[--color-text-primary]">
                      {t(MODE_FULL_KEY[mode])}
                    </strong>
                  </span>
                  <ul className="m-0 mt-1 flex list-none flex-col p-0">
                    {SECTION_CATALOG[mode].map((s, idx) => {
                      const checked = sections[mode].includes(s.id);
                      const last = idx === SECTION_CATALOG[mode].length - 1;
                      return (
                        <li
                          key={s.id}
                          className={[
                            "group flex cursor-pointer items-center gap-[10px] py-[9px]",
                            last
                              ? ""
                              : "border-b border-dashed border-[--color-border-subtle]",
                          ].join(" ")}
                          onClick={() => toggleSection(s.id)}
                        >
                          <span
                            aria-hidden="true"
                            className={[
                              "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-[4px] border-[1.5px] transition-colors",
                              checked
                                ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                                : "border-[--color-border-strong]",
                            ].join(" ")}
                          >
                            {checked ? (
                              <Check size={10} strokeWidth={3} />
                            ) : null}
                          </span>
                          <span className="w-5 font-mono text-[10px] tracking-[0.04em] text-[--color-text-tertiary]">
                            {String(idx + 1).padStart(2, "0")}
                          </span>
                          <span className="flex-1 text-[13.5px] text-[--color-text-primary] transition-colors group-hover:text-[--color-feedback-success]">
                            {s.title}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                </section>

                <section className="px-[22px] py-[18px]">
                  <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                    {t("equity_research.settings.section_custom_sections")}
                  </span>
                  {customs[mode].map((c, i) => (
                    <CustomSectionRow
                      key={c.id}
                      section={c}
                      onChange={(next) => {
                        const copy = [...customs[mode]];
                        copy[i] = next;
                        setCustoms({ ...customs, [mode]: copy });
                      }}
                      onRemove={() => {
                        const copy = customs[mode].filter((_, j) => j !== i);
                        setCustoms({ ...customs, [mode]: copy });
                      }}
                    />
                  ))}
                  {pendingCustom ? (
                    <div className="mb-2 space-y-2 rounded-md border border-[--color-border-subtle] p-2">
                      <input
                        aria-label={t("equity_research.settings.custom_title_aria")}
                        placeholder={t("equity_research.settings.custom_title_placeholder")}
                        autoFocus
                        className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
                        value={pendingCustom.title}
                        onChange={(e) =>
                          setPendingCustom({
                            ...pendingCustom,
                            title: e.target.value,
                          })
                        }
                      />
                      <textarea
                        aria-label={t("equity_research.settings.custom_desc_aria")}
                        placeholder={t("equity_research.settings.custom_desc_placeholder")}
                        rows={2}
                        className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
                        value={pendingCustom.description ?? ""}
                        onChange={(e) =>
                          setPendingCustom({
                            ...pendingCustom,
                            description: e.target.value || null,
                          })
                        }
                      />
                      <div className="flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => setPendingCustom(null)}
                          className="h-7 px-2 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
                        >
                          {t("equity_research.settings.cancel")}
                        </button>
                        <button
                          type="button"
                          onClick={addCustom}
                          disabled={!pendingCustom.title}
                          className="h-7 rounded-sm bg-[--color-accent-primary] px-2 text-sm text-[--color-accent-on] disabled:opacity-40"
                        >
                          {t("equity_research.settings.add_section_button")}
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() =>
                        setPendingCustom({ id: "", title: "", description: null })
                      }
                      className="inline-flex h-7 items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-all hover:border-solid hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
                    >
                      <Plus size={11} strokeWidth={2} />
                      {t("equity_research.settings.add_custom_section")}
                    </button>
                  )}
                </section>
              </>
            )}

            <section className="border-t border-[--color-border-subtle] px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                {t("equity_research.settings.section_web_search_budget")}
              </span>
              <p className="mb-[14px] text-[12.5px] leading-[1.5] text-[--color-text-secondary]">
                {t("equity_research.settings.web_search_help")}
              </p>
              <ul className="m-0 flex list-none flex-col gap-[10px] p-0">
                {(Object.keys(WEB_SEARCH_BUDGET_DEFAULTS) as ReportMode[]).map(
                  (m) => (
                    <li
                      key={m}
                      className="flex items-center justify-between gap-3"
                    >
                      <span className="text-[13.5px] text-[--color-text-primary]">
                        {t(MODE_KEY[m])}
                      </span>
                      <div className="flex items-center gap-[8px]">
                        <input
                          type="text"
                          inputMode="numeric"
                          aria-label={t("equity_research.settings.web_search_aria", {
                            mode: t(MODE_KEY[m]),
                          })}
                          value={budgetInputs[m]}
                          onChange={(e) => setBudget(m, e.target.value)}
                          placeholder={String(WEB_SEARCH_BUDGET_DEFAULTS[m])}
                          className="h-7 w-[64px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-right text-[13px] tabular-nums text-[--color-text-primary] placeholder:text-[--color-text-tertiary]"
                        />
                        <span className="text-[12px] text-[--color-text-tertiary]">
                          {t("equity_research.settings.searches_suffix")}
                        </span>
                      </div>
                    </li>
                  ),
                )}
              </ul>
            </section>
          </div>

          {onForceCacheRefreshChange ? (
            <section className="border-t border-[--color-border-subtle] px-[22px] py-[16px]">
              <label
                className="flex cursor-pointer items-start gap-3"
                data-testid="er-force-cache-refresh"
              >
                <input
                  type="checkbox"
                  checked={!!forceCacheRefresh}
                  onChange={(e) =>
                    onForceCacheRefreshChange(e.target.checked)
                  }
                  className="mt-[3px] h-4 w-4 cursor-pointer accent-[--color-accent-primary]"
                />
                <span className="flex flex-col gap-1 text-[13.5px] text-[--color-text-primary]">
                  Force cache refresh
                  <span className="text-[12px] text-[--color-text-secondary]">
                    Bypass cached transcripts and investor-day documents on
                    the next report. One-shot — re-arms after each run.
                  </span>
                </span>
              </label>
            </section>
          ) : null}

          {onEngineV2EnabledChange ? (
            <section className="border-t border-[--color-border-subtle] px-[22px] py-[16px]">
              <label
                className="flex cursor-pointer items-start gap-3"
                data-testid="er-engine-v2"
              >
                <input
                  type="checkbox"
                  checked={!!engineV2Enabled}
                  onChange={(e) => onEngineV2EnabledChange(e.target.checked)}
                  className="mt-[3px] h-4 w-4 cursor-pointer accent-[--color-accent-primary]"
                />
                <span className="flex flex-col gap-1 text-[13.5px] text-[--color-text-primary]">
                  v2.2 engine (preview)
                  <span className="text-[12px] text-[--color-text-secondary]">
                    Route the next report through the new pipeline with
                    capability-checked Clarifier, per-section verifier, and
                    run summary. Requires a v2.2 template selected above.
                  </span>
                </span>
              </label>
            </section>
          ) : null}

          <div className="flex justify-end gap-2 rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[14px]">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-4 font-display text-[13.5px] font-medium text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              {t("equity_research.settings.cancel")}
            </button>
            <button
              type="button"
              onClick={save}
              className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
            >
              {t("equity_research.settings.save")}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function normalizeSelected(
  raw: ErConfig["selected_template_id_by_mode"] | undefined,
): Record<ReportMode, string> {
  const out: Record<ReportMode, string> = {
    stock_initiation: "default",
    stock_update: "default",
    sector_research: "default",
  };
  if (!raw) return out;
  for (const m of Object.keys(out) as ReportMode[]) {
    const v = raw[m];
    if (typeof v === "string" && v) out[m] = v;
  }
  return out;
}

function normalizeBudgetInputs(
  raw: ErConfig["web_search_budgets_by_mode"] | undefined,
): Record<ReportMode, string> {
  const out: Record<ReportMode, string> = {
    stock_initiation: "",
    stock_update: "",
    sector_research: "",
  };
  if (!raw) return out;
  for (const m of Object.keys(out) as ReportMode[]) {
    const v = raw[m];
    if (typeof v === "number" && Number.isInteger(v) && v > 0) {
      out[m] = String(v);
    }
  }
  return out;
}
