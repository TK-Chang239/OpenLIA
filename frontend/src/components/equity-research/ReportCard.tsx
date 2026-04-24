import { FileText } from "lucide-react";

import type { ReportMode } from "../../api/equity-research";

const MODE_TITLE: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation Report",
  stock_update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

interface Props {
  reportId: string;
  mode: ReportMode;
  subject: string;
  companyName: string | null;
  createdAt: string;
  preview: string;
  onOpen: (reportId: string) => void;
  onDownload: (reportId: string, format: "pdf" | "docx") => void;
  onSave: (reportId: string) => void;
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
  subject,
  companyName,
  createdAt,
  preview,
  onOpen,
  onDownload,
  onSave,
}: Props) {
  const date = formatDate(createdAt);
  const subjectLine = companyName
    ? `${subject}  ·  ${companyName}  ·  ${date}`
    : `${subject}  ·  ${date}`;

  return (
    <div className="max-w-[560px] rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-sm overflow-hidden">
      <div className="px-4 py-3 flex items-start gap-3">
        <FileText size={16} className="text-[--color-text-tertiary]" />
        <div>
          <div className="text-base font-medium text-[--color-text-primary]">
            {MODE_TITLE[mode]}
          </div>
          <div className="text-sm text-[--color-text-secondary]">
            {subjectLine}
          </div>
        </div>
      </div>
      <div className="px-4 py-3 text-sm text-[--color-text-secondary] leading-relaxed line-clamp-3">
        {preview}
      </div>
      <div className="px-4 py-2.5 flex items-center gap-2 bg-[--color-bg-base] border-t border-[--color-border-subtle]">
        <button
          type="button"
          onClick={() => onOpen(reportId)}
          className="px-3 h-7 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm"
        >
          Open Report
        </button>
        <button
          type="button"
          onClick={() => onDownload(reportId, "pdf")}
          className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm"
        >
          Download PDF
        </button>
        <button
          type="button"
          onClick={() => onSave(reportId)}
          className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm"
        >
          Save to Repo
        </button>
      </div>
    </div>
  );
}
