import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  EuScheduleEntry,
  WatchlistEntry,
} from "../../api/earnings-update";

interface Props {
  entry: WatchlistEntry;
  nextRelease?: EuScheduleEntry;
  onRemove: (id: string) => void;
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function isPast(iso: string | null | undefined): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return d < today;
}

export function WatchlistCard({ entry, nextRelease, onRemove }: Props) {
  const { t } = useTranslation();
  const fiscalDate = nextRelease?.fiscal_date ?? null;
  const timing = nextRelease?.release_timing ?? null;
  const overdue = isPast(fiscalDate);
  return (
    <div
      role="group"
      aria-label={t("earnings.watchlist_card.group_aria", { ticker: entry.ticker })}
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
        aria-label={t("earnings.watchlist_card.remove_aria", { ticker: entry.ticker })}
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
        {fiscalDate ? formatDate(fiscalDate) : t("earnings.watchlist_card.no_upcoming_date")}
      </div>
      {overdue ? (
        <span className="text-xs rounded-full px-2 py-0.5 bg-[--color-surface-hover] text-[--color-text-tertiary]">
          {t("earnings.watchlist_card.date_passed")}
        </span>
      ) : timing ? (
        <span
          className={[
            "text-xs rounded-full px-2 py-0.5 w-fit",
            timing === "pre_market"
              ? "bg-[--color-info]/10 text-[--color-info]"
              : "bg-[--color-warning]/10 text-[--color-warning]",
          ].join(" ")}
        >
          {timing === "pre_market"
            ? t("earnings.watchlist_card.pre_market")
            : t("earnings.watchlist_card.post_market")}
        </span>
      ) : null}
    </div>
  );
}
