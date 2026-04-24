import type { ReactNode } from "react";

export function AuthCard({ children }: { children: ReactNode }) {
  return (
    <section className="bg-bg-elevated border border-border-subtle rounded-2xl w-full max-w-[420px] px-8 py-10 md:rounded-2xl max-md:border-0 max-md:rounded-none max-md:px-6 max-md:py-8">
      {children}
    </section>
  );
}
