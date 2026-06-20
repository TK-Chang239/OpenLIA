import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { logoutAll } from "../../api/auth";
import { mapTransportError } from "../../api/errors";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";

export function SessionsPanel() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function onSignOutAll() {
    setBanner(null);
    setSubmitting(true);
    try {
      await logoutAll();
      // logout-all revokes every session including this one; reset local auth
      // state and send the user back to the login screen.
      await logout();
      navigate("/login", { replace: true });
    } catch (err) {
      setBanner(mapTransportError(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      {banner && <Banner variant={banner.variant} message={banner.message} />}
      <p className="text-sm text-text-secondary">
        {t("settings.account.sessions.description")}
      </p>
      <button
        type="button"
        onClick={() => {
          void onSignOutAll();
        }}
        disabled={submitting}
        aria-busy={submitting}
        className="self-start h-10 px-4 rounded-md border border-border-subtle text-sm font-medium text-text-primary flex items-center justify-center hover:bg-bg-elevated transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
        ) : (
          t("settings.account.sessions.sign_out_all")
        )}
      </button>
    </div>
  );
}
