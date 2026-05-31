import { X, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { EuScheduleEntry, WatchlistEntry } from "../../api/earnings-update";

import { AddTickerPopover } from "./AddTickerPopover";

interface WatchlistModalProps {
  open: boolean;
  entries: WatchlistEntry[];
  onClose: () => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  nextReleaseByTicker?: Map<string, EuScheduleEntry>;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function isPast(iso: string): boolean {
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}

export function WatchlistModal({
  open,
  entries,
  onClose,
  onAdd,
  onRemove,
  nextReleaseByTicker,
}: WatchlistModalProps) {
  const { t } = useTranslation();
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-label={t("earnings.watchlist_modal.aria")}
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <button
        type="button"
        aria-label={t("earnings.watchlist_modal.close_aria")}
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
      />
      <div className="relative bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] w-[480px] max-w-[92vw] max-h-[80vh] flex flex-col overflow-hidden shadow-lg">
        <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle]">
          <div>
            <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
              {t("earnings.watchlist_modal.title")}
            </h2>
            <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
              {t("earnings.watchlist_modal.subtitle")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("earnings.watchlist_modal.close_modal_aria")}
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
              {t("earnings.watchlist_modal.empty")}
            </p>
          ) : (
            <ul className="divide-y divide-[var(--color-border-subtle)]">
              {entries.map((e) => {
                const nr = nextReleaseByTicker?.get(e.ticker);
                const fiscalDate = nr?.fiscal_date ?? null;
                const timing = nr?.release_timing ?? null;
                const overdue = fiscalDate ? isPast(fiscalDate) : false;
                return (
                  <li
                    key={e.id}
                    className="flex items-center gap-3 px-5 py-3"
                    data-testid="watchlist-row"
                  >
                    <span className="font-mono text-[13px] font-semibold text-[--color-text-primary] w-16">
                      {e.ticker}
                    </span>
                    <span className="flex-1 text-[13px] text-[--color-text-secondary] truncate">
                      {e.company_name}
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={[
                          "text-[11px]",
                          overdue
                            ? "text-[--color-feedback-error]"
                            : fiscalDate
                              ? "text-[--color-text-secondary]"
                              : "text-[--color-text-tertiary]",
                        ].join(" ")}
                        data-testid="watchlist-next-date"
                      >
                        {fiscalDate
                          ? formatDate(fiscalDate)
                          : t("earnings.watchlist_card.no_upcoming_date")}
                      </span>
                      {!overdue && timing ? (
                        <span
                          className={[
                            "text-[10px] rounded-full px-1.5 py-px",
                            timing === "pre_market"
                              ? "bg-[--color-info]/10 text-[--color-info]"
                              : "bg-[--color-warning]/10 text-[--color-warning]",
                          ].join(" ")}
                          data-testid="watchlist-timing-badge"
                        >
                          {timing === "pre_market"
                            ? t("earnings.watchlist_card.pre_market")
                            : t("earnings.watchlist_card.post_market")}
                        </span>
                      ) : null}
                    </span>
                    <button
                      type="button"
                      onClick={() => void onRemove(e.id)}
                      aria-label={t("earnings.watchlist_modal.remove_ticker_aria", { ticker: e.ticker })}
                      className="text-[--color-text-tertiary] hover:text-[--color-feedback-error]"
                    >
                      <Trash2 size={14} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
