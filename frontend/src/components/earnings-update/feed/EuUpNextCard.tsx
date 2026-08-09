import { useTranslation } from "react-i18next";

import type { EuScheduleEntry } from "../../../api/earnings-update";

interface Props {
  entry: EuScheduleEntry;
}

function formatRunTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d
    .toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    .replace(/^0/, "");
}

export function EuUpNextCard({ entry }: Props) {
  const { t } = useTranslation();
  const timingLabel =
    entry.release_timing === "pre_market"
      ? t("earnings.feed.up_next_pre_market")
      : entry.release_timing === "post_market"
        ? t("earnings.feed.up_next_post_market")
        : null;

  return (
    <article className="flex flex-col gap-2 px-4 py-4 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-border-strong] hover:-translate-y-0.5 hover:shadow-sm transition-all duration-[--duration-normal]">
      {timingLabel ? (
        <span className="font-mono text-[9px] tracking-[0.14em] uppercase text-[--color-text-tertiary]">
          {timingLabel}
        </span>
      ) : null}
      <div className="flex items-baseline gap-2.5">
        <span className="font-mono text-[15px] font-semibold tracking-wide text-[--color-text-primary]">
          {entry.ticker}
        </span>
        <span className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary]">
          {entry.fiscal_date}
        </span>
      </div>
      <span className="font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary] mt-0.5">
        {t("earnings.feed.up_next_scheduled", {
          when: formatRunTime(entry.scheduled_run_at),
        })}
      </span>
      {entry.eps_estimate || entry.revenue_estimate ? (
        <span className="font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary]">
          {t("earnings.feed.up_next_est_eps")}{" "}
          <strong className="text-[--color-text-secondary] font-semibold">
            {entry.eps_estimate ?? "—"}
          </strong>{" "}
          · {t("earnings.feed.up_next_rev")}{" "}
          <strong className="text-[--color-text-secondary] font-semibold">
            {entry.revenue_estimate ?? "—"}
          </strong>
        </span>
      ) : null}
    </article>
  );
}
