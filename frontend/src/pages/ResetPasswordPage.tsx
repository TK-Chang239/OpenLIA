import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import { AuthCard } from "../components/auth/AuthCard";
import { AuthLayout } from "../components/auth/AuthLayout";
import { ResetPasswordForm } from "../components/auth/ResetPasswordForm";
import { Banner } from "../components/primitives/Banner";

export function ResetPasswordPage() {
  const { t } = useTranslation();
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
            message={t("auth.reset.link_invalid")}
          />
        )}
      </AuthCard>
    </AuthLayout>
  );
}
