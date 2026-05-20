import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { CheckCircle } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { WatchlistEntry } from "../../api/earnings-update";

interface Props {
  open: boolean;
  onClose: () => void;
  onReportReady: (result: { report_id: string; title: string }) => void;
  startReport: (payload: {
    ticker: string;
  }) => Promise<{ report_id: string; title: string }>;
  entries?: WatchlistEntry[];
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function OnDemandReportModal({
  open,
  onClose,
  onReportReady,
  startReport,
  entries,
}: Props) {
  const { t } = useTranslation();
  const [ticker, setTicker] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const trimmed = ticker.trim().toUpperCase();
  const matchedEntry = useMemo(() => {
    if (!entries || !trimmed) return null;
    return entries.find((e) => e.ticker.toUpperCase() === trimmed) ?? null;
  }, [entries, trimmed]);

  async function handleGenerate() {
    setErr(null);
    setSubmitting(true);
    try {
      const result = await startReport({
        ticker: trimmed,
      });
      onReportReady(result);
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? t("earnings.on_demand_modal.failed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] max-w-[480px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-1">
            {t("earnings.on_demand_modal.title")}
          </Dialog.Title>
          <Dialog.Description className="text-sm text-[--color-text-secondary] mb-4">
            {t("earnings.on_demand_modal.description")}
          </Dialog.Description>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder={t("earnings.on_demand_modal.ticker_placeholder")}
            className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-3 h-9 text-sm text-[--color-text-primary]"
          />
          {matchedEntry ? (
            <div
              data-testid="selected-company"
              className="mt-2 flex items-center gap-2 text-sm text-[--color-text-primary]"
            >
              <CheckCircle
                size={16}
                className="text-[--color-feedback-success]"
                aria-hidden
              />
              <span className="font-semibold">{matchedEntry.ticker}</span>
              <span className="text-[--color-text-secondary]">
                — {matchedEntry.company_name}
              </span>
              <span className="text-[--color-text-tertiary] ml-auto">
                {t("earnings.on_demand_modal.last_earnings", {
                  date: formatDate(matchedEntry.next_earnings_date),
                })}
              </span>
            </div>
          ) : null}
          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
          ) : null}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              {t("earnings.on_demand_modal.cancel")}
            </button>
            <button
              type="button"
              disabled={!trimmed || submitting}
              onClick={() => void handleGenerate()}
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {submitting
                ? t("earnings.on_demand_modal.generating")
                : t("earnings.on_demand_modal.generate")}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
