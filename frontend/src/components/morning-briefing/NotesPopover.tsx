import * as Popover from "@radix-ui/react-popover";
import { type ReactNode, useState } from "react";

interface Props {
  topic: string;
  notes: string;
  onSave: (notes: string) => void;
  children: ReactNode;
}

export function NotesPopover({ topic, notes, onSave, children }: Props) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(notes);

  const onOpenChange = (next: boolean) => {
    if (next) setDraft(notes);
    setOpen(next);
  };

  const done = () => {
    onSave(draft);
    setOpen(false);
  };

  return (
    <Popover.Root open={open} onOpenChange={onOpenChange}>
      <Popover.Trigger asChild>{children}</Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="start"
          sideOffset={6}
          className="rounded-[var(--radius-lg,0.5rem)] border p-3 shadow-md w-64 z-50"
          style={{
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-base)",
          }}
          data-testid={`notes-popover-${topic}`}
        >
          <label className="block text-xs mb-1 font-medium">
            Notes for {topic}
          </label>
          <textarea
            data-testid={`notes-popover-textarea-${topic}`}
            className="w-full text-xs rounded border p-1"
            style={{ borderColor: "var(--color-border-subtle)" }}
            rows={4}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex justify-end mt-2">
            <button
              type="button"
              onClick={done}
              className="px-3 py-1 rounded text-xs"
              style={{
                background: "var(--color-accent-primary)",
                color: "var(--color-accent-on)",
              }}
              data-testid={`notes-popover-done-${topic}`}
            >
              Done
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
