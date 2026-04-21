import type { ReactNode } from "react";

export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <section className="bg-bg-elevated border border-border-subtle rounded-xl shadow-lg w-full max-w-[420px] px-8 py-10 md:border md:shadow-lg md:rounded-xl max-md:border-0 max-md:shadow-none max-md:rounded-none max-md:px-6 max-md:py-8">
      {children}
    </section>
  );
}
