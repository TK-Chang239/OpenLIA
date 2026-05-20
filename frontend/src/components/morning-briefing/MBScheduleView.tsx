import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbSchedule,
  MbScheduleUpsert,
} from "../../api/morning-briefing";
import { AddScheduleModal } from "./AddScheduleModal";
import { ScheduleRow } from "./ScheduleRow";

interface Props {
  schedules: MbSchedule[] | null | undefined;
  loading?: boolean;
  onCreateSchedule: (payload: MbScheduleUpsert) => Promise<MbSchedule>;
  onUpdateSchedule: (
    id: string,
    payload: MbScheduleUpsert,
  ) => Promise<MbSchedule>;
  onRemoveSchedule: (id: string) => Promise<void>;
}

type Toast = { kind: "success" | "error"; text: string };

export function MBScheduleView({
  schedules: schedulesProp,
  loading,
  onCreateSchedule,
  onUpdateSchedule,
  onRemoveSchedule,
}: Props) {
  const { t } = useTranslation();
  const schedules = schedulesProp ?? [];
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [initial, setInitial] = useState<MbScheduleUpsert | undefined>(
    undefined,
  );
  const [toast, setToast] = useState<Toast | null>(null);

  useEffect(() => {
    if (!toast) return;
    const id = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(id);
  }, [toast]);

  const submit = async (payload: MbScheduleUpsert) => {
    try {
      if (editingId) {
        await onUpdateSchedule(editingId, payload);
      } else {
        await onCreateSchedule(payload);
      }
      setModalOpen(false);
      setEditingId(null);
      setInitial(undefined);
      setToast({
        kind: "success",
        text: t("morning_briefing.schedule_view.saved_toast"),
      });
    } catch (err) {
      const text =
        err instanceof Error
          ? err.message
          : t("morning_briefing.schedule_view.save_failed");
      setToast({ kind: "error", text });
    }
  };

  const editSchedule = (schedule: MbSchedule) => {
    setEditingId(schedule.id);
    setInitial({
      time: schedule.time,
      timezone: schedule.timezone,
      days_of_week: schedule.days_of_week,
      label: schedule.label,
    });
    setModalOpen(true);
  };

  const deleteSchedule = async (id: string) => {
    try {
      await onRemoveSchedule(id);
      setToast({
        kind: "success",
        text: t("morning_briefing.schedule_view.removed_toast"),
      });
    } catch (err) {
      const text =
        err instanceof Error
          ? err.message
          : t("morning_briefing.schedule_view.remove_failed");
      setToast({ kind: "error", text });
    }
  };

  const openAdd = () => {
    setEditingId(null);
    setInitial(undefined);
    setModalOpen(true);
  };

  return (
    <div
      className="max-w-[880px] mx-auto px-8 pt-7 pb-16 relative"
      data-testid="mb-schedule-view"
    >
      <section>
        <div className="flex items-center justify-between gap-3 mb-3">
          <span className="font-mono text-[11px] font-medium tracking-[0.14em] uppercase text-[--color-text-secondary]">
            {t("morning_briefing.schedule_view.active_schedules")}
            {schedules.length > 0 ? (
              <span
                aria-hidden="true"
                className="ml-2 font-mono text-[10px] tracking-[0.04em] px-1.5 py-px rounded-full"
                style={{
                  background: "var(--color-surface-active)",
                  color: "var(--color-text-secondary)",
                }}
              >
                {schedules.length}
              </span>
            ) : null}
          </span>
          <button
            type="button"
            data-testid="mb-add-schedule"
            onClick={openAdd}
            className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md border bg-transparent text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            <Plus size={13} strokeWidth={1.8} />
            {t("morning_briefing.schedule_view.add_schedule")}
          </button>
        </div>
        <p className="text-[13px] text-[--color-text-secondary] mb-3.5 leading-[1.5] m-0 -mt-1.5">
          {t("morning_briefing.schedule_view.description")}
        </p>
        {loading ? (
          <div
            className="bg-[--color-bg-elevated] border rounded-[--radius-lg] py-7 text-center text-[13px]"
            style={{
              borderColor: "var(--color-border-subtle)",
              color: "var(--color-text-tertiary)",
            }}
          >
            {t("morning_briefing.schedule_view.loading")}
          </div>
        ) : schedules.length > 0 ? (
          <div
            className="bg-[--color-bg-elevated] border rounded-[--radius-lg] overflow-hidden"
            style={{ borderColor: "var(--color-border-subtle)" }}
          >
            {schedules.map((s) => (
              <ScheduleRow
                key={s.id}
                schedule={s}
                onEdit={() => editSchedule(s)}
                onDelete={() => void deleteSchedule(s.id)}
              />
            ))}
          </div>
        ) : (
          <div
            className="bg-[--color-bg-elevated] border rounded-[--radius-lg] py-7 text-center text-[13px]"
            style={{
              borderColor: "var(--color-border-subtle)",
              color: "var(--color-text-tertiary)",
            }}
          >
            {t("morning_briefing.schedule_view.empty")}
          </div>
        )}
      </section>

      <AddScheduleModal
        open={modalOpen}
        onClose={() => {
          setModalOpen(false);
          setEditingId(null);
          setInitial(undefined);
        }}
        onSubmit={submit}
        initial={initial}
      />

      {toast ? (
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
      ) : null}
    </div>
  );
}
