/**
 * EuRefreshButton — header control that re-fetches each watchlist ticker's
 * next earnings release date on demand (the same calendar sync the weekly
 * cron runs) and surfaces an inline result.
 *
 * Self-contained: owns its idle/syncing/done/error state machine and the
 * auto-clearing status text. The parent supplies `onRefresh`, which performs
 * the sync plus any on-screen refresh and resolves to the synced ticker count.
 */
import { RefreshCw } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

type Status =
  | { kind: "idle" }
  | { kind: "syncing" }
  | { kind: "done"; count: number }
  | { kind: "error" };

interface Props {
  /** Runs the sync + refresh; resolves to the number of tickers synced. */
  onRefresh: () => Promise<number>;
  /** True when the watchlist is empty — nothing to sync. */
  disabled?: boolean;
}

const CLEAR_MS = 4000;

export function EuRefreshButton({
  onRefresh,
  disabled = false,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [status, setStatus] = useState<Status>({ kind: "idle" });
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const handleClick = useCallback(async () => {
    if (disabled) return;
    setStatus({ kind: "syncing" });
    try {
      const count = await onRefresh();
      setStatus({ kind: "done", count });
    } catch {
      setStatus({ kind: "error" });
    } finally {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setStatus({ kind: "idle" }), CLEAR_MS);
    }
  }, [disabled, onRefresh]);

  const syncing = status.kind === "syncing";

  let statusText: string | null = null;
  let statusClass = "text-[--color-text-tertiary]";
  if (status.kind === "syncing") {
    statusText = t("earnings.refresh.syncing");
  } else if (status.kind === "done") {
    statusText = t("earnings.refresh.done", { n: status.count });
  } else if (status.kind === "error") {
    statusText = t("earnings.refresh.failed");
    statusClass = "text-[--color-feedback-error]";
  }

  return (
    <div className="flex items-center gap-2">
      {statusText ? (
        <span role="status" className={`text-[11.5px] ${statusClass}`}>
          {statusText}
        </span>
      ) : null}
      <button
        type="button"
        onClick={() => void handleClick()}
        disabled={disabled || syncing}
        aria-label={t("earnings.refresh.aria")}
        title={
          disabled
            ? t("earnings.refresh.empty_hint")
            : t("earnings.refresh.aria")
        }
        className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] transition-colors duration-[--duration-normal] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:cursor-not-allowed disabled:opacity-50"
      >
        <RefreshCw size={14} className={syncing ? "animate-spin" : undefined} />
      </button>
    </div>
  );
}
