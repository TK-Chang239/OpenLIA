import type { InputHTMLAttributes } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  id: string;
  error?: string;
}

export function Input({
  label,
  id,
  error,
  className,
  ...rest
}: InputProps): JSX.Element {
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={id} className="text-sm text-text-secondary">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? "true" : undefined}
        className={[
          "h-9 px-3 rounded-md bg-bg-elevated border border-border-subtle text-sm text-text-primary",
          "focus:outline-none focus:border-accent-primary",
          className ?? "",
        ].join(" ")}
        {...rest}
      />
      {error ? (
        <span className="text-xs text-red-400" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
