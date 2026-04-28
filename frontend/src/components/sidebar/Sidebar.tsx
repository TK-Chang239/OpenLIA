import { useEffect } from "react";
import type { JSX } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { ChevronLeft, ChevronRight, LogOut, Settings, User } from "lucide-react";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";
import { NavItem } from "./NavItem";
import { useCollapsed } from "./useCollapsed";
import { useNotificationPoll } from "./useNotificationPoll";
import { useAuth } from "../../auth/AuthContext";
import { useDeptHealth } from "../../store/dept-health";

export function Sidebar(): JSX.Element {
  const [collapsed, setCollapsed] = useCollapsed();
  const { unreadByDepartment, markRead } = useNotificationPoll();
  const healths = useDeptHealth((s) => s.healths);
  const location = useLocation();
  const { status, logout } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  useEffect(() => {
    const match = DEPARTMENT_NAV.find((entry) => entry.path === location.pathname);
    if (match?.departmentId && (unreadByDepartment[match.departmentId] ?? 0) > 0) {
      void markRead(match.departmentId);
    }
  }, [location.pathname, markRead, unreadByDepartment]);

  return (
    <nav
      aria-label="Main navigation"
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
            General
          </div>
        )}
        {CORE_NAV.map((entry) => (
          <NavItem
            key={entry.id}
            label={entry.label}
            icon={entry.icon}
            path={entry.path}
            collapsed={collapsed}
            hasUnread={false}
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
            Departments
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
              label={entry.label}
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
        className="flex-shrink-0 px-2 py-2 space-y-0.5"
        style={{ borderTop: "1px solid var(--color-sidebar-divider)" }}
      >
        <NavItem
          label="Settings"
          icon={Settings}
          path="/settings"
          collapsed={collapsed}
          hasUnread={false}
        />
        <NavLink
          to="/settings/account"
          aria-label={collapsed ? "Account" : undefined}
          className={[
            "flex items-center gap-[10px] px-2 py-[9px] rounded-md w-full",
            "transition-colors duration-normal ease-out",
            collapsed ? "justify-center" : "",
          ].join(" ")}
          style={({ isActive }: { isActive: boolean }) => ({
            background: isActive ? "var(--color-sidebar-active)" : "transparent",
            color: isActive
              ? "var(--color-sidebar-text-strong)"
              : "var(--color-sidebar-text)",
          })}
        >
          <span
            className="w-[18px] h-[18px] rounded-full inline-flex items-center justify-center"
            style={{ background: "var(--color-accent-primary)" }}
          >
            <User
              size={11}
              strokeWidth={1.5}
              style={{ color: "var(--color-accent-on)" }}
            />
          </span>
          {collapsed ? null : (
            <span className="text-[13px]">Account</span>
          )}
        </NavLink>
        {status === "authenticated" && (
          <button
            type="button"
            onClick={() => {
              void handleSignOut();
            }}
            aria-label="Sign out"
            className={[
              "w-full flex items-center gap-2 px-2 py-[9px] text-[13px] rounded-md transition-colors duration-normal ease-out",
              collapsed ? "justify-center" : "",
            ].join(" ")}
            style={{ color: "var(--color-sidebar-text)" }}
          >
            <LogOut size={16} strokeWidth={1.5} />
            {collapsed ? null : <span>Sign out</span>}
          </button>
        )}
        <button
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed(!collapsed)}
          className={[
            "w-full flex items-center gap-2 px-2 py-[9px] text-[13px] rounded-md transition-colors duration-normal ease-out",
            collapsed ? "justify-center" : "",
          ].join(" ")}
          style={{ color: "var(--color-sidebar-text)" }}
        >
          {collapsed ? (
            <ChevronRight size={16} strokeWidth={1.5} />
          ) : (
            <ChevronLeft size={16} strokeWidth={1.5} />
          )}
          {collapsed ? null : <span>Collapse</span>}
        </button>
      </footer>
    </nav>
  );
}
