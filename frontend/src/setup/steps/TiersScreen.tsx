import { useMemo, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { testModel } from "../../api/setup";
import { inferProvider } from "./inferProvider";
import type { ApiKey } from "./KeysScreen";

export type TierName = "thinking" | "everyday" | "quick";

export interface TierEntry {
  ui_id: string;
  key_id: string;
  model: string;
  status: "untested" | "testing" | "ok" | "error";
  error?: string | null;
}

export type TierMap = Record<TierName, TierEntry[]>;

export function TiersScreen({
  totalSteps,
  requiredTiers,
  keys,
  tiers,
  onChange,
  onBack,
  onNext,
  loading,
  submitError,
}: {
  totalSteps: number;
  requiredTiers: TierName[];
  keys: ApiKey[];
  tiers: TierMap;
  onChange: (next: TierMap) => void;
  onBack: () => void;
  onNext: () => void;
  loading: boolean;
  submitError: string | null;
}) {
  const tierHasGreen = (entries: TierEntry[]) => entries.some((e) => e.status === "ok");
  const canSubmit = useMemo(
    () => requiredTiers.every((tier) => tierHasGreen(tiers[tier])),
    [requiredTiers, tiers],
  );

  const setTier = (tier: TierName, entries: TierEntry[]) =>
    onChange({ ...tiers, [tier]: entries });

  return (
    <WizardShell
      title="AI Models"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={!canSubmit}
          loading={loading}
        />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-2">
        Choose which key and model to use for each tier. OpenLIA uses a Thinking model for deep
        analysis, an Everyday model for general chat, and a Quick model for classification.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        Required: <strong>{requiredTiers.join(", ")}</strong>. At least one working entry per tier.
      </p>
      {(["thinking", "everyday", "quick"] as TierName[]).map((tier) => (
        <TierCard
          key={tier}
          tierLabel={tier[0].toUpperCase() + tier.slice(1)}
          tierValue={tier}
          keys={keys}
          entries={tiers[tier]}
          onChange={(entries) => setTier(tier, entries)}
        />
      ))}
      {submitError ? (
        <p className="text-sm text-[--color-feedback-error] mt-4">{submitError}</p>
      ) : null}
    </WizardShell>
  );
}

type TierEditor = { mode: "closed" } | { mode: "add" } | { mode: "edit"; ui_id: string };

function TierCard({
  tierLabel,
  tierValue,
  keys,
  entries,
  onChange,
}: {
  tierLabel: string;
  tierValue: TierName;
  keys: ApiKey[];
  entries: TierEntry[];
  onChange: (entries: TierEntry[]) => void;
}) {
  const [editor, setEditor] = useState<TierEditor>({ mode: "closed" });
  const [draft, setDraft] = useState<{ key_id: string; model: string }>({
    key_id: keys[0]?.id ?? "",
    model: "",
  });

  const runTest = async (entry: TierEntry, currentEntries: TierEntry[]) => {
    const key = keys.find((k) => k.id === entry.key_id);
    if (!key) {
      onChange(
        currentEntries.map((e) =>
          e.ui_id === entry.ui_id
            ? { ...e, status: "error", error: "Selected key was removed" }
            : e,
        ),
      );
      return;
    }
    onChange(
      currentEntries.map((e) =>
        e.ui_id === entry.ui_id ? { ...e, status: "testing", error: null } : e,
      ),
    );
    try {
      const result = await testModel({
        provider: inferProvider(entry.model, key.api_key, key.base_url),
        model: entry.model,
        api_key: key.api_key,
        base_url: key.base_url,
      });
      onChange(
        currentEntries.map((e) =>
          e.ui_id === entry.ui_id
            ? { ...e, status: result.ok ? "ok" : "error", error: result.error }
            : e,
        ),
      );
    } catch (err) {
      onChange(
        currentEntries.map((e) =>
          e.ui_id === entry.ui_id
            ? { ...e, status: "error", error: err instanceof Error ? err.message : "test failed" }
            : e,
        ),
      );
    }
  };

  const removeEntry = (ui_id: string) => {
    onChange(entries.filter((e) => e.ui_id !== ui_id));
    if (editor.mode === "edit" && editor.ui_id === ui_id) closeEditor();
  };

  const startAdd = () => {
    setDraft({ key_id: keys[0]?.id ?? "", model: "" });
    setEditor({ mode: "add" });
  };
  const startEdit = (entry: TierEntry) => {
    setDraft({ key_id: entry.key_id, model: entry.model });
    setEditor({ mode: "edit", ui_id: entry.ui_id });
  };
  const closeEditor = () => {
    setEditor({ mode: "closed" });
    setDraft({ key_id: keys[0]?.id ?? "", model: "" });
  };

  const saveDraft = async () => {
    if (!draft.key_id || !draft.model.trim()) return;
    if (editor.mode === "edit") {
      const updated: TierEntry = {
        ui_id: editor.ui_id,
        key_id: draft.key_id,
        model: draft.model.trim(),
        status: "testing",
      };
      const next = entries.map((e) => (e.ui_id === editor.ui_id ? updated : e));
      onChange(next);
      closeEditor();
      await runTest(updated, next);
      return;
    }
    const newEntry: TierEntry = {
      ui_id: crypto.randomUUID(),
      key_id: draft.key_id,
      model: draft.model.trim(),
      status: "testing",
    };
    const next = [...entries, newEntry];
    onChange(next);
    closeEditor();
    await runTest(newEntry, next);
  };

  return (
    <section
      data-testid={`tier-${tierValue}`}
      className="border border-[--color-border-subtle] rounded-[--radius-md] p-4 mb-4"
    >
      <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">{tierLabel}</h3>
      <ul className="flex flex-col gap-2 mb-3">
        {entries.map((entry) => {
          const key = keys.find((k) => k.id === entry.key_id);
          const isEditing = editor.mode === "edit" && editor.ui_id === entry.ui_id;
          return (
            <li
              key={entry.ui_id}
              className="flex flex-col gap-2 px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs text-[--color-text-tertiary] truncate">
                    {key?.label ?? "(removed key)"}
                  </span>
                  <span className="text-sm text-[--color-text-primary] truncate">
                    {entry.model}
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full ${
                      entry.status === "ok"
                        ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
                        : entry.status === "error"
                          ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
                          : "bg-[--color-surface-active] text-[--color-text-tertiary]"
                    }`}
                  >
                    {entry.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {entry.status === "error" ? (
                    <button
                      type="button"
                      aria-label="Retry test"
                      onClick={() => runTest(entry, entries)}
                      className="text-xs px-2 h-7 rounded-[--radius-md] border border-[--color-border-secondary] text-[--color-text-secondary] hover:text-[--color-text-primary]"
                    >
                      Retry
                    </button>
                  ) : null}
                  <button
                    type="button"
                    aria-label={isEditing ? "Close editor" : "Edit model"}
                    data-test="edit"
                    onClick={() => (isEditing ? closeEditor() : startEdit(entry))}
                    className={`text-[--color-text-secondary] hover:text-[--color-text-primary] ${
                      isEditing ? "text-[--color-text-primary]" : ""
                    }`}
                  >
                    <Pencil size={14} />
                  </button>
                  <button
                    type="button"
                    aria-label="Remove model"
                    onClick={() => removeEntry(entry.ui_id)}
                    className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              </div>
              {entry.status === "error" && entry.error && !isEditing ? (
                <p className="text-xs text-[--color-feedback-error] break-words">{entry.error}</p>
              ) : null}
              {isEditing ? <EditorBlock keys={keys} draft={draft} setDraft={setDraft} onCancel={closeEditor} onSave={saveDraft} /> : null}
            </li>
          );
        })}
      </ul>
      {editor.mode === "add" ? (
        <EditorBlock keys={keys} draft={draft} setDraft={setDraft} onCancel={closeEditor} onSave={saveDraft} />
      ) : (
        <button
          type="button"
          data-test="add"
          onClick={startAdd}
          disabled={keys.length === 0 || editor.mode === "edit"}
          className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] disabled:opacity-50"
        >
          <Plus size={14} />
          Add model
        </button>
      )}
    </section>
  );
}

function EditorBlock({
  keys,
  draft,
  setDraft,
  onCancel,
  onSave,
}: {
  keys: ApiKey[];
  draft: { key_id: string; model: string };
  setDraft: (next: { key_id: string; model: string }) => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  return (
    <div className="flex flex-col gap-2 border border-[--color-border-subtle] rounded-[--radius-md] p-3 bg-[--color-bg-base] mt-1">
      <select
        name="key_id"
        value={draft.key_id}
        onChange={(e) => setDraft({ ...draft, key_id: e.target.value })}
        className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
      >
        {keys.map((k) => (
          <option key={k.id} value={k.id}>
            {k.label}
          </option>
        ))}
      </select>
      <input
        name="model"
        value={draft.model}
        onChange={(e) => setDraft({ ...draft, model: e.target.value })}
        placeholder="Model ID (e.g. gpt-4o, claude-sonnet-4-5, gemini-2.5-pro)"
        className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
      />
      <div className="flex justify-end gap-2">
        <button
          type="button"
          data-test="cancel"
          className="h-8 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
          onClick={onCancel}
        >
          Cancel
        </button>
        <button
          type="button"
          data-test="test"
          disabled={!draft.key_id || !draft.model.trim()}
          onClick={onSave}
          className="h-8 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary] disabled:opacity-50"
        >
          Test &amp; Save
        </button>
      </div>
    </div>
  );
}
