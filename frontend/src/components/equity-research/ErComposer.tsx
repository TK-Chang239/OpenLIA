import { ArrowUp, ChevronDown, Paperclip, Square } from "lucide-react";
import {
  type JSX,
  type ReactNode,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

import type { ReportLength, ReportMode } from "../../api/equity-research";
import { PendingAttachmentChip } from "../chat/PendingAttachmentChip";

const MAX_HEIGHT = 120;

const MODE_PILL_LABEL: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
};
const LENGTH_PILL_LABEL: Record<ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

interface Props {
  value: string;
  onChange: (next: string) => void;
  onSubmit: (text: string, attachments?: File[]) => void;
  onStop?: () => void;
  isStreaming: boolean;
  placeholder: string;
  mode: ReportMode;
  length: ReportLength;
  onModeClick: () => void;
  modelPicker?: ReactNode;
  toolPicker?: ReactNode;
  initialValue?: string;
  /** Disables submission entirely (e.g., config still loading). */
  disabled?: boolean;
}

export function ErComposer({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming,
  placeholder,
  mode,
  length,
  onModeClick,
  modelPicker,
  toolPicker,
  initialValue,
  disabled,
}: Props): JSX.Element {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const helperId = useId();
  const [attachments, setAttachments] = useState<File[]>([]);
  const seededRef = useRef<string | null>(initialValue ?? null);

  useLayoutEffect(() => {
    if (!initialValue) return;
    if (seededRef.current === initialValue) return;
    seededRef.current = initialValue;
    onChange(initialValue);
    taRef.current?.focus();
    // onChange is stable enough for parent-controlled textarea; no need to retrigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialValue]);

  useLayoutEffect(() => {
    const ta = taRef.current;
    if (!ta) return;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, MAX_HEIGHT)}px`;
  }, [value]);

  const submit = () => {
    if (disabled) return;
    const trimmed = value.trim();
    if (!trimmed && attachments.length === 0) return;
    if (attachments.length > 0) onSubmit(trimmed, attachments);
    else onSubmit(trimmed);
    setAttachments([]);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length > 0) setAttachments((prev) => [...prev, ...files]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeAttachment = (idx: number) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  };

  const sendDisabled =
    disabled || (value.trim().length === 0 && attachments.length === 0);

  return (
    <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 pt-3 pb-[18px]">
      <div
        className="mx-auto max-w-[720px] rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-1 transition-all duration-normal ease-out focus-within:border-[--color-feedback-success] focus-within:shadow-[0_0_0_3px_rgba(212,255,0,0.12)]"
        data-testid="er-composer"
      >
        <textarea
          ref={taRef}
          id={`${helperId}-ta`}
          aria-label="Equity research prompt"
          aria-describedby={helperId}
          rows={1}
          value={value}
          placeholder={placeholder}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          className="w-full min-h-[44px] resize-none border-0 bg-transparent px-[14px] pt-3 pb-[6px] font-display text-[14.5px] leading-[1.5] text-[--color-text-primary] outline-none placeholder:text-[--color-text-tertiary]"
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

        <div className="flex items-center gap-2 px-2 py-[6px] pl-[10px]">
          <button
            type="button"
            aria-label="Attach files"
            onClick={() => fileInputRef.current?.click()}
            className="inline-flex items-center justify-center rounded-md p-[7px] text-[--color-text-secondary] transition-colors duration-normal ease-out hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
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

          <button
            type="button"
            onClick={onModeClick}
            aria-label="Change report mode and length"
            className="inline-flex items-center gap-2 rounded-full border border-[--color-border-subtle] bg-[--color-bg-base] py-[5px] pl-2 pr-[10px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
          >
            <span
              aria-hidden="true"
              className="h-1.5 w-1.5 rounded-full bg-[--color-accent-primary] shadow-[0_0_5px_rgba(212,255,0,0.6)]"
            />
            <strong className="font-medium tracking-[0.06em] text-[--color-text-primary]">
              {MODE_PILL_LABEL[mode]}
            </strong>
            <span className="text-[--color-text-tertiary]">·</span>
            <span>{LENGTH_PILL_LABEL[length]}</span>
            <ChevronDown
              size={10}
              strokeWidth={2}
              className="opacity-70"
              aria-hidden="true"
            />
          </button>

          {modelPicker}
          {toolPicker}

          <div className="flex-1" />

          <span
            id={helperId}
            className="hidden font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-text-tertiary] sm:inline"
          >
            <span aria-hidden="true">↵</span> Send
            <span className="mx-2 text-[--color-border-subtle]">·</span>
            <span aria-hidden="true">⇧↵</span> New line
          </span>

          {isStreaming ? (
            <button
              type="button"
              aria-label="Stop generating"
              onClick={onStop}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-accent-primary] text-[--color-accent-on] transition-colors duration-normal ease-out hover:bg-[--color-accent-hover] active:scale-[0.95]"
            >
              <Square size={12} strokeWidth={2.4} />
            </button>
          ) : (
            <button
              type="button"
              aria-label="Send"
              onClick={submit}
              disabled={sendDisabled}
              className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-[--color-accent-primary] text-[--color-accent-on] transition-all duration-normal ease-out hover:bg-[--color-accent-hover] active:scale-[0.95] disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ArrowUp size={14} strokeWidth={2.2} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
