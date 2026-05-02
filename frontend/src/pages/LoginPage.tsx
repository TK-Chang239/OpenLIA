import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { getSignupPolicy, type SignupPolicy } from "../api/auth";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { LoginForm } from "../components/auth/LoginForm";
import { useAuth } from "../auth/AuthContext";

const FALLBACK_POLICY: SignupPolicy = {
  mode: "invite_only",
  invite_required: true,
};

export function LoginPage() {
  const { status } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const invite = searchParams.get("invite") ?? undefined;
  const [policy, setPolicy] = useState<SignupPolicy>(FALLBACK_POLICY);

  useEffect(() => {
    let cancelled = false;
    getSignupPolicy()
      .then((p) => {
        // fetchJson returns null for 204 / non-JSON / parse failure;
        // keep the FALLBACK_POLICY when the response is missing or malformed.
        if (cancelled) return;
        if (p && typeof p === "object" && typeof p.mode === "string") {
          setPolicy(p);
        }
      })
      .catch(() => {
        if (!cancelled) setPolicy(FALLBACK_POLICY);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (status === "authenticated" || status === "personal") {
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    }
  }, [status, searchParams, navigate]);

  return (
    <AuthLayout>
      <AuthCard>
        <LoginForm inviteToken={invite} policyMode={policy.mode} />
      </AuthCard>
    </AuthLayout>
  );
}
