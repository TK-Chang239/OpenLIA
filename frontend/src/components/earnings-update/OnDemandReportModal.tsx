/**
 * OnDemandReportModal — kick off an Earnings Update v2 run for any ticker.
 *
 * Accepts a free-text ticker (watchlist tickers are offered as datalist
 * suggestions, but any ticker is allowed). Starting a run only POSTs to
 * ``/v2/runs/start`` and hands the new ``report_id`` back to the page,
 * which owns the live-streaming card. The run uses the user's saved
 * model & template — there is no per-run override here.
 */
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import { startRun, type WatchlistEntry } from "../../api/earnings-update";

interface Props {
  open: boolean;
  watchlist: WatchlistEntry[];
  onClose: () => void;
  onStarted: (reportId: string, ticker: string) => void;
}

export function OnDemandReportModal({
  open,
  watchlist,
  onClose,
  onStarted,
}: Props) {
  const [ticker, setTicker] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const trimmed = ticker.trim().toUpperCase();

  async function handleStart() {
    setErr(null);
    setSubmitting(true);
    try {
      const { report_id } = await startRun({ ticker: trimmed });
      onStarted(report_id, trimmed);
      setTicker("");
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? "Failed to start report");
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
            On-demand earnings report
          </Dialog.Title>
          <Dialog.Description className="text-sm text-[--color-text-secondary] mb-4">
            Enter any ticker to generate an Earnings Update report now.
          </Dialog.Description>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            list="eu-v2-ondemand-watchlist"
            placeholder="Ticker (e.g. AAPL.US)"
            data-testid="eu-v2-ondemand-ticker"
            className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-3 h-9 text-sm text-[--color-text-primary]"
          />
          <datalist id="eu-v2-ondemand-watchlist">
            {watchlist.map((e) => (
              <option key={e.id} value={e.ticker}>
                {e.company_name ?? e.ticker}
              </option>
            ))}
          </datalist>
          <p className="text-xs text-[--color-text-tertiary] mt-2">
            Uses your saved model &amp; template — change in Settings.
          </p>
          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
          ) : null}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!trimmed || submitting}
              onClick={() => void handleStart()}
              data-testid="eu-v2-ondemand-start"
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {submitting ? "Starting…" : "Generate report"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
