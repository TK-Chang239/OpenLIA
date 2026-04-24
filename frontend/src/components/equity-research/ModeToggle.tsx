import clsx from "clsx";

export interface ModeToggleOption<T extends string> {
  value: T;
  label: string;
}

interface Props<T extends string> {
  value: T;
  options: ModeToggleOption<T>[];
  onChange: (value: T) => void;
  ariaLabel?: string;
}

export function ModeToggle<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: Props<T>) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="inline-flex rounded-md border border-[--color-border-subtle] p-0.5 bg-[--color-bg-base]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            className={clsx(
              "px-3 h-8 text-sm rounded-[--radius-sm] transition-colors",
              active
                ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
            )}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
