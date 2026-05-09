import type { JSX } from "react";
import { SourceChip } from "./SourceChip";
import { mapToolCallToSource } from "./toolCallSourceMap";
import { useFileViewerOptional, kindFromFilename } from "../viewer/FileViewerContext";

interface Props {
  toolName: string;
  argsPreview: string;
  status: "running" | "done" | "failed";
  summary?: string;
  /** Structured tool-call result. When it carries an `attachment_id` or
   *  `report_id`, the chip becomes clickable and opens the artifact in
   *  the FileViewer. */
  structured?: Record<string, unknown> | null;
  /** Stagger index within the chip row (0,1,2,...). */
  index?: number;
}

/** ToolCallChip is the in-thread source attribution chip — restyled to the
 *  design's source-chip aesthetic. The label is computed by
 *  `mapToolCallToSource` so common backend tool names (read_repo_item,
 *  search_news, etc.) surface as friendly labels with appropriate icons. */
export function ToolCallChip({
  toolName,
  argsPreview,
  status,
  summary,
  structured,
  index = 0,
}: Props): JSX.Element {
  const viewer = useFileViewerOptional();
  const mapped = mapToolCallToSource(toolName, argsPreview, structured);

  // Failed calls surface the technical name + args so the user can debug.
  // Running calls use the mapped label but show pending styling.
  const label =
    status === "failed"
      ? `${toolName} failed`
      : status === "done" && summary
        ? summary
        : mapped.label;

  const onClick = buildOnClick(structured ?? null, mapped.label, viewer);

  return (
    <SourceChip
      label={truncate(label, 60)}
      kind={mapped.kind}
      title={summary ?? `${toolName}(${argsPreview})`}
      pending={status === "running"}
      onClick={onClick ?? undefined}
      index={index}
    />
  );
}

function truncate(s: string, max: number): string {
  if (s.length <= max) return s;
  return s.slice(0, max - 1).trimEnd() + "…";
}

function buildOnClick(
  structured: Record<string, unknown> | null,
  fallbackLabel: string,
  viewer: ReturnType<typeof useFileViewerOptional>,
): (() => void) | null {
  if (!structured || !viewer) return null;

  const attachmentId =
    typeof structured.attachment_id === "string" ? structured.attachment_id : null;
  const reportId =
    typeof structured.report_id === "string" ? structured.report_id : null;
  const filename =
    typeof structured.filename === "string"
      ? structured.filename
      : typeof structured.title === "string"
        ? (structured.title as string)
        : fallbackLabel;

  if (reportId) {
    return () =>
      viewer.open({
        filename,
        kind: "markdown",
        metadata: "REPORT",
        source: { kind: "report", reportId },
      });
  }
  if (attachmentId) {
    return () =>
      viewer.open({
        filename,
        kind: kindFromFilename(filename),
        metadata: "ATTACHMENT",
        source: { kind: "attachment", attachmentId },
      });
  }
  return null;
}
