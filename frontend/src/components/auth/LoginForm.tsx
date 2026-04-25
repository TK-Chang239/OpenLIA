import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";
import { PasswordInput } from "../primitives/PasswordInput";

export type SignupPolicyMode = "open" | "invite_only" | "closed";

export interface LoginFormProps {
  inviteToken?: string;
  policyMode?: SignupPolicyMode;
}

interface FormState {
  email: string;
  password: string;
  persistent: boolean;
}

const INITIAL_STATE: FormState = {
  email: "",
  password: "",
  persistent: false,
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface ServerError {
  code?: string;
  message?: string;
  field?: string;
  metadata?: Record<string, unknown>;
}

export function LoginForm({ inviteToken, policyMode }: LoginFormProps) {
  const { login } = useAuth();
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const canSubmit =
    form.email.trim().length > 0 &&
    form.password.length > 0 &&
    !submitting;

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFieldErrors({});
    setBanner(null);

    if (!EMAIL_RE.test(form.email)) {
      setFieldErrors({ email: "Enter a valid email address." });
      return;
    }

    setSubmitting(true);
    try {
      await login({
        email: form.email.trim(),
        password: form.password,
        persistent: form.persistent,
      });
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    } catch (err) {
      handleError(err);
    } finally {
      setSubmitting(false);
    }
  }

  function handleError(err: unknown) {
    if (!(err instanceof ApiError)) {
      setBanner(mapTransportError(err));
      return;
    }
    if (err.status === 0 || err.status >= 500) {
      setBanner(mapTransportError(err));
      return;
    }
    const body = (err.body as ServerError | null) ?? {};
    if (body.code === "account_locked") {
      const retryRaw = body.metadata?.retry_after_seconds;
      const seconds = typeof retryRaw === "number" ? retryRaw : 0;
      const minutes = Math.max(1, Math.ceil(seconds / 60));
      const banner =
        seconds > 0
          ? `Try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`
          : (body.message ?? "Account is temporarily locked.");
      setBanner({ message: banner, variant: "warning" });
      return;
    }
    if (body.code === "rate_limited") {
      setBanner({
        message: body.message ?? "Too many attempts. Please wait.",
        variant: "warning",
      });
      return;
    }
    if (body.field) {
      setFieldErrors({ [body.field]: body.message ?? "Invalid value." });
      return;
    }
    setBanner({
      message: body.message ?? "Email or password is incorrect.",
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
          autoComplete="username"
          value={form.email}
          onChange={(e) => update("email", e.target.value)}
          disabled={submitting}
          aria-describedby={fieldErrors.email ? "email-error" : undefined}
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
          autoComplete="current-password"
          hasError={Boolean(fieldErrors.password)}
          disabled={submitting}
          describedBy={fieldErrors.password ? "password-error" : undefined}
        />
      </FormField>

      <div className="flex items-center gap-2 mb-5">
        <input
          type="checkbox"
          id="persistent"
          checked={form.persistent}
          onChange={(e) => update("persistent", e.target.checked)}
          className="accent-accent-primary w-4 h-4 rounded-sm cursor-pointer"
          disabled={submitting}
        />
        <label
          htmlFor="persistent"
          className="text-sm text-text-secondary cursor-pointer"
        >
          Keep me logged in
        </label>
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Log In"
        )}
      </button>

      <div className="flex items-center justify-between mt-4">
        <Link
          to="/forgot-password"
          className="text-sm text-accent-primary hover:text-accent-hover"
        >
          Forgot password?
        </Link>
      </div>

      {inviteToken && policyMode !== "closed" && (
        <p className="mt-6 text-sm text-text-secondary text-center">
          Don&apos;t have an account?{" "}
          <Link
            to={`/register?invite=${encodeURIComponent(inviteToken)}`}
            className="text-accent-primary hover:text-accent-hover"
          >
            Sign up
          </Link>
        </p>
      )}
    </form>
  );
}
