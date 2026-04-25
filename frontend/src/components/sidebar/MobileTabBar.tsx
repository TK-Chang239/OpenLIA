import type { JSX } from "react";
import { NavLink } from "react-router-dom";
import { CORE_NAV, DEPARTMENT_NAV } from "./navData";

const TAB_ENTRIES = [
  CORE_NAV[0],
  DEPARTMENT_NAV[0],
  DEPARTMENT_NAV[1],
  DEPARTMENT_NAV[3],
  CORE_NAV[2],
].filter((entry): entry is (typeof CORE_NAV)[number] => Boolean(entry));

export function MobileTabBar(): JSX.Element {
  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed bottom-0 left-0 right-0 z-30 flex h-14 items-stretch border-t border-border-subtle bg-bg-base md:hidden"
    >
      {TAB_ENTRIES.map((entry) => {
        const Icon = entry.icon;
        return (
          <NavLink
            key={entry.id}
            to={entry.path}
            end={entry.path === "/"}
            className="flex flex-1 flex-col items-center justify-center gap-0.5 text-[10px] uppercase"
            style={({ isActive }: { isActive: boolean }) => ({
              color: isActive
                ? "var(--color-accent-primary)"
                : "var(--color-text-secondary)",
              letterSpacing: "var(--tracking-label)",
            })}
          >
            <Icon size={18} strokeWidth={1.5} />
            <span>{entry.label.split(" ")[0]}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}
