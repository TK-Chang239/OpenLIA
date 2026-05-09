import type { JSX } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { LiaBadge } from "./LiaBadge";
import { MarkdownCodeRenderer } from "./MarkdownCodeRenderer";
import { ReportThumbnail } from "./ReportThumbnail";
import { SkillLoadedCard } from "./SkillLoadedCard";
import { AssistantMessageTag } from "./AssistantMessageTag";
import { useReducedMotion } from "../../hooks/useReducedMotion";

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
  flagChips?: Array<{ category: string; text: string }>;
  skillLoads?: Array<{ skillId: string; displayName: string }>;
  /** Department slug for the AssistantMessageTag (e.g., "secretary"). */
  departmentId?: string | null;
  /** Total token count for the response. */
  tokens?: number | null;
  /** Wall-clock latency from send→done, in ms. */
  latencyMs?: number | null;
}

function MarkdownText({ text }: { text: string }): JSX.Element {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code: MarkdownCodeRenderer as never,
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
  flagChips,
  skillLoads,
  departmentId,
  tokens,
  latencyMs,
}: Props): JSX.Element {
  const inlineChunks: AssistantChunk[] =
    chunks ?? (content !== undefined ? [{ type: "text", text: content }] : []);
  const reduce = useReducedMotion();

  return (
    <motion.article
      aria-label="Assistant message"
      initial={{ opacity: 0, y: reduce ? 0 : 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduce ? 0 : 0.2, ease: [0.16, 1, 0.3, 1] }}
      className="flex items-start gap-3"
    >
      <LiaBadge />
      <div className="flex flex-col min-w-0 max-w-[600px]">
        {!streaming ? (
          <AssistantMessageTag
            departmentId={departmentId}
            tokens={tokens}
            latencyMs={latencyMs}
          />
        ) : null}
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
          {skillLoads && skillLoads.length > 0 && (
            <div className="mt-2">
              {skillLoads.map((s, i) => (
                <SkillLoadedCard key={`s-${i}`} skillId={s.skillId} displayName={s.displayName} />
              ))}
            </div>
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
        {flagChips && flagChips.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {flagChips.map((chip, i) => (
              <span
                key={i}
                className="inline-flex items-center rounded-md bg-amber-100 px-2 py-0.5 text-xs text-amber-900"
                title={chip.category}
              >
                {chip.text}
              </span>
            ))}
          </div>
        )}
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
    </motion.article>
  );
}
