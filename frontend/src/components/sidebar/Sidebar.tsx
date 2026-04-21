import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { ChevronLeft, ChevronRight, Settings, User } from "lucide-react";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";
import { NavItem } from "./NavItem";
import { useCollapsed } from "./useCollapsed";
import { useNotificationPoll } from "./useNotificationPoll";

export function Sidebar(): JSX.Element {
  const [collapsed, setCollapsed] = useCollapsed();
  const { unreadByDepartment, markRead } = useNotificationPoll();
  const location = useLocation();

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
        "flex flex-col h-screen bg-sidebar-bg border-r border-border-subtle",
        "transition-[width] duration-200 ease-in-out",
        collapsed ? "w-[60px]" : "w-[240px]",
      ].join(" ")}
    >
      <header
        className={[
          "h-14 flex items-center border-b border-border-subtle flex-shrink-0",
          collapsed ? "justify-center" : "justify-between px-4",
        ].join(" ")}
      >
        {collapsed ? null : (
          <span className="text-xl font-semibold tracking-tight text-text-primary">
            LIA
          </span>
        )}
        <button
          type="button"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
          onClick={() => setCollapsed(!collapsed)}
          className="w-7 h-7 rounded-md text-text-secondary hover:bg-surface-hover hover:text-text-primary inline-flex items-center justify-center"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
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
          <div className="my-2 h-px bg-border-subtle" aria-hidden="true" />
        ) : (
          <div
            role="separator"
            className="px-2 pt-4 pb-1 text-xs font-medium uppercase tracking-[0.04em] text-text-tertiary"
          >
            Departments
          </div>
        )}

        {DEPARTMENT_NAV.map((entry) => (
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
          />
        ))}
      </div>

      <footer className="flex-shrink-0 border-t border-border-subtle px-2 py-2 space-y-0.5">
        <NavItem
          label="Settings"
          icon={Settings}
          path="/settings"
          collapsed={collapsed}
          hasUnread={false}
        />
        <div
          className={[
            "flex items-center gap-[10px] px-2 py-[10px]",
            collapsed ? "justify-center" : "",
          ].join(" ")}
        >
          <span className="w-[18px] h-[18px] rounded-full bg-accent-primary inline-flex items-center justify-center">
            <User size={11} className="text-white" strokeWidth={1.5} />
          </span>
          {collapsed ? null : (
            <span className="text-sm text-text-secondary truncate">Account</span>
          )}
        </div>
      </footer>
    </nav>
  );
}
