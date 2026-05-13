import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import type { ApiKey } from "./KeysScreen";

export interface ModelEntry {
  key_id: string;
  model_ref: string;
  display_name: string;
}

interface Props {
  totalSteps: number;
  keys: ApiKey[];
  entries: ModelEntry[];
  onChange: (next: ModelEntry[]) => void;
  onBack: () => void;
  onNext: () => void;
}

type Draft = { model_ref: string; display_name: string };

export function RegisterModelsScreen({
  totalSteps,
  keys,
  entries,
  onChange,
  onBack,
  onNext,
}: Props) {
  const canSubmit = entries.length > 0;

  return (
    <WizardShell
      title="Register Models"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={<WizardFooter onBack={onBack} onNext={onNext} nextDisabled={!canSubmit} />}
    >
      <p className="text-sm text-[--color-text-secondary] mb-2">
        Register the models you want OpenLIA to use. For each API key, add zero or more
        models with their provider model identifier and a friendly display name.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        You'll assign these models to departments and system roles on the next screen.
      </p>

      <div className="flex flex-col gap-4">
        {keys.map((k) => (
          <KeyCard
            key={k.id}
            apiKey={k}
            entries={entries.filter((e) => e.key_id === k.id)}
            onAdd={(draft) =>
              onChange([
                ...entries,
                {
                  key_id: k.id,
                  model_ref: draft.model_ref.trim(),
                  display_name: draft.display_name.trim(),
                },
              ])
            }
            onRemove={(idx) => {
              // Map local index (within this key's entries) to absolute index.
              let seen = 0;
              const next = entries.filter((e) => {
                if (e.key_id !== k.id) return true;
                const keep = seen !== idx;
                seen += 1;
                return keep;
              });
              onChange(next);
            }}
          />
        ))}
      </div>
    </WizardShell>
  );
}

function KeyCard({
  apiKey,
  entries,
  onAdd,
  onRemove,
}: {
  apiKey: ApiKey;
  entries: ModelEntry[];
  onAdd: (draft: Draft) => void;
  onRemove: (idx: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>({ model_ref: "", display_name: "" });

  const canSave = draft.model_ref.trim().length > 0 && draft.display_name.trim().length > 0;

  const save = () => {
    if (!canSave) return;
    onAdd(draft);
    setDraft({ model_ref: "", display_name: "" });
    setEditing(false);
  };

  return (
    <section
      data-testid={`register-card-${apiKey.id}`}
      className="border border-[--color-border-subtle] rounded-[--radius-md] p-4"
    >
      <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">{apiKey.label}</h3>
      <ul className="flex flex-col gap-2 mb-3">
        {entries.map((entry, idx) => (
          <li
            key={`${entry.model_ref}-${idx}`}
            className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="text-sm text-[--color-text-primary] truncate">
                {entry.display_name}
              </span>
              <span className="text-xs text-[--color-text-tertiary] truncate">
                {entry.model_ref}
              </span>
            </div>
            <button
              type="button"
              aria-label="Remove model"
              onClick={() => onRemove(idx)}
              className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
      {editing ? (
        <div className="flex flex-col gap-2 border border-[--color-border-subtle] rounded-[--radius-md] p-3 bg-[--color-bg-base]">
          <input
            name="model_ref"
            value={draft.model_ref}
            onChange={(e) => setDraft({ ...draft, model_ref: e.target.value })}
            placeholder="Model ID (e.g. gpt-5.4-pro)"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <input
            name="display_name"
            value={draft.display_name}
            onChange={(e) => setDraft({ ...draft, display_name: e.target.value })}
            placeholder="Display name (e.g. GPT 5.4 Pro)"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setEditing(false);
                setDraft({ model_ref: "", display_name: "" });
              }}
              className="h-8 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!canSave}
              onClick={save}
              className="h-8 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary] disabled:opacity-50"
            >
              Save
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setEditing(true)}
          className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <Plus size={14} />
          Add model
        </button>
      )}
    </section>
  );
}
