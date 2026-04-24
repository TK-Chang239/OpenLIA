import { useState } from "react";

import type {
  CustomSection,
  MbConfig,
  MbSchedule,
  MbScheduleUpsert,
  ReportLength,
  TopicEntry,
} from "../../api/morning-briefing";
import {
  DEFAULT_MB_SECTIONS,
  MB_SECTION_CATALOG,
} from "../../lib/morning-briefing/section-catalog";

const LENGTHS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

const DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

interface Props {
  config: MbConfig;
  schedule: MbSchedule | null;
  onSaveConfig: (cfg: MbConfig) => Promise<MbConfig>;
  onSaveSchedule: (payload: MbScheduleUpsert) => Promise<MbSchedule>;
  onRemoveSchedule: () => Promise<void>;
}

export function MBSettingsView({
  config,
  schedule,
  onSaveConfig,
  onSaveSchedule,
  onRemoveSchedule,
}: Props) {
  const [draft, setDraft] = useState<MbConfig>(config);
  const [saving, setSaving] = useState(false);

  const enabled = new Set(draft.enabled_section_ids);

  const toggleSection = (id: string) => {
    const next = new Set(enabled);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setDraft({ ...draft, enabled_section_ids: [...next] });
  };

  const updateTopics = (sectionId: string, topics: TopicEntry[]) => {
    setDraft({
      ...draft,
      section_topics: { ...draft.section_topics, [sectionId]: topics },
    });
  };

  const addCustom = () => {
    const id = crypto.randomUUID();
    const next: CustomSection = { id, title: "", description: "" };
    setDraft({ ...draft, custom_sections: [...draft.custom_sections, next] });
  };

  const updateCustom = (idx: number, patch: Partial<CustomSection>) => {
    const updated = draft.custom_sections.map((cs, i) =>
      i === idx ? { ...cs, ...patch } : cs,
    );
    setDraft({ ...draft, custom_sections: updated });
  };

  const removeCustom = (idx: number) => {
    setDraft({
      ...draft,
      custom_sections: draft.custom_sections.filter((_, i) => i !== idx),
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSaveConfig(draft);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <section>
        <h3 className="text-base font-semibold mb-2">Length</h3>
        <div className="flex gap-2">
          {LENGTHS.map((l) => (
            <button
              type="button"
              key={l}
              className={`px-3 py-1 rounded-md border ${
                draft.report_length === l
                  ? "bg-primary text-primary-foreground"
                  : "bg-surface"
              }`}
              onClick={() => setDraft({ ...draft, report_length: l })}
            >
              {l}
            </button>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-base font-semibold mb-2">Coverage sections</h3>
        <div className="space-y-2">
          {DEFAULT_MB_SECTIONS.map((id) => {
            const entry = MB_SECTION_CATALOG[id];
            const topics = draft.section_topics[id] ?? [];
            const isEnabled = enabled.has(id);
            return (
              <div
                key={id}
                className="rounded-md border border-border bg-surface p-3"
              >
                <label className="flex items-center gap-2 font-medium">
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={() => toggleSection(id)}
                  />
                  {entry.title}
                </label>
                <p className="text-xs text-muted-foreground mt-1">
                  {entry.hint}
                </p>
                {isEnabled && entry.hasTopics && (
                  <TopicsEditor
                    placeholder={entry.topicPlaceholder}
                    topics={topics}
                    onChange={(t) => updateTopics(id, t)}
                  />
                )}
                {isEnabled && entry.hasReferencePortfolioToggle && (
                  <label className="flex items-center gap-2 mt-2 text-sm">
                    <input
                      type="checkbox"
                      checked={draft.reference_portfolio}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          reference_portfolio: e.target.checked,
                        })
                      }
                    />
                    Reference Portfolio (inject holdings for the Portfolio
                    Watch block)
                  </label>
                )}
              </div>
            );
          })}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">Custom sections</h3>
          <button
            type="button"
            className="text-sm text-primary hover:underline"
            onClick={addCustom}
          >
            + Add
          </button>
        </div>
        <div className="space-y-2">
          {draft.custom_sections.map((cs, idx) => (
            <div
              key={cs.id}
              className="rounded-md border border-border bg-surface p-3 space-y-2"
            >
              <input
                className="w-full border rounded px-2 py-1"
                placeholder="Title"
                value={cs.title}
                onChange={(e) => updateCustom(idx, { title: e.target.value })}
              />
              <textarea
                className="w-full border rounded px-2 py-1"
                placeholder="Description — tells the LLM what this section covers"
                value={cs.description}
                onChange={(e) =>
                  updateCustom(idx, { description: e.target.value })
                }
              />
              <button
                type="button"
                className="text-xs text-destructive hover:underline"
                onClick={() => removeCustom(idx)}
              >
                Remove
              </button>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-base font-semibold mb-2">Schedule</h3>
        <ScheduleEditor
          schedule={schedule}
          onSave={onSaveSchedule}
          onRemove={onRemoveSchedule}
        />
      </section>

      <div className="flex justify-end">
        <button
          type="button"
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground disabled:opacity-50"
          disabled={saving}
          onClick={save}
        >
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>
    </div>
  );
}

function TopicsEditor({
  topics,
  placeholder,
  onChange,
}: {
  topics: TopicEntry[];
  placeholder: string;
  onChange: (topics: TopicEntry[]) => void;
}) {
  const [next, setNext] = useState("");

  const add = () => {
    const trimmed = next.trim();
    if (!trimmed) return;
    onChange([...topics, { topic: trimmed, notes: "" }]);
    setNext("");
  };

  const update = (idx: number, patch: Partial<TopicEntry>) => {
    onChange(topics.map((t, i) => (i === idx ? { ...t, ...patch } : t)));
  };

  const remove = (idx: number) => {
    onChange(topics.filter((_, i) => i !== idx));
  };

  return (
    <div className="space-y-2 mt-2">
      <div className="flex gap-2">
        <input
          className="flex-1 border rounded px-2 py-1"
          placeholder={placeholder}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
        />
        <button
          type="button"
          className="px-3 py-1 rounded border"
          onClick={add}
        >
          Add
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {topics.map((t, idx) => (
          <span
            key={idx}
            className="inline-flex items-center gap-2 rounded-full bg-muted px-2 py-1 text-xs"
          >
            <span>{t.topic}</span>
            <input
              className="border rounded px-1 text-xs w-32"
              placeholder="notes"
              value={t.notes}
              onChange={(e) => update(idx, { notes: e.target.value })}
            />
            <button
              type="button"
              className="text-destructive"
              onClick={() => remove(idx)}
            >
              ×
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}

function ScheduleEditor({
  schedule,
  onSave,
  onRemove,
}: {
  schedule: MbSchedule | null;
  onSave: (payload: MbScheduleUpsert) => Promise<MbSchedule>;
  onRemove: () => Promise<void>;
}) {
  const [time, setTime] = useState(schedule?.time ?? "07:00");
  const [timezone, setTimezone] = useState(
    schedule?.timezone ?? "America/New_York",
  );
  const [days, setDays] = useState<string[]>(
    schedule?.days_of_week ?? ["mon", "tue", "wed", "thu", "fri"],
  );
  const [label, setLabel] = useState(schedule?.label ?? "");
  const [saving, setSaving] = useState(false);

  const toggleDay = (d: string) => {
    const next = new Set(days);
    if (next.has(d)) next.delete(d);
    else next.add(d);
    setDays(Array.from(next));
  };

  const save = async () => {
    setSaving(true);
    try {
      await onSave({ time, timezone, days_of_week: days, label });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex gap-2">
        <input
          className="border rounded px-2 py-1"
          value={time}
          onChange={(e) => setTime(e.target.value)}
          placeholder="HH:MM"
        />
        <input
          className="flex-1 border rounded px-2 py-1"
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          placeholder="America/New_York"
        />
        <input
          className="flex-1 border rounded px-2 py-1"
          value={label}
          onChange={(e) => setLabel(e.target.value)}
          placeholder="Label (e.g., Pre-Market)"
        />
      </div>
      <div className="flex gap-1 flex-wrap">
        {DAY_NAMES.map((d) => (
          <button
            type="button"
            key={d}
            className={`px-2 py-1 rounded border text-xs ${
              days.includes(d) ? "bg-primary text-primary-foreground" : ""
            }`}
            onClick={() => toggleDay(d)}
          >
            {d}
          </button>
        ))}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className="px-3 py-1 rounded bg-primary text-primary-foreground disabled:opacity-50"
          disabled={saving}
          onClick={save}
        >
          {schedule ? "Update schedule" : "Create schedule"}
        </button>
        {schedule && (
          <button
            type="button"
            className="px-3 py-1 rounded border text-destructive"
            onClick={onRemove}
          >
            Remove
          </button>
        )}
      </div>
    </div>
  );
}
