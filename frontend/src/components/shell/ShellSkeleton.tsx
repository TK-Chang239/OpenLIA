import type { JSX } from "react";

export function ShellSkeleton(): JSX.Element {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="grid h-screen w-full bg-bg-base"
      style={{ gridTemplateColumns: "auto 1fr" }}
    >
      <div className="hidden md:flex w-[220px] flex-col bg-sidebar-bg">
        <div className="h-12 m-3 rounded-md bg-bg-elevated animate-pulse" />
        <div className="px-3 space-y-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-7 rounded-md bg-bg-elevated animate-pulse"
            />
          ))}
        </div>
      </div>
      <section
        className="grid overflow-hidden"
        style={{ gridTemplateRows: "auto 1fr" }}
      >
        <div className="h-12 border-b border-border-subtle bg-bg-base flex items-center px-7">
          <div className="h-4 w-40 rounded bg-bg-elevated animate-pulse" />
        </div>
        <div className="p-6">
          <div className="h-32 rounded-md bg-bg-elevated animate-pulse" />
        </div>
      </section>
      <span className="sr-only">Loading...</span>
    </div>
  );
}
