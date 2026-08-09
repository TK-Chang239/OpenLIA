import type { JSX } from "react";
import { AlertCircle, FileX } from "lucide-react";

interface ErrorProps {
  message?: string;
  onRetry: () => void;
}

export function RendererError({ message, onRetry }: ErrorProps): JSX.Element {
  return (
    <div
      role="alert"
      className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center"
    >
      <AlertCircle size={32} className="text-[--color-feedback-error]" aria-hidden />
      <p className="text-sm text-[--color-text-secondary]">
        {message ?? "Failed to load file."}
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="text-sm text-[--color-accent-primary] hover:underline"
      >
        Try again
      </button>
    </div>
  );
}

export function RendererEmpty(): JSX.Element {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <FileX size={28} className="text-[--color-text-tertiary]" aria-hidden />
      <p className="text-sm text-[--color-text-secondary]">This file is empty.</p>
    </div>
  );
}

export function RendererLoading(): JSX.Element {
  return (
    <div className="space-y-2 p-6">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="ol-skeleton h-4" />
      ))}
    </div>
  );
}
