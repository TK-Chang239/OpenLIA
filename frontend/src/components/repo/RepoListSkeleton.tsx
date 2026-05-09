import type { JSX } from "react";

const WIDTHS = ["40%", "55%", "35%", "50%", "40%", "55%", "35%", "50%"] as const;

export function RepoListSkeleton(): JSX.Element {
  return (
    <ul data-testid="repo-skeleton" className="divide-y divide-[--color-border-subtle]">
      {WIDTHS.map((w, i) => (
        <li key={i} className="flex items-center gap-[14px] px-4 py-[14px]">
          <div className="h-9 w-9 flex-shrink-0 animate-pulse rounded-md border border-[--color-border-subtle] bg-[--color-surface-hover]" />
          <div className="flex flex-1 flex-col gap-[6px]">
            <div
              className="h-[14px] animate-pulse rounded bg-[--color-surface-hover]"
              style={{ width: w }}
            />
            <div className="h-[10px] w-56 animate-pulse rounded bg-[--color-surface-hover]" />
          </div>
        </li>
      ))}
    </ul>
  );
}
