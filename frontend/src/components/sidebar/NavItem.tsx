import type { JSX } from "react";
import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";

export interface NavItemProps {
  label: string;
  icon: LucideIcon;
  path: string;
  collapsed: boolean;
  hasUnread: boolean;
}

export function NavItem({
  label,
  icon: Icon,
  path,
  collapsed,
  hasUnread,
}: NavItemProps): JSX.Element {
  return (
    <NavLink
      to={path}
      end={path === "/"}
      aria-label={collapsed ? label : undefined}
      className={({ isActive }) =>
        [
          "relative flex items-center gap-[10px] rounded-md w-full",
          "transition-colors duration-normal ease-out",
          collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
          isActive ? "" : "",
        ]
          .filter(Boolean)
          .join(" ")
      }
      style={({ isActive }: { isActive: boolean }) => ({
        background: isActive ? "var(--color-sidebar-active)" : "transparent",
        color: isActive
          ? "var(--color-sidebar-text-strong)"
          : "var(--color-sidebar-text)",
      })}
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              aria-hidden="true"
              className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5"
              style={{ background: "var(--color-accent-primary)" }}
            />
          ) : null}
          <span className="relative inline-flex">
            <Icon
              size={16}
              strokeWidth={1.5}
              style={{ stroke: isActive ? "var(--color-accent-primary)" : "currentColor" }}
            />
            {hasUnread ? (
              <span
                data-testid="nav-item-dot"
                className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full"
                style={{
                  background: "var(--color-accent-primary)",
                  boxShadow: "0 0 6px rgba(212,255,0,0.7)",
                }}
              />
            ) : null}
          </span>
          {collapsed ? null : (
            <span className="text-[13px] font-display truncate">{label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}
