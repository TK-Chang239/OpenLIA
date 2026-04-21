import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { consumePasswordReset } from "../../api/auth";
import { ApiError } from "../../api/client";
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
      errs.new_password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (newPw !== confirm) {
      errs.confirm = "Passwords do not match.";
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
        const body = (err.body as ServerError | null) ?? {};
        if (body.code === "token_invalid" || body.code === "token_expired") {
          setBanner({
            message:
              body.message ??
              "This reset link has expired or has already been used. Contact your administrator for a new one.",
            variant: "error",
          });
        } else if (body.field) {
          setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
        } else {
          setBanner({
            message: body.message ?? "Reset failed. Please try again.",
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

  if (done) {
    return (
      <div>
        <Banner
          variant="success"
          message="Password updated successfully. You can now log in."
        />
        <p className="mt-6 text-sm text-text-secondary text-center">
          <Link
            to="/login"
            className="text-accent-primary hover:text-accent-hover"
          >
            Back to Log In
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
        disabled={submitting || newPw.length === 0 || confirm.length === 0}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Reset Password"
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          Back to Log In
        </Link>
      </p>
    </form>
  );
}
