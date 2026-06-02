# Morning Briefing — Run Now Full Settings + Remembered Choices Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Morning Briefing "Run now" modal a full ad-hoc config form (model, template, instructions, connectors, length, language, reasoning) that remembers the user's previous Run Now choices via `localStorage`.

**Architecture:** Extract the 7 config controls already living inside `ScheduleEditorModal` into a shared `MbConfigFields` component consumed by both the schedule editor and the rewritten Run Now modal. Persist the last submitted Run Now config to `localStorage["mb.run_now.last_config"]`; prefill from it on open, save on Generate, fall back to library defaults on first use. Frontend only — the backend `POST /runs/start` ad-hoc path and `MbRunStartIn` already accept every field.

**Tech Stack:** React + TypeScript, Radix UI dialogs, react-i18next, Vitest + Testing Library. All commands run from `frontend/`.

Spec: `docs/superpowers/specs/2026-06-02-mb-run-now-full-settings-design.md`

---

## File Structure

- Create: `frontend/src/components/morning-briefing/MbConfigFields.tsx` — shared config controls + `MbConfigDraft` type + `isBriefEmpty` + `Toggle`/`sectionTitle` helpers.
- Create: `frontend/src/components/morning-briefing/mbRunNowDraft.ts` — library defaults + `localStorage` load/save for the Run Now config.
- Create: `frontend/src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts`
- Create: `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`
- Modify: `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx` — consume `MbConfigFields`, delete its inline config sections.
- Rewrite: `frontend/src/components/morning-briefing/MbRunNowModal.tsx` — full form, prefill, persist.
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx:444-449` — drop the `schedules` prop on `<MbRunNowModal/>`.
- Modify: `frontend/src/i18n/locales/en.json` (run_now_modal block) and `frontend/src/i18n/locales/zh-TW.json` (run_now_modal block).

---

## Task 1: Create `MbConfigFields` shared component

This lifts the config portion of `ScheduleEditorModal` verbatim into a reusable component. The editor still has its own copy after this task (removed in Task 3) — both compile and all existing tests stay green.

**Files:**
- Create: `frontend/src/components/morning-briefing/MbConfigFields.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import * as settingsApi from "../../../api/settings";
import {
  MbConfigFields,
  isBriefEmpty,
  type MbConfigDraft,
} from "../MbConfigFields";

function draft(over: Partial<MbConfigDraft> = {}): MbConfigDraft {
  return {
    template_id: "mb_default",
    instructions_id: null,
    provider_ids: [],
    web_search: false,
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
    ...over,
  };
}

describe("MbConfigFields", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders the config controls", async () => {
    render(<MbConfigFields draft={draft()} onChange={vi.fn()} />);
    expect(await screen.findByTestId("mb-template-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-instructions-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-language-select")).toBeInTheDocument();
  });

  it("does NOT render scheduling fields", async () => {
    render(<MbConfigFields draft={draft()} onChange={vi.fn()} />);
    await screen.findByTestId("mb-template-select");
    expect(screen.queryByTestId("mb-schedule-time")).not.toBeInTheDocument();
  });

  it("isBriefEmpty is true only for freeform + no instructions", () => {
    expect(isBriefEmpty(draft({ template_id: "freeform", instructions_id: null }))).toBe(true);
    expect(isBriefEmpty(draft({ template_id: "freeform", instructions_id: "i1" }))).toBe(false);
    expect(isBriefEmpty(draft({ template_id: "mb_default", instructions_id: null }))).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`
Expected: FAIL — cannot resolve module `../MbConfigFields`.

- [ ] **Step 3: Create the component**

Create `frontend/src/components/morning-briefing/MbConfigFields.tsx`:

```tsx
/**
 * MbConfigFields — the shared Morning Briefing config controls.
 *
 * The model / template / instructions / connectors / length / language /
 * reasoning controls, lifted out of ScheduleEditorModal so both the schedule
 * editor and the Run Now modal render the exact same settings. Owns the
 * template/instructions/data-source hooks and the upload sub-modals; the
 * parent owns the draft state and passes a patcher via `onChange`.
 *
 * MB is purely template/instructions-driven — no ticker. The scheduling
 * fields (time/timezone/days/label/is_enabled) live only in the editor.
 */
import { useState, type ReactNode } from "react";
import { Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDataSource,
  MbReasoningEffort,
  MbReportLength,
} from "../../api/morning-briefing";
import { useMbDataSources } from "../../hooks/useMbDataSources";
import { useMbInstructions } from "../../hooks/useMbInstructions";
import { useMbTemplates } from "../../hooks/useMbTemplates";

import { MbInstructionsUploadModal } from "./MbInstructionsUploadModal";
import { MbModelPicker, type MbModelSelection } from "./MbModelPicker";
import { MbTemplateUploadModal } from "./MbTemplateUploadModal";

const LENGTH_IDS: readonly MbReportLength[] = [
  "concise",
  "normal",
  "elaborative",
];

/** The per-run config slice shared by the editor and the Run Now modal. */
export interface MbConfigDraft {
  template_id: string;
  instructions_id: string | null;
  provider_ids: string[];
  web_search: boolean;
  provider_kind: string | null;
  model: string | null;
  language: string;
  length: string;
  reasoning_effort: MbReasoningEffort;
}

/** Freeform template with no instructions has nothing to brief on. */
export function isBriefEmpty(draft: MbConfigDraft): boolean {
  return draft.template_id === "freeform" && !draft.instructions_id;
}

export function sectionTitle(text: string) {
  return (
    <h3 className="text-[15px] font-semibold text-[--color-text-primary] mb-1">
      {text}
    </h3>
  );
}

export function Toggle({
  on,
  onClick,
  testId,
  label,
  ariaLabel,
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: ReactNode;
  ariaLabel?: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={[
        "flex items-center justify-between gap-4 px-4 py-3.5 transition-colors",
        disabled
          ? "opacity-50 cursor-not-allowed pointer-events-none"
          : "cursor-pointer hover:bg-[--color-surface-hover]",
      ].join(" ")}
    >
      <span className="text-[13.5px] font-medium text-[--color-text-primary]">
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={ariaLabel}
        data-testid={testId}
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on && !disabled
            ? "bg-[--color-accent-primary]"
            : "bg-[--color-border-subtle]",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
            on && !disabled ? "left-5" : "left-1",
          ].join(" ")}
        />
      </button>
    </label>
  );
}

interface Props {
  draft: MbConfigDraft;
  onChange: (patch: Partial<MbConfigDraft>) => void;
}

export function MbConfigFields({ draft, onChange }: Props) {
  const { t } = useTranslation();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);

  const {
    templates,
    create: createTemplate,
    upload: uploadTemplate,
    remove: removeTemplate,
  } = useMbTemplates();
  const {
    instructions,
    upload: uploadInstructions,
    remove: removeInstructions,
  } = useMbInstructions();
  const { sources } = useMbDataSources({
    provider_kind: draft.provider_kind ?? undefined,
    model: draft.model ?? undefined,
    enabled_provider_ids: draft.provider_ids,
    web_search: draft.web_search,
  });

  const LENGTH_LABELS: Record<MbReportLength, string> = {
    concise: t("morning_briefing.schedule_editor.length_concise"),
    normal: t("morning_briefing.schedule_editor.length_normal"),
    elaborative: t("morning_briefing.schedule_editor.length_elaborative"),
  };

  const REASONING_OPTIONS: readonly {
    value: MbReasoningEffort;
    label: string;
  }[] = [
    {
      value: null,
      label: t("morning_briefing.schedule_editor.reasoning_default"),
    },
    {
      value: "medium",
      label: t("morning_briefing.schedule_editor.reasoning_medium"),
    },
    {
      value: "high",
      label: t("morning_briefing.schedule_editor.reasoning_high"),
    },
  ];

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeTemplate = templates.find((tpl) => tpl.id === draft.template_id);

  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeInstructions = instructions.find(
    (ins) => ins.id === draft.instructions_id,
  );

  function handleModel(sel: MbModelSelection | null) {
    if (!sel) return;
    onChange({ provider_kind: sel.provider_kind, model: sel.model });
  }

  async function handleUploadMarkdown(name: string, markdown: string) {
    const created = await createTemplate({ name, source_markdown: markdown });
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleUploadFile(name: string, file: File) {
    const created = await uploadTemplate(name, file);
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleDeleteTemplate() {
    if (!activeTemplate || activeTemplate.is_builtin) return;
    await removeTemplate(activeTemplate.id);
    onChange({ template_id: "freeform" });
  }

  async function handleUploadInstructions(name: string, file: File) {
    const created = await uploadInstructions(name, file);
    onChange({ instructions_id: created.id });
    setInstructionsOpen(false);
  }

  async function handleDeleteInstructions() {
    if (!activeInstructions || activeInstructions.is_builtin) return;
    if (
      !window.confirm(
        t("morning_briefing.schedule_editor.instructions_delete_confirm"),
      )
    ) {
      return;
    }
    await removeInstructions(activeInstructions.id);
    onChange({ instructions_id: null });
  }

  const isWebSearchSource = (s: MbDataSource) =>
    s.routing === "model_native" || s.key === "model_web_search";

  function sourceEnabled(s: MbDataSource): boolean {
    return isWebSearchSource(s)
      ? draft.web_search
      : draft.provider_ids.includes(s.key);
  }

  function toggleSource(s: MbDataSource): void {
    if (isWebSearchSource(s)) {
      onChange({ web_search: !draft.web_search });
      return;
    }
    const has = draft.provider_ids.includes(s.key);
    onChange({
      provider_ids: has
        ? draft.provider_ids.filter((k) => k !== s.key)
        : [...draft.provider_ids, s.key],
    });
  }

  function reasonText(s: MbDataSource): string | null {
    if (s.available || !s.unavailable_reason) return null;
    const key = `morning_briefing.schedule_editor.ds_reason_${s.unavailable_reason}`;
    const resolved = t(key);
    return resolved !== key
      ? resolved
      : t("morning_briefing.schedule_editor.ds_reason_unknown");
  }

  function categoryLabel(category: string): string {
    const key = `morning_briefing.schedule_editor.ds_category_${category}`;
    const resolved = t(key);
    return resolved !== key ? resolved : category;
  }

  function renderSource(s: MbDataSource) {
    const reason = reasonText(s);
    const label = (
      <span className="flex items-center gap-2">
        <span>{s.display_name}</span>
        <span className="inline-flex items-center rounded-full bg-[--color-surface-hover] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-[--color-text-tertiary]">
          {categoryLabel(s.category)}
        </span>
      </span>
    );
    return (
      <div key={s.key}>
        <Toggle
          on={sourceEnabled(s) && s.available}
          onClick={() => toggleSource(s)}
          testId={`mb-connector-${s.key}`}
          label={label}
          ariaLabel={s.display_name}
          disabled={!s.available}
        />
        {reason ? (
          <p className="px-4 pb-3 -mt-1 text-[12px] text-[--color-text-tertiary] leading-[1.4]">
            {reason}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <>
      {/* Model */}
      <section className="mb-7">
        {sectionTitle(t("morning_briefing.schedule_editor.model_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.model_hint")}
        </p>
        <MbModelPicker
          onChange={handleModel}
          value={{
            provider_kind: draft.provider_kind,
            model: draft.model,
          }}
        />
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Template */}
      <section className="mb-7">
        {sectionTitle(t("morning_briefing.schedule_editor.template_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.template_hint")}
        </p>
        <div className="flex items-center gap-2">
          <select
            value={draft.template_id}
            onChange={(e) => onChange({ template_id: e.target.value })}
            data-testid="mb-template-select"
            className="flex-1 h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          >
            <option value="freeform">
              {t("morning_briefing.schedule_editor.template_freeform")}
            </option>
            {sortedTemplates.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name}
                {tpl.is_builtin
                  ? ""
                  : t("morning_briefing.schedule_editor.template_custom_suffix")}
              </option>
            ))}
          </select>
          {activeTemplate && !activeTemplate.is_builtin ? (
            <button
              type="button"
              onClick={() => void handleDeleteTemplate()}
              aria-label={t(
                "morning_briefing.schedule_editor.template_delete_aria",
              )}
              data-testid="mb-template-delete"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-feedback-danger] hover:border-[--color-feedback-danger] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            data-testid="mb-template-upload-open"
            className="inline-flex items-center h-9 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px] whitespace-nowrap"
          >
            {t("morning_briefing.schedule_editor.template_upload")}
          </button>
        </div>
        {draft.template_id === "freeform" ? (
          <p
            data-testid="mb-template-freeform-hint"
            className="mt-3 text-[12px] text-[--color-text-tertiary] leading-[1.5]"
          >
            {t("morning_briefing.schedule_editor.template_freeform_hint")}
          </p>
        ) : null}
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Instructions */}
      <section className="mb-7">
        {sectionTitle(t("morning_briefing.schedule_editor.instructions_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.instructions_hint")}
        </p>
        <div className="flex items-center gap-2">
          <select
            value={draft.instructions_id ?? ""}
            onChange={(e) =>
              onChange({ instructions_id: e.target.value || null })
            }
            data-testid="mb-instructions-select"
            className="flex-1 h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          >
            <option value="">
              {t("morning_briefing.schedule_editor.instructions_none")}
            </option>
            {sortedInstructions.map((ins) => (
              <option key={ins.id} value={ins.id}>
                {ins.name}
                {ins.is_builtin
                  ? ""
                  : t(
                      "morning_briefing.schedule_editor.instructions_custom_suffix",
                    )}
              </option>
            ))}
          </select>
          {activeInstructions && !activeInstructions.is_builtin ? (
            <button
              type="button"
              onClick={() => void handleDeleteInstructions()}
              aria-label={t(
                "morning_briefing.schedule_editor.instructions_delete_aria",
              )}
              data-testid="mb-instructions-delete"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-feedback-danger] hover:border-[--color-feedback-danger] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setInstructionsOpen(true)}
            data-testid="mb-instructions-upload-open"
            className="inline-flex items-center h-9 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px] whitespace-nowrap"
          >
            {t("morning_briefing.schedule_editor.instructions_upload")}
          </button>
        </div>
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Connectors */}
      <section className="mb-7">
        {sectionTitle(t("morning_briefing.schedule_editor.connectors_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.connectors_hint")}
        </p>
        {sources && sources.length === 0 ? (
          <p
            data-testid="mb-data-sources-empty"
            className="text-[13px] text-[--color-text-tertiary] leading-[1.5] border border-[--color-border-subtle] rounded-lg px-4 py-3"
          >
            {t("morning_briefing.schedule_editor.ds_empty")}
          </p>
        ) : (
          <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
            {(sources ?? []).map((s) => renderSource(s))}
          </div>
        )}
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Length */}
      <section className="mb-7">
        {sectionTitle(t("morning_briefing.schedule_editor.length_title"))}
        <div
          role="radiogroup"
          aria-label={t("morning_briefing.schedule_editor.length_aria")}
          className="inline-flex gap-1 p-1 bg-[--color-surface-hover] rounded-lg mt-2"
        >
          {LENGTH_IDS.map((id) => {
            const active = draft.length === id;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={active}
                aria-label={id}
                onClick={() => onChange({ length: id })}
                className={[
                  "px-3.5 py-1.5 rounded-md text-[13px] transition-all duration-[--duration-fast]",
                  active
                    ? "bg-[--color-bg-elevated] text-[--color-text-primary] font-medium shadow-sm"
                    : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
                ].join(" ")}
              >
                {LENGTH_LABELS[id]}
              </button>
            );
          })}
        </div>
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Language */}
      <section className={draft.provider_kind === "anthropic" ? "mb-7" : "mb-2"}>
        {sectionTitle(t("morning_briefing.schedule_editor.language_title"))}
        <select
          value={draft.language}
          onChange={(e) => onChange({ language: e.target.value })}
          data-testid="mb-language-select"
          className="mt-2 h-9 w-[200px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
        >
          <option value="en">English</option>
          <option value="zh-Hant">繁體中文</option>
        </select>
      </section>

      {/* Reasoning effort — Anthropic only */}
      {draft.provider_kind === "anthropic" ? (
        <>
          <hr className="border-0 border-t border-[--color-border-subtle] my-7" />
          <section className="mb-2">
            {sectionTitle(t("morning_briefing.schedule_editor.reasoning_title"))}
            <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-2">
              {t("morning_briefing.schedule_editor.reasoning_hint")}
            </p>
            <select
              value={draft.reasoning_effort ?? ""}
              onChange={(e) =>
                onChange({
                  reasoning_effort: (e.target.value ||
                    null) as MbReasoningEffort,
                })
              }
              data-testid="mb-reasoning-select"
              className="h-9 w-[200px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            >
              {REASONING_OPTIONS.map((opt) => (
                <option key={opt.value ?? "null"} value={opt.value ?? ""}>
                  {opt.label}
                </option>
              ))}
            </select>
          </section>
        </>
      ) : null}

      <MbTemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadMarkdown={handleUploadMarkdown}
        onUploadFile={handleUploadFile}
      />

      <MbInstructionsUploadModal
        open={instructionsOpen}
        onClose={() => setInstructionsOpen(false)}
        onUpload={handleUploadInstructions}
      />
    </>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/morning-briefing/__tests__/MbConfigFields.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/MbConfigFields.tsx frontend/src/components/morning-briefing/__tests__/MbConfigFields.test.tsx
git commit -m "feat(morning-briefing): extract shared MbConfigFields component"
```

---

## Task 2: Create the Run Now draft persistence module

**Files:**
- Create: `frontend/src/components/morning-briefing/mbRunNowDraft.ts`
- Test: `frontend/src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";

import {
  RUN_NOW_LS_KEY,
  libraryDefaultDraft,
  loadRunNowDraft,
  saveRunNowDraft,
} from "../mbRunNowDraft";

describe("mbRunNowDraft", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns library defaults when nothing is stored", () => {
    expect(loadRunNowDraft()).toEqual(libraryDefaultDraft());
  });

  it("library default is a runnable (non-freeform) template", () => {
    expect(libraryDefaultDraft().template_id).toBe("mb_default");
  });

  it("round-trips a saved draft", () => {
    const draft = {
      ...libraryDefaultDraft(),
      template_id: "freeform",
      instructions_id: "ins-1",
      provider_ids: ["eodhd"],
      web_search: true,
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
      language: "zh-Hant",
      length: "concise",
      reasoning_effort: "high" as const,
    };
    saveRunNowDraft(draft);
    expect(loadRunNowDraft()).toEqual(draft);
  });

  it("merges a partial stored config over the defaults", () => {
    window.localStorage.setItem(
      RUN_NOW_LS_KEY,
      JSON.stringify({ length: "elaborative" }),
    );
    expect(loadRunNowDraft()).toEqual({
      ...libraryDefaultDraft(),
      length: "elaborative",
    });
  });

  it("falls back to defaults on malformed JSON", () => {
    window.localStorage.setItem(RUN_NOW_LS_KEY, "not json{");
    expect(loadRunNowDraft()).toEqual(libraryDefaultDraft());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts`
Expected: FAIL — cannot resolve module `../mbRunNowDraft`.

- [ ] **Step 3: Create the module**

Create `frontend/src/components/morning-briefing/mbRunNowDraft.ts`:

```ts
/**
 * Persistence for the Run Now config. The form remembers the user's previous
 * Run Now submission per browser under `mb.run_now.last_config` and prefills
 * from it; first use falls back to the library defaults (mb_default template,
 * backend-default model, no connectors). "Previous run" = the last config
 * actually submitted via Run Now — scheduled runs keep their own bindings.
 */
import type { MbConfigDraft } from "./MbConfigFields";

export const RUN_NOW_LS_KEY = "mb.run_now.last_config";

export function libraryDefaultDraft(): MbConfigDraft {
  return {
    template_id: "mb_default",
    instructions_id: null,
    provider_ids: [],
    web_search: false,
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
  };
}

export function loadRunNowDraft(): MbConfigDraft {
  if (typeof window === "undefined") return libraryDefaultDraft();
  try {
    const raw = window.localStorage.getItem(RUN_NOW_LS_KEY);
    if (!raw) return libraryDefaultDraft();
    const parsed = JSON.parse(raw) as Partial<MbConfigDraft>;
    return { ...libraryDefaultDraft(), ...parsed };
  } catch {
    return libraryDefaultDraft();
  }
}

export function saveRunNowDraft(draft: MbConfigDraft): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(RUN_NOW_LS_KEY, JSON.stringify(draft));
  } catch {
    /* localStorage may be disabled */
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/mbRunNowDraft.ts frontend/src/components/morning-briefing/__tests__/mbRunNowDraft.test.ts
git commit -m "feat(morning-briefing): add Run Now draft localStorage persistence"
```

---

## Task 3: Rewire `ScheduleEditorModal` to use `MbConfigFields`

Delete the editor's inline config sections/helpers/hooks and render `<MbConfigFields/>` instead. The editor keeps the Timing section, footer, and `noDays` check. The existing `ScheduleEditorModal.test.tsx` is the regression guard — all its `data-testid`s are preserved by `MbConfigFields`.

**Files:**
- Modify: `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`

- [ ] **Step 1: Replace the import block**

In `ScheduleEditorModal.tsx`, replace the top imports (the `lucide-react`, api type, hooks, and sub-component imports — current lines 12-31) with:

```tsx
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDayOfWeek,
  MbReasoningEffort,
  MbSchedule,
  MbScheduleIn,
} from "../../api/morning-briefing";

import {
  MbConfigFields,
  Toggle,
  isBriefEmpty,
  sectionTitle,
  type MbConfigDraft,
} from "./MbConfigFields";
```

Note: `Trash2` and `ReactNode` are no longer imported here (they moved to `MbConfigFields`); `MbDataSource`, `MbReportLength`, the three `useMb*` hooks, `MbInstructionsUploadModal`, `MbModelPicker`/`MbModelSelection`, and `MbTemplateUploadModal` imports are removed.

- [ ] **Step 2: Delete now-shared module-level constants and helpers**

Delete these blocks from `ScheduleEditorModal.tsx` (they now live in `MbConfigFields`):
- `const LENGTH_IDS = [...]` (current lines 33-37).
- The `sectionTitle(...)` function definition (current lines 127-133).
- The `Toggle({...})` function definition (current lines 135-186).

Keep `DAY_NAMES` and `TIMEZONES`. Keep `DraftState`, `readProviderIds`, `readWebSearch`, `draftFromSchedule`, `freshDraft` unchanged (`DraftState` is a superset of `MbConfigDraft`, so it satisfies the `MbConfigFields` `draft` prop).

- [ ] **Step 3: Delete the editor's config-only hooks, derived values, and handlers**

Inside the `ScheduleEditorModal` component body, delete:
- The `uploadOpen` / `instructionsOpen` `useState` lines (current 202-203).
- The `useMbTemplates`, `useMbInstructions`, `useMbDataSources` hook calls (current 205-221).
- `LENGTH_LABELS` and `REASONING_OPTIONS` (current 223-245).
- `sortedTemplates`, `activeTemplate`, `sortedInstructions`, `activeInstructions` (current 247-259).
- The handlers `handleModel`, `handleUploadMarkdown`, `handleUploadFile`, `handleDeleteTemplate`, `handleUploadInstructions`, `handleDeleteInstructions` (current 264-308).
- The functions `isWebSearchSource`, `sourceEnabled`, `toggleSource`, `reasonText`, `categoryLabel`, `renderSource` (current 347-414).

Keep `saving` state, `editing`, `draft`/`setDraft`, `toggleDay`, `handleSave`, `noDays`.

Change the `bothEmpty` derivation (current line 261) to use the shared helper:

```tsx
const bothEmpty = isBriefEmpty(draft);
const noDays = draft.days_of_week.length === 0;
```

- [ ] **Step 4: Replace the inline config sections in the JSX with `<MbConfigFields/>`**

In the scrollable body, the Timing `</section>` is followed by an `<hr/>` then the Model/Template/Instructions/Connectors/Length/Language/Reasoning markup (current lines 562-813). Delete that entire run of sections (from the `{/* Model */}` comment through the closing `) : null}` of the Reasoning block) and replace it with a single component, keeping the `<hr/>` that separates Timing from the config:

```tsx
            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            <MbConfigFields
              draft={draft}
              onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
            />
```

(The `<hr/>` here is the existing one at current line 560; ensure exactly one `<hr/>` sits between the Timing section and `<MbConfigFields/>`.)

- [ ] **Step 5: Delete the editor's upload sub-modals**

Delete the `<MbTemplateUploadModal .../>` and `<MbInstructionsUploadModal .../>` blocks near the bottom (current lines 847-858); they now render inside `MbConfigFields`. The component's outer `</Dialog.Root>` close stays.

- [ ] **Step 6: Run the schedule-editor and typecheck to verify green**

Run: `npx vitest run src/components/morning-briefing/__tests__/ScheduleEditorModal.test.tsx`
Expected: PASS (all existing tests — `mb-schedule-time`, `mb-template-select`, `mb-instructions-select`, `mb-language-select`, `mb-both-empty-error`, etc. still found).

Run: `npm run lint`  (= `tsc --noEmit`)
Expected: no errors. Note: `tsconfig.json` sets `noUnusedLocals`/`noUnusedParameters: true`, so any import, helper, or hook left behind in the editor after the deletions in Steps 1-5 will fail this — the typecheck is the guard that the cleanup is complete.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/morning-briefing/ScheduleEditorModal.tsx
git commit -m "refactor(morning-briefing): ScheduleEditorModal consumes MbConfigFields"
```

---

## Task 4: Update Run Now modal i18n copy

Do this before rewriting the modal so the new strings resolve. Update both locales: drop the schedule-picker keys, refresh title/description.

**Files:**
- Modify: `frontend/src/i18n/locales/en.json`
- Modify: `frontend/src/i18n/locales/zh-TW.json`

- [ ] **Step 1: Update `en.json` run_now_modal block**

Replace the `morning_briefing.run_now_modal` block (current en.json lines 1081-1090) with:

```json
    "run_now_modal": {
      "title": "Run a briefing now",
      "description": "Configure the settings below, then generate a briefing immediately. Your choices are remembered for next time.",
      "empty_error": "Pick a template or instructions before generating.",
      "failed": "Failed to start briefing",
      "cancel": "Cancel",
      "starting": "Starting…",
      "generate": "Generate briefing"
    },
```

- [ ] **Step 2: Update `zh-TW.json` run_now_modal block**

Replace the `morning_briefing.run_now_modal` block (current zh-TW.json lines 1081-1090) with:

```json
    "run_now_modal": {
      "title": "立即執行簡報",
      "description": "在下方設定選項，然後立即產生簡報。系統會記住您的選擇供下次使用。",
      "empty_error": "產生前請先選擇範本或指示。",
      "failed": "啟動簡報失敗",
      "cancel": "取消",
      "starting": "啟動中…",
      "generate": "產生簡報"
    },
```

- [ ] **Step 3: Verify JSON is valid**

Run: `node -e "require('./src/i18n/locales/en.json'); require('./src/i18n/locales/zh-TW.json'); console.log('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/i18n/locales/en.json frontend/src/i18n/locales/zh-TW.json
git commit -m "i18n(morning-briefing): Run Now full-form copy"
```

---

## Task 5: Rewrite `MbRunNowModal` as a full config form

**Files:**
- Rewrite: `frontend/src/components/morning-briefing/MbRunNowModal.tsx`
- Test: `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`:

```tsx
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import * as settingsApi from "../../../api/settings";
import { MbRunNowModal } from "../MbRunNowModal";
import { RUN_NOW_LS_KEY } from "../mbRunNowDraft";

describe("MbRunNowModal", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.localStorage.clear();
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders the full config controls and no schedule dropdown", async () => {
    render(
      <MbRunNowModal open onClose={vi.fn()} onStarted={vi.fn()} />,
    );
    expect(await screen.findByTestId("mb-template-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-instructions-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-language-select")).toBeInTheDocument();
    expect(screen.queryByTestId("mb-run-now-schedule")).not.toBeInTheDocument();
  });

  it("starts an ad-hoc run, persists the draft, and reports the report id", async () => {
    const startSpy = vi
      .spyOn(api, "startMbRun")
      .mockResolvedValue({ report_id: "rNew" });
    const onStarted = vi.fn();
    render(
      <MbRunNowModal open onClose={vi.fn()} onStarted={onStarted} />,
    );
    fireEvent.click(await screen.findByTestId("mb-run-now-start"));

    await waitFor(() => expect(onStarted).toHaveBeenCalledWith("rNew"));
    const payload = startSpy.mock.calls[0][0];
    expect(payload.schedule_id).toBeUndefined();
    expect(payload.template_id).toBe("mb_default");
    expect(payload.enabled_connectors).toEqual({
      provider_ids: [],
      web_search: false,
    });
    expect(window.localStorage.getItem(RUN_NOW_LS_KEY)).not.toBeNull();
  });

  it("disables Generate when freeform template has no instructions", async () => {
    window.localStorage.setItem(
      RUN_NOW_LS_KEY,
      JSON.stringify({ template_id: "freeform", instructions_id: null }),
    );
    render(
      <MbRunNowModal open onClose={vi.fn()} onStarted={vi.fn()} />,
    );
    expect(await screen.findByTestId("mb-run-now-start")).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`
Expected: FAIL — current modal still renders the schedule dropdown / new props mismatch.

- [ ] **Step 3: Rewrite the modal**

Replace the entire contents of `frontend/src/components/morning-briefing/MbRunNowModal.tsx` with:

```tsx
/**
 * MbRunNowModal — kick off a Morning Briefing run immediately with full
 * settings. A pure ad-hoc config form (model, template, instructions,
 * connectors, length, language, reasoning) — no schedule picker, no ticker.
 *
 * Prefills from the user's previous Run Now submission (localStorage) and
 * saves the config again on a successful Generate. Starting a run POSTs to
 * /runs/start (ad-hoc path, no schedule_id) and hands the new report_id back
 * to the page, which owns the live-streaming card.
 */
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { startMbRun, type MbRunStartIn } from "../../api/morning-briefing";

import {
  MbConfigFields,
  isBriefEmpty,
  type MbConfigDraft,
} from "./MbConfigFields";
import { loadRunNowDraft, saveRunNowDraft } from "./mbRunNowDraft";

interface Props {
  open: boolean;
  onClose: () => void;
  onStarted: (reportId: string) => void;
}

export function MbRunNowModal({ open, onClose, onStarted }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<MbConfigDraft>(() => loadRunNowDraft());
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Re-read the remembered config each time the modal opens.
  useEffect(() => {
    if (open) {
      setDraft(loadRunNowDraft());
      setErr(null);
    }
  }, [open]);

  const empty = isBriefEmpty(draft);

  async function handleStart() {
    setErr(null);
    setSubmitting(true);
    try {
      const payload: MbRunStartIn = {
        template_id: draft.template_id,
        instructions_id: draft.instructions_id,
        enabled_connectors: {
          provider_ids: draft.provider_ids,
          web_search: draft.web_search,
        },
        provider_kind: draft.provider_kind ?? undefined,
        model: draft.model ?? undefined,
        language: draft.language,
        length: draft.length,
        reasoning_effort: draft.reasoning_effort,
      };
      const { report_id } = await startMbRun(payload);
      saveRunNowDraft(draft);
      onStarted(report_id);
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? t("morning_briefing.run_now_modal.failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  {t("morning_briefing.run_now_modal.title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="text-[12px] text-[--color-text-tertiary] m-0">
                  {t("morning_briefing.run_now_modal.description")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("morning_briefing.run_now_modal.cancel")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <MbConfigFields
              draft={draft}
              onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
            />
          </div>

          <footer className="flex items-center justify-end gap-3 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
            {empty ? (
              <p
                data-testid="mb-run-now-empty-error"
                className="mr-auto text-[12px] text-[--color-feedback-danger] leading-[1.4]"
              >
                {t("morning_briefing.run_now_modal.empty_error")}
              </p>
            ) : err ? (
              <p className="mr-auto text-[12px] text-[--color-feedback-error] leading-[1.4]">
                {err}
              </p>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong] transition-colors text-[13px] font-medium"
            >
              {t("morning_briefing.run_now_modal.cancel")}
            </button>
            <button
              type="button"
              disabled={submitting || empty}
              onClick={() => void handleStart()}
              data-testid="mb-run-now-start"
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {submitting
                ? t("morning_briefing.run_now_modal.starting")
                : t("morning_briefing.run_now_modal.generate")}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/morning-briefing/MbRunNowModal.tsx frontend/src/components/morning-briefing/__tests__/MbRunNowModal.test.tsx
git commit -m "feat(morning-briefing): Run Now full config form with remembered choices"
```

---

## Task 6: Drop the `schedules` prop on the page's Run Now modal

`MbRunNowModal` no longer takes `schedules`. Remove the now-invalid prop so the page typechecks.

**Files:**
- Modify: `frontend/src/pages/departments/MorningBriefing.tsx:444-449`

- [ ] **Step 1: Remove the prop**

Change the `<MbRunNowModal .../>` usage (current lines 444-449) from:

```tsx
      <MbRunNowModal
        open={runNowOpen}
        schedules={schedules}
        onClose={() => setRunNowOpen(false)}
        onStarted={(reportId) => setLiveReportId(reportId)}
      />
```

to:

```tsx
      <MbRunNowModal
        open={runNowOpen}
        onClose={() => setRunNowOpen(false)}
        onStarted={(reportId) => setLiveReportId(reportId)}
      />
```

Leave `schedules` (and its source) in place — it is still used by the schedules view and `ScheduleEditorModal` elsewhere in the page.

- [ ] **Step 2: Run the page test + typecheck**

Run: `npx vitest run src/pages/departments/MorningBriefing.test.tsx`
Expected: PASS — including "opens the Run now modal" (clicks Run now, finds `mb-run-now-start`). The page test's `beforeEach` already mocks `listMbTemplates`, `listMbInstructions`, `getMbDataSources`, and `getEnabledModels`, so the full form mounts cleanly.

Run: `npm run lint`  (= `tsc --noEmit`)
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/departments/MorningBriefing.tsx
git commit -m "feat(morning-briefing): wire full-form Run Now on the page"
```

---

## Task 7: Full verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full morning-briefing frontend test suite**

Run: `npx vitest run src/components/morning-briefing src/pages/departments/MorningBriefing.test.tsx`
Expected: PASS — all morning-briefing component + page tests, including the new `MbConfigFields`, `mbRunNowDraft`, and `MbRunNowModal` suites and the unchanged `ScheduleEditorModal` suite.

- [ ] **Step 2: Typecheck + production build**

Run: `npm run build`
Expected: TypeScript passes and Vite build succeeds.

- [ ] **Step 3: Lint the frontend**

Run: `npm run lint`  (= `tsc --noEmit`)
Expected: no errors. (This is the same typecheck `npm run build` runs; there is no separate eslint/prettier npm script in this project.)

- [ ] **Step 4: Backend sanity (no backend code changed)**

Run from repo root: `uv run pytest packages/server/tests/routes/ -k morning_briefing -q`
Expected: PASS — the MB route tests still pass (the ad-hoc `/runs/start` contract is unchanged). Per project memory the full server suite can hang on SSE/stream tests, so this targeted run is the sanity check.

- [ ] **Step 5: Confirm the tree is clean**

Run: `git status --short`
Expected: empty — every change was committed in Tasks 1-6 (`npm run lint` does not modify files, so there is normally nothing new to commit here). If a pre-commit hook reformatted anything, `git add -A && git commit -m "chore(morning-briefing): formatting"`.

---

## Self-Review Notes

**Spec coverage:**
- Full form only / no schedule picker → Task 5 (modal rewrite; test asserts no `mb-run-now-schedule`).
- Approach A shared `MbConfigFields` → Tasks 1, 3.
- Remember previous choices via `localStorage` → Tasks 2, 5 (`loadRunNowDraft` on open, `saveRunNowDraft` on Generate).
- Library-default fallback (`mb_default`, runnable) → Task 2 (`libraryDefaultDraft`), Task 5 (test: default payload `template_id === "mb_default"`).
- `isBriefEmpty` gates Generate → Tasks 1, 5.
- Backend unchanged → no backend task; Task 7 sanity only.
- i18n en + zh-Hant, drop dead keys → Task 4.
- Tests rewritten; schedule-editor tests preserved → Tasks 3, 5, 6, 7.

**Type consistency:** `MbConfigDraft` (defined Task 1) is consumed identically in Tasks 2, 3, 5. `MbModelSelection`, `MbReasoningEffort`, `MbReportLength`, `MbDataSource`, `MbRunStartIn` match the existing `api/morning-briefing.ts` and `MbModelPicker` exports. `MbConfigFields`/`isBriefEmpty`/`Toggle`/`sectionTitle` exports match their imports in the editor and modal.

**No placeholders:** every code step shows complete content; edit steps name exact files, anchor code, and line ranges.
