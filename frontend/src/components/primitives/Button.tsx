import type { ButtonHTMLAttributes, JSX } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const base =
  "relative inline-flex items-center justify-center gap-2 rounded-md px-4 py-[9px] font-display text-[13px] font-medium uppercase transition-all duration-normal ease-out active:scale-[0.96] overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed";

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
  ...rest
}: ButtonProps): JSX.Element {
  return (
    <button
      type={type}
      className={[base, variants[variant], className ?? ""].join(" ")}
      style={{ letterSpacing: "0.07em" }}
      {...rest}
    />
  );
}
