/**
 * CoverageDrawer — right-slide panel for the user's tracked tickers
 * ("coverage"). Replaces the centered WatchlistModal. Lists tickers
 * grouped by earnings timing (live / soon / reported / queued) with a
 * stats strip and an inline add-ticker row.
 */
import { Plus, Trash2, X } from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import type {
  EuScheduleEntry,
  RunSummary,
  WatchlistEntry,
} from "../../api/earnings-update";
import {
  type CoverageBucketKey,
  type CoverageItem,
  coverageGroups,
} from "./coverageGroups";

interface Props {
  open: boolean;
  entries: WatchlistEntry[];
  byTicker: Map<string, EuScheduleEntry>;
  runs: RunSummary[];
  onClose: () => void;
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
  /** Optional open-report handler for reported rows. */
  onOpenReport?: (reportId: string) => void;
  /** Injectable clock for tests. */
  now?: number;
}

interface ErrorWithStatus {
  status?: number;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

const BUCKET_LABEL_KEY: Record<CoverageBucketKey, string> = {
  live: "earnings.coverage.bucket_live",
  soon: "earnings.coverage.bucket_soon",
  reported: "earnings.coverage.bucket_reported",
  queued: "earnings.coverage.bucket_queued",
};

export function CoverageDrawer({
  open,
  entries,
  byTicker,
  runs,
  onClose,
  onAdd,
  onRemove,
  onOpenReport,
  now,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const clock = now ?? Date.now();
  const buckets = useMemo(
    () => coverageGroups(entries, byTicker, runs, clock),
    [entries, byTicker, runs, clock],
  );

  const trackedCount = entries.length;
  const liveCount = buckets.find((b) => b.key === "live")?.items.length ?? 0;
  const thisWeekCount = buckets.find((b) => b.key === "soon")?.items.length ?? 0;

  if (!open) return null;

  async function handleAdd() {
    setErr(null);
    const ticker = value.trim().toUpperCase();
    if (!ticker) return;
    setSubmitting(true);
    try {
      await onAdd(ticker);
      setValue("");
    } catch (e) {
      const status = (e as ErrorWithStatus).status;
      if (status === 409) setErr(t("earnings.add_ticker.already_watching", { ticker }));
      else if (status === 404) setErr(t("earnings.add_ticker.not_found", { ticker }));
      else setErr(t("earnings.add_ticker.add_failed"));
    } finally {
      setSubmitting(false);
    }
  }

  function whenText(item: CoverageItem): string {
    if (item.bucket === "live") return t("earnings.coverage.when_live");
    if (item.bucket === "reported") {
      return item.date
        ? `${formatDate(item.date)} · ${t("earnings.coverage.when_done")}`
        : t("earnings.coverage.when_done");
    }
    if (item.date) {
      const timing =
        item.timing === "pre_market"
          ? t("earnings.watchlist_card.pre_market")
          : item.timing === "post_market"
            ? t("earnings.watchlist_card.post_market")
            : null;
      return timing ? `${formatDate(item.date)} · ${timing}` : formatDate(item.date);
    }
    return t("earnings.coverage.when_awaiting");
  }

  const nonEmpty = buckets.filter((b) => b.items.length > 0);

  return (
    <div className="fixed inset-0 z-50" data-testid="coverage-drawer">
      <button
        type="button"
        data-testid="coverage-backdrop"
        aria-label={t("earnings.coverage.close_aria")}
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-[rgba(13,13,11,0.42)]"
      />
      <aside
        role="dialog"
        aria-label={t("earnings.coverage.title")}
        className="absolute right-0 top-0 flex h-full w-[460px] max-w-[92vw] flex-col border-l border-[--color-border-subtle] bg-[--color-bg-base] shadow-[-8px_0_32px_rgba(13,13,11,0.10)] motion-safe:animate-[ol-drawer-in_240ms_ease-out]"
      >
        <header className="flex flex-col gap-[14px] border-b border-[--color-border-subtle] px-5 pb-[14px] pt-[18px]">
          <div className="flex items-start justify-between">
            <div>
              <p className="m-0 font-mono text-[9.5px] uppercase tracking-[0.14em] text-[--color-text-tertiary]">
                {t("earnings.coverage.eyebrow")}
              </p>
              <h2 className="m-0 mt-0.5 text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary]">
                {t("earnings.coverage.title")}
              </h2>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("earnings.coverage.close_aria")}
              className="text-[--color-text-secondary] hover:text-[--color-text-primary]"
            >
              <X size={16} />
            </button>
          </div>
          <div className="flex items-stretch gap-1.5">
            <input
              data-testid="coverage-add-input"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleAdd();
              }}
              placeholder={t("earnings.add_ticker.placeholder")}
              className="h-[38px] flex-1 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 text-[13.5px] text-[--color-text-primary] outline-none transition-colors focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(var(--color-accent-primary-rgb),0.10)]"
            />
            <button
              type="button"
              data-testid="coverage-add-btn"
              onClick={() => void handleAdd()}
              disabled={submitting}
              className="inline-flex h-[38px] items-center gap-1.5 rounded-md bg-[--color-accent-primary] px-3.5 font-mono text-[11px] font-semibold uppercase tracking-[0.08em] text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              <Plus size={13} /> {t("earnings.add_ticker.add")}
            </button>
          </div>
          {err ? <p className="m-0 text-xs text-[--color-feedback-error]">{err}</p> : null}
        </header>

        <div
          data-testid="coverage-stats"
          className="flex gap-[18px] border-b border-[--color-border-subtle] bg-[--color-bg-elevated] px-5 py-3"
        >
          <Stat label={t("earnings.coverage.stat_tracked")} value={trackedCount} />
          <Stat label={t("earnings.coverage.stat_this_week")} value={thisWeekCount} />
          <Stat label={t("earnings.coverage.stat_live")} value={liveCount} />
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-4 pt-1.5">
          {trackedCount === 0 ? (
            <p
              data-testid="coverage-empty"
              className="px-2 py-10 text-center text-[13px] text-[--color-text-tertiary]"
            >
              {t("earnings.coverage.empty")}
            </p>
          ) : (
            nonEmpty.map((b) => (
              <section key={b.key} data-testid={`coverage-bucket-${b.key}`} className="mb-3">
                <div className="flex items-center gap-2 px-2 py-1.5">
                  <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                    {t(BUCKET_LABEL_KEY[b.key])}
                  </span>
                  <span className="font-mono text-[10px] text-[--color-text-tertiary]">{b.items.length}</span>
                </div>
                <ul className="flex flex-col">
                  {b.items.map((item) => (
                    <li
                      key={item.entry.id}
                      className="group flex items-center gap-3 rounded-md px-2 py-2 hover:bg-[--color-surface-hover]"
                    >
                      <span className="w-16 shrink-0 font-mono text-[13px] font-semibold text-[--color-text-primary]">
                        {item.entry.ticker}
                      </span>
                      <span className="flex-1 truncate text-[13px] text-[--color-text-secondary]">
                        {item.entry.company_name}
                      </span>
                      <span className="shrink-0 text-[11px] text-[--color-text-tertiary]">{whenText(item)}</span>
                      {item.reportId && onOpenReport ? (
                        <button
                          type="button"
                          onClick={() => onOpenReport(item.reportId as string)}
                          className="shrink-0 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-feedback-success] hover:underline"
                        >
                          {t("earnings.coverage.open_report")}
                        </button>
                      ) : null}
                      <button
                        type="button"
                        data-testid={`coverage-remove-${item.entry.id}`}
                        onClick={() => void onRemove(item.entry.id)}
                        aria-label={t("earnings.coverage.remove_aria", { ticker: item.entry.ticker })}
                        className="shrink-0 text-[--color-text-tertiary] opacity-0 transition-opacity hover:text-[--color-feedback-error] group-hover:opacity-100"
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )}
        </div>
      </aside>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="flex flex-col gap-px">
      <span className="font-mono text-[9.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">{label}</span>
      <span className="text-[15px] font-semibold tabular-nums text-[--color-text-primary]">{value}</span>
    </div>
  );
}
