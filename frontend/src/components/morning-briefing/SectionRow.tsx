import type { ReactNode } from "react";
import { Check } from "lucide-react";

interface Props {
  id: string;
  title: string;
  hint?: string;
  badge?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  children?: ReactNode;
}

export function SectionRow({
  id,
  title,
  hint,
  badge,
  checked,
  onChange,
  children,
}: Props) {
  const labelId = `mb-section-${id}-label`;
  return (
    <div
      className="flex gap-3.5 items-start px-5 py-[18px] border-b last:border-b-0"
      style={{ borderColor: "var(--color-border-subtle)" }}
      data-testid={`section-row-${id}`}
    >
      <button
        type="button"
        role="checkbox"
        aria-checked={checked}
        aria-labelledby={labelId}
        data-testid={`section-row-${id}-checkbox`}
        onClick={() => onChange(!checked)}
        className="mt-0.5 h-[18px] w-[18px] rounded-[4px] flex items-center justify-center border-[1.5px] flex-shrink-0 transition-colors duration-[--duration-normal] focus-visible:shadow-[0_0_0_3px_rgba(212,255,0,0.25)] focus-visible:outline-none"
        style={{
          borderColor: checked
            ? "var(--color-accent-primary)"
            : "var(--color-border-strong)",
          background: checked
            ? "var(--color-accent-primary)"
            : "var(--color-bg-base)",
        }}
      >
        {checked ? (
          <Check
            size={12}
            strokeWidth={3}
            style={{ color: "var(--color-accent-on)" }}
          />
        ) : null}
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2.5">
          <span
            id={labelId}
            className="text-[15px] font-medium"
            style={{
              color: checked
                ? "var(--color-text-primary)"
                : "var(--color-text-tertiary)",
            }}
          >
            {title}
          </span>
          {badge ? (
            <span
              className="font-mono text-[9.5px] tracking-[0.1em] uppercase px-2 py-0.5 border rounded"
              style={{
                color: "var(--color-text-tertiary)",
                borderColor: "var(--color-border-subtle)",
              }}
            >
              {badge}
            </span>
          ) : null}
        </div>
        {hint ? (
          <p
            className="text-[12px] mt-0.5 leading-[1.45] m-0"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {hint}
          </p>
        ) : null}
        {children}
      </div>
    </div>
  );
}
