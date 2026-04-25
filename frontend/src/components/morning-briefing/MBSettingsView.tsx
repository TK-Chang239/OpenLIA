import { useEffect, useState } from "react";

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
import { AddScheduleModal } from "./AddScheduleModal";
import { CustomSectionRow } from "./CustomSectionRow";
import { NotesPopover } from "./NotesPopover";
import { ScheduleRow } from "./ScheduleRow";
import { SectionRow } from "./SectionRow";
import { TopicChip } from "./TopicChip";

const LENGTHS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

interface Props {
  config: MbConfig;
  schedule: MbSchedule | null;
  onSaveConfig: (cfg: MbConfig) => Promise<MbConfig>;
  onSaveSchedule: (payload: MbScheduleUpsert) => Promise<MbSchedule>;
  onRemoveSchedule: () => Promise<void>;
}

type Toast = { kind: "success" | "error"; text: string };

export function MBSettingsView({
  config,
  schedule,
  onSaveConfig,
  onSaveSchedule,
  onRemoveSchedule,
}: Props) {
  const [draft, setDraft] = useState<MbConfig>(config);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [scheduleInitial, setScheduleInitial] = useState<
    MbScheduleUpsert | undefined
  >(undefined);
  const [topicInputs, setTopicInputs] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const enabled = new Set(draft.enabled_section_ids);

  const toggleSection = (id: string, next: boolean) => {
    const set = new Set(enabled);
    if (next) set.add(id);
    else set.delete(id);
    setDraft({ ...draft, enabled_section_ids: [...set] });
  };

  const updateTopics = (sectionId: string, topics: TopicEntry[]) => {
    setDraft({
      ...draft,
      section_topics: { ...draft.section_topics, [sectionId]: topics },
    });
  };

  const addTopic = (sectionId: string) => {
    const text = (topicInputs[sectionId] ?? "").trim();
    if (!text) return;
    const current = draft.section_topics[sectionId] ?? [];
    updateTopics(sectionId, [...current, { topic: text, notes: "" }]);
    setTopicInputs((p) => ({ ...p, [sectionId]: "" }));
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
      setToast({ kind: "success", text: "Settings saved." });
    } catch (err) {
      const text = err instanceof Error ? err.message : "Save failed.";
      setToast({ kind: "error", text });
    } finally {
      setSaving(false);
    }
  };

  const submitSchedule = async (payload: MbScheduleUpsert) => {
    try {
      await onSaveSchedule(payload);
      setScheduleModalOpen(false);
      setScheduleInitial(undefined);
      setToast({ kind: "success", text: "Schedule saved." });
    } catch (err) {
      const text =
        err instanceof Error ? err.message : "Schedule save failed.";
      setToast({ kind: "error", text });
    }
  };

  const editSchedule = () => {
    if (!schedule) return;
    setScheduleInitial({
      time: schedule.time,
      timezone: schedule.timezone,
      days_of_week: schedule.days_of_week,
      label: schedule.label,
    });
    setScheduleModalOpen(true);
  };

  const deleteSchedule = async () => {
    try {
      await onRemoveSchedule();
      setToast({ kind: "success", text: "Schedule removed." });
    } catch (err) {
      const text = err instanceof Error ? err.message : "Remove failed.";
      setToast({ kind: "error", text });
    }
  };

  return (
    <div className="space-y-6 relative" data-testid="mb-settings-view">
      <section>
        <h3 className="text-base font-semibold mb-2">Length</h3>
        <div className="flex gap-2">
          {LENGTHS.map((l) => (
            <button
              type="button"
              key={l}
              aria-pressed={draft.report_length === l}
              className="px-3 py-1 rounded-[var(--radius-lg,0.5rem)] border text-sm"
              style={{
                borderColor: "var(--color-border-subtle)",
                background:
                  draft.report_length === l
                    ? "var(--color-accent-primary)"
                    : "var(--color-bg-base)",
                color:
                  draft.report_length === l
                    ? "var(--color-accent-on)"
                    : "inherit",
              }}
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
              <SectionRow
                key={id}
                id={id}
                title={entry.title}
                hint={entry.hint}
                checked={isEnabled}
                onChange={(c) => toggleSection(id, c)}
              >
                {isEnabled && entry.hasTopics && (
                  <div className="space-y-2 mt-2">
                    <div className="flex gap-2">
                      <input
                        className="flex-1 rounded border px-2 py-1 text-sm"
                        style={{
                          borderColor: "var(--color-border-subtle)",
                        }}
                        placeholder={entry.topicPlaceholder}
                        value={topicInputs[id] ?? ""}
                        onChange={(e) =>
                          setTopicInputs((p) => ({
                            ...p,
                            [id]: e.target.value,
                          }))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            addTopic(id);
                          }
                        }}
                        data-testid={`topic-input-${id}`}
                      />
                      <button
                        type="button"
                        onClick={() => addTopic(id)}
                        className="px-3 py-1 rounded border text-sm"
                        style={{
                          borderColor: "var(--color-border-subtle)",
                        }}
                      >
                        Add
                      </button>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {topics.map((t, idx) => (
                        <NotesPopover
                          key={`${t.topic}-${idx}`}
                          topic={t.topic}
                          notes={t.notes}
                          onSave={(notes) => {
                            const next = topics.map((x, i) =>
                              i === idx ? { ...x, notes } : x,
                            );
                            updateTopics(id, next);
                          }}
                        >
                          <span>
                            <TopicChip
                              topic={t.topic}
                              hasNotes={t.notes.trim().length > 0}
                              onClick={() => {}}
                              onRemove={() => {
                                updateTopics(
                                  id,
                                  topics.filter((_, i) => i !== idx),
                                );
                              }}
                            />
                          </span>
                        </NotesPopover>
                      ))}
                    </div>
                  </div>
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
              </SectionRow>
            );
          })}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">Custom sections</h3>
          <button
            type="button"
            className="text-sm underline"
            onClick={addCustom}
            data-testid="mb-add-custom-section"
          >
            + Add
          </button>
        </div>
        <div className="space-y-2">
          {draft.custom_sections.map((cs, idx) => (
            <CustomSectionRow
              key={cs.id}
              section={cs}
              onChange={(p) => updateCustom(idx, p)}
              onRemove={() => removeCustom(idx)}
            />
          ))}
        </div>
      </section>

      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-base font-semibold">Schedule</h3>
          {!schedule && (
            <button
              type="button"
              onClick={() => {
                setScheduleInitial(undefined);
                setScheduleModalOpen(true);
              }}
              className="text-sm underline"
              data-testid="mb-add-schedule"
            >
              + Add schedule
            </button>
          )}
        </div>
        {schedule ? (
          <ScheduleRow
            schedule={schedule}
            onEdit={editSchedule}
            onDelete={deleteSchedule}
          />
        ) : (
          <p
            className="text-xs"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            No schedule yet.
          </p>
        )}
      </section>

      <div className="flex justify-end">
        <button
          type="button"
          className="px-4 py-2 rounded-[var(--radius-lg,0.5rem)] text-sm disabled:opacity-50"
          style={{
            background: "var(--color-accent-primary)",
            color: "var(--color-accent-on)",
          }}
          disabled={saving}
          onClick={save}
          data-testid="mb-save-settings"
        >
          {saving ? "Saving…" : "Save settings"}
        </button>
      </div>

      <AddScheduleModal
        open={scheduleModalOpen}
        onClose={() => {
          setScheduleModalOpen(false);
          setScheduleInitial(undefined);
        }}
        onSubmit={submitSchedule}
        initial={scheduleInitial}
      />

      {toast && (
        <div
          role="status"
          data-testid={`mb-toast-${toast.kind}`}
          className="fixed bottom-4 right-4 rounded-[var(--radius-lg,0.5rem)] px-3 py-2 text-sm shadow-md z-50"
          style={{
            background:
              toast.kind === "success"
                ? "var(--color-accent-primary)"
                : "var(--color-feedback-error)",
            color: "var(--color-accent-on)",
          }}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
