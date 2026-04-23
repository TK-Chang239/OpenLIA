interface Props {
  content: string;
  timestamp?: string;
}

export function UserBubble({ content, timestamp }: Props): JSX.Element {
  return (
    <article role="article" aria-label="User message" className="flex flex-col items-end">
      <div className="max-w-[72%] whitespace-pre-wrap rounded-2xl rounded-br-sm border border-[--color-border-secondary] bg-[--color-accent-primary]/10 px-4 py-3 text-md leading-relaxed text-[--color-text-primary]">
        {content}
      </div>
      {timestamp ? (
        <time className="mt-1 text-xs text-[--color-text-tertiary]">{timestamp}</time>
      ) : null}
    </article>
  );
}
