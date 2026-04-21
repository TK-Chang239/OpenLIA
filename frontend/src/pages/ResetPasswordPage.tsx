import { useSearchParams } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ResetPasswordForm } from "../components/auth/ResetPasswordForm";
import { Banner } from "../components/primitives/Banner";

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  return (
    <AuthLayout>
      <AuthCard>
        {token ? (
          <ResetPasswordForm token={token} />
        ) : (
          <Banner
            variant="error"
            message="This reset link is invalid. Contact your administrator for a new one."
          />
        )}
      </AuthCard>
    </AuthLayout>
  );
}
