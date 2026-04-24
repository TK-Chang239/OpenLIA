import { X } from "lucide-react";

import { WatchlistEntry } from "../../api/earnings-update";

interface Props {
  entry: WatchlistEntry;
  onRemove: (id: string) => void;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function isPast(iso: string | null): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}

export function WatchlistCard({ entry, onRemove }: Props) {
  const overdue = isPast(entry.next_earnings_date);
  return (
    <div
      role="group"
      aria-label={`Watchlist entry ${entry.ticker}`}
      className={[
        "group flex-shrink-0 w-[148px] bg-[--color-bg-elevated]",
        "border rounded-[--radius-lg] p-3 flex flex-col gap-1 relative",
        overdue
          ? "border-[--color-feedback-error]"
          : "border-[--color-border-subtle] hover:border-[--color-border-secondary] hover:shadow-sm",
        "transition-all duration-[--duration-fast]",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={() => onRemove(entry.id)}
        aria-label={`Remove ${entry.ticker}`}
        className={[
          "absolute right-1 top-1 p-1 rounded opacity-0 group-hover:opacity-100",
          "text-[--color-text-tertiary] hover:text-[--color-text-primary]",
          "transition-opacity duration-[--duration-fast]",
        ].join(" ")}
      >
        <X size={14} />
      </button>
      <div className="text-base font-semibold text-[--color-text-primary]">
        {entry.ticker}
      </div>
      <div className="text-xs text-[--color-text-secondary] truncate">
        {entry.company_name}
      </div>
      <div className="text-sm font-medium text-[--color-text-primary] mt-1">
        {formatDate(entry.next_earnings_date)}
      </div>
      {overdue ? (
        <span className="text-xs rounded-full px-2 py-0.5 bg-[--color-surface-hover] text-[--color-text-tertiary]">
          Date passed
        </span>
      ) : entry.release_timing ? (
        <span
          className={[
            "text-xs rounded-full px-2 py-0.5 w-fit",
            entry.release_timing === "pre_market"
              ? "bg-[--color-info]/10 text-[--color-info]"
              : "bg-[--color-warning]/10 text-[--color-warning]",
          ].join(" ")}
        >
          {entry.release_timing === "pre_market" ? "Pre-Market" : "Post-Market"}
        </span>
      ) : null}
    </div>
  );
}
