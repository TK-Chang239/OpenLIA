import * as Popover from "@radix-ui/react-popover";
import { type ReactNode, useState } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  topic: string;
  notes: string;
  onSave: (notes: string) => void;
  children: ReactNode;
}

export function NotesPopover({ topic, notes, onSave, children }: Props) {
  const { t } = useTranslation();
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
          className="z-[60] flex flex-col gap-2.5 p-4 w-[296px] rounded-[--radius-lg] border bg-[--color-bg-elevated] shadow-md"
          style={{ borderColor: "var(--color-border-subtle)" }}
          data-testid={`notes-popover-${topic}`}
        >
          <span className="text-[15px] font-semibold text-[--color-text-primary]">
            {topic}
          </span>
          <textarea
            data-testid={`notes-popover-textarea-${topic}`}
            placeholder={t("morning_briefing.notes.placeholder")}
            className="w-full h-20 resize-none rounded-md border bg-[--color-bg-input] px-2.5 py-2 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary] placeholder:text-[--color-text-tertiary]"
            style={{ borderColor: "var(--color-border-subtle)" }}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={done}
              className="inline-flex items-center h-7 px-3 rounded-md text-[13px] font-medium bg-[--color-accent-primary] text-[--color-accent-on] hover:bg-[--color-accent-hover]"
              data-testid={`notes-popover-done-${topic}`}
            >
              {t("morning_briefing.notes.done")}
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
