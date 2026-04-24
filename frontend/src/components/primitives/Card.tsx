import type { HTMLAttributes, JSX, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLElement> {
  children: ReactNode;
}

export function Card({ children, className, ...rest }: CardProps): JSX.Element {
  return (
    <section
      role="region"
      className={[
        "group relative block rounded-lg border border-border-subtle bg-bg-elevated p-5 overflow-hidden",
        "transition-all duration-normal ease-out",
        "hover:-translate-y-1 hover:border-yellow-600",
        className ?? "",
      ].join(" ")}
      {...rest}
    >
      {children}
      <span
        aria-hidden="true"
        className="absolute bottom-0 left-0 h-[2px] w-0 bg-accent-primary transition-[width] duration-slow ease-out group-hover:w-full"
      />
    </section>
  );
}
