import type { JSX } from "react";

export function LivePill({ label = "LIVE_FEED_ACTIVE" }: { label?: string }): JSX.Element {
  return (
    <span
      className="inline-flex items-center gap-2 px-[10px] py-1 rounded-full font-mono text-[10px] uppercase"
      style={{
        letterSpacing: "var(--tracking-label)",
        border: "1px solid var(--yellow-600)",
        background: "var(--color-accent-subtle)",
        color: "var(--color-feedback-success)",
      }}
    >
      <span
        aria-hidden="true"
        className="w-[7px] h-[7px] rounded-full"
        style={{
          background: "var(--yellow-600)",
          animation: "ol-pulse 1.8s var(--ease-in-out) infinite",
        }}
      />
      {label}
    </span>
  );
}
