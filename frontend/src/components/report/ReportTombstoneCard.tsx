import type { JSX } from "react";
import { FileClock } from "lucide-react";
import { useTranslation } from "react-i18next";

export interface ReportTombstoneCardProps {
  /**
   * ISO timestamp the report was tombstoned (Report.expired_at). When
   * present, a "Removed on {date}" line is shown; when absent the card
   * still renders the generic heading + retention message.
   */
  expiredAt?: string | null;
}

function formatRemovedOn(iso: string, lang: string): string | null {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(lang, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * "No longer available" card shown in place of a report body once the
 * report has been tombstoned by the retention policy. The backend blanks
 * the schema and stamps expired_at; exports return 410. This is the
 * designed empty-state the viewer renders instead of a raw error.
 */
export function ReportTombstoneCard({
  expiredAt,
}: ReportTombstoneCardProps): JSX.Element {
  const { t, i18n } = useTranslation();
  const removedOn = expiredAt ? formatRemovedOn(expiredAt, i18n.language) : null;

  return (
    <div
      role="status"
      data-testid="report-tombstone-card"
      className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center"
    >
      <FileClock
        size={32}
        className="text-[--color-text-tertiary]"
        aria-hidden
      />
      <h2 className="text-base font-semibold text-[--color-text-primary]">
        {t("report.tombstone_heading")}
      </h2>
      <p className="max-w-[36ch] text-sm text-[--color-text-secondary]">
        {t("report.tombstone_message")}
      </p>
      {removedOn && (
        <p className="text-xs text-[--color-text-tertiary]">
          {t("report.tombstone_removed_on", { date: removedOn })}
        </p>
      )}
    </div>
  );
}
