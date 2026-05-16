import { motion, useReducedMotion } from "framer-motion";
import { Bookmark, Clock, FileText, Globe, Layers } from "lucide-react";
import { type JSX, useState } from "react";

import type { ReportMode } from "../../api/equity-research";
import { ReportDownloadButton } from "../report/ReportDownloadButton";

const MODE_TITLE: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation Report",
  stock_update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

interface Props {
  reportId: string;
  mode: ReportMode;
  /** Resolved ticker (e.g. "AAPL"). Falls back to the raw subject if missing. */
  ticker?: string | null;
  /** Resolved company name (e.g. "Apple Inc."). Optional. */
  companyName?: string | null;
  /** Original user input (used as fallback when ticker is unresolved). */
  subject: string;
  createdAt: string;
  preview: string;
  /** Number of sections in the generated report. */
  sectionsCount?: number;
  /** Generation duration in seconds (from dispatch to "complete"). */
  generatedSeconds?: number | null;
  /** Number of cited sources. */
  citationsCount?: number;
  onOpen: (reportId: string) => void;
  onSave: (reportId: string) => void | Promise<void>;
  initialSaved?: boolean;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function ReportCard({
  reportId,
  mode,
  ticker,
  companyName,
  subject,
  createdAt,
  preview,
  sectionsCount,
  generatedSeconds,
  citationsCount,
  onOpen,
  onSave,
  initialSaved = false,
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const [saved, setSaved] = useState(initialSaved);
  const [saving, setSaving] = useState(false);

  const handleSave = async () => {
    if (saving || saved) return;
    setSaving(true);
    try {
      await onSave(reportId);
      setSaved(true);
    } finally {
      setSaving(false);
    }
  };

  const date = formatDate(createdAt);
  const subParts: JSX.Element[] = [];
  if (ticker) {
    subParts.push(
      <strong key="ticker" className="font-medium text-[--color-text-primary]">
        {ticker}
      </strong>,
    );
  } else {
    subParts.push(
      <span key="subject" className="truncate">
        {subject}
      </span>,
    );
  }
  if (companyName) subParts.push(<span key="company">{companyName}</span>);
  subParts.push(<span key="date">{date}</span>);

  return (
    <motion.article
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      className="max-w-[560px] overflow-hidden rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm"
    >
      <header className="flex items-start gap-3 px-[18px] pt-4 pb-3">
        <div
          aria-hidden="true"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[rgba(168,204,0,0.3)] bg-[rgba(212,255,0,0.16)] text-[--color-feedback-success]"
        >
          <FileText size={16} strokeWidth={1.6} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="text-[15px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
            {MODE_TITLE[mode]}
          </span>
          <span className="flex flex-wrap items-center gap-[5px] truncate font-mono text-[11px] tracking-[0.02em] text-[--color-text-secondary]">
            {subParts.map((p, i) => (
              <span key={i} className="inline-flex items-center gap-[5px]">
                {p}
                {i < subParts.length - 1 ? (
                  <span aria-hidden="true" className="text-[--color-text-tertiary]">
                    ·
                  </span>
                ) : null}
              </span>
            ))}
          </span>
        </div>
        <span className="inline-flex flex-shrink-0 items-center gap-[5px] self-start rounded-full border border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-feedback-success]">
          <span
            aria-hidden="true"
            className="h-[5px] w-[5px] rounded-full bg-[--color-feedback-success] shadow-[0_0_4px_rgba(168,204,0,0.7)]"
          />
          Ready
        </span>
      </header>

      <p className="m-0 line-clamp-3 px-[18px] pb-[14px] text-[13px] leading-[1.6] text-[--color-text-secondary]">
        {preview}{" "}
        <button
          type="button"
          onClick={() => onOpen(reportId)}
          className="font-medium text-[--color-text-primary] hover:text-[--color-feedback-success]"
        >
          read more →
        </button>
      </p>

      {(sectionsCount || generatedSeconds != null || citationsCount) ? (
        <div
          className="flex flex-wrap gap-[14px] px-[18px] pb-[14px] font-mono text-[10px] tracking-[0.06em] text-[--color-text-tertiary]"
          data-testid="er-report-card-meta"
        >
          {sectionsCount ? (
            <span className="inline-flex items-center gap-[5px]">
              <Layers size={11} strokeWidth={1.6} />
              {sectionsCount} sections
            </span>
          ) : null}
          {generatedSeconds != null ? (
            <span className="inline-flex items-center gap-[5px]">
              <Clock size={11} strokeWidth={1.6} />
              Generated in {generatedSeconds.toFixed(1)}s
            </span>
          ) : null}
          {citationsCount ? (
            <span className="inline-flex items-center gap-[5px]">
              <Globe size={11} strokeWidth={1.6} />
              {citationsCount} sources cited
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-center gap-2 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[18px] py-3">
        <button
          type="button"
          onClick={() => onOpen(reportId)}
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 text-[13px] font-medium text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover]"
        >
          <FileText size={13} strokeWidth={1.7} />
          Open Report
        </button>

        <ReportDownloadButton reportId={reportId} variant="primary" />

        <div className="flex-1" />

        <button
          type="button"
          onClick={() => void handleSave()}
          aria-label={saved ? "Saved to Repository" : "Save to Repository"}
          aria-pressed={saved}
          disabled={saving}
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md px-2 text-[13px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:opacity-50"
        >
          <Bookmark
            size={14}
            strokeWidth={1.7}
            fill={saved ? "currentColor" : "none"}
            data-testid="bookmark-icon"
          />
          {saved ? "Saved" : "Save to Repo"}
        </button>
      </div>
    </motion.article>
  );
}
