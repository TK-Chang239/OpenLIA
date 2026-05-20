import { useEffect, useRef, useState } from "react";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  CustomSection,
  MbConfig,
  ReportLength,
  TopicEntry,
} from "../../api/morning-briefing";
import {
  DEFAULT_MB_SECTIONS,
  MB_SECTION_CATALOG,
} from "../../lib/morning-briefing/section-catalog";
import { CustomSectionRow } from "./CustomSectionRow";
import { ModelPicker } from "./ModelPicker";
import { NotesPopover } from "./NotesPopover";
import { SectionRow } from "./SectionRow";
import { TopicChip } from "./TopicChip";

const LENGTH_IDS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

interface Props {
  config: MbConfig;
  onSaveConfig: (cfg: MbConfig) => Promise<MbConfig>;
  onError?: (msg: string) => void;
}

type Toast = { kind: "success" | "error"; text: string };

export function MBSettingsView({ config, onSaveConfig, onError }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<MbConfig>(config);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [editingTopicSection, setEditingTopicSection] = useState<string | null>(
    null,
  );
  const topicInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, [toast]);

  useEffect(() => {
    if (editingTopicSection && topicInputRef.current) {
      topicInputRef.current.focus();
    }
  }, [editingTopicSection]);

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

  const commitTopic = (sectionId: string, value: string) => {
    const text = value.trim();
    if (!text) return;
    const current = draft.section_topics[sectionId] ?? [];
    if (current.some((t) => t.topic.toLowerCase() === text.toLowerCase())) {
      return;
    }
    updateTopics(sectionId, [...current, { topic: text, notes: "" }]);
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
      setToast({
        kind: "success",
        text: t("morning_briefing.settings_view.saved_toast"),
      });
    } catch (err) {
      const text =
        err instanceof Error
          ? err.message
          : t("morning_briefing.settings_view.save_failed");
      setToast({ kind: "error", text });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="max-w-[880px] mx-auto px-8 pt-7 pb-16 relative"
      data-testid="mb-settings-view"
    >
      <SetSection eyebrow={t("morning_briefing.runnow.report_length")}>
        <p className="text-[13px] text-[--color-text-secondary] mb-3.5 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.settings_view.report_length_hint")}
        </p>
        <div
          className="inline-flex p-0.5 rounded-md border bg-[--color-bg-elevated]"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
          {LENGTH_IDS.map((id) => {
            const active = draft.report_length === id;
            return (
              <button
                type="button"
                key={id}
                aria-pressed={active}
                onClick={() => setDraft({ ...draft, report_length: id })}
                className="h-7 px-3.5 rounded-[5px] text-[13px] font-medium transition-colors duration-[--duration-normal]"
                style={{
                  background: active
                    ? "var(--color-accent-primary)"
                    : "transparent",
                  color: active
                    ? "var(--color-accent-on)"
                    : "var(--color-text-secondary)",
                }}
              >
                {t(`morning_briefing.length.${id}`)}
              </button>
            );
          })}
        </div>
      </SetSection>

      <SetSection number="01" eyebrow={t("morning_briefing.settings_view.report_sections")}>
        <p className="text-[13px] text-[--color-text-secondary] mb-3.5 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.settings_view.report_sections_hint")}
        </p>
        <div
          className="bg-[--color-bg-elevated] border rounded-[--radius-lg] overflow-hidden"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
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
                badge={
                  id === "executive_summary"
                    ? t("morning_briefing.runnow.always_on_summary")
                    : undefined
                }
                checked={isEnabled}
                onChange={(c) => toggleSection(id, c)}
              >
                {isEnabled && entry.hasTopics && (
                  <div className="flex flex-wrap gap-1.5 mt-3">
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
                    {editingTopicSection === id ? (
                      <span
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border-dashed border bg-transparent"
                        style={{ borderColor: "var(--color-border-secondary)" }}
                      >
                        <input
                          ref={topicInputRef}
                          type="text"
                          placeholder={t("morning_briefing.settings_view.topic_input_placeholder")}
                          data-testid={`topic-input-${id}`}
                          className="bg-transparent border-0 outline-0 text-[13px] text-[--color-text-primary] placeholder:text-[--color-text-tertiary] w-[150px]"
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === ",") {
                              e.preventDefault();
                              commitTopic(id, e.currentTarget.value);
                              e.currentTarget.value = "";
                            } else if (e.key === "Escape") {
                              setEditingTopicSection(null);
                            }
                          }}
                          onBlur={(e) => {
                            commitTopic(id, e.currentTarget.value);
                            setEditingTopicSection(null);
                          }}
                        />
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setEditingTopicSection(id)}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border-dashed border bg-transparent text-[13px] text-[--color-text-tertiary] hover:text-[--color-text-secondary] hover:border-[--color-text-secondary]"
                        style={{ borderColor: "var(--color-border-secondary)" }}
                      >
                        <Plus size={11} strokeWidth={2.5} />
                        {entry.topicPlaceholder ||
                          t("morning_briefing.settings_view.add_topic")}
                      </button>
                    )}
                  </div>
                )}
                {isEnabled && entry.hasReferencePortfolioToggle && (
                  <label
                    className="flex items-center gap-2.5 mt-3 px-3 py-2.5 rounded-md border bg-[--color-bg-base] text-[13px] text-[--color-text-secondary]"
                    style={{ borderColor: "var(--color-border-subtle)" }}
                  >
                    <input
                      type="checkbox"
                      checked={draft.reference_portfolio}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          reference_portfolio: e.target.checked,
                        })
                      }
                      className="accent-[--color-accent-primary]"
                    />
                    <span>
                      <strong className="text-[--color-text-primary] font-medium">
                        {t("morning_briefing.settings_view.reference_portfolio_strong")}
                      </strong>{" "}
                      {t("morning_briefing.settings_view.reference_portfolio_hint")}
                    </span>
                  </label>
                )}
              </SectionRow>
            );
          })}
        </div>
      </SetSection>

      <SetSection
        number="02"
        eyebrow={t("morning_briefing.settings_view.custom_sections")}
        action={
          <button
            type="button"
            onClick={addCustom}
            data-testid="mb-add-custom-section"
            className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            <Plus size={13} strokeWidth={1.8} />
            {t("morning_briefing.settings_view.add_section")}
          </button>
        }
      >
        <p className="text-[13px] text-[--color-text-secondary] mb-3.5 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.settings_view.custom_sections_hint")}
        </p>
        {draft.custom_sections.length === 0 ? (
          <div
            className="bg-[--color-bg-elevated] border rounded-[--radius-lg] py-7 text-center text-[13px]"
            style={{
              borderColor: "var(--color-border-subtle)",
              color: "var(--color-text-tertiary)",
            }}
          >
            {t("morning_briefing.settings_view.no_custom_yet")}
          </div>
        ) : (
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
        )}
      </SetSection>

      <SetSection number="03" eyebrow={t("morning_briefing.settings_view.default_model")}>
        <p className="text-[13px] text-[--color-text-secondary] mb-3 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.settings_view.default_model_hint")}
        </p>
        <ModelPicker
          departmentSlug="morning-briefing"
          onError={onError}
        />
      </SetSection>

      <div className="flex justify-end mt-8">
        <button
          type="button"
          className="inline-flex items-center h-9 px-4 rounded-md text-[13.5px] font-medium disabled:opacity-50 bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover]"
          disabled={saving}
          onClick={save}
          data-testid="mb-save-settings"
        >
          {saving
            ? t("morning_briefing.settings_view.saving")
            : t("morning_briefing.settings_view.save_settings")}
        </button>
      </div>

      {toast && (
        <div
          role="status"
          data-testid={`mb-toast-${toast.kind}`}
          className="fixed bottom-6 right-6 inline-flex items-center gap-2.5 px-3.5 py-2.5 rounded-md text-[13px] shadow-md z-50"
          style={{
            background:
              toast.kind === "success"
                ? "var(--color-text-primary)"
                : "var(--color-feedback-error)",
            color:
              toast.kind === "success"
                ? "var(--color-bg-base)"
                : "var(--color-feedback-error-on)",
          }}
        >
          {toast.kind === "success" ? (
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ background: "var(--color-accent-primary)" }}
            />
          ) : null}
          <span>{toast.text}</span>
        </div>
      )}
    </div>
  );
}

function SetSection({
  number,
  eyebrow,
  action,
  children,
}: {
  number?: string;
  eyebrow: string;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="mt-8 first:mt-0">
      <div className="flex items-center justify-between gap-3 mb-3">
        <span className="font-mono text-[11px] font-medium tracking-[0.14em] uppercase text-[--color-text-secondary] flex items-center gap-2">
          {number ? (
            <span className="text-[--color-text-tertiary]">{number}</span>
          ) : null}
          {eyebrow}
        </span>
        {action}
      </div>
      {children}
    </section>
  );
}
