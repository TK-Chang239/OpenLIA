import * as Popover from "@radix-ui/react-popover";
import { ArrowUpRight } from "lucide-react";
import { useEffect, useState } from "react";

import { fetchHoldings, type PortfolioHolding } from "../../api/portfolio";

interface Props {
  onSelect: (ticker: string) => void;
}

export function FromPortfolioPicker({ onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [holdings, setHoldings] = useState<PortfolioHolding[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || holdings !== null || error) return;
    fetchHoldings()
      .then(setHoldings)
      .catch(() => setError("Portfolio unavailable"));
  }, [open, holdings, error]);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1 px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          From Portfolio
          <ArrowUpRight size={12} />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="w-[240px] max-h-[300px] overflow-y-auto rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg p-1">
          {error && (
            <div className="p-2 text-xs text-[--color-text-tertiary]">{error}</div>
          )}
          {!error && holdings === null && (
            <div className="p-2 text-xs text-[--color-text-tertiary]">Loading...</div>
          )}
          {holdings && holdings.length === 0 && (
            <div className="p-2 text-xs text-[--color-text-tertiary]">No holdings yet</div>
          )}
          {holdings?.map((h) => (
            <button
              key={h.ticker}
              type="button"
              onClick={() => {
                onSelect(h.ticker);
                setOpen(false);
              }}
              className="w-full text-left px-2 py-1.5 text-sm rounded-[--radius-sm] hover:bg-[--color-surface-hover] flex justify-between"
            >
              <span className="font-medium">{h.ticker}</span>
              {h.name && (
                <span className="text-[--color-text-tertiary] truncate">{h.name}</span>
              )}
            </button>
          ))}
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
