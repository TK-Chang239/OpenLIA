interface Props {
  topic: string;
  hasNotes: boolean;
  onClick: () => void;
  onRemove: () => void;
}

export function TopicChip({ topic, hasNotes, onClick, onRemove }: Props) {
  return (
    <span
      className="inline-flex items-center gap-2 rounded-full px-2 py-1 text-xs"
      style={{
        background: "var(--color-bg-elevated, var(--color-bg-base))",
        border: "1px solid var(--color-border-subtle)",
      }}
      data-testid={`topic-chip-${topic}`}
    >
      <button
        type="button"
        onClick={onClick}
        className="inline-flex items-center gap-1"
        data-testid={`topic-chip-body-${topic}`}
      >
        {hasNotes && (
          <span
            aria-hidden="true"
            data-testid={`topic-chip-dot-${topic}`}
            className="inline-block"
            style={{
              width: 4,
              height: 4,
              borderRadius: 9999,
              background: "var(--color-accent-primary)",
            }}
          />
        )}
        <span>{topic}</span>
      </button>
      <button
        type="button"
        aria-label={`Remove ${topic}`}
        onClick={onRemove}
        style={{ color: "var(--color-text-tertiary)" }}
        data-testid={`topic-chip-remove-${topic}`}
      >
        {"×"}
      </button>
    </span>
  );
}
