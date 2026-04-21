import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { LoginForm } from "../components/auth/LoginForm";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { status } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const invite = searchParams.get("invite") ?? undefined;

  useEffect(() => {
    if (status === "authenticated" || status === "personal") {
      const next = searchParams.get("next") ?? "/";
      navigate(next, { replace: true });
    }
  }, [status, searchParams, navigate]);

  return (
    <AuthLayout>
      <AuthCard>
        <LoginForm inviteToken={invite} />
      </AuthCard>
    </AuthLayout>
  );
}
