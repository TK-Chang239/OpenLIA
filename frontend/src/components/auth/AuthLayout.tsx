import type { ReactNode } from "react";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <main
      aria-label="Authentication"
      className="min-h-screen bg-bg-base flex flex-col items-center justify-center p-4"
    >
      <div className="mb-6 flex flex-col items-center">
        <span className="text-2xl font-semibold text-text-primary">LIA</span>
        <span className="text-sm text-text-secondary mt-1">
          Your financial assistant
        </span>
      </div>
      {children}
    </main>
  );
}
