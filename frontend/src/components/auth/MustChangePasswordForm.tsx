import { Loader2 } from "lucide-react";
import { useState } from "react";
import { changePassword } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
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

export function MustChangePasswordForm() {
  const { clearMustChangePassword, refresh } = useAuth();
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
      errs.current_password = "Enter your current (temporary) password.";
    }
    if (newPw.length < PASSWORD_MIN) {
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (newPw === current && newPw.length > 0) {
      errs.new_password = "New password must differ from the temporary one.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      await changePassword({ current_password: current, new_password: newPw });
      clearMustChangePassword();
      await refresh();
    } catch (err) {
      if (err instanceof ApiError) {
        const body = (err.body as ServerError | null) ?? {};
        if (body.field) {
          setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
        } else {
          setBanner({
            message: body.message ?? "Password change failed.",
            variant: "error",
          });
        }
      } else {
        setBanner({
          message: "Unexpected error. Please try again.",
          variant: "error",
        });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      <p className="text-sm text-text-secondary mb-5">
        Your administrator has reset your password. Please set a new one to
        continue.
      </p>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField
        id="current_password"
        label="Temporary Password"
        error={fieldErrors.current_password}
      >
        <PasswordInput
          id="current_password"
          value={current}
          onChange={setCurrent}
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.current_password)}
          disabled={submitting}
        />
      </FormField>

      <FormField
        id="new_password"
        label="New Password"
        error={fieldErrors.new_password}
      >
        <PasswordInput
          id="new_password"
          value={newPw}
          onChange={setNewPw}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.new_password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={newPw} />
      </FormField>

      <FormField
        id="confirm"
        label="Confirm New Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={confirm}
          onChange={setConfirm}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Set Password"
        )}
      </button>
    </form>
  );
}
