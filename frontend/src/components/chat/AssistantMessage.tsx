import type { JSX } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LiaBadge } from "./LiaBadge";
import { CodeBlock } from "./CodeBlock";
import { ReportThumbnail } from "./ReportThumbnail";

export type AssistantChunk =
  | { type: "text"; text: string }
  | { type: "thumbnail"; report_id: string; filename: string };

interface Props {
  /**
   * Inline chunks (text + thumbnails). When omitted, falls back to rendering
   * the legacy ``content`` string so historical (non-streaming) callers keep
   * working.
   */
  chunks?: AssistantChunk[];
  /** Legacy plain content. Used only when ``chunks`` is undefined. */
  content?: string;
  streaming: boolean;
  timestamp?: string;
  stopped?: boolean;
}

function MarkdownText({ text }: { text: string }): JSX.Element {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code: CodeBlock as never,
      }}
    >
      {text}
    </ReactMarkdown>
  );
}

export function AssistantMessage({
  chunks,
  content,
  streaming,
  timestamp,
  stopped,
}: Props): JSX.Element {
  const inlineChunks: AssistantChunk[] =
    chunks ?? (content !== undefined ? [{ type: "text", text: content }] : []);

  return (
    <article aria-label="Assistant message" className="flex items-start gap-3">
      <LiaBadge />
      <div className="flex flex-col min-w-0 max-w-[600px]">
        <div className="rounded-[10px] border border-border-subtle bg-bg-elevated px-4 py-[14px] text-[14.5px] leading-[1.65] font-display text-text-primary prose prose-sm dark:prose-invert max-w-none">
          {inlineChunks.map((c, i) =>
            c.type === "text" ? (
              <MarkdownText key={`t-${i}`} text={c.text} />
            ) : (
              <div key={`tn-${i}`} className="my-2">
                <ReportThumbnail reportId={c.report_id} filename={c.filename} />
              </div>
            ),
          )}
          {streaming ? (
            <span
              data-testid="streaming-cursor"
              className="ml-0.5 inline-block"
              style={{ color: "rgba(212, 255, 0, 0.7)" }}
            >
              &#9612;
            </span>
          ) : null}
        </div>
        {stopped ? (
          <span className="mt-1.5 block font-mono text-[10px] italic text-text-tertiary">
            Response stopped.
          </span>
        ) : null}
        {timestamp ? (
          <time className="mt-1 block font-mono text-[10px] text-text-tertiary">
            {timestamp}
          </time>
        ) : null}
      </div>
    </article>
  );
}
