import type { JSX } from "react";
import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import * as Dialog from "@radix-ui/react-dialog";
import { LogOut, Settings, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";
import { NavItem } from "./NavItem";
import { useAuth } from "../../auth/AuthContext";
import { useNotificationPoll } from "./useNotificationPoll";

export interface MobileSidebarOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function MobileSidebarOverlay({
  open,
  onOpenChange,
}: MobileSidebarOverlayProps): JSX.Element {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const { status, logout } = useAuth();
  const { unreadByDepartment } = useNotificationPoll();

  useEffect(() => {
    onOpenChange(false);
    // close overlay on route change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  async function handleSignOut() {
    await logout();
    onOpenChange(false);
    navigate("/login", { replace: true });
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          data-testid="mobile-sidebar-scrim"
        />
        <Dialog.Content
          aria-describedby={undefined}
          className="fixed inset-y-0 left-0 z-50 flex h-full w-[260px] flex-col bg-sidebar-bg shadow-xl outline-none md:hidden"
          style={{ color: "var(--color-sidebar-text)" }}
        >
          <Dialog.Title className="sr-only">{t("shell.navigation_label")}</Dialog.Title>
          <header className="flex items-center justify-between px-3 py-3 border-b border-border-subtle">
            <span
              className="font-display text-[15px] font-semibold tracking-tight"
              style={{ color: "var(--color-sidebar-text-strong)" }}
            >
              OpenLia
            </span>
            <Dialog.Close
              aria-label={t("shell.close_navigation_aria")}
              className="rounded-md p-1.5"
              style={{ color: "var(--color-sidebar-text)" }}
            >
              <X size={16} strokeWidth={1.5} />
            </Dialog.Close>
          </header>
          <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
            {CORE_NAV.map((entry) => (
              <NavItem
                key={entry.id}
                label={t(entry.labelKey, { defaultValue: entry.label })}
                icon={entry.icon}
                path={entry.path}
                collapsed={false}
                hasUnread={false}
              />
            ))}
            <div
              role="separator"
              className="px-2 pt-4 pb-2 font-mono text-[9px] uppercase"
              style={{
                letterSpacing: "var(--tracking-micro)",
                color: "var(--color-sidebar-text-muted)",
                fontWeight: 500,
              }}
            >
              {t("nav.section_departments")}
            </div>
            {DEPARTMENT_NAV.map((entry) => (
              <NavItem
                key={entry.id}
                label={t(entry.labelKey, { defaultValue: entry.label })}
                icon={entry.icon}
                path={entry.path}
                collapsed={false}
                hasUnread={
                  entry.departmentId !== null &&
                  (unreadByDepartment[entry.departmentId] ?? 0) > 0
                }
              />
            ))}
          </div>
          <footer
            className="px-2 py-2 space-y-0.5"
            style={{ borderTop: "1px solid var(--color-sidebar-divider)" }}
          >
            <NavItem
              label={t("nav.settings")}
              icon={Settings}
              path="/settings"
              collapsed={false}
              hasUnread={false}
            />
            {status === "authenticated" && (
              <button
                type="button"
                onClick={() => {
                  void handleSignOut();
                }}
                aria-label={t("shell.sign_out")}
                className="w-full flex items-center gap-2 px-2 py-[9px] text-[13px] rounded-md"
                style={{ color: "var(--color-sidebar-text)" }}
              >
                <LogOut size={16} strokeWidth={1.5} />
                <span>{t("shell.sign_out")}</span>
              </button>
            )}
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
