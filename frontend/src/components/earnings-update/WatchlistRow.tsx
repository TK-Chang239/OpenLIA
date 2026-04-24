import { WatchlistEntry } from "../../api/earnings-update";

import { AddTickerPopover } from "./AddTickerPopover";
import { WatchlistCard } from "./WatchlistCard";

interface Props {
  entries: WatchlistEntry[];
  onAdd: (ticker: string) => Promise<void>;
  onRemove: (id: string) => Promise<void>;
}

export function WatchlistRow({ entries, onAdd, onRemove }: Props) {
  return (
    <section>
      <header className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Watchlist
        </h3>
        <AddTickerPopover onAdd={onAdd} />
      </header>
      {entries.length === 0 ? (
        <div className="mx-6 mb-4 border border-dashed border-[--color-border-subtle] rounded-[--radius-lg] h-[120px] flex items-center justify-center text-sm text-[--color-text-tertiary]">
          Add companies to your watchlist to track upcoming earnings
        </div>
      ) : (
        <div
          className="flex gap-3 overflow-x-auto px-6 pb-4"
          style={{ scrollSnapType: "x mandatory" }}
        >
          {entries.map((e) => (
            <WatchlistCard
              key={e.id}
              entry={e}
              onRemove={(id) => void onRemove(id)}
            />
          ))}
        </div>
      )}
    </section>
  );
}
