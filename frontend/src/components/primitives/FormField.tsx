import { AlertCircle } from "lucide-react";
import type { ReactNode } from "react";

export interface FormFieldProps {
  id: string;
  label: string;
  helper?: string;
  error?: string;
  children: ReactNode;
}

export function FormField({
  id,
  label,
  helper,
  error,
  children,
}: FormFieldProps) {
  return (
    <div className="flex flex-col gap-1.5 mb-4">
      <label
        htmlFor={id}
        className="text-sm font-medium text-text-primary"
      >
        {label}
      </label>
      {children}
      {helper && !error && (
        <span className="text-xs text-text-secondary">{helper}</span>
      )}
      {error && (
        <span
          id={`${id}-error`}
          className="text-xs text-feedback-error flex items-center gap-1"
        >
          <AlertCircle size={12} />
          {error}
        </span>
      )}
    </div>
  );
}
