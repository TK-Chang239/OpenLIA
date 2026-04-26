import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";

export interface ApiKey {
  id: string;
  label: string;
  api_key: string;
  base_url?: string;
}

type Editor =
  | { mode: "closed" }
  | { mode: "add" }
  | { mode: "edit"; id: string };

export function KeysScreen({
  totalSteps,
  keys,
  onChange,
  onBack,
  onNext,
}: {
  totalSteps: number;
  keys: ApiKey[];
  onChange: (next: ApiKey[]) => void;
  onBack: () => void;
  onNext: () => void;
}) {
  const [editor, setEditor] = useState<Editor>(keys.length === 0 ? { mode: "add" } : { mode: "closed" });
  const [draft, setDraft] = useState<{ label: string; api_key: string; base_url: string }>({
    label: "",
    api_key: "",
    base_url: "",
  });
  const [showAdvanced, setShowAdvanced] = useState(false);

  const startAdd = () => {
    setDraft({ label: "", api_key: "", base_url: "" });
    setShowAdvanced(false);
    setEditor({ mode: "add" });
  };
  const startEdit = (k: ApiKey) => {
    setDraft({ label: k.label, api_key: k.api_key, base_url: k.base_url ?? "" });
    setShowAdvanced(Boolean(k.base_url));
    setEditor({ mode: "edit", id: k.id });
  };
  const closeEditor = () => {
    setEditor({ mode: "closed" });
    setDraft({ label: "", api_key: "", base_url: "" });
    setShowAdvanced(false);
  };

  const labelTaken = keys.some(
    (k) =>
      k.label.trim().toLowerCase() === draft.label.trim().toLowerCase() &&
      !(editor.mode === "edit" && k.id === editor.id),
  );
  const canSave = draft.label.trim().length > 0 && draft.api_key.trim().length > 0 && !labelTaken;

  const saveDraft = () => {
    if (!canSave) return;
    const updated: ApiKey = {
      id: editor.mode === "edit" ? editor.id : crypto.randomUUID(),
      label: draft.label.trim(),
      api_key: draft.api_key.trim(),
      base_url: draft.base_url.trim() || undefined,
    };
    if (editor.mode === "edit") {
      onChange(keys.map((k) => (k.id === editor.id ? updated : k)));
    } else {
      onChange([...keys, updated]);
    }
    closeEditor();
  };

  const removeKey = (id: string) => {
    onChange(keys.filter((k) => k.id !== id));
    if (editor.mode === "edit" && editor.id === id) closeEditor();
  };

  const canSubmit = keys.length > 0 && editor.mode === "closed";

  return (
    <WizardShell
      title="API Keys"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={<WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!canSubmit} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-2">
        Add one or more API keys. You'll pick which model to use for each key on the next screen.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        Give each key a label so you can recognize it later (e.g. "My OpenAI", "Work Anthropic").
      </p>

      <ul className="flex flex-col gap-2 mb-3" data-testid="api-keys-list">
        {keys.map((k) => (
          <li
            key={k.id}
            className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-sm text-[--color-text-primary] truncate">{k.label}</span>
              <span className="text-xs text-[--color-text-tertiary] truncate">
                {k.api_key.slice(0, 6)}…{k.api_key.slice(-4)}
              </span>
              {k.base_url ? (
                <span className="text-xs text-[--color-text-tertiary] truncate">{k.base_url}</span>
              ) : null}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Edit key"
                data-test="edit-key"
                onClick={() => startEdit(k)}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary]"
              >
                <Pencil size={14} />
              </button>
              <button
                type="button"
                aria-label="Remove key"
                onClick={() => removeKey(k.id)}
                className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </li>
        ))}
      </ul>

      {editor.mode !== "closed" ? (
        <div className="flex flex-col gap-2 border border-[--color-border-subtle] rounded-[--radius-md] p-3 bg-[--color-bg-base]">
          <input
            name="key_label"
            value={draft.label}
            onChange={(e) => setDraft({ ...draft, label: e.target.value })}
            placeholder="Label (e.g. My OpenAI)"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <input
            name="key_value"
            type="password"
            value={draft.api_key}
            onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
            placeholder="API key"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          {showAdvanced ? (
            <input
              name="key_base_url"
              value={draft.base_url}
              onChange={(e) => setDraft({ ...draft, base_url: e.target.value })}
              placeholder="Base URL (for self-hosted / proxy endpoints)"
              className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          ) : (
            <button
              type="button"
              onClick={() => setShowAdvanced(true)}
              className="text-xs text-[--color-text-tertiary] hover:text-[--color-text-primary] self-start"
            >
              Advanced: set custom base URL
            </button>
          )}
          {labelTaken ? (
            <p className="text-xs text-[--color-feedback-error]">Label already used.</p>
          ) : null}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              data-test="cancel-key"
              className="h-8 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
              onClick={closeEditor}
            >
              Cancel
            </button>
            <button
              type="button"
              data-test="save-key"
              disabled={!canSave}
              onClick={saveDraft}
              className="h-8 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary] disabled:opacity-50"
            >
              {editor.mode === "edit" ? "Update key" : "Save key"}
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          data-test="add-key"
          onClick={startAdd}
          className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <Plus size={14} />
          Add API key
        </button>
      )}
    </WizardShell>
  );
}
