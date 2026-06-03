/**
 * MbRunNowModal — kick off a Morning Briefing run immediately with full
 * settings. A pure ad-hoc config form (model, template, instructions,
 * connectors, length, language, reasoning) — no schedule picker, no ticker.
 *
 * Prefills from the user's previous Run Now submission (localStorage) and
 * saves the config again on a successful Generate. Starting a run POSTs to
 * /runs/start (ad-hoc path, no schedule_id) and hands the new report_id back
 * to the page, which owns the live-streaming card.
 */
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import { startMbRun, type MbRunStartIn } from "../../api/morning-briefing";

import {
  MbConfigFields,
  isBriefEmpty,
  type MbConfigDraft,
} from "./MbConfigFields";
import { loadRunNowDraft, saveRunNowDraft } from "./mbRunNowDraft";

interface Props {
  open: boolean;
  onClose: () => void;
  onStarted: (reportId: string) => void;
}

export function MbRunNowModal({ open, onClose, onStarted }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<MbConfigDraft>(() => loadRunNowDraft());
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Re-read the remembered config each time the modal opens.
  useEffect(() => {
    if (open) {
      setDraft(loadRunNowDraft());
      setErr(null);
    }
  }, [open]);

  const empty = isBriefEmpty(draft);

  async function handleStart() {
    setErr(null);
    setSubmitting(true);
    try {
      const payload: MbRunStartIn = {
        template_id: draft.template_id,
        instructions_id: draft.instructions_id,
        enabled_connectors: {
          provider_ids: draft.provider_ids,
          web_search: draft.web_search,
        },
        provider_kind: draft.provider_kind ?? undefined,
        model: draft.model ?? undefined,
        language: draft.language,
        length: draft.length,
        reasoning_effort: draft.reasoning_effort,
      };
      const { report_id } = await startMbRun(payload);
      saveRunNowDraft(draft);
      onStarted(report_id);
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? t("morning_briefing.run_now_modal.failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  {t("morning_briefing.run_now_modal.title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="text-[12px] text-[--color-text-tertiary] m-0">
                  {t("morning_briefing.run_now_modal.description")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("morning_briefing.run_now_modal.cancel")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <MbConfigFields
              draft={draft}
              onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
            />
          </div>

          <footer className="flex items-center justify-end gap-3 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
            {empty ? (
              <p
                data-testid="mb-run-now-empty-error"
                className="mr-auto text-[12px] text-[--color-feedback-danger] leading-[1.4]"
              >
                {t("morning_briefing.run_now_modal.empty_error")}
              </p>
            ) : err ? (
              <p className="mr-auto text-[12px] text-[--color-feedback-error] leading-[1.4]">
                {err}
              </p>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong] transition-colors text-[13px] font-medium"
            >
              {t("morning_briefing.run_now_modal.cancel")}
            </button>
            <button
              type="button"
              disabled={submitting || empty}
              onClick={() => void handleStart()}
              data-testid="mb-run-now-start"
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {submitting
                ? t("morning_briefing.run_now_modal.starting")
                : t("morning_briefing.run_now_modal.generate")}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
