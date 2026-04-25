import { Loader2 } from "lucide-react";
import { useState } from "react";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
import { Banner, type BannerVariant } from "../../components/primitives/Banner";
import { FormField } from "../../components/primitives/FormField";
import { PasswordInput } from "../../components/primitives/PasswordInput";
import { PasswordStrengthMeter } from "../../components/primitives/PasswordStrengthMeter";

const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function ChangePasswordForm() {
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirm, setConfirm] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit =
    current.length > 0 &&
    newPw.length > 0 &&
    confirm.length > 0 &&
    !submitting;

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = "New password must differ from the current one.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      setBanner({ message: "Password updated.", variant: "success" });
      setCurrent("");
      setNewPw("");
      setConfirm("");
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 0 || err.status >= 500) {
          setBanner(mapTransportError(err));
        } else {
          const body = (err.body as ServerError | null) ?? {};
          if (body.field) {
            setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
          } else {
            setBanner({
              message: body.message ?? "Password change failed.",
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
    <form onSubmit={onSubmit} noValidate className="max-w-md">
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="account_current_password"
        label="Current Password"
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="account_current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
          describedBy={
            fieldErrors.current_password
              ? "account_current_password-error"
              : undefined
          }
        />
      </FormField>

      <FormField
        id="account_new_password"
        label="New Password"
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="account_new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
          describedBy={
            fieldErrors.new_password
              ? "account_new_password-error"
              : undefined
          }
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="account_confirm_password"
        label="Confirm New Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="account_confirm_password"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
          describedBy={
            fieldErrors.confirm ? "account_confirm_password-error" : undefined
          }
        />
      </FormField>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="h-10 px-4 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Change Password"
        )}
      </button>
    </form>
  );
}
