import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { motion, useReducedMotion } from "framer-motion";
import {
  Bookmark,
  ChevronDown,
  Clock,
  FileText,
  Globe,
  Layers,
  MessageSquare,
  Trash2,
} from "lucide-react";
import { type JSX, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ReportMode } from "../../api/equity-research";
import { createSession } from "../../api/chat";
import { DeleteReportDialog } from "../report/DeleteReportDialog";
import { useSavedReportsOptional } from "../repo/SavedReportsContext";
import type { FailedReport } from "./FailedReportCard";
import { FailedReportCard } from "./FailedReportCard";
import type { GeneratingReport } from "./GeneratingPlaceholderCard";
import { GeneratingPlaceholderCard } from "./GeneratingPlaceholderCard";

// ─── Status-based report object (background generation) ──────────────────────

export type ReportStatus = "generating" | "failed" | "cancelled" | "complete";

export interface BgReport {
  id: string;
  status: ReportStatus;
  started_at?: string | null;
  original_request?: { user_input?: string | null } | null;
  failure_reason?: string | null;
}

// ─── Flat-props API for completed reports ─────────────────────────────────────

const MODE_TITLE: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation Report",
  stock_update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

const RETENTION_DAYS = 7;
const MS_PER_DAY = 86_400_000;

function ageDays(iso: string, now: number = Date.now()): number {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return 0;
  return (now - t) / MS_PER_DAY;
}

interface CompletedProps {
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
  onDownload: (reportId: string, format: "pdf" | "docx") => void;
  onSave: (reportId: string) => void | Promise<void>;
  /** Soft-unsave: removes the repo_items pointer. Only invoked when age < 7d. */
  onUnsave?: (reportId: string) => void | Promise<void>;
  /** Hard delete: tombstones the report. Only invoked when age >= 7d and saved. */
  onDelete?: (reportId: string) => void | Promise<void>;
  initialSaved?: boolean;
  /** ISO timestamp; when set, render the tombstone variant. */
  expiredAt?: string | null;
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

function CompletedReportCard({
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
  onDownload,
  onSave,
  onUnsave,
  onDelete,
  initialSaved = false,
  expiredAt = null,
}: CompletedProps): JSX.Element {
  const reduce = useReducedMotion();
  const navigate = useNavigate();
  const savedCtx = useSavedReportsOptional();
  const [localSaved, setLocalSaved] = useState(initialSaved);
  const [saving, setSaving] = useState(false);
  const [discussing, setDiscussing] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const saved = savedCtx ? savedCtx.isSaved(reportId) || localSaved : localSaved;
  const isExpired = expiredAt != null;
  const isOldSaved = !isExpired && saved && ageDays(createdAt) >= RETENTION_DAYS;

  const handleSaveToggle = async () => {
    if (saving) return;
    setSaving(true);
    try {
      if (saved) {
        if (onUnsave) {
          await onUnsave(reportId);
          setLocalSaved(false);
          savedCtx?.markUnsaved(reportId);
        }
      } else {
        await onSave(reportId);
        setLocalSaved(true);
        savedCtx?.markSaved(reportId);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (deleting || !onDelete) return;
    setDeleting(true);
    try {
      await onDelete(reportId);
      setDeleteOpen(false);
    } finally {
      setDeleting(false);
    }
  };

  const handleDiscuss = async () => {
    if (discussing) return;
    setDiscussing(true);
    try {
      const title = ticker ?? subject;
      const session = await createSession({
        department: "equity_research",
        title,
        attached_report_id: reportId,
      });
      navigate(`/chat/${session.id}`);
    } finally {
      setDiscussing(false);
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

  if (isExpired) {
    return (
      <motion.article
        initial={reduce ? { opacity: 0 } : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22, ease: "easeOut" }}
        className="max-w-[560px] overflow-hidden rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-base] opacity-80"
        data-testid="er-report-card-tombstone"
      >
        <header className="flex items-start gap-3 px-[18px] pt-4 pb-3">
          <div
            aria-hidden="true"
            className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg border border-[--color-border-subtle] bg-[--color-surface-hover] text-[--color-text-tertiary]"
          >
            <FileText size={16} strokeWidth={1.6} />
          </div>
          <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
            <span className="text-[15px] font-semibold tracking-[-0.005em] text-[--color-text-secondary]">
              {MODE_TITLE[mode]}
            </span>
            <span className="flex flex-wrap items-center gap-[5px] truncate font-mono text-[11px] tracking-[0.02em] text-[--color-text-tertiary]">
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
        </header>
        <p className="m-0 px-[18px] pb-[18px] text-[13px] italic leading-[1.6] text-[--color-text-tertiary]">
          Report no longer available — automatically expired after 7 days.
        </p>
      </motion.article>
    );
  }

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

        <button
          type="button"
          onClick={() => void handleDiscuss()}
          disabled={discussing}
          className="inline-flex h-[30px] items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-transparent px-3 text-[13px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:opacity-50"
        >
          <MessageSquare size={13} strokeWidth={1.7} />
          Discuss
        </button>

        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              aria-label="Download"
              className="inline-flex h-[30px] items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-transparent px-3 text-[13px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              Download
              <ChevronDown size={12} strokeWidth={2} />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              sideOffset={4}
              className="z-50 min-w-[180px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-1 text-sm shadow-lg"
            >
              <DropdownMenu.Item
                onSelect={() => onDownload(reportId, "pdf")}
                className="cursor-pointer rounded-sm px-2 py-1.5 outline-none data-[highlighted]:bg-[--color-surface-hover]"
              >
                Download as PDF
              </DropdownMenu.Item>
              <DropdownMenu.Item
                onSelect={() => onDownload(reportId, "docx")}
                className="cursor-pointer rounded-sm px-2 py-1.5 outline-none data-[highlighted]:bg-[--color-surface-hover]"
              >
                Download as DOCX
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <div className="flex-1" />

        {isOldSaved ? (
          <button
            type="button"
            onClick={() => setDeleteOpen(true)}
            aria-label="Delete report"
            disabled={deleting}
            className="inline-flex h-[30px] items-center gap-[6px] rounded-md px-2 text-[13px] text-[--color-feedback-error] transition-colors hover:bg-[--color-surface-hover] disabled:opacity-50"
          >
            <Trash2 size={14} strokeWidth={1.7} data-testid="delete-icon" />
            Delete
          </button>
        ) : (
          <button
            type="button"
            onClick={() => void handleSaveToggle()}
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
        )}
      </div>

      <DeleteReportDialog
        open={deleteOpen}
        reportTitle={MODE_TITLE[mode]}
        onCancel={() => setDeleteOpen(false)}
        onConfirm={handleDeleteConfirm}
      />
    </motion.article>
  );
}

// ─── Dispatcher ───────────────────────────────────────────────────────────────

interface BgReportProps {
  report: BgReport;
  navigate?: (path: string) => void;
}

export function ReportCard(props: BgReportProps): JSX.Element;
export function ReportCard(props: CompletedProps): JSX.Element;
export function ReportCard(props: BgReportProps | CompletedProps): JSX.Element {
  const routerNavigate = useNavigate();

  if ("report" in props) {
    const { report, navigate: nav } = props;
    const go = nav ?? routerNavigate;
    switch (report.status) {
      case "generating":
        return <GeneratingPlaceholderCard report={report as GeneratingReport} />;
      case "failed":
      case "cancelled":
        return <FailedReportCard report={report as FailedReport} navigate={go} />;
      case "complete":
      default:
        return <div className="card card--complete" />;
    }
  }

  return <CompletedReportCard {...props} />;
}
