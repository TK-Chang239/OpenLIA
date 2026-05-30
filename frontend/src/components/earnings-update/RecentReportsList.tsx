import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { RunSummary } from "../../api/earnings-update";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RunSummary[];
  onOpenReport: (id: string) => void;
  onOpenCabinet: () => void;
}

const STORAGE_KEY = "eu-opened-reports";
const NEW_WINDOW_MS = 24 * 60 * 60 * 1000;

function readOpened(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

function writeOpened(opened: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(opened)));
  } catch {
    // ignore quota errors
  }
}

function isWithinNewWindow(createdAt: string): boolean {
  const ts = new Date(createdAt).getTime();
  if (Number.isNaN(ts)) return false;
  return Date.now() - ts < NEW_WINDOW_MS;
}

export function RecentReportsList({
  reports,
  onOpenReport,
  onOpenCabinet,
}: Props) {
  const { t } = useTranslation();
  const [openedIds, setOpenedIds] = useState<Set<string>>(() => readOpened());

  useEffect(() => {
    writeOpened(openedIds);
  }, [openedIds]);

  const handleOpen = useCallback(
    (id: string) => {
      setOpenedIds((prev) => {
        if (prev.has(id)) return prev;
        const next = new Set(prev);
        next.add(id);
        return next;
      });
      onOpenReport(id);
    },
    [onOpenReport],
  );

  return (
    <section>
      <header className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          {t("earnings.recent_reports.heading")}
        </h3>
        <button
          type="button"
          onClick={onOpenCabinet}
          className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]"
        >
          {t("earnings.recent_reports.open_cabinet")}
        </button>
      </header>
      {reports.length === 0 ? (
        <div className="mx-6 mb-4 text-center py-8 text-sm text-[--color-text-tertiary]">
          {t("earnings.recent_reports.empty")}
        </div>
      ) : (
        <div>
          {reports.map((r) => (
            <ReportRowItem
              key={r.report_id}
              report={r}
              onOpen={handleOpen}
              isNew={
                isWithinNewWindow(r.created_at) && !openedIds.has(r.report_id)
              }
            />
          ))}
        </div>
      )}
    </section>
  );
}
