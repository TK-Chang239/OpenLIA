import type { HTMLAttributes, JSX, ReactNode } from "react";

export type BadgeVariant = "neutral" | "accent" | "success" | "error" | "warning";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  variant?: BadgeVariant;
}

const variantStyle: Record<BadgeVariant, { background: string; color: string; borderColor: string }> = {
  neutral: {
    background: "var(--color-bg-elevated)",
    color: "var(--color-text-secondary)",
    borderColor: "var(--color-border-subtle)",
  },
  accent: {
    background: "var(--color-accent-subtle)",
    color: "var(--color-feedback-success)",
    borderColor: "var(--yellow-600)",
  },
  success: {
    background: "rgba(107, 130, 0, 0.1)",
    color: "var(--color-feedback-success)",
    borderColor: "var(--yellow-600)",
  },
  error: {
    background: "rgba(224, 92, 48, 0.1)",
    color: "var(--color-feedback-error)",
    borderColor: "var(--color-border-error)",
  },
  warning: {
    background: "rgba(220, 150, 20, 0.1)",
    color: "var(--color-feedback-warning)",
    borderColor: "var(--color-feedback-warning)",
  },
};

export function Badge({
  children,
  variant = "neutral",
  className,
  ...rest
}: BadgeProps): JSX.Element {
  const s = variantStyle[variant];
  return (
    <span
      className={[
        "inline-flex items-center gap-[6px] px-[10px] py-[3px] rounded-full font-mono text-[9px] uppercase border",
        className ?? "",
      ].join(" ")}
      style={{
        letterSpacing: "var(--tracking-micro)",
        background: s.background,
        color: s.color,
        borderColor: s.borderColor,
      }}
      {...rest}
    >
      {children}
    </span>
  );
}
