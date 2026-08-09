import type { InputHTMLAttributes, JSX } from "react";

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
      <label htmlFor={id} className="ol-label">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? "true" : undefined}
        className={[
          "h-10 px-3 rounded-md bg-bg-input border border-border-subtle text-[14px] font-display text-text-primary",
          "transition-all duration-normal ease-out",
          "hover:border-border-strong",
          "focus:outline-none focus:border-yellow-600 focus:shadow-input-focus",
          className ?? "",
        ].join(" ")}
        {...rest}
      />
      {error ? (
        <span className="text-xs text-feedback-error" role="alert">
          {error}
        </span>
      ) : null}
    </div>
  );
}
