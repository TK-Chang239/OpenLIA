import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Props {
  topic: string;
  hasNotes: boolean;
  onClick: () => void;
  onRemove: () => void;
}

export function TopicChip({ topic, hasNotes, onClick, onRemove }: Props) {
  const { t } = useTranslation();
  return (
    <span
      className="relative inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-[--color-surface-active] text-[13px] text-[--color-text-primary] cursor-pointer transition-colors duration-[--duration-normal] hover:bg-[--color-bg-code]"
      data-testid={`topic-chip-${topic}`}
    >
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1.5 outline-none"
        data-testid={`topic-chip-body-${topic}`}
      >
        <span>{topic}</span>
      </button>
      <button
        type="button"
        aria-label={t("morning_briefing.topic_chip.remove_aria", { topic })}
        onClick={(e) => {
          e.stopPropagation();
          onRemove();
        }}
        className="w-3.5 h-3.5 inline-flex items-center justify-center rounded-full ml-0.5 text-[--color-text-tertiary] hover:bg-black/10 hover:text-[--color-text-primary]"
        data-testid={`topic-chip-remove-${topic}`}
      >
        <X size={10} strokeWidth={2.5} />
      </button>
      {hasNotes ? (
        <span
          aria-hidden="true"
          data-testid={`topic-chip-dot-${topic}`}
          className="absolute top-[3px] right-[3px] w-1.5 h-1.5 rounded-full"
          style={{
            background: "var(--color-accent-primary)",
            boxShadow: "0 0 0 1px var(--color-bg-elevated), 0 0 0 2px rgba(212,255,0,0.4)",
          }}
        />
      ) : null}
    </span>
  );
}
