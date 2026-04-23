import { LiaBadge } from "./LiaBadge";

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: Props): JSX.Element {
  return (
    <div className="flex items-start gap-3">
      <LiaBadge />
      <div className="flex items-center gap-2 text-sm text-[--color-feedback-error]">
        <span>{message}</span>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="ml-1 text-[--color-accent-primary] hover:underline"
          >
            Try again
          </button>
        ) : null}
      </div>
    </div>
  );
}
