import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export interface PasswordInputProps {
  id: string;
  value: string;
  onChange: (next: string) => void;
  autoComplete?: string;
  placeholder?: string;
  hasError?: boolean;
  disabled?: boolean;
}

export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete = "current-password",
  placeholder,
  hasError = false,
  disabled = false,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const borderClass = hasError
    ? "border-feedback-error ring-2 ring-feedback-error/20"
    : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus";

  return (
    <div className="relative">
      <input
        id={id}
        data-testid="password-input"
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        disabled={disabled}
        className={`w-full h-10 rounded-md bg-bg-input px-3 pr-10 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast border ${borderClass}`}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? "Hide password" : "Show password"}
        className="absolute right-3 top-1/2 -translate-y-1/2 w-7 h-7 flex items-center justify-center rounded-sm text-text-secondary hover:text-text-primary"
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}
