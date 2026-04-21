import { AlertCircle, AlertTriangle, CheckCircle } from "lucide-react";
import type { ReactNode } from "react";

export type BannerVariant = "error" | "success" | "warning";

export interface BannerProps {
  message: ReactNode;
  variant?: BannerVariant;
}

const VARIANT_CLASS: Record<BannerVariant, string> = {
  error:
    "bg-feedback-error/10 text-feedback-error border border-feedback-error/20",
  success:
    "bg-feedback-success/10 text-feedback-success border border-feedback-success/20",
  warning:
    "bg-feedback-warning/10 text-feedback-warning border border-feedback-warning/20",
};

const VARIANT_ICON: Record<BannerVariant, typeof AlertCircle> = {
  error: AlertCircle,
  success: CheckCircle,
  warning: AlertTriangle,
};

export function Banner({ message, variant = "error" }: BannerProps) {
  const Icon = VARIANT_ICON[variant];
  const role = variant === "success" ? "status" : "alert";
  return (
    <div
      role={role}
      className={`rounded-md px-4 py-3 text-sm mb-5 flex items-start gap-2 ${VARIANT_CLASS[variant]}`}
    >
      <Icon size={14} className="mt-0.5 flex-shrink-0" />
      <span>{message}</span>
    </div>
  );
}
