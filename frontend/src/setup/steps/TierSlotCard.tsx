import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import type { TierEntry } from "../../api/setup";
import { testModel } from "../../api/setup";

const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "gemini", label: "Google Gemini" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "openai_compat", label: "OpenAI-compatible" },
  { value: "ollama", label: "Ollama (local)" },
];

export interface TierEntryWithStatus extends TierEntry {
  ui_id: string;
  status: "untested" | "testing" | "ok" | "error";
  error?: string | null;
}

export function TierSlotCard({
  tierLabel,
  tierValue,
  entries,
  onChange,
}: {
  tierLabel: string;
  tierValue: "thinking" | "everyday" | "quick";
  entries: TierEntryWithStatus[];
  onChange: (entries: TierEntryWithStatus[]) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState<TierEntry>({ provider: "openai", model: "", api_key: "" });

  const runTest = async (entry: TierEntryWithStatus, currentEntries: TierEntryWithStatus[]) => {
    onChange(
      currentEntries.map((e) =>
        e.ui_id === entry.ui_id ? { ...e, status: "testing", error: null } : e,
      ),
    );
    try {
      const result = await testModel({
        provider: entry.provider,
        model: entry.model,
        api_key: entry.api_key,
        base_url: entry.base_url,
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
  };

  return (
    <section
      data-testid={`tier-${tierValue}`}
      className="border border-[--color-border-subtle] rounded-[--radius-md] p-4 mb-4"
    >
      <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">{tierLabel}</h3>
      <ul className="flex flex-col gap-2 mb-3">
        {entries.map((entry) => (
          <li
            key={entry.ui_id}
            className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]"
          >
            <div className="flex items-center gap-3">
              <span className="text-xs text-[--color-text-tertiary]">{entry.provider}</span>
              <span className="text-sm text-[--color-text-primary]">{entry.model}</span>
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
            <button
              type="button"
              aria-label="Remove model"
              onClick={() => removeEntry(entry.ui_id)}
              className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
            >
              <Trash2 size={14} />
            </button>
          </li>
        ))}
      </ul>
      {adding ? (
        <div className="flex flex-col gap-2 border border-[--color-border-subtle] rounded-[--radius-md] p-3 bg-[--color-bg-base]">
          <select
            value={draft.provider}
            onChange={(e) => setDraft({ ...draft, provider: e.target.value })}
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          >
            {PROVIDER_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <input
            name="model"
            value={draft.model}
            onChange={(e) => setDraft({ ...draft, model: e.target.value })}
            placeholder="Model ID"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <input
            name="api_key"
            type="password"
            value={draft.api_key ?? ""}
            onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
            placeholder="API key"
            className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              data-test="cancel"
              className="h-8 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
              onClick={() => setAdding(false)}
            >
              Cancel
            </button>
            <button
              type="button"
              data-test="test"
              onClick={async () => {
                const ui_id = crypto.randomUUID();
                const newEntry: TierEntryWithStatus = { ...draft, ui_id, status: "testing" };
                const next = [...entries, newEntry];
                onChange(next);
                setAdding(false);
                setDraft({ provider: "openai", model: "", api_key: "" });
                await runTest(newEntry, next);
              }}
              className="h-8 px-3 rounded-[--radius-md] text-sm border border-[--color-border-secondary]"
            >
              Test & Save
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          data-test="add"
          onClick={() => setAdding(true)}
          className="inline-flex items-center gap-2 h-8 px-3 rounded-[--radius-md] border border-dashed border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <Plus size={14} />
          Add model
        </button>
      )}
    </section>
  );
}
