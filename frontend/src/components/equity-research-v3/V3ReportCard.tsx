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
  AlertTriangle,
  Clock,
  ExternalLink,
  FileText,
  Globe,
  Image as ImageIcon,
  Layers,
  Loader2,
} from "lucide-react";
import { type JSX } from "react";

import type { V3Event, V3ReportDetail } from "../../api/equity-research-v3";
import { v3HtmlUrl } from "../../api/equity-research-v3";
import { V3ActivityFeed } from "./V3ActivityFeed";
import { ReportDownloadButton } from "../report/ReportDownloadButton";
import { SaveToRepoButton } from "../chat/SaveToRepoButton";
import { useFileViewerOptional } from "../viewer/FileViewerContext";

export type V3CardPhase = "generating" | "ready";

export interface V3CardLive {
  status: "streaming" | "completed" | "failed" | "cancelled";
  sectionsWritten: number;
  chartsEmitted: number;
  citationsSeen: number;
  elapsedSeconds: number | null;
  events: V3Event[];
  terminalMessage: string | null;
  errorMessage: string | null;
}

interface Props {
  /** Defaults to "ready" so existing detail-only callers are unchanged. */
  phase?: V3CardPhase;
  /** Header subject. Ready phase falls back to ``detail.report.subject``. */
  subject?: string;
  /** Friendly template label for the meta line. Ready phase falls back
   *  to ``detail.report.template_id``. */
  templateLabel?: string;
  /** ISO date for the meta line. Ready phase falls back to
   *  ``detail.report.created_at``. */
  createdAtIso?: string | null;
  /** Persisted detail — present in the ready phase. */
  detail?: V3ReportDetail | null;
  /** Optional preview text (ready phase). Falls back to first section. */
  preview?: string;
  /** Generation duration in seconds (ready phase meta row). */
  generatedSeconds?: number | null;
  /** Ready-phase: flips the pill to "Revising…" while a revision runs. */
  revising?: boolean;
  /** Pre-populate the Save-to-Repo "Saved" state on first paint. */
  initialSaved?: boolean;
  /** Live stream data — required in the generating phase. */
  live?: V3CardLive;
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
  phase = "ready",
  subject,
  templateLabel,
  createdAtIso,
  detail,
  preview,
  generatedSeconds,
  revising = false,
  initialSaved = false,
  live,
}: Props): JSX.Element {
  const reduce = useReducedMotion();
  const fileViewer = useFileViewerOptional();

  const generating = phase === "generating";
  const headerSubject = detail?.report.subject ?? subject ?? "";
  const headerTemplate = templateLabel ?? detail?.report.template_id ?? "";
  const headerDateIso = detail?.report.created_at ?? createdAtIso ?? null;
  const previewText = detail ? (preview ?? deriveFallbackPreview(detail)) : "";
  const htmlHref = detail ? v3HtmlUrl(detail.report.report_id) : "#";

  const openInViewer = (trigger?: HTMLElement | null) => {
    if (!detail) return;
    if (!fileViewer) {
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
            {headerSubject}
          </span>
          <span className="flex flex-wrap items-center gap-[5px] truncate font-mono text-[11px] tracking-[0.02em] text-[--color-text-secondary]">
            <span className="truncate">{headerTemplate}</span>
            {headerDateIso ? (
              <>
                <span aria-hidden="true" className="text-[--color-text-tertiary]">·</span>
                <span>{formatDate(headerDateIso)}</span>
              </>
            ) : null}
          </span>
        </div>
        <StatusPill phase={phase} status={live?.status} revising={revising} />
      </header>

      {generating ? (
        <>
          {live?.errorMessage ? (
            <p className="m-0 px-[18px] pb-[10px] text-[12px] text-[--color-feedback-danger]">
              {live.errorMessage}
            </p>
          ) : live?.terminalMessage ? (
            <p className="m-0 px-[18px] pb-[10px] text-[12px] text-[--color-feedback-warning]">
              {live.terminalMessage}
            </p>
          ) : null}
          <V3ActivityFeed events={live?.events ?? []} />
        </>
      ) : previewText ? (
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
        <MetaCounts
          generating={generating}
          live={live}
          detail={detail}
          generatedSeconds={generatedSeconds}
        />
      </div>

      {generating ? null : detail ? (
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
          <span data-testid="er-v3-report-card-download">
            <ReportDownloadButton
              reportId={detail.report.report_id}
              engine="v3"
              variant="primary"
            />
          </span>
          <span data-testid="er-v3-report-card-save">
            <SaveToRepoButton
              reportId={detail.report.report_id}
              engine="v3"
              initialSaved={initialSaved}
              variant="viewer-header"
            />
          </span>
          <a
            href={htmlHref}
            target="_blank"
            rel="noopener noreferrer"
            data-testid="er-v3-report-card-standalone"
            title="Open the printable HTML in a new tab (use the browser's Save As to grab a Word or PDF copy)"
            className="ml-auto inline-flex h-[30px] items-center gap-[6px] rounded-md px-2 text-[12px] text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-secondary]"
          >
            <ExternalLink size={12} strokeWidth={1.7} />
            Standalone
          </a>
        </div>
      ) : null}
    </motion.article>
  );
}

function MetaCounts({
  generating,
  live,
  detail,
  generatedSeconds,
}: {
  generating: boolean;
  live?: V3CardLive;
  detail?: V3ReportDetail | null;
  generatedSeconds?: number | null;
}): JSX.Element {
  const sections = generating ? (live?.sectionsWritten ?? 0) : (detail?.sections.length ?? 0);
  const charts = generating ? (live?.chartsEmitted ?? 0) : (detail?.charts.length ?? 0);
  const sources = generating ? (live?.citationsSeen ?? 0) : (detail?.citations.length ?? 0);
  const elapsed = generating ? (live?.elapsedSeconds ?? null) : (generatedSeconds ?? null);

  return (
    <>
      {sections > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <Layers size={11} strokeWidth={1.6} />
          {sections} section{sections === 1 ? "" : "s"}
        </span>
      ) : null}
      {charts > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <ImageIcon size={11} strokeWidth={1.6} />
          {charts} chart{charts === 1 ? "" : "s"}
        </span>
      ) : null}
      {sources > 0 ? (
        <span className="inline-flex items-center gap-[5px]">
          <Globe size={11} strokeWidth={1.6} />
          {sources} source{sources === 1 ? "" : "s"}
        </span>
      ) : null}
      {elapsed != null ? (
        <span className="inline-flex items-center gap-[5px]">
          <Clock size={11} strokeWidth={1.6} />
          {generating ? `Elapsed ${elapsed.toFixed(1)}s` : `Generated in ${elapsed.toFixed(1)}s`}
        </span>
      ) : null}
    </>
  );
}

function StatusPill({
  phase,
  status,
  revising,
}: {
  phase: V3CardPhase;
  status?: V3CardLive["status"];
  revising: boolean;
}): JSX.Element {
  const base =
    "inline-flex flex-shrink-0 items-center gap-[5px] self-start rounded-full border px-2 py-[3px] font-mono text-[9px] uppercase tracking-[0.1em]";

  if (phase === "generating") {
    if (status === "failed") {
      return (
        <span
          data-testid="er-v3-report-card-failed"
          className={`${base} border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] text-[--color-feedback-danger]`}
        >
          <AlertTriangle size={10} strokeWidth={2} aria-hidden="true" />
          Failed
        </span>
      );
    }
    if (status === "cancelled") {
      return (
        <span
          data-testid="er-v3-report-card-cancelled"
          className={`${base} border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] text-[--color-feedback-warning]`}
        >
          Cancelled
        </span>
      );
    }
    if (status === "completed") {
      return (
        <span
          data-testid="er-v3-report-card-finalizing"
          className={`${base} border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]`}
        >
          <span aria-hidden="true" className="h-[5px] w-[5px] rounded-full bg-[--color-feedback-success]" />
          Finalizing
        </span>
      );
    }
    return (
      <span
        data-testid="er-v3-report-card-generating"
        className={`${base} border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]`}
      >
        <Loader2 size={10} strokeWidth={2.2} className="motion-safe:animate-spin" aria-hidden="true" />
        Generating
      </span>
    );
  }

  if (revising) {
    return (
      <span
        data-testid="er-v3-report-card-revising"
        className={`${base} border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]`}
      >
        <span aria-hidden="true" className="h-[5px] w-[5px] animate-pulse rounded-full bg-[--color-text-secondary]" />
        Revising
      </span>
    );
  }

  return (
    <span
      data-testid="er-v3-report-card-ready"
      className={`${base} border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]`}
    >
      <span
        aria-hidden="true"
        className="h-[5px] w-[5px] rounded-full bg-[--color-feedback-success] shadow-[0_0_4px_rgba(168,204,0,0.7)]"
      />
      Ready
    </span>
  );
}
