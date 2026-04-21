import { useSearchParams, Navigate } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { RegisterForm } from "../components/auth/RegisterForm";
import { Banner } from "../components/primitives/Banner";

export function RegisterPage() {
  const [searchParams] = useSearchParams();
  const invite = searchParams.get("invite");

  if (!invite) {
    return <Navigate to="/login" replace />;
  }

  return (
    <AuthLayout>
      <AuthCard>
        {invite.length < 8 ? (
          <Banner
            variant="error"
            message="This invite link is no longer valid. Contact your administrator for a new one."
          />
        ) : (
          <RegisterForm inviteToken={invite} />
        )}
      </AuthCard>
    </AuthLayout>
  );
}
