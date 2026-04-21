import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ForgotPasswordForm } from "../components/auth/ForgotPasswordForm";

export function ForgotPasswordPage() {
  return (
    <AuthLayout>
      <AuthCard>
        <ForgotPasswordForm />
      </AuthCard>
    </AuthLayout>
  );
}
