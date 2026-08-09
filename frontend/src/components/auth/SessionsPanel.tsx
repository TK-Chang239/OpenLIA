import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  listAuthSessions,
  logoutAll,
  revokeAuthSession,
  type AuthSession,
} from "../../api/auth";
import { mapTransportError } from "../../api/errors";
import { useAuth } from "../../auth/AuthContext";
import { Banner, type BannerVariant } from "../primitives/Banner";

export function SessionsPanel() {
  const { t } = useTranslation();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [revoking, setRevoking] = useState<string | null>(null);
  const [banner, setBanner] = useState<
    { message: string; variant: BannerVariant } | null
  >(null);

  async function loadSessions() {
    try {
      setSessions(await listAuthSessions());
      setLoadError(null);
    } catch {
      setLoadError(t("settings.account.sessions.load_failed"));
      setSessions([]);
    }
  }

  useEffect(() => {
    void loadSessions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onRevoke(id: string) {
    setBanner(null);
    setRevoking(id);
    try {
      await revokeAuthSession(id);
      await loadSessions();
    } catch (err) {
      setBanner(mapTransportError(err));
    } finally {
      setRevoking(null);
    }
  }

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

      {sessions === null ? (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <Loader2 size={16} className="animate-spin" aria-label={t("auth.loading_aria")} />
          {t("settings.account.sessions.loading")}
        </div>
      ) : loadError ? (
        <Banner variant="error" message={loadError} />
      ) : sessions.length === 0 ? (
        <p className="text-sm text-text-secondary">
          {t("settings.account.sessions.empty")}
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {sessions.map((s) => (
            <li
              key={s.id}
              className="flex items-center gap-3 rounded-md border border-border-subtle px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-2 text-sm text-text-primary">
                  <span className="truncate">
                    {s.user_agent ||
                      t("settings.account.sessions.unknown_device")}
                  </span>
                  {s.current ? (
                    <span className="shrink-0 rounded-full bg-bg-elevated px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-feedback-success">
                      {t("settings.account.sessions.current")}
                    </span>
                  ) : null}
                </p>
                <p className="text-xs text-text-tertiary">
                  {s.ip_address ? `${s.ip_address} · ` : ""}
                  {t("settings.account.sessions.last_active", {
                    when: new Date(s.last_seen_at).toLocaleString(),
                  })}
                </p>
              </div>
              {!s.current ? (
                <button
                  type="button"
                  onClick={() => void onRevoke(s.id)}
                  disabled={revoking === s.id}
                  aria-busy={revoking === s.id}
                  className="shrink-0 h-8 px-3 rounded-md border border-border-subtle text-xs font-medium text-text-primary hover:bg-bg-elevated transition-colors duration-fast disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {revoking === s.id ? (
                    <Loader2 size={14} className="animate-spin" aria-label={t("auth.loading_aria")} />
                  ) : (
                    t("settings.account.sessions.revoke")
                  )}
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

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
