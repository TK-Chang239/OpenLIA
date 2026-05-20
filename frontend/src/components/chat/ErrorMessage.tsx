import { useTranslation } from "react-i18next";
import { LiaBadge } from "./LiaBadge";

interface Props {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: Props): JSX.Element {
  const { t } = useTranslation();
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
            {t("chat.try_again")}
          </button>
        ) : null}
      </div>
    </div>
  );
}
