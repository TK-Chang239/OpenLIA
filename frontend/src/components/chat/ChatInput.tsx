import { useId, useLayoutEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { ArrowUp, Square } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder: string;
}

const MAX_HEIGHT = 120;
const HELPER_COPY = "Enter to send · Shift+Enter for new line";

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  placeholder,
}: Props): JSX.Element {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);
  const helperId = useId();

  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="flex-shrink-0 px-6 py-4 bg-bg-base">
      <div className="mx-auto max-w-[720px]">
        <div className="rounded-[10px] border border-border-subtle bg-bg-elevated p-1 transition-all duration-normal ease-out focus-within:border-yellow-600 focus-within:shadow-input-focus">
          <textarea
            ref={taRef}
            id={`${helperId}-textarea`}
            aria-label="Chat message"
            aria-describedby={helperId}
            placeholder={placeholder}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full min-h-[46px] resize-none border-0 bg-transparent px-3 pt-3 pb-[6px] font-display text-[14px] leading-[1.5] text-text-primary outline-none placeholder:text-text-tertiary"
            style={{ maxHeight: MAX_HEIGHT, overflowY: "auto" }}
          />
          <div className="flex items-center gap-2 px-2 py-[6px] pl-[10px]">
            <div className="flex-1" />
            {isStreaming ? (
              <button
                type="button"
                aria-label="Stop generating"
                onClick={onStop}
                className="inline-flex items-center justify-center rounded-md p-[9px] text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover"
              >
                <Square size={14} strokeWidth={2} />
              </button>
            ) : (
              <button
                type="button"
                aria-label="Send"
                onClick={submit}
                disabled={value.trim().length === 0}
                className="inline-flex items-center justify-center rounded-md p-[9px] transition-colors duration-normal ease-out hover:bg-accent-hover active:scale-[0.96] disabled:cursor-not-allowed disabled:opacity-40"
                style={{
                  background: "var(--color-accent-primary)",
                  color: "var(--color-accent-on)",
                }}
              >
                <ArrowUp size={15} strokeWidth={2} />
              </button>
            )}
          </div>
        </div>
        <p
          id={helperId}
          className="mt-2 text-xs text-[--color-text-tertiary] text-center select-none"
        >
          {HELPER_COPY}
        </p>
      </div>
    </div>
  );
}
