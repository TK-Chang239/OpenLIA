import type { JSX } from "react";
import { Menu } from "lucide-react";
import { ThemeToggle } from "./ThemeToggle";
import { LivePill } from "./LivePill";
import { useMobileNav } from "../../layouts/MobileNavContext";

export interface TopBarProps {
  crumbs: string[];
  stamps?: string[];
  live?: boolean;
}

export function TopBar({ crumbs, stamps = [], live = false }: TopBarProps): JSX.Element {
  const last = crumbs[crumbs.length - 1];
  const head = crumbs.slice(0, -1);
  const { setOpen } = useMobileNav();
  return (
    <div
      className="flex items-center gap-[14px] px-7 py-[14px] border-b border-border-subtle bg-bg-base"
    >
      <button
        type="button"
        aria-label="Open navigation"
        onClick={() => setOpen(true)}
        className="md:hidden inline-flex items-center justify-center rounded-md p-1.5 text-text-secondary hover:text-text-primary"
      >
        <Menu size={18} strokeWidth={1.5} />
      </button>
      <nav
        aria-label="Breadcrumb"
        className="flex items-center gap-2 font-mono text-[10px] uppercase text-text-secondary"
        style={{ letterSpacing: "var(--tracking-label)" }}
      >
        {head.map((c) => (
          <span key={c} className="flex items-center gap-2">
            {c}
            <span className="text-text-tertiary">/</span>
          </span>
        ))}
        <strong className="text-text-primary font-semibold">{last}</strong>
      </nav>
      <div className="ml-auto flex items-center gap-[14px]">
        {live && <LivePill />}
        {stamps.map((s) => (
          <span
            key={s}
            className="font-mono text-[10px] uppercase text-text-tertiary"
            style={{ letterSpacing: "var(--tracking-label)" }}
          >
            {s}
          </span>
        ))}
        <ThemeToggle />
      </div>
    </div>
  );
}
