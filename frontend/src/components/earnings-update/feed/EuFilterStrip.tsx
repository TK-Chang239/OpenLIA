import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Plus, Search } from "lucide-react";

import type { FeedFilter } from "./feedHelpers";

interface Props {
  filter: FeedFilter;
  onFilterChange: (next: FeedFilter) => void;
  search: string;
  onSearchChange: (next: string) => void;
  onAdHoc: () => void;
}

const FILTERS: { id: FeedFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "watchlist", label: "Watchlist" },
  { id: "portfolio", label: "Portfolio" },
  { id: "beats", label: "Beats" },
  { id: "misses", label: "Misses" },
];

export function EuFilterStrip({
  filter,
  onFilterChange,
  search,
  onSearchChange,
  onAdHoc,
}: Props) {
  const segRef = useRef<HTMLDivElement | null>(null);
  const btnRefs = useRef<Map<FeedFilter, HTMLButtonElement>>(new Map());
  const [pillStyle, setPillStyle] = useState<{
    left: number;
    width: number;
  } | null>(null);

  useLayoutEffect(() => {
    const btn = btnRefs.current.get(filter);
    if (!btn) return;
    setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
  }, [filter]);

  useEffect(() => {
    function onResize() {
      const btn = btnRefs.current.get(filter);
      if (!btn) return;
      setPillStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
    }
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, [filter]);

  return (
    <div className="flex gap-2 items-center flex-wrap mb-[22px]">
      <div
        ref={segRef}
        role="tablist"
        aria-label="Earnings filter"
        className="inline-flex p-[3px] border border-[--color-border-subtle] rounded-lg bg-[--color-bg-elevated] relative"
      >
        {pillStyle ? (
          <span
            aria-hidden
            className="absolute top-[3px] bottom-[3px] bg-[--color-text-primary] rounded-[5px] z-[1] pointer-events-none transition-[left,width] duration-[320ms] ease-[cubic-bezier(0.32,0.72,0,1)]"
            style={{ left: pillStyle.left, width: pillStyle.width }}
          />
        ) : null}
        {FILTERS.map((f) => {
          const isOn = f.id === filter;
          return (
            <button
              key={f.id}
              ref={(el) => {
                if (el) btnRefs.current.set(f.id, el);
              }}
              type="button"
              role="tab"
              aria-selected={isOn}
              data-filter={f.id}
              onClick={() => onFilterChange(f.id)}
              className={`relative z-[2] bg-transparent border-0 px-3 py-1.5 text-[12.5px] cursor-pointer rounded-[5px] transition-colors duration-[220ms] ${
                isOn
                  ? "text-[--color-bg-base]"
                  : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
              }`}
            >
              {f.label}
            </button>
          );
        })}
      </div>
      <div className="flex-1" />
      <div className="inline-flex items-center gap-2 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] min-w-[220px]">
        <Search size={13} className="text-[--color-text-tertiary]" />
        <input
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Filter by ticker, sector, or quote..."
          aria-label="Filter reports"
          className="border-0 bg-transparent outline-none text-[13px] text-[--color-text-primary] w-full placeholder:text-[--color-text-tertiary]"
        />
      </div>
      <button
        type="button"
        onClick={onAdHoc}
        className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-[--color-bg-elevated] text-[12.5px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-normal]"
        aria-label="Generate ad-hoc report"
      >
        <Plus size={13} /> Ad-hoc
      </button>
    </div>
  );
}
