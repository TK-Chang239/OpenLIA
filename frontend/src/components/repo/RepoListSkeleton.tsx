const WIDTHS = ["40%", "55%", "35%", "50%", "40%", "55%", "35%", "50%"] as const;

export function RepoListSkeleton(): JSX.Element {
  return (
    <ul data-testid="repo-skeleton" className="divide-y divide-[--color-border-subtle]">
      {WIDTHS.map((w, i) => (
        <li key={i} className="flex items-center gap-4 px-4 py-3.5">
          <div className="w-5 h-5 rounded bg-[--color-surface-hover] animate-pulse flex-shrink-0" />
          <div className="flex flex-col flex-1">
            <div
              className="h-4 rounded bg-[--color-surface-hover] animate-pulse"
              style={{ width: w }}
            />
            <div className="h-3 rounded bg-[--color-surface-hover] animate-pulse w-48 mt-1.5" />
          </div>
        </li>
      ))}
    </ul>
  );
}
