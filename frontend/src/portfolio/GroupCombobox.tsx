import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { ChevronDown, X } from "lucide-react";

export interface GroupComboboxProps {
  readonly value: string | null;
  readonly groups: string[];
  readonly onChange: (next: string | null) => void;
  readonly onCreateGroup?: (name: string) => Promise<void> | void;
  readonly placeholder?: string;
  readonly disabled?: boolean;
}

/** Single-select group picker.
 *  - Typing filters existing groups.
 *  - Enter on a highlighted option selects it.
 *  - Enter on a novel string creates a new group and selects it.
 *  - ✕ clears selection (sets null). */
export function GroupCombobox({
  value,
  groups,
  onChange,
  onCreateGroup,
  placeholder = "No group",
  disabled = false,
}: GroupComboboxProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const q = query.trim();
  const matches = q
    ? groups.filter((g) => g.toLowerCase().includes(q.toLowerCase()))
    : groups;
  const exact = matches.find((g) => g.toLowerCase() === q.toLowerCase());
  const showCreate = q.length > 0 && !exact && Boolean(onCreateGroup);

  const optionsCount = matches.length + (showCreate ? 1 : 0);
  const safeHighlight = Math.min(highlight, Math.max(0, optionsCount - 1));

  const select = (name: string) => {
    onChange(name);
    setQuery("");
    setOpen(false);
  };

  const handleCreate = async () => {
    if (!onCreateGroup) return;
    const name = q;
    await onCreateGroup(name);
    select(name);
  };

  const onKeyDown = async (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setOpen(true);
      setHighlight((h) => Math.min(optionsCount - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (safeHighlight < matches.length) {
        const pick = matches[safeHighlight];
        if (pick) select(pick);
      } else if (showCreate) {
        await handleCreate();
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setQuery("");
    }
  };

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        disabled={disabled}
        onClick={() => {
          if (disabled) return;
          setOpen((v) => !v);
          setTimeout(() => inputRef.current?.focus(), 0);
        }}
        className="flex w-full items-center justify-between gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-left text-sm text-[--color-text-primary] transition-colors hover:border-[--color-border-strong] disabled:opacity-60"
        aria-haspopup="listbox"
        aria-expanded={open}
        data-testid="group-combobox-toggle"
      >
        <span className={value ? "" : "text-[--color-text-tertiary]"}>
          {value ?? placeholder}
        </span>
        <span className="flex items-center gap-1">
          {value !== null && !disabled ? (
            <span
              role="button"
              tabIndex={0}
              aria-label="Clear group"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  e.stopPropagation();
                  onChange(null);
                }
              }}
              className="rounded p-0.5 text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              <X size={12} aria-hidden="true" />
            </span>
          ) : null}
          <ChevronDown size={14} aria-hidden="true" className="text-[--color-text-tertiary]" />
        </span>
      </button>

      {open ? (
        <div
          role="listbox"
          className="absolute z-20 mt-1 max-h-64 w-full overflow-auto rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg"
        >
          <div className="border-b border-[--color-border-subtle] p-2">
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setHighlight(0);
              }}
              onKeyDown={onKeyDown}
              placeholder="Search or type new group…"
              className="w-full rounded border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-1.5 text-sm text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
              data-testid="group-combobox-input"
            />
          </div>
          <ul className="py-1">
            {matches.length === 0 && !showCreate ? (
              <li className="px-3 py-2 text-sm text-[--color-text-tertiary]">
                No groups yet
              </li>
            ) : null}
            {matches.map((g, i) => (
              <li
                key={g}
                role="option"
                aria-selected={value === g}
                onMouseEnter={() => setHighlight(i)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(g);
                }}
                className={`flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm ${
                  i === safeHighlight
                    ? "bg-[--color-surface-hover] text-[--color-text-primary]"
                    : "text-[--color-text-secondary]"
                }`}
                data-testid={`group-option-${g}`}
              >
                <span>{g}</span>
                {value === g ? (
                  <span className="font-mono text-[10px] text-[--color-accent-primary]">
                    SELECTED
                  </span>
                ) : null}
              </li>
            ))}
            {showCreate ? (
              <li
                role="option"
                aria-selected={false}
                onMouseEnter={() => setHighlight(matches.length)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  void handleCreate();
                }}
                className={`flex cursor-pointer items-center justify-between px-3 py-1.5 text-sm ${
                  matches.length === safeHighlight
                    ? "bg-[--color-surface-hover]"
                    : ""
                }`}
                data-testid="group-create-option"
              >
                <span className="text-[--color-text-primary]">
                  Create <strong>{q}</strong>
                </span>
                <span className="font-mono text-[10px] text-[--color-accent-primary]">
                  NEW
                </span>
              </li>
            ) : null}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
