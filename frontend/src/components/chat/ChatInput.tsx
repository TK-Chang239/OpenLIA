import { useLayoutEffect, useRef, useState } from "react";
import { ArrowUp, Square } from "lucide-react";

interface Props {
  onSend: (text: string) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder: string;
}

const MAX_HEIGHT = 120;

export function ChatInput({ onSend, onStop, isStreaming, placeholder }: Props): JSX.Element {
  const [value, setValue] = useState("");
  const taRef = useRef<HTMLTextAreaElement>(null);

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
    <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 py-4">
      <div className="mx-auto max-w-[720px]">
        <div className="flex items-end gap-2 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3">
          <textarea
            ref={taRef}
            aria-label="Chat message"
            placeholder={placeholder}
            rows={1}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            className="flex-1 resize-none bg-transparent text-md leading-relaxed text-[--color-text-primary] outline-none placeholder:text-[--color-text-tertiary]"
            style={{ maxHeight: MAX_HEIGHT, overflowY: "auto" }}
          />
          {isStreaming ? (
            <button
              type="button"
              aria-label="Stop generating"
              onClick={onStop}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-surface-active] text-[--color-text-secondary]"
            >
              <Square size={14} />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Send"
              onClick={submit}
              disabled={value.trim().length === 0}
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-accent-primary] text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowUp size={14} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
