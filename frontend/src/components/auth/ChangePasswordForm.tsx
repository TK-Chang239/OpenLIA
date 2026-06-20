import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";
import { PasswordStrengthMeter } from "../primitives/PasswordStrengthMeter";

const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function ChangePasswordForm() {
  const { t } = useTranslation();
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (current.length === 0) {
      errs.current_password = t("auth.errors.enter_current_password");
    }
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = t("auth.errors.password_too_short", { min: PASSWORD_MIN });
    }
    if (newPw !== confirm) {
      errs.confirm = t("auth.errors.passwords_do_not_match");
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = t("auth.errors.new_password_must_differ_current");
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      setCurrent("");
      setNewPw("");
      setConfirm("");
      setBanner({
        message: t("settings.account.change_password.success"),
        variant: "success",
      });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) {
          setBanner(mapTransportError(err));
        } else {
          const body = (err.body as ServerError | null) ?? {};
          if (body.field) {
            setFieldErrors({ [body.field]: body.message ?? t("auth.errors.invalid_value") });
          } else {
            setBanner({
              message: body.message ?? t("auth.errors.password_change_failed"),
              variant: "error",
            });
          }
        }
      } else {
        setBanner(mapTransportError(err));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="current_password"
        label={t("settings.account.change_password.current_label")}
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
          describedBy={fieldErrors.current_password ? "current_password-error" : undefined}
        />
      </FormField>

      <FormField
        id="new_password"
        label={t("settings.account.change_password.new_label")}
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
          describedBy={fieldErrors.new_password ? "new_password-error" : undefined}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label={t("settings.account.change_password.confirm_label")}
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
          describedBy={fieldErrors.confirm ? "confirm-error" : undefined}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
        ) : (
          t("settings.account.change_password.submit")
        )}
      </button>
    </form>
  );
}
