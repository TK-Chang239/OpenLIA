import { useEffect, useId, useRef, useState } from "react";

import {
  createHolding,
  searchTickers,
  type SearchResult,
} from "../api/portfolio";

export interface SearchAndAddProps {
  readonly groups: readonly string[];
  readonly existingTickers: ReadonlySet<string>;
  readonly onAdded: (ticker: string) => void;
}

interface PendingPick {
  readonly ticker: string;
  readonly name: string | null;
}

export function SearchAndAdd({
  groups,
  existingTickers,
  onAdded,
}: SearchAndAddProps): JSX.Element {
  const inputId = useId();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [pending, setPending] = useState<PendingPick | null>(null);
  const [selectedGroups, setSelectedGroups] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const popoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 300ms debounced search.
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!q.trim()) {
      setResults([]);
      setOpen(false);
      return;
    }
    debounceRef.current = setTimeout(() => {
      void searchTickers(q)
        .then((rows) => {
          setResults(rows);
          setOpen(true);
          setActive(0);
        })
        .catch(() => {
          setResults([]);
        });
    }, 300);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q]);

  const visible = results.map((r) => ({
    ...r,
    already_added: r.already_added ?? existingTickers.has(r.ticker),
  }));

  const choose = async (row: SearchResult) => {
    if (row.already_added || existingTickers.has(row.ticker)) return;
    setPending({ ticker: row.ticker, name: row.name });
    setSelectedGroups([]);
    setOpen(false);
    setQ("");
    setResults([]);
  };

  const commit = async () => {
    if (!pending) return;
    try {
      await createHolding({
        ticker: pending.ticker,
        groups: selectedGroups.length ? selectedGroups : undefined,
      });
      onAdded(pending.ticker);
    } finally {
      setPending(null);
      setSelectedGroups([]);
    }
  };

  // Auto-dismiss the group-assignment popup after 4s — committing with the
  // currently-selected groups (default: All-only).
  useEffect(() => {
    if (!pending) return;
    if (popoverTimer.current) clearTimeout(popoverTimer.current);
    popoverTimer.current = setTimeout(() => {
      void commit();
    }, 4000);
    return () => {
      if (popoverTimer.current) clearTimeout(popoverTimer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, visible.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const row = visible[active];
      if (row) void choose(row);
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div className="relative w-full max-w-md" data-testid="search-and-add">
      <label htmlFor={inputId} className="sr-only">
        Search ticker
      </label>
      <input
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={`${inputId}-list`}
        aria-autocomplete="list"
        value={q}
        placeholder="Search ticker (e.g., AAPL)"
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={onKeyDown}
        className="w-full px-3 py-2 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
        data-testid="search-input"
      />
      {open && visible.length > 0 ? (
        <ul
          id={`${inputId}-list`}
          role="listbox"
          className="absolute z-10 mt-1 w-full bg-[--color-surface-elevated] border border-[--color-border-subtle] rounded-[--radius-sm] shadow text-sm"
          data-testid="search-results"
        >
          {visible.map((row, i) => (
            <li
              key={row.ticker}
              role="option"
              aria-selected={i === active}
              data-testid={`search-row-${row.ticker}`}
              data-already-added={row.already_added ? "true" : "false"}
              onMouseDown={(e) => {
                e.preventDefault();
                void choose(row);
              }}
              className={`px-3 py-2 flex items-center justify-between cursor-pointer ${
                i === active ? "bg-[--color-surface-hover]" : ""
              } ${row.already_added ? "opacity-60 cursor-not-allowed" : ""}`}
            >
              <span className="font-medium">{row.ticker}</span>
              <span className="text-xs text-[--color-text-tertiary] flex items-center gap-2">
                {row.name ?? ""}
                {row.exchange ? <span className="text-[10px]">{row.exchange}</span> : null}
                {row.already_added ? <span>· Already added</span> : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
      {pending ? (
        <div
          role="dialog"
          aria-label="Assign to groups"
          data-testid="group-assign-popup"
          className="absolute z-20 mt-1 w-full bg-[--color-surface-elevated] border border-[--color-border-subtle] rounded-[--radius-sm] shadow p-3 text-sm"
        >
          <div className="font-medium mb-2">
            Assign {pending.ticker} to groups
          </div>
          <ul className="space-y-1">
            <li>
              <label className="flex items-center gap-2 opacity-70">
                <input type="checkbox" checked disabled aria-label="All" />
                <span>All</span>
              </label>
            </li>
            {groups.map((g) => (
              <li key={g}>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={selectedGroups.includes(g)}
                    onChange={(e) => {
                      setSelectedGroups((prev) =>
                        e.target.checked
                          ? [...prev, g]
                          : prev.filter((x) => x !== g),
                      );
                    }}
                    data-testid={`group-checkbox-${g}`}
                  />
                  <span>{g}</span>
                </label>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex justify-end">
            <button
              type="button"
              className="text-xs px-2 py-1 border border-[--color-border-subtle] rounded-[--radius-sm]"
              onClick={() => void commit()}
              data-testid="group-assign-confirm"
            >
              Done
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
