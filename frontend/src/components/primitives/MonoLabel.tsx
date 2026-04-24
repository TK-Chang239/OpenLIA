import type { HTMLAttributes, JSX, ReactNode } from "react";

interface MonoLabelProps extends HTMLAttributes<HTMLSpanElement> {
  children: ReactNode;
  size?: "sm" | "md";
}

export function MonoLabel({
  children,
  size = "md",
  className,
  ...rest
}: MonoLabelProps): JSX.Element {
  return (
    <span
      className={[size === "sm" ? "ol-label-sm" : "ol-label", className ?? ""].join(" ")}
      {...rest}
    >
      {children}
    </span>
  );
}
