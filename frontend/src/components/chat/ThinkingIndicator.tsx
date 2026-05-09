import { LiaBadge } from "./LiaBadge";

export function ThinkingIndicator(): JSX.Element {
  return (
    <div className="flex items-center gap-3" role="status" aria-live="polite">
      <LiaBadge />
      <div className="flex items-center gap-1.5 rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3.5 py-2.5 shadow-sm">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            data-i={i}
            aria-hidden="true"
            className="ol-dot inline-block h-1.5 w-1.5 rounded-full bg-[--color-accent-primary]"
          />
        ))}
      </div>
      <span className="sr-only">LIA is thinking...</span>
    </div>
  );
}
