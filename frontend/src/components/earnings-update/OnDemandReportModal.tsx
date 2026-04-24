import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  onReportReady: (result: { report_id: string; title: string }) => void;
  startReport: (payload: {
    ticker: string;
  }) => Promise<{ report_id: string; title: string }>;
}

export function OnDemandReportModal({
  open,
  onClose,
  onReportReady,
  startReport,
}: Props) {
  const [ticker, setTicker] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleGenerate() {
    setErr(null);
    setSubmitting(true);
    try {
      const result = await startReport({
        ticker: ticker.trim().toUpperCase(),
      });
      onReportReady(result);
      onClose();
    } catch (e) {
      setErr((e as Error).message ?? "Failed to generate report");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[480px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-1">
            On-Demand Earnings Update
          </Dialog.Title>
          <Dialog.Description className="text-sm text-[--color-text-secondary] mb-4">
            Generate an earnings analysis for a company's most recently released
            earnings report.
          </Dialog.Description>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="Ticker symbol (e.g. AAPL)"
            className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-3 h-9 text-sm text-[--color-text-primary]"
          />
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
              disabled={!ticker.trim() || submitting}
              onClick={() => void handleGenerate()}
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {submitting ? "Generating..." : "Generate Report"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
