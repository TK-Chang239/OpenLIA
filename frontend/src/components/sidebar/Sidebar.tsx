import { useEffect } from "react";
import type { JSX } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight, LogOut, Settings } from "lucide-react";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";
import { NavItem } from "./NavItem";
import { useCollapsed } from "./useCollapsed";
import { useNotificationPoll } from "./useNotificationPoll";
import { useAuth } from "../../auth/AuthContext";
import { useDeptHealth } from "../../store/dept-health";
import pkg from "../../../package.json";

function deriveInitials(name: string | null, email: string | null): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  if (email && email.length > 0) return email.slice(0, 2).toUpperCase();
  return "LI";
}

function deriveDisplayName(name: string | null, email: string | null): string {
  if (name && name.trim()) return name;
  if (email) return email;
  return "Local";
}

export function Sidebar(): JSX.Element {
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useCollapsed();
  const { unreadByDepartment, markRead } = useNotificationPoll();
  const healths = useDeptHealth((s) => s.healths);
  const location = useLocation();
  const { status, user, logout } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    const match = DEPARTMENT_NAV.find((entry) => entry.path === location.pathname);
    if (match?.departmentId && (unreadByDepartment[match.departmentId] ?? 0) > 0) {
      void markRead(match.departmentId);
    }
  }, [location.pathname, markRead, unreadByDepartment]);

  async function handleSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  const initials = deriveInitials(user?.display_name ?? null, user?.email ?? null);
  const displayName = deriveDisplayName(user?.display_name ?? null, user?.email ?? null);
  const modeLabel = status === "personal" ? t("common.personal") : t("common.company");
  const roleLine = `${modeLabel} · v${pkg.version}`;

  return (
    <nav
      aria-label={t("nav.main_navigation")}
      className={[
        "hidden md:flex flex-col h-screen bg-sidebar-bg",
        "transition-[width] duration-normal ease-in-out",
        collapsed ? "w-[52px]" : "w-[220px]",
      ].join(" ")}
      style={{ color: "var(--color-sidebar-text)" }}
    >
      <header
        className={[
          "flex items-center gap-[10px] flex-shrink-0",
          collapsed ? "justify-center py-3" : "px-[10px] pt-[14px] pb-[18px]",
        ].join(" ")}
      >
        <span
          className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold bg-accent-primary text-accent-on shadow-accent"
          style={{ fontSize: 10 }}
        >
          LIA
        </span>
        {!collapsed && (
          <span
            className="font-display text-[15px] font-semibold tracking-tight"
            style={{ color: "var(--color-sidebar-text-strong)" }}
          >
            OpenLia
          </span>
        )}
      </header>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
        {!collapsed && (
          <div
            role="separator"
            className="px-2 pt-1 pb-2 font-mono text-[9px] uppercase"
            style={{
              letterSpacing: "var(--tracking-micro)",
              color: "var(--color-sidebar-text-muted)",
              fontWeight: 500,
            }}
          >
            {t("nav.section_general")}
          </div>
        )}
        {CORE_NAV.map((entry) => (
          <NavItem
            key={entry.id}
            label={t(entry.labelKey)}
            icon={entry.icon}
            path={entry.path}
            collapsed={collapsed}
            hasUnread={
              entry.departmentId !== null &&
              (unreadByDepartment[entry.departmentId] ?? 0) > 0
            }
          />
        ))}

        {collapsed ? (
          <div
            className="my-2 h-px"
            style={{ background: "var(--color-sidebar-divider)" }}
            aria-hidden="true"
          />
        ) : (
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
        )}

        {DEPARTMENT_NAV.map((entry) => {
          const health = entry.departmentId
            ? healths[entry.departmentId]
            : undefined;
          const disabledReason =
            health?.status === "disabled" ? (health.reason ?? "") : null;
          return (
            <NavItem
              key={entry.id}
              label={t(entry.labelKey)}
              icon={entry.icon}
              path={entry.path}
              collapsed={collapsed}
              hasUnread={
                entry.departmentId !== null &&
                (unreadByDepartment[entry.departmentId] ?? 0) > 0
              }
              disabledReason={disabledReason}
            />
          );
        })}
      </div>

      <footer
        className="flex-shrink-0 px-2 pt-2 pb-[14px] space-y-0.5"
        style={{ borderTop: "1px solid var(--color-sidebar-divider)" }}
      >
        <NavItem
          label={t("nav.settings")}
          icon={Settings}
          path="/settings"
          collapsed={collapsed}
          hasUnread={false}
        />

        {status === "authenticated" && (
          <button
            type="button"
            onClick={() => {
              void handleSignOut();
            }}
            aria-label={t("shell.sign_out")}
            className={[
              "flex items-center gap-[10px] rounded-md w-full",
              "transition-colors duration-normal ease-out",
              collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
            ].join(" ")}
            style={{ color: "var(--color-sidebar-text)" }}
          >
            <LogOut size={16} strokeWidth={1.5} />
            {!collapsed && (
              <span className="text-[13px] font-display truncate">
                {t("shell.sign_out")}
              </span>
            )}
          </button>
        )}

        <button
          type="button"
          aria-label={collapsed ? t("nav.expand_sidebar") : t("nav.collapse_sidebar")}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed(!collapsed)}
          className={[
            "relative flex items-center gap-[10px] rounded-md w-full",
            "transition-colors duration-normal ease-out",
            collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
          ].join(" ")}
          style={{ color: "var(--color-sidebar-text)" }}
        >
          {collapsed ? (
            <ChevronRight size={16} strokeWidth={1.5} />
          ) : (
            <>
              <ChevronLeft size={16} strokeWidth={1.5} />
              <span className="text-[13px] font-display truncate">{t("nav.collapse")}</span>
            </>
          )}
        </button>

        <div
          className={[
            "flex items-center gap-[10px] mt-2 pt-[14px]",
            collapsed ? "justify-center" : "px-[10px]",
          ].join(" ")}
          style={{ borderTop: "1px solid var(--color-sidebar-divider)" }}
        >
          <span
            aria-hidden="true"
            className="inline-flex items-center justify-center w-[28px] h-[28px] rounded-md flex-shrink-0 font-mono"
            style={{
              background: "var(--neutral-800)",
              color: "var(--color-sidebar-text-strong)",
              fontSize: 11,
              fontWeight: 600,
            }}
          >
            {initials}
          </span>
          {!collapsed && (
            <div className="flex flex-col gap-[2px] min-w-0">
              <span
                className="text-[13px] truncate"
                style={{ color: "var(--color-sidebar-text-strong)" }}
              >
                {displayName}
              </span>
              <span
                className="font-mono text-[9px] uppercase truncate"
                style={{
                  letterSpacing: "var(--tracking-micro)",
                  color: "var(--color-sidebar-text-muted)",
                }}
              >
                {roleLine}
              </span>
            </div>
          )}
        </div>
      </footer>
    </nav>
  );
}
