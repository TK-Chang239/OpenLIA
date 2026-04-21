import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { register } from "../../api/auth";
import { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";
import { PasswordStrengthMeter } from "../primitives/PasswordStrengthMeter";

export interface RegisterFormProps {
  inviteToken: string;
}

interface FormState {
  email: string;
  password: string;
  confirm: string;
  display_name: string;
}

const INITIAL_STATE: FormState = {
  email: "",
  password: "",
  confirm: "",
  display_name: "",
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_MIN = 8;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
}

export function RegisterForm({ inviteToken }: RegisterFormProps) {
  const { refresh, setMustChangePassword } = useAuth();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const canSubmit =
    form.email.trim().length > 0 &&
    form.password.length > 0 &&
    form.confirm.length > 0 &&
    !submitting;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    const errs: Record<string, string> = {};
    if (!EMAIL_RE.test(form.email)) {
      errs.email = "Enter a valid email address.";
    }
    if (form.password.length < PASSWORD_MIN) {
      errs.password = `Password must be at least ${PASSWORD_MIN} characters.`;
    }
    if (form.password !== form.confirm) {
      errs.confirm = "Passwords do not match.";
    }
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }

    setSubmitting(true);
    try {
      const result = await register({
        email: form.email.trim(),
        password: form.password,
        display_name: form.display_name.trim() || undefined,
        invite_token: inviteToken,
      });
      setMustChangePassword(result.must_change_password);
      await refresh();
      navigate("/", { replace: true });
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  function handleError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setBanner({
        message: "Unexpected error. Please try again.",
        variant: "error",
      });
      return;
    }
    const body = (err.body as ServerError | null) ?? {};
    if (
      body.code === "invite_invalid" ||
      body.code === "invite_required" ||
      body.code === "signup_closed"
    ) {
      setBanner({
        message:
          body.message ??
          "This invite link is no longer valid. Contact your administrator for a new one.",
        variant: "error",
      });
      return;
    }
    if (body.field) {
      setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
      return;
    }
    setBanner({
      message: body.message ?? "Registration failed. Please try again.",
      variant: "error",
    });
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}

      <FormField id="email" label="Email" error={fieldErrors.email}>
        <input
          id="email"
          type="email"
          autoComplete="email"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          disabled={submitting}
          className={`w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast ${
            fieldErrors.email
              ? "border-feedback-error ring-2 ring-feedback-error/20"
              : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
          }`}
        />
      </FormField>

      <FormField id="password" label="Password" error={fieldErrors.password}>
        <PasswordInput
          id="password"
          value={form.password}
          onChange={(v) => update("password", v)}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.password)}
          disabled={submitting}
        />
        <PasswordStrengthMeter value={form.password} />
      </FormField>

      <FormField
        id="confirm"
        label="Confirm Password"
        error={fieldErrors.confirm}
      >
        <PasswordInput
          id="confirm"
          value={form.confirm}
          onChange={(v) => update("confirm", v)}
          autoComplete="new-password"
          hasError={Boolean(fieldErrors.confirm)}
          disabled={submitting}
        />
      </FormField>

      <FormField id="display_name" label="Display Name (optional)">
        <input
          id="display_name"
          type="text"
          autoComplete="name"
          value={form.display_name}
          onChange={(e) => update("display_name", e.target.value)}
          disabled={submitting}
          className="w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary placeholder:text-text-tertiary outline-none transition-colors duration-fast border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
        />
      </FormField>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Create Account"
        )}
      </button>

      <p className="mt-6 text-sm text-text-secondary text-center">
        Already have an account?{" "}
        <Link to="/login" className="text-accent-primary hover:text-accent-hover">
          Log in
        </Link>
      </p>
    </form>
  );
}
