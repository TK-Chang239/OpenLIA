import type { ReactNode } from "react";

interface Props {
  id: string;
  title: string;
  hint?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: ReactNode;
}

export function SectionRow({
  id,
  title,
  hint,
  checked,
  onChange,
  children,
}: Props) {
  const labelId = `mb-section-${id}-label`;
  return (
    <div
      className="rounded-[var(--radius-lg,0.5rem)] border p-3"
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-base)",
      }}
      data-testid={`section-row-${id}`}
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          role="checkbox"
          aria-checked={checked}
          aria-labelledby={labelId}
          data-testid={`section-row-${id}-checkbox`}
          onClick={() => onChange(!checked)}
          className="h-4 w-4 rounded border flex items-center justify-center"
          style={{
            borderColor: "var(--color-border-subtle)",
            background: checked
              ? "var(--color-accent-primary)"
              : "transparent",
          }}
        >
          {checked && (
            <span
              aria-hidden="true"
              className="text-[10px] leading-none"
              style={{ color: "var(--color-accent-on)" }}
            >
              {"✓"}
            </span>
          )}
        </button>
        <span id={labelId} className="font-medium">
          {title}
        </span>
      </div>
      {hint && (
        <p
          className="text-xs mt-1"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {hint}
        </p>
      )}
      {children}
    </div>
  );
}
