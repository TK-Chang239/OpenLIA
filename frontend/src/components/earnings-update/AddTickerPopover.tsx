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
          className="flex items-center gap-1 border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-7 hover:border-[--color-border-primary]"
          aria-label="Add ticker"
        >
          <Plus size={14} /> Add Ticker
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={4}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] p-3 w-[280px] shadow-md"
        >
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleSubmit();
            }}
            placeholder="Ticker symbol or company name"
            className="w-full bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm text-[--color-text-primary]"
          />
          {err ? (
            <p className="text-xs text-[--color-feedback-error] mt-2">{err}</p>
          ) : null}
          <div className="flex justify-end mt-3">
            <button
              type="button"
              onClick={() => void handleSubmit()}
              disabled={submitting}
              className="text-sm bg-[--color-accent-primary] text-white h-7 px-3 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              Add
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
