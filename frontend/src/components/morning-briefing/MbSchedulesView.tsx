/**
 * MbSchedulesView — full-screen list of Morning Briefing schedules.
 *
 * Lists each schedule with its next fire time (via formatNextBriefing),
 * enabled state, and edit / delete affordances. "New schedule" and per-row
 * "Edit" open the ScheduleEditorModal (owned by the parent page).
 */
import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbSchedule } from "../../api/morning-briefing";
import { formatNextBriefing } from "../../lib/morning-briefing/next-briefing";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  schedules: MbSchedule[];
  onBack: () => void;
  onAdd: () => void;
  onEdit: (schedule: MbSchedule) => void;
  onRemove: (id: string) => Promise<void>;
}

export function MbSchedulesView({
  schedules,
  onBack,
  onAdd,
  onEdit,
  onRemove,
}: Props) {
  const { t } = useTranslation();
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);

  return (
    <div
      className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto"
      data-testid="mb-schedules"
    >
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-[--color-accent-primary]"
        >
          {t("morning_briefing.schedules.back")}
        </button>
        <h2 className="text-xl font-semibold">
          {t("morning_briefing.schedules.title")}
        </h2>
        <span className="w-32 flex justify-end">
          <button
            type="button"
            onClick={onAdd}
            data-testid="mb-schedules-add"
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover]"
          >
            <Plus size={13} /> {t("morning_briefing.schedules.add")}
          </button>
        </span>
      </header>

      <div className="max-w-[800px] mx-auto px-4 sm:px-6 py-6">
        {schedules.length === 0 ? (
          <p className="text-[13px] text-[--color-text-tertiary] border border-dashed border-[--color-border-subtle] rounded-lg px-4 py-8 text-center">
            {t("morning_briefing.schedules.empty")}
          </p>
        ) : (
          <ul className="flex flex-col gap-2">
            {schedules.map((s) => (
              <li
                key={s.id}
                data-testid="mb-schedule-row"
                className="flex items-center gap-3 px-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px]"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] font-medium text-[--color-text-primary]">
                      {s.label || s.time}
                    </span>
                    {!s.is_enabled ? (
                      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] border border-[--color-border-subtle] rounded px-1.5 py-px">
                        {t("morning_briefing.schedules.disabled_badge")}
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[12px] text-[--color-text-secondary] m-0 mt-0.5">
                    {t("morning_briefing.schedules.next_run", {
                      when: formatNextBriefing(s),
                    })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onEdit(s)}
                  className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
                >
                  <Pencil size={13} /> {t("morning_briefing.schedules.edit")}
                </button>
                <button
                  type="button"
                  onClick={() => setPendingRemoval(s.id)}
                  aria-label={t("morning_briefing.schedules.delete_aria")}
                  className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
                >
                  <Trash2 size={14} />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("morning_briefing.schedules.remove_title")}
        description={t("morning_briefing.schedules.remove_description")}
        confirmLabel={t("morning_briefing.schedules.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (id) void onRemove(id);
        }}
      />
    </div>
  );
}
