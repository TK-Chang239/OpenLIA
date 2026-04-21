import { passwordStrength, type StrengthLevel } from "../../auth/passwordStrength";

export interface PasswordStrengthMeterProps {
  value: string;
}

const LABELS: Record<StrengthLevel, string> = {
  0: "",
  1: "Weak",
  2: "Fair",
  3: "Good",
  4: "Strong",
};

const BAR_COLOR: Record<StrengthLevel, string> = {
  0: "bg-border-subtle",
  1: "bg-feedback-error",
  2: "bg-feedback-warning",
  3: "bg-feedback-warning",
  4: "bg-feedback-success",
};

const LABEL_COLOR: Record<StrengthLevel, string> = {
  0: "text-text-tertiary",
  1: "text-feedback-error",
  2: "text-feedback-warning",
  3: "text-feedback-warning",
  4: "text-feedback-success",
};

export function PasswordStrengthMeter({ value }: PasswordStrengthMeterProps) {
  if (value.length === 0) return null;
  const level = passwordStrength(value);
  return (
    <div className="flex flex-col gap-1 mt-1.5">
      <div className="flex justify-between items-center">
        <div className="flex gap-1 flex-1">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className={`h-1 flex-1 rounded-full ${
                i <= level ? BAR_COLOR[level] : "bg-border-subtle"
              }`}
            />
          ))}
        </div>
        <span className={`text-xs ml-2 ${LABEL_COLOR[level]}`}>
          {LABELS[level]}
        </span>
      </div>
    </div>
  );
}
