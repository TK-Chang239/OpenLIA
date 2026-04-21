import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

export function Button({
  variant = "primary",
  className,
  type = "button",
  ...rest
}: ButtonProps): JSX.Element {
  const base =
    "inline-flex items-center justify-center h-9 px-3 rounded-md text-sm font-medium transition-colors duration-[120ms] disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClass =
    variant === "primary"
      ? "bg-accent-primary text-white hover:opacity-90"
      : "bg-surface-hover text-text-primary hover:bg-surface-active";
  return (
    <button
      type={type}
      className={[base, variantClass, className ?? ""].join(" ")}
      {...rest}
    />
  );
}
