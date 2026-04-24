import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main
      aria-label="Authentication"
      className="min-h-screen bg-bg-base flex flex-col items-center justify-center p-4"
    >
      <div className="mb-6 flex items-center gap-[10px]">
        <span
          className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold text-[10px]"
          style={{
            background: "var(--color-accent-primary)",
            color: "var(--color-accent-on)",
            boxShadow: "var(--shadow-accent)",
          }}
        >
          LIA
        </span>
        <span className="font-display text-[15px] font-semibold text-text-primary">
          OpenLia
        </span>
      </div>
      {children}
    </main>
  );
}
