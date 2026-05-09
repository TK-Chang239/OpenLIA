import { useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Plus } from "lucide-react";

interface Props {
  onAdd: (ticker: string) => Promise<void>;
}

interface ErrorWithStatus {
  status?: number;
}

export function AddTickerPopover({ onAdd }: Props) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setErr(null);
    const ticker = value.trim().toUpperCase();
    if (!ticker) return;
    setSubmitting(true);
    try {
      await onAdd(ticker);
      setValue("");
      setOpen(false);
    } catch (e) {
      const status = (e as ErrorWithStatus).status;
      if (status === 409) setErr(`Already watching ${ticker}`);
      else if (status === 404) setErr(`Ticker ${ticker} not found`);
      else setErr("Failed to add ticker");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors duration-[--duration-normal] text-[12.5px]"
          aria-label="Add ticker"
        >
          <Plus size={13} /> Add Ticker
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={6}
          className="z-[60] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] p-3 w-[280px] shadow-md"
        >
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleSubmit();
            }}
            placeholder="Ticker symbol or company name"
            className="w-full bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-md px-3 h-9 text-[13.5px] text-[--color-text-primary] outline-none focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(var(--color-accent-primary-rgb),0.10)] transition-colors"
          />
          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
          ) : null}
          <div className="flex justify-end mt-3">
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={submitting}
              className="inline-flex items-center h-8 px-3.5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {submitting ? "Adding..." : "Add"}
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
