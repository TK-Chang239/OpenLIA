import { useState } from "react";

interface Props {
  tickers: string[];
  selected: string | null; // null = "All"
  onSelect: (ticker: string | null) => void;
  onAdd: (ticker: string) => void;
  onRemove: (ticker: string) => void;
  onImportFromPortfolio?: () => void;
}

export function TickerSelector({
  tickers,
  selected,
  onSelect,
  onAdd,
  onRemove,
  onImportFromPortfolio,
}: Props) {
  const [draft, setDraft] = useState("");
  const tooMany = tickers.length >= 21;

  const handleAdd = () => {
    const next = draft.trim().toUpperCase();
    if (next) {
      onAdd(next);
      setDraft("");
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => onSelect(null)}
          className={[
            "rounded-full border px-3 py-1 text-xs",
            selected === null
              ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
              : "border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-primary]",
          ].join(" ")}
        >
          All
        </button>
        {tickers.map((t) => (
          <span
            key={t}
            className="group inline-flex items-center"
          >
            <button
              type="button"
              onClick={() => onSelect(t)}
              data-testid={`ticker-pill-${t}`}
              className={[
                "rounded-l-full border px-3 py-1 text-xs",
                selected === t
                  ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                  : "border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-primary]",
              ].join(" ")}
            >
              {t}
            </button>
            <button
              type="button"
              aria-label={`Remove ${t}`}
              onClick={() => onRemove(t)}
              className="rounded-r-full border border-l-0 border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 text-xs text-[--color-text-secondary] opacity-0 group-hover:opacity-100 focus:opacity-100"
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              handleAdd();
            }
          }}
          placeholder="Add ticker"
          className="w-32 rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1 text-xs"
        />
        <button
          type="button"
          onClick={handleAdd}
          className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-elevated] px-2 py-1 text-xs"
        >
          + Add
        </button>
        {onImportFromPortfolio ? (
          <button
            type="button"
            onClick={onImportFromPortfolio}
            className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-elevated] px-2 py-1 text-xs"
          >
            Import from Portfolio
          </button>
        ) : null}
      </div>
      {tooMany ? (
        <div
          data-testid="ticker-warning"
          className="rounded-md border border-[--color-feedback-warning] bg-[--color-feedback-warning-bg] px-2 py-1 text-xs text-[--color-feedback-warning]"
        >
          Tracking {tickers.length} tickers — performance may degrade above 20.
        </div>
      ) : null}
    </div>
  );
}
