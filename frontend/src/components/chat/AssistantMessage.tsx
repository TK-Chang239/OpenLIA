import { LiaBadge } from "./LiaBadge";

interface Props {
  content: string;
  streaming: boolean;
  timestamp?: string;
  stopped?: boolean;
}

export function AssistantMessage({ content, streaming, timestamp, stopped }: Props): JSX.Element {
  return (
    <article
      aria-label="Assistant message"
      className="flex items-start gap-3"
    >
      <LiaBadge />
      <div className="min-w-0 flex-1">
        <div
          className="whitespace-pre-wrap text-md leading-[1.75] text-[--color-text-primary]"
        >
          {content}
          {streaming ? (
            <span
              data-testid="streaming-cursor"
              className="ml-0.5 inline-block text-[--color-accent-primary]/50"
            >
              &#9612;
            </span>
          ) : null}
        </div>
        {stopped ? (
          <span className="mt-1.5 block text-xs italic text-[--color-text-tertiary]">
            Response stopped.
          </span>
        ) : null}
        {timestamp ? (
          <time className="mt-1 block text-xs text-[--color-text-tertiary]">{timestamp}</time>
        ) : null}
      </div>
    </article>
  );
}
