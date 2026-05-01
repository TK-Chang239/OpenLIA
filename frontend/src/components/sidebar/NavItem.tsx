import type { JSX } from "react";
import { NavLink } from "react-router-dom";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { LucideIcon } from "lucide-react";

export interface NavItemProps {
  label: string;
  icon: LucideIcon;
  path: string;
  collapsed: boolean;
  hasUnread: boolean;
  /**
   * When set, the item is rendered muted (lower opacity) and a tooltip
   * with this reason is attached. The link itself remains active so the
   * user can still navigate to the page (which surfaces a banner with the
   * same reason and a CTA back to Settings).
   */
  disabledReason?: string | null;
}

const TOOLTIP_DELAY_MS = 300;

function LinkBody({
  label,
  icon: Icon,
  path,
  collapsed,
  hasUnread,
  disabledReason,
}: NavItemProps): JSX.Element {
  const isDisabled = !!disabledReason;
  return (
    <NavLink
      to={path}
      end={path === "/"}
      aria-label={collapsed ? label : undefined}
      aria-disabled={isDisabled || undefined}
      data-disabled={isDisabled || undefined}
      title={isDisabled ? (disabledReason ?? undefined) : undefined}
      className={({ isActive }) =>
        [
          "relative flex items-center gap-[10px] rounded-md w-full",
          "transition-colors duration-normal ease-out",
          collapsed ? "justify-center px-0 py-[9px]" : "px-[10px] py-[9px]",
          isActive ? "" : "",
          isDisabled ? "opacity-50" : "",
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

export function NavItem(props: NavItemProps): JSX.Element {
  if (!props.collapsed) {
    return <LinkBody {...props} />;
  }

  // Collapsed mode: wrap in Radix Tooltip so hovered icons show their label.
  // Radix wires aria-describedby + role="tooltip" automatically.
  return (
    <Tooltip.Provider delayDuration={TOOLTIP_DELAY_MS}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <span className="block">
            <LinkBody {...props} />
          </span>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={8}
            role="tooltip"
            className="z-50 rounded-md px-2 py-1 font-mono text-[10px] uppercase"
            style={{
              background: "var(--color-bg-elevated)",
              color: "var(--color-text-primary)",
              border: "1px solid var(--color-border-subtle)",
              letterSpacing: "var(--tracking-label)",
            }}
          >
            {props.label}
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  );
}
