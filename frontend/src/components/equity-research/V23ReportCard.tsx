/**
 * V23ReportCard — compact summary card for a completed v2.3 run.
 *
 * Sits in the composer where the inline report used to render and acts
 * as the entry point to the full-screen <V23ReportFullScreen> viewer.
 * Mirrors the v2.2 ReportCard pattern but consumes the v2.3
 * RunPayload directly (no markdown round-trip).
 */
import { Download, FileText } from "lucide-react";
import { type JSX, useMemo } from "react";

import {
  type V23ReportType,
  type V23RunPayload,
  v23DocxUrl,
} from "../../api/equity-research-v2-3";

const REPORT_TYPE_LABEL: Record<V23ReportType, string> = {
  initiation: "Stock Initiation Report",
  update: "Stock Update Report",
  sector_research: "Sector Research Report",
  morning_brief: "Morning Brief",
  earnings_review: "Earnings Review",
};

interface Props {
  payload: V23RunPayload;
  /** ISO timestamp of when the run completed; rendered in the header. */
  completedAt?: string | null;
  /** Open the full-screen viewer; the page wires this to ?view=report. */
  onOpen: () => void;
}

export function V23ReportCard({
  payload,
  completedAt,
  onOpen,
}: Props): JSX.Element {
  const title = REPORT_TYPE_LABEL[payload.report_type];
  const dateLabel = useMemo(() => formatDate(completedAt), [completedAt]);
  const preview = firstSentence(payload.thesis.central_argument);
  const chartCount = payload.charts.length;
  const footnoteCount = payload.footnotes.length;

  return (
    <article
      data-testid="er-v2-3-report-card"
      className="overflow-hidden rounded-lg border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm"
    >
      <header className="flex items-start gap-3 px-4 py-3">
        <FileText
          size={16}
          className="mt-[2px] flex-shrink-0 text-[--color-text-tertiary]"
        />
        <div className="flex flex-1 flex-col gap-[2px]">
          <div className="flex items-center gap-2">
            <span className="font-display text-[14.5px] font-medium text-[--color-text-primary]">
              {title}
            </span>
            <span className="font-mono text-[9.5px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
              {payload.language}
            </span>
          </div>
          <div className="text-[12.5px] text-[--color-text-secondary]">
            {payload.tickers.join(", ")}
            {dateLabel ? <span> · {dateLabel}</span> : null}
          </div>
        </div>
      </header>

      <div className="border-t border-[--color-border-subtle] px-4 py-3 text-[13px] leading-[1.55] text-[--color-text-primary]">
        <p className="line-clamp-3">{preview}</p>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          {payload.thesis.valuation_stance ? (
            <span data-testid="er-v2-3-report-card-valuation">
              Valuation · {payload.thesis.valuation_stance}
            </span>
          ) : null}
          <span>{chartCount} chart{chartCount === 1 ? "" : "s"}</span>
          <span>{footnoteCount} footnote{footnoteCount === 1 ? "" : "s"}</span>
        </div>
      </div>

      <footer className="flex items-center justify-between gap-2 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-4 py-2.5">
        <button
          type="button"
          onClick={onOpen}
          data-testid="er-v2-3-report-card-open"
          className="inline-flex h-7 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[12.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
        >
          Open Report
        </button>
        <a
          href={v23DocxUrl(payload.run_id)}
          download
          data-testid="er-v2-3-report-card-download"
          className="inline-flex h-7 items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2.5 font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
        >
          <Download size={11} /> .docx
        </a>
      </footer>
    </article>
  );
}

function firstSentence(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) return "";
  const m = /^([^.!?]*[.!?])\s/.exec(trimmed);
  return m ? m[1].trim() : trimmed;
}

function formatDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
