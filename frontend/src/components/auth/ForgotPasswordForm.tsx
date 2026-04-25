import { Loader2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { requestPasswordReset } from "../../api/auth";
import { ApiError } from "../../api/client";
import { mapTransportError } from "../../api/errors";
import { Banner, type BannerVariant } from "../primitives/Banner";
import { FormField } from "../primitives/FormField";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const NEUTRAL_MESSAGE =
  "If the email matches an account, your admin has been notified. They'll send you a reset link.";

export function ForgotPasswordForm() {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setEmailError(null);
    setBanner(null);
    if (!EMAIL_RE.test(email)) {
      setEmailError("Enter a valid email address.");
      return;
    }
    setSubmitting(true);
    try {
      await requestPasswordReset(email.trim());
      setDone(true);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setBanner({
          message: "Too many requests. Please wait and try again.",
          variant: "warning",
        });
      } else if (
        err instanceof TypeError ||
        (err instanceof ApiError && (err.status === 0 || err.status >= 500))
      ) {
        setBanner(mapTransportError(err));
      } else {
        // Anti-enumeration on 4xx: still show neutral confirmation.
        setDone(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div>
        <Banner variant="success" message={NEUTRAL_MESSAGE} />
        <p className="mt-6 text-sm text-text-secondary text-center">
          <Link to="/login" className="text-accent-primary hover:text-accent-hover">
            Back to Log In
          </Link>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate>
      {banner && <Banner variant={banner.variant} message={banner.message} />}
      <p className="text-sm text-text-secondary mb-5">
        Enter your email and we&apos;ll notify your admin to approve a password
        reset.
      </p>

      <FormField id="email" label="Email" error={emailError ?? undefined}>
        <input
          id="email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={submitting}
          aria-describedby={emailError ? "email-error" : undefined}
          className={`w-full h-10 rounded-md border bg-bg-input px-3 text-sm text-text-primary outline-none transition-colors duration-fast ${
            emailError
              ? "border-feedback-error ring-2 ring-feedback-error/20"
              : "border-border-subtle focus:border-border-secondary focus:ring-2 focus:ring-focus"
          }`}
        />
      </FormField>

      <button
        type="submit"
        disabled={submitting || email.trim().length === 0}
        aria-busy={submitting}
        className="w-full h-10 rounded-md bg-accent-primary text-white text-sm font-medium flex items-center justify-center hover:bg-accent-hover transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label="Loading" />
        ) : (
          "Request Reset"
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
