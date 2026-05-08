import type { JSX } from "react";
import { useState } from "react";
import { ChevronDown, Menu, Plus } from "lucide-react";

import { useMobileNav } from "../../layouts/MobileNavContext";
import { useChatHeader } from "../../layouts/ChatHeaderContext";
import { ChatHistoryPopover } from "../chat/ChatHistoryPopover";
import { LivePill } from "./LivePill";
import { ThemeToggle } from "./ThemeToggle";

export interface TopBarProps {
  crumbs: string[];
  stamps?: string[];
  live?: boolean;
}

export function TopBar({
  crumbs,
  stamps = [],
  live = false,
}: TopBarProps): JSX.Element {
  const last = crumbs[crumbs.length - 1];
  const head = crumbs.slice(0, -1);
  const { setOpen } = useMobileNav();
  const chatHeader = useChatHeader();
  const [popoverOpen, setPopoverOpen] = useState(false);
  const showChatCrumb = Boolean(chatHeader && chatHeader.chatTitle);

  return (
    <div className="flex items-center gap-[14px] border-b border-border-subtle bg-bg-base px-7 py-[14px]">
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
        <strong className="font-semibold text-text-primary">{last}</strong>
        {showChatCrumb && chatHeader ? (
          <span className="relative flex items-center gap-2">
            <span className="text-text-tertiary">/</span>
            <button
              type="button"
              aria-haspopup="menu"
              aria-expanded={popoverOpen}
              onClick={() => setPopoverOpen((v) => !v)}
              className="flex items-center gap-1 font-semibold text-text-primary hover:text-text-primary"
            >
              <span className="max-w-[260px] truncate">
                {chatHeader.chatTitle}
              </span>
              <ChevronDown size={12} strokeWidth={1.5} aria-hidden />
            </button>
            {popoverOpen ? (
              <ChatHistoryPopover
                departmentId={chatHeader.departmentId}
                activeSessionId={chatHeader.activeSessionId}
                onSelect={(id) => {
                  chatHeader.onSelect(id);
                  setPopoverOpen(false);
                }}
                onActiveDeleted={() => {
                  chatHeader.onCreate();
                  setPopoverOpen(false);
                }}
                onClose={() => setPopoverOpen(false)}
              />
            ) : null}
          </span>
        ) : null}
      </nav>
      <div className="ml-auto flex items-center gap-[14px]">
        {live && <LivePill />}
        {chatHeader ? (
          <button
            type="button"
            onClick={chatHeader.onCreate}
            className="inline-flex items-center gap-1 rounded-md border border-border-subtle px-2 py-1 text-xs font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary"
          >
            <Plus size={12} strokeWidth={2} aria-hidden />
            New Chat
          </button>
        ) : null}
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
