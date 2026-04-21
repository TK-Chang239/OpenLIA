import { Outlet } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { MustChangePasswordForm } from "../components/auth/MustChangePasswordForm";
import { useAuth } from "../auth/AuthContext";

export function MustChangePasswordGate() {
  const { mustChangePassword } = useAuth();
  if (mustChangePassword) {
    return (
      <AuthLayout>
        <AuthCard>
          <MustChangePasswordForm />
        </AuthCard>
      </AuthLayout>
    );
  }
  return <Outlet />;
}
