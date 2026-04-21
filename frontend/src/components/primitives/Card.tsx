import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export function Card({ children, className, ...rest }: CardProps): JSX.Element {
  return (
    <section
      role="region"
      className={[
        "bg-bg-elevated border border-border-subtle rounded-md p-4",
        className ?? "",
      ].join(" ")}
      {...rest}
    >
      {children}
    </section>
  );
}
