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
          "relative flex items-center gap-[10px] rounded-md px-2 py-[10px] w-full",
          "transition-colors duration-[120ms]",
          collapsed ? "justify-center" : "",
          isActive
            ? "bg-accent-subtle text-text-primary"
            : "text-text-secondary hover:bg-surface-hover hover:text-text-primary",
        ]
          .filter(Boolean)
          .join(" ")
      }
    >
      {({ isActive }) => (
        <>
          {isActive ? (
            <span
              aria-hidden="true"
              className="absolute left-0 top-2 bottom-2 w-[3px] rounded-full bg-accent-primary"
            />
          ) : null}
          <span className="relative inline-flex">
            <Icon
              size={18}
              strokeWidth={1.5}
              className={isActive ? "text-accent-primary" : "text-icon-primary"}
            />
            {hasUnread ? (
              <span
                data-testid="nav-item-dot"
                className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full bg-accent-primary"
              />
            ) : null}
          </span>
          {collapsed ? null : (
            <span className="text-sm font-medium truncate">{label}</span>
          )}
        </>
      )}
    </NavLink>
  );
}
