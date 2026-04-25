import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Bookmark, ChevronDown, FileText } from "lucide-react";
import { useState } from "react";

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
  subject,
  companyName,
  createdAt,
  preview,
  onOpen,
  onDownload,
  onSave,
  initialSaved = false,
}: Props) {
  const [saved, setSaved] = useState<boolean>(initialSaved);
  const [saving, setSaving] = useState<boolean>(false);
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
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              aria-label="Download"
              className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm inline-flex items-center gap-1"
            >
              Download
              <ChevronDown size={12} />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              className="min-w-[180px] rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg p-1 text-sm"
              sideOffset={4}
            >
              <DropdownMenu.Item
                onSelect={() => onDownload(reportId, "pdf")}
                className="px-2 py-1.5 rounded-[--radius-sm] outline-none cursor-pointer hover:bg-[--color-surface-hover]"
              >
                Download as PDF
              </DropdownMenu.Item>
              <DropdownMenu.Item
                onSelect={() => onDownload(reportId, "docx")}
                className="px-2 py-1.5 rounded-[--radius-sm] outline-none cursor-pointer hover:bg-[--color-surface-hover]"
              >
                Download as DOCX
              </DropdownMenu.Item>
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>
        <button
          type="button"
          onClick={() => void handleSave()}
          aria-label={saved ? "Saved to Repo" : "Save to Repo"}
          aria-pressed={saved}
          disabled={saving}
          className="px-3 h-7 rounded-[--radius-md] border border-[--color-border-subtle] text-sm inline-flex items-center gap-1 disabled:opacity-50"
        >
          <Bookmark
            size={14}
            fill={saved ? "currentColor" : "none"}
            data-testid="bookmark-icon"
          />
          {saved ? "Saved" : "Save to Repo"}
        </button>
      </div>
    </div>
  );
}
