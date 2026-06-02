/**
 * MbRunNowModal — kick off a Morning Briefing run immediately.
 *
 * Either run a saved schedule's bound config (pick from the list) or run
 * ad-hoc using the Library defaults (no schedule_id). There is NO ticker —
 * MB is purely template/instructions-driven. Starting a run POSTs to
 * /runs/start and hands the new report_id back to the page, which owns the
 * live-streaming card.
 */
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";

import { startMbRun, type MbSchedule } from "../../api/morning-briefing";

interface Props {
  open: boolean;
  schedules: MbSchedule[];
  onClose: () => void;
  onStarted: (reportId: string) => void;
}

const ADHOC = "__adhoc__";

export function MbRunNowModal({ open, schedules, onClose, onStarted }: Props) {
  const { t } = useTranslation();
  const [choice, setChoice] = useState<string>(ADHOC);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleStart() {
    setErr(null);
    setSubmitting(true);
    try {
      const { report_id } = await startMbRun(
        choice === ADHOC ? {} : { schedule_id: choice },
      );
      onStarted(report_id);
      setChoice(ADHOC);
      onClose();
    } catch (e) {
      setErr(
        (e as Error).message ?? t("morning_briefing.run_now_modal.failed"),
      );
    } finally {
      setSubmitting(false);
    }
  }

  function labelFor(s: MbSchedule): string {
    const days = s.days_of_week.join(", ");
    return s.label ? `${s.label} · ${s.time} · ${days}` : `${s.time} · ${days}`;
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] max-w-[480px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-1">
            {t("morning_briefing.run_now_modal.title")}
          </Dialog.Title>
          <Dialog.Description className="text-sm text-[--color-text-secondary] mb-4">
            {t("morning_briefing.run_now_modal.description")}
          </Dialog.Description>

          <label className="flex flex-col gap-1.5">
            <span className="text-[12px] text-[--color-text-tertiary]">
              {t("morning_briefing.run_now_modal.schedule_label")}
            </span>
            <select
              value={choice}
              onChange={(e) => setChoice(e.target.value)}
              data-testid="mb-run-now-schedule"
              className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            >
              <option value={ADHOC}>
                {t("morning_briefing.run_now_modal.schedule_adhoc")}
              </option>
              {schedules.map((s) => (
                <option key={s.id} value={s.id}>
                  {labelFor(s)}
                </option>
              ))}
            </select>
          </label>

          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-3">{err}</p>
          ) : null}

          <div className="flex justify-end gap-2 mt-5">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              {t("morning_briefing.run_now_modal.cancel")}
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={() => void handleStart()}
              data-testid="mb-run-now-start"
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {submitting
                ? t("morning_briefing.run_now_modal.starting")
                : t("morning_briefing.run_now_modal.generate")}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
