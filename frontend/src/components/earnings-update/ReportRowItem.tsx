import { useTranslation } from "react-i18next";

import { RunSummary } from "../../api/earnings-update";
import { ReportDownloadButton } from "../report/ReportDownloadButton";

interface Props {
  report: RunSummary;
  onOpen: (id: string) => void;
  showExtras?: boolean;
  onRemove?: (id: string) => void;
  isNew?: boolean;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function ReportRowItem({
  report,
  onOpen,
  showExtras,
  onRemove,
  isNew = false,
}: Props) {
  const { t } = useTranslation();
  return (
    <div
      role="row"
      className="flex items-center gap-4 px-6 py-3.5 border-b border-[--color-border-subtle] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-fast]"
    >
      {isNew ? (
        <span
          aria-label={t("earnings.report_row.new_aria")}
          className="inline-block w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] flex-shrink-0"
        />
      ) : null}
      <span className="text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0">
        {report.ticker ?? "—"}
      </span>
      <span className="flex-1 text-base text-[--color-text-primary]">
        {report.subject}
      </span>
      <span className="hidden sm:block text-sm text-[--color-text-secondary] flex-shrink-0">
        {formatDate(report.created_at)}
      </span>
      <button
        type="button"
        onClick={() => onOpen(report.report_id)}
        className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover] ml-2"
      >
        {t("earnings.report_row.open")}
      </button>
      {showExtras ? (
        <>
          <ReportDownloadButton reportId={report.report_id} className="ml-2" />
          <button
            type="button"
            onClick={() => onRemove?.(report.report_id)}
            aria-label={t("earnings.report_row.remove_aria")}
            className="text-sm text-[--color-text-secondary] hover:text-[--color-feedback-error] ml-2"
          >
            ×
          </button>
        </>
      ) : null}
    </div>
  );
}
