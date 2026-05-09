import { X, Trash2 } from "lucide-react";

import type { WatchlistEntry } from "../../api/earnings-update";

import { AddTickerPopover } from "./AddTickerPopover";

interface Props {
  open: boolean;
  entries: WatchlistEntry[];
  onClose: () => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

export function CoverageModal({
  open,
  entries,
  onClose,
  onAdd,
  onRemove,
}: Props) {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label="Coverage"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <button
        type="button"
        aria-label="Close"
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />
      <div className="relative bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] w-[480px] max-w-[92vw] max-h-[80vh] flex flex-col overflow-hidden shadow-lg">
        <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle]">
          <div>
            <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
              Coverage
            </h2>
            <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
              Auto-generated when earnings release
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close coverage modal"
            className="text-[--color-text-secondary] hover:text-[--color-text-primary]"
          >
            <X size={16} />
          </button>
        </header>
        <div className="px-5 py-3 border-b border-[--color-border-subtle] flex justify-end">
          <AddTickerPopover onAdd={onAdd} />
        </div>
        <div className="flex-1 overflow-y-auto">
          {entries.length === 0 ? (
            <p className="px-5 py-8 text-center text-[13px] text-[--color-text-tertiary]">
              No tickers in coverage. Add one to start tracking earnings.
            </p>
          ) : (
            <ul className="divide-y divide-[var(--color-border-subtle)]">
              {entries.map((e) => (
                <li
                  key={e.id}
                  className="flex items-center gap-3 px-5 py-3"
                  data-testid="coverage-row"
                >
                  <span className="font-mono text-[13px] font-semibold text-[--color-text-primary] w-16">
                    {e.ticker}
                  </span>
                  <span className="flex-1 text-[13px] text-[--color-text-secondary] truncate">
                    {e.company_name}
                  </span>
                  {e.next_earnings_date ? (
                    <span className="font-mono text-[10px] tracking-[0.06em] uppercase text-[--color-text-tertiary]">
                      {e.next_earnings_date}
                    </span>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void onRemove(e.id)}
                    aria-label={`Remove ${e.ticker}`}
                    className="text-[--color-text-tertiary] hover:text-[--color-feedback-error]"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
