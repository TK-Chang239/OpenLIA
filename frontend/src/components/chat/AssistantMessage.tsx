import type { JSX } from "react";
import { LiaBadge } from "./LiaBadge";

interface Props {
  content: string;
  streaming: boolean;
  timestamp?: string;
  stopped?: boolean;
}

export function AssistantMessage({
  content,
  streaming,
  timestamp,
  stopped,
}: Props): JSX.Element {
  return (
    <article aria-label="Assistant message" className="flex items-start gap-3">
      <LiaBadge />
      <div className="flex flex-col min-w-0 max-w-[600px]">
        <div className="rounded-[10px] border border-border-subtle bg-bg-elevated px-4 py-[14px] text-[14.5px] leading-[1.65] font-display text-text-primary whitespace-pre-wrap">
          {content}
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
