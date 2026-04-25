import { useEffect, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router-dom";
import { getSignupPolicy, type SignupPolicy } from "../api/auth";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { RegisterForm } from "../components/auth/RegisterForm";
import { Banner } from "../components/primitives/Banner";

const FALLBACK_POLICY: SignupPolicy = {
  mode: "invite_only",
  invite_required: true,
};

type PolicyState =
  | { status: "loading" }
  | { status: "ready"; policy: SignupPolicy };

export function RegisterPage() {
  const [searchParams] = useSearchParams();
  const invite = searchParams.get("invite");
  const [state, setState] = useState<PolicyState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getSignupPolicy()
      .then((p) => {
        if (!cancelled) setState({ status: "ready", policy: p });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "ready", policy: FALLBACK_POLICY });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!invite) {
    return <Navigate to="/login" replace />;
  }

  if (state.status === "loading") {
    return (
      <AuthLayout>
        <AuthCard>
          <p className="text-sm text-text-secondary">Loading…</p>
        </AuthCard>
      </AuthLayout>
    );
  }

  if (state.policy.mode === "closed") {
    return (
      <AuthLayout>
        <AuthCard>
          <Banner variant="error" message="Registration is closed." />
          <p className="mt-6 text-sm text-text-secondary text-center">
            <Link
              to="/login"
              className="text-accent-primary hover:text-accent-hover"
            >
              Back to Log In
            </Link>
          </p>
        </AuthCard>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <AuthCard>
        <RegisterForm inviteToken={invite} />
      </AuthCard>
    </AuthLayout>
  );
}
