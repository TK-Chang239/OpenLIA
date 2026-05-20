import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  CircleDashed,
  Plus,
  RotateCcw,
  Square,
  Zap,
} from "lucide-react";
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
import { useReportStream } from "../report/useReportStream";
import { CustomSectionRow } from "./CustomSectionRow";
import { ModelPicker } from "./ModelPicker";
import { NotesPopover } from "./NotesPopover";
import { SectionRow } from "./SectionRow";
import { TopicChip } from "./TopicChip";

const STORAGE_KEY = "mb_run_now_draft_v1";
const LENGTH_IDS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

interface Props {
  baseConfig: MbConfig;
  onError: (msg: string) => void;
  onReportSaved: (reportId: string) => void;
  onOpenReport: (reportId: string) => void;
}

function loadDraft(fallback: MbConfig): MbConfig {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as MbConfig;
    if (
      typeof parsed === "object" &&
      parsed &&
      Array.isArray(parsed.enabled_section_ids)
    ) {
      return { ...fallback, ...parsed };
    }
    return fallback;
  } catch {
    return fallback;
  }
}

function persistDraft(draft: MbConfig) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    /* localStorage unavailable; ignore */
  }
}

export function MBRunNowView({
  baseConfig,
  onError,
  onReportSaved,
  onOpenReport,
}: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<MbConfig>(() => loadDraft(baseConfig));
  const [editingTopicSection, setEditingTopicSection] = useState<string | null>(
    null,
  );
  const topicInputRef = useRef<HTMLInputElement | null>(null);
  const seenIdRef = useRef<string | null>(null);
  const seenErrorRef = useRef<string | null>(null);

  const { state, start, stop, reset } = useReportStream();

  useEffect(() => {
    persistDraft(draft);
  }, [draft]);

  useEffect(() => {
    if (editingTopicSection && topicInputRef.current) {
      topicInputRef.current.focus();
    }
  }, [editingTopicSection]);

  useEffect(() => {
    if (
      state.status === "complete" &&
      state.reportId &&
      seenIdRef.current !== state.reportId
    ) {
      seenIdRef.current = state.reportId;
      onReportSaved(state.reportId);
    } else if (
      state.status === "error" &&
      state.errorMessage &&
      seenErrorRef.current !== state.errorMessage
    ) {
      seenErrorRef.current = state.errorMessage;
      onError(state.errorMessage);
    }
  }, [state.status, state.reportId, state.errorMessage, onError, onReportSaved]);

  const enabled = useMemo(
    () => new Set(draft.enabled_section_ids),
    [draft.enabled_section_ids],
  );

  const running = state.status === "starting" || state.status === "writing";
  const hasResult = state.status === "complete" && state.reportId;

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
    if (current.some((t) => t.topic.toLowerCase() === text.toLowerCase()))
      return;
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

  const resetToSaved = () => {
    setDraft(baseConfig);
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
    }
  };

  const onRun = () => {
    seenIdRef.current = null;
    seenErrorRef.current = null;
    reset();
    start({
      url: "/api/departments/morning-briefing/report",
      body: {
        report_length: draft.report_length,
        enabled_section_ids: draft.enabled_section_ids,
        section_topics: draft.section_topics,
        custom_sections: draft.custom_sections,
        reference_portfolio: draft.reference_portfolio,
      },
    });
  };

  const onCancel = () => {
    stop();
  };

  return (
    <div
      className="max-w-[880px] mx-auto px-8 pt-7 pb-16 relative"
      data-testid="mb-runnow-view"
    >
      <div className="mb-6">
        <p className="text-[13px] text-[--color-text-secondary] m-0 leading-[1.5]">
          {t("morning_briefing.runnow.intro")}
        </p>
      </div>

      <SetSection eyebrow={t("morning_briefing.runnow.report_length")}>
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
                disabled={running}
                className="h-7 px-3.5 rounded-[5px] text-[13px] font-medium transition-colors duration-[--duration-normal] disabled:opacity-50"
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

      <SetSection number="01" eyebrow={t("morning_briefing.runnow.report_sections")}>
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
                {isEnabled && entry.hasTopics ? (
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
                          placeholder={t("morning_briefing.runnow.topic_input_placeholder")}
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
                        disabled={running}
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border-dashed border bg-transparent text-[13px] text-[--color-text-tertiary] hover:text-[--color-text-secondary] hover:border-[--color-text-secondary] disabled:opacity-50"
                        style={{ borderColor: "var(--color-border-secondary)" }}
                      >
                        <Plus size={11} strokeWidth={2.5} />
                        {entry.topicPlaceholder ||
                          t("morning_briefing.runnow.add_topic")}
                      </button>
                    )}
                  </div>
                ) : null}
                {isEnabled && entry.hasReferencePortfolioToggle ? (
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
                      disabled={running}
                      className="accent-[--color-accent-primary]"
                    />
                    <span>
                      <strong className="text-[--color-text-primary] font-medium">
                        {t("morning_briefing.runnow.reference_portfolio_strong")}
                      </strong>{" "}
                      {t("morning_briefing.runnow.reference_portfolio_hint")}
                    </span>
                  </label>
                ) : null}
              </SectionRow>
            );
          })}
        </div>
      </SetSection>

      <SetSection
        number="02"
        eyebrow={t("morning_briefing.runnow.custom_sections")}
        action={
          <button
            type="button"
            onClick={addCustom}
            disabled={running}
            className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] disabled:opacity-50"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            <Plus size={13} strokeWidth={1.8} />
            {t("morning_briefing.runnow.add_section")}
          </button>
        }
      >
        {draft.custom_sections.length === 0 ? (
          <div
            className="bg-[--color-bg-elevated] border rounded-[--radius-lg] py-7 text-center text-[13px]"
            style={{
              borderColor: "var(--color-border-subtle)",
              color: "var(--color-text-tertiary)",
            }}
          >
            {t("morning_briefing.runnow.no_custom_sections")}
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

      <SetSection number="03" eyebrow={t("morning_briefing.runnow.model_section")}>
        <p className="text-[13px] text-[--color-text-secondary] mb-3 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.runnow.model_description")}
        </p>
        <ModelPicker
          departmentSlug="morning-briefing"
          onError={onError}
        />
      </SetSection>

      {running ? (
        <ProgressPanel
          phase={state.phase}
          sections={state.sections}
          toolCalls={state.toolCalls}
          t={t}
        />
      ) : null}

      {hasResult ? (
        <div
          className="mt-7 p-4 rounded-[--radius-lg] border flex items-center gap-3"
          style={{
            borderColor: "rgba(107,130,0,0.3)",
            background: "rgba(107,130,0,0.06)",
          }}
        >
          <Check
            size={16}
            strokeWidth={2}
            style={{ color: "var(--color-feedback-success)" }}
          />
          <div className="flex-1 text-[13.5px] text-[--color-text-primary]">
            {t("morning_briefing.runnow.briefing_complete")}
          </div>
          <button
            type="button"
            onClick={() => state.reportId && onOpenReport(state.reportId)}
            data-testid="mb-runnow-view-report"
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md text-[13px] font-medium border border-[--color-text-primary] bg-[--color-text-primary] text-[--color-bg-base] hover:bg-black"
          >
            {t("morning_briefing.runnow.view_report")}
            <ArrowRight size={13} />
          </button>
        </div>
      ) : null}

      <div className="flex items-center justify-between mt-8">
        <button
          type="button"
          onClick={resetToSaved}
          disabled={running}
          className="inline-flex items-center gap-1.5 h-9 px-3 rounded-md text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] disabled:opacity-50"
        >
          <RotateCcw size={13} />
          {t("morning_briefing.runnow.reset_defaults")}
        </button>
        {running ? (
          <button
            type="button"
            onClick={onCancel}
            data-testid="mb-runnow-cancel"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md text-[13.5px] font-medium border bg-transparent text-[--color-feedback-error] hover:bg-[rgba(224,92,48,0.08)]"
            style={{ borderColor: "var(--color-feedback-error)" }}
          >
            <Square size={13} strokeWidth={2} fill="currentColor" />
            {t("morning_briefing.runnow.cancel")}
          </button>
        ) : (
          <button
            type="button"
            onClick={onRun}
            data-testid="mb-runnow-run"
            className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md text-[13.5px] font-medium bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover]"
          >
            <Zap size={14} strokeWidth={2} />
            {t("morning_briefing.runnow.run")}
          </button>
        )}
      </div>
    </div>
  );
}

function ProgressPanel({
  phase,
  sections,
  toolCalls,
  t,
}: {
  phase: string | null;
  sections: { id: string; title: string; status: string }[];
  toolCalls: { toolName: string }[];
  t: (key: string) => string;
}) {
  const phaseLabel =
    phase === "fetching_data"
      ? t("morning_briefing.runnow.phase_gathering_data")
      : phase === "writing"
        ? t("morning_briefing.runnow.phase_writing")
        : phase === "finalizing"
          ? t("morning_briefing.runnow.phase_finalizing")
          : t("morning_briefing.runnow.phase_starting");
  return (
    <div
      className="mt-7 p-5 rounded-[--radius-lg] border bg-[--color-bg-elevated] flex flex-col gap-3"
      style={{ borderColor: "var(--color-border-subtle)" }}
      data-testid="mb-runnow-progress"
    >
      <div className="flex items-center gap-2">
        <span
          className="w-1.5 h-1.5 rounded-full animate-live-pulse"
          style={{ background: "var(--color-accent-primary)" }}
        />
        <span className="font-mono text-[10px] tracking-[0.14em] uppercase text-[--color-text-secondary]">
          {phaseLabel}
        </span>
      </div>
      {sections.length > 0 ? (
        <ul className="flex flex-col gap-1.5 m-0 p-0 list-none">
          {sections.map((s, i) => (
            <li
              key={`${s.title}-${i}`}
              className="flex items-center gap-2 text-[13px]"
              style={{
                color:
                  s.status === "done"
                    ? "var(--color-text-primary)"
                    : "var(--color-text-secondary)",
              }}
            >
              {s.status === "done" ? (
                <Check
                  size={13}
                  strokeWidth={2.5}
                  style={{ color: "var(--color-feedback-success)" }}
                />
              ) : s.status === "writing" ? (
                <span className="animate-live-pulse">
                  <CircleDashed size={13} strokeWidth={2} />
                </span>
              ) : (
                <CircleDashed
                  size={13}
                  strokeWidth={2}
                  style={{ color: "var(--color-text-tertiary)" }}
                />
              )}
              {s.title}
            </li>
          ))}
        </ul>
      ) : null}
      {toolCalls.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {toolCalls.slice(-4).map((t, i) => (
            <span
              key={`${t.toolName}-${i}`}
              className="inline-flex items-center px-2 py-0.5 rounded font-mono text-[10px] tracking-[0.04em] uppercase"
              style={{
                background: "var(--color-surface-active)",
                color: "var(--color-text-secondary)",
              }}
            >
              {t.toolName}
            </span>
          ))}
        </div>
      ) : null}
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
