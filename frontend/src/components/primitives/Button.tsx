import type { ButtonHTMLAttributes, JSX, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  children?: ReactNode;
}

const base =
  "group relative inline-flex items-center justify-center gap-2 rounded-md px-4 py-[9px] font-display text-[13px] font-medium uppercase transition-all duration-normal ease-out active:scale-[0.96] overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2 focus-visible:ring-offset-[--color-bg-base]";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-accent-primary text-accent-on hover:bg-accent-hover",
  secondary:
    "border border-border-secondary text-text-primary hover:border-border-strong",
  ghost:
    "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
};

export function Button({
  variant = "primary",
  className,
  type = "button",
  children,
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      className={[base, variants[variant], className ?? ""].join(" ")}
      style={{ letterSpacing: "0.07em" }}
      {...rest}
    >
      {variant === "primary" ? (
        <span
          aria-hidden="true"
          data-testid="button-fill-wipe"
          className="absolute inset-0 -translate-x-full bg-accent-hover transition-transform duration-normal ease-out group-hover:translate-x-0"
        />
      ) : null}
      <span className="relative z-10 inline-flex items-center justify-center gap-2">
        {children}
      </span>
    </button>
  );
}
