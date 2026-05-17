import { useId, useLayoutEffect, useRef, useState } from "react";
import type { JSX, ReactNode } from "react";
import { ArrowUp, Paperclip, Square } from "lucide-react";
import { PendingAttachmentChip } from "./PendingAttachmentChip";

interface Props {
  onSend: (text: string, attachments?: File[]) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder: string;
  /** Rendered in the toolbar row, left of the send button. */
  leftSlot?: ReactNode;
  /** Seeds the textarea on mount (or whenever the seed changes to a new
   *  non-empty value). Used by the Home → Secretary "?prompt=" prefill. */
  initialValue?: string;
}

const MAX_HEIGHT = 120;
const HELPER_COPY = "Enter to send · Shift+Enter for new line";

// Mirrors the server-side allowlist + caps in
// ``openlia_server.services.attachments``. Client-side validation here is
// for UX (immediate feedback); the server re-validates authoritatively.
const PER_FILE_MAX_BYTES = 25 * 1024 * 1024;
const PER_MESSAGE_MAX_FILES = 10;
const ALLOWED_MIMES = new Set([
  "text/plain",
  "text/markdown",
  "text/csv",
  "application/json",
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.presentationml.presentation",
]);

function _validateFile(f: File): string | null {
  if (f.size > PER_FILE_MAX_BYTES) {
    return `${f.name}: too large (max 25 MB)`;
  }
  if (!ALLOWED_MIMES.has(f.type)) {
    return `${f.name}: file type not supported`;
  }
  return null;
}

export function ChatInput({
  onSend,
  onStop,
  isStreaming,
  placeholder,
  leftSlot,
  initialValue,
}: Props): JSX.Element {
  const [value, setValue] = useState(initialValue ?? "");
  const [attachments, setAttachments] = useState<File[]>([]);
  const [attachmentErrors, setAttachmentErrors] = useState<string[]>([]);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const helperId = useId();
  const seededRef = useRef<string | null>(initialValue ?? null);
  // When the parent passes a *new* non-empty initialValue (e.g. user clicks
  // a different Home suggestion that lands on the same Secretary page),
  // re-seed the composer and focus it.
  useLayoutEffect(() => {
    if (!initialValue) return;
    if (seededRef.current === initialValue) return;
    seededRef.current = initialValue;
    setValue(initialValue);
    taRef.current?.focus();
  }, [initialValue]);

  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    const trimmed = value.trim();
    // Allow empty text if there are attachments — common chat-app pattern
    // ("look at this file" without a caption).
    if (!trimmed && attachments.length === 0) return;
    if (attachments.length > 0) {
      onSend(trimmed, attachments);
    } else {
      onSend(trimmed);
    }
    setValue("");
    setAttachments([]);
    setAttachmentErrors([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const incoming = Array.from(e.target.files ?? []);
    const accepted: File[] = [];
    const errors: string[] = [];
    for (const f of incoming) {
      const err = _validateFile(f);
      if (err) {
        errors.push(err);
      } else {
        accepted.push(f);
      }
    }
    setAttachments((prev) => {
      const combined = [...prev, ...accepted];
      if (combined.length > PER_MESSAGE_MAX_FILES) {
        errors.push(
          `only ${PER_MESSAGE_MAX_FILES} files per message — extra files ignored`,
        );
        return combined.slice(0, PER_MESSAGE_MAX_FILES);
      }
      return combined;
    });
    setAttachmentErrors(errors);
    // Reset the input so the same file can be picked again after removal.
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
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
          {attachments.length > 0 ? (
            <div className="flex flex-wrap gap-[6px] px-3 pb-2">
              {attachments.map((f, i) => (
                <PendingAttachmentChip
                  key={`${f.name}-${i}`}
                  filename={f.name}
                  sizeBytes={f.size}
                  onRemove={() => removeAttachment(i)}
                />
              ))}
            </div>
          ) : null}
          {attachmentErrors.length > 0 ? (
            <div
              role="alert"
              aria-live="polite"
              className="px-3 pb-2 text-xs text-status-warning"
            >
              {attachmentErrors.map((msg, i) => (
                <div key={i}>{msg}</div>
              ))}
            </div>
          ) : null}
          <div className="flex items-center gap-2 px-2 py-[6px] pl-[10px]">
            <button
              type="button"
              aria-label="Attach files"
              onClick={() => fileInputRef.current?.click()}
              className="inline-flex items-center justify-center rounded-md p-[6px] text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover hover:text-text-primary"
            >
              <Paperclip size={16} strokeWidth={1.5} />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={handleFileSelect}
              aria-hidden="true"
              tabIndex={-1}
            />
            {leftSlot ?? null}
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
                disabled={value.trim().length === 0 && attachments.length === 0}
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
