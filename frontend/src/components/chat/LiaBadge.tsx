import type { JSX } from "react";

export function LiaBadge(): JSX.Element {
  return (
    <span
      aria-label="LIA"
      className="inline-flex shrink-0 items-center justify-center w-7 h-7 rounded-md font-display font-bold text-[10px]"
      style={{
        background: "var(--color-accent-primary)",
        color: "var(--color-accent-on)",
        boxShadow: "var(--shadow-accent)",
      }}
    >
      LIA
    </span>
  );
}
