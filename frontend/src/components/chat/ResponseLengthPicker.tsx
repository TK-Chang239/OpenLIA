import { useEffect, useState } from "react";
import type { JSX } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Ruler } from "lucide-react";

import { patchSession, type ResponseLength } from "../../api/chat";

const OPTIONS: ReadonlyArray<{
  value: ResponseLength;
  label: string;
  hint: string;
}> = [
  { value: "concise", label: "Concise", hint: "1–3 sentences" },
  { value: "normal", label: "Normal", hint: "Default discipline" },
  { value: "detailed", label: "Detailed", hint: "Headings, full reasoning" },
];

const LABEL: Record<ResponseLength, string> = {
  concise: "Concise",
  normal: "Normal",
  detailed: "Detailed",
};

interface Props {
  sessionId: string;
  /** Initial value from the session row. ``null`` is shown as "Normal". */
  initialValue?: ResponseLength | null;
}

/** Per-session response-length picker for the Secretary composer. Persists
 *  to ``chat_sessions.response_length`` via PATCH; "Normal" is stored as
 *  NULL on the backend so the runtime omits the system-prompt directive. */
export function ResponseLengthPicker({
  sessionId,
  initialValue,
}: Props): JSX.Element {
  const [value, setValue] = useState<ResponseLength>(initialValue ?? "normal");
  const [busy, setBusy] = useState(false);

  // Sync from the parent when the session changes (e.g. user switches chats)
  // or when the initial GET resolves after mount with a non-default choice.
  useEffect(() => {
    setValue(initialValue ?? "normal");
  }, [sessionId, initialValue]);

  const handleSelect = async (next: ResponseLength) => {
    if (next === value) return;
    setBusy(true);
    setValue(next);
    try {
      await patchSession(sessionId, { response_length: next });
    } catch {
      // swallow — the next send still uses the optimistic local choice for
      // this turn; the user can retry.
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Choose response length"
          disabled={busy}
          className="inline-flex items-center gap-[6px] rounded-sm border px-2 py-[4px] font-mono text-[10px] uppercase transition-colors duration-normal ease-out disabled:opacity-60 hover:border-border-strong hover:text-text-primary"
          style={{
            letterSpacing: "0.06em",
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-base)",
            color: "var(--color-text-secondary)",
          }}
        >
          <Ruler size={10} strokeWidth={1.5} aria-hidden />
          <span className="truncate max-w-[100px]">{LABEL[value]}</span>
          <ChevronDown size={10} strokeWidth={1.5} aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          className="z-50 min-w-[220px] overflow-hidden rounded-md border p-1"
          style={{
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-elevated)",
            boxShadow: "var(--shadow-md)",
          }}
        >
          <DropdownMenu.Label
            className="px-2 pt-1 pb-[2px] font-mono text-[9px] uppercase"
            style={{
              letterSpacing: "var(--tracking-micro)",
              color: "var(--color-text-tertiary)",
            }}
          >
            Response length
          </DropdownMenu.Label>
          {OPTIONS.map((opt) => {
            const active = opt.value === value;
            return (
              <DropdownMenu.Item
                key={opt.value}
                onSelect={() => {
                  void handleSelect(opt.value);
                }}
                className="flex cursor-pointer items-center justify-between rounded-sm px-2 py-[6px] text-[12px] outline-none data-[highlighted]:bg-surface-hover"
                style={{
                  color: active
                    ? "var(--color-text-primary)"
                    : "var(--color-text-secondary)",
                }}
              >
                <span className="flex flex-col">
                  <span>{opt.label}</span>
                  <span
                    className="text-[10px]"
                    style={{ color: "var(--color-text-tertiary)" }}
                  >
                    {opt.hint}
                  </span>
                </span>
                {active ? (
                  <span
                    aria-hidden="true"
                    className="ml-2 inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: "var(--color-accent-primary)" }}
                  />
                ) : null}
              </DropdownMenu.Item>
            );
          })}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
