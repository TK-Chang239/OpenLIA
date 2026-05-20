import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { consumePasswordReset } from "../../api/auth";
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

export interface ResetPasswordFormProps {
  token: string;
}

export function ResetPasswordForm({ token }: ResetPasswordFormProps) {
  const { t } = useTranslation();
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = t("auth.errors.password_too_short", { min: PASSWORD_MIN });
    }
    if (newPw !== confirm) {
      errs.confirm = t("auth.errors.passwords_do_not_match");
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await consumePasswordReset({ token, new_password: newPw });
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) {
          setBanner(mapTransportError(err));
        } else {
          const body = (err.body as ServerError | null) ?? {};
          if (body.code === "token_invalid" || body.code === "token_expired") {
            setBanner({
              message:
                body.message ?? t("auth.errors.reset_link_expired"),
              variant: "error",
            });
          } else if (body.field) {
            setFieldErrors({ [body.field]: body.message ?? t("auth.errors.invalid_value") });
          } else {
            setBanner({
              message: body.message ?? t("auth.errors.reset_failed"),
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

  if (done) {
    return (
      <div>
        <Banner
          variant="success"
          message={t("auth.reset.success")}
        />
        <p className="mt-6 text-sm text-text-secondary text-center">
          <Link
            to="/login"
            className="text-accent-primary hover:text-accent-hover"
          >
            {t("auth.reset.back_to_login")}
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="new_password"
        label={t("auth.reset.new_password_label")}
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
          describedBy={
            fieldErrors.new_password ? "new_password-error" : undefined
          }
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label={t("auth.reset.confirm_new_password_label")}
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
        disabled={submitting || newPw.length === 0 || confirm.length === 0}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
        ) : (
          t("auth.reset.submit")
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          {t("auth.reset.back_to_login")}
        </Link>
      </p>
    </form>
  );
}
