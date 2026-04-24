import type { JSX } from "react";

interface Props {
  content: string;
  timestamp?: string;
}

export function UserBubble({ content, timestamp }: Props): JSX.Element {
  return (
    <article role="article" aria-label="User message" className="flex flex-col items-end">
      <div
        className="max-w-[520px] whitespace-pre-wrap rounded-[10px] px-[15px] py-[11px] text-[14px] leading-[1.5] font-display"
        style={{
          background: "var(--color-user-bubble-bg)",
          color: "var(--color-user-bubble-text)",
        }}
      >
        {content}
      </div>
      {timestamp ? (
        <time className="mt-1 font-mono text-[10px] text-text-tertiary">{timestamp}</time>
      ) : null}
    </article>
  );
}
