/**
 * V3ReportCard — v3 equivalent of the v1/v2 ReportCard.
 *
 * Visual shape mirrors ``components/equity-research/ReportCard``:
 * rounded card with a left icon, title + meta line, "Ready" pill,
 * preview text with "Read more" link, meta row (sections / charts /
 * sources), and a primary-action row at the bottom. Adapted for v3:
 *
 *   - Title is the report subject (ticker or topic)
 *   - Meta line: template name + creation date
 *   - Primary actions: Open HTML, Download PDF (the two v3 export
 *     paths) + the revision chat sits below this card on the page
 *   - "Ready" pill flips to "Revising…" while a revision runs
 */
import { motion, useReducedMotion } from "framer-motion";
import {
  Clock,
  Download,
  ExternalLink,
  FileText,
  Globe,
  Image as ImageIcon,
  Layers,
} from "lucide-react";
import { type JSX } from "react";

import type { V3ReportDetail } from "../../api/equity-research-v3";
import { v3HtmlUrl, v3PdfUrl } from "../../api/equity-research-v3";
import { useFileViewerOptional } from "../viewer/FileViewerContext";

interface Props {
  detail: V3ReportDetail;
  /** Optional preview text. Falls back to the first section's
   *  markdown (truncated). The renderer prefers the cover-style
   *  summary when v3 grows one. */
  preview?: string;
  /** Generation duration in seconds (from dispatch to "complete"). */
  generatedSeconds?: number | null;
  /** When true, the status pill renders as "Revising…" instead of
   *  "Ready". The page sets this while ``listV3Revisions`` shows a
   *  ``running`` revision row. */
  revising?: boolean;
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

function deriveFallbackPreview(detail: V3ReportDetail): string {
  const first = detail.sections[0];
  if (!first) return "";
  // Strip simple markdown markers so the preview reads cleanly.
  const stripped = first.markdown
    .replace(/\[\^[a-z0-9_]+\]/g, "")
    .replace(/\{\{chart:[a-z0-9_]+\}\}/g, "")
    .replace(/[#*_>`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return stripped.slice(0, 320);
}

export function V3ReportCard({
  detail,
  preview,
  generatedSeconds,
  revising = false,
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const fileViewer = useFileViewerOptional();
  const previewText = preview ?? deriveFallbackPreview(detail);
  const htmlHref = v3HtmlUrl(detail.report.report_id);
  const pdfHref = v3PdfUrl(detail.report.report_id);

  const openInViewer = (trigger?: HTMLElement | null) => {
    if (!fileViewer) {
      // No FileViewer mounted in the tree (tests, embedded contexts) —
      // fall back to the standalone HTML window so the user is never
      // left without a way to read the report.
      window.open(htmlHref, "_blank", "noopener,noreferrer");
      return;
    }
    fileViewer.open({
      filename: detail.report.subject || "Equity Research Report",
      kind: "report",
      metadata: `v3 engine · ${detail.report.template_id}`,
      source: { kind: "v3_report", reportId: detail.report.report_id },
      trigger: trigger ?? null,
    });
  };

  return (
    <motion.article
      initial={reduce ? { opacity: 0 } : { opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      data-testid="er-v3-report-card"
      className="max-w-[640px] overflow-hidden rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm"
    >
      <header className="flex items-start gap-3 px-[18px] pt-4 pb-3">
        <div
          aria-hidden="true"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[rgba(168,204,0,0.3)] bg-[rgba(212,255,0,0.16)] text-[--color-feedback-success]"
        >
          <FileText size={16} strokeWidth={1.6} />
        </div>
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="truncate text-[15px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
            {detail.report.subject}
          </span>
          <span className="flex flex-wrap items-center gap-[5px] truncate font-mono text-[11px] tracking-[0.02em] text-[--color-text-secondary]">
            <span className="truncate">{detail.report.template_id}</span>
            <span aria-hidden="true" className="text-[--color-text-tertiary]">·</span>
            <span>{formatDate(detail.report.created_at)}</span>
          </span>
        </div>
        <StatusPill revising={revising} />
      </header>

      {previewText ? (
        <p className="m-0 line-clamp-3 px-[18px] pb-[14px] text-[13px] leading-[1.6] text-[--color-text-secondary]">
          {previewText}{" "}
          <button
            type="button"
            onClick={(e) => openInViewer(e.currentTarget)}
            className="font-medium text-[--color-text-primary] hover:text-[--color-feedback-success]"
          >
            Read more
          </button>
        </p>
      ) : null}

      <div
        className="flex flex-wrap gap-[14px] px-[18px] pb-[14px] font-mono text-[10px] tracking-[0.06em] text-[--color-text-tertiary]"
        data-testid="er-v3-report-card-meta"
      >
        {detail.sections.length > 0 ? (
          <span className="inline-flex items-center gap-[5px]">
            <Layers size={11} strokeWidth={1.6} />
            {detail.sections.length} section{detail.sections.length === 1 ? "" : "s"}
          </span>
        ) : null}
        {detail.charts.length > 0 ? (
          <span className="inline-flex items-center gap-[5px]">
            <ImageIcon size={11} strokeWidth={1.6} />
            {detail.charts.length} chart{detail.charts.length === 1 ? "" : "s"}
          </span>
        ) : null}
        {generatedSeconds != null ? (
          <span className="inline-flex items-center gap-[5px]">
            <Clock size={11} strokeWidth={1.6} />
            generated in {generatedSeconds.toFixed(1)}s
          </span>
        ) : null}
        {detail.citations.length > 0 ? (
          <span className="inline-flex items-center gap-[5px]">
            <Globe size={11} strokeWidth={1.6} />
            {detail.citations.length} source{detail.citations.length === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-2 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[18px] py-3">
        <button
          type="button"
          onClick={(e) => openInViewer(e.currentTarget)}
          data-testid="er-v3-report-card-open"
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 text-[13px] font-medium text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover]"
        >
          <FileText size={13} strokeWidth={1.7} />
          Open report
        </button>
        <a
          href={pdfHref}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="er-v3-report-card-pdf"
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-transparent px-3 text-[13px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
        >
          <Download size={13} strokeWidth={1.7} />
          Download PDF
        </a>
        {/* Standalone-HTML window — the original "open new tab"
            behaviour, kept as a secondary action so the user can use
            the browser's native Save As → Word / Print → PDF. */}
        <a
          href={htmlHref}
          target="_blank"
          rel="noopener noreferrer"
          data-testid="er-v3-report-card-standalone"
          title="Open the printable HTML in a new tab (use the browser's Save As to grab a Word or PDF copy)"
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md px-2 text-[12px] text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-secondary]"
        >
          <ExternalLink size={12} strokeWidth={1.7} />
          Standalone
        </a>
      </div>
    </motion.article>
  );
}

function StatusPill({ revising }: { revising: boolean }): JSX.Element {
  if (revising) {
    return (
      <span
        data-testid="er-v3-report-card-revising"
        className="inline-flex flex-shrink-0 items-center gap-[5px] self-start rounded-full border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-secondary]"
      >
        <span
          aria-hidden="true"
          className="h-[5px] w-[5px] animate-pulse rounded-full bg-[--color-text-secondary]"
        />
        Revising
      </span>
    );
  }
  return (
    <span
      data-testid="er-v3-report-card-ready"
      className="inline-flex flex-shrink-0 items-center gap-[5px] self-start rounded-full border border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-feedback-success]"
    >
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] rounded-full bg-[--color-feedback-success] shadow-[0_0_4px_rgba(168,204,0,0.7)]"
      />
      Ready
    </span>
  );
}
