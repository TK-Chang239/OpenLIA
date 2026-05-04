import { useEffect, useRef } from "react";

import type { Department } from "../../api/chat";
import { ChatHistoryList } from "./ChatHistoryList";

interface Props {
  departmentId: string;
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onClose: () => void;
  /** Forwarded to the underlying ``ChatHistoryList`` so the host can
   *  switch to a fresh session when the active one is deleted. */
  onActiveDeleted?: (deletedId: string) => void;
  /** Bumped by the host (e.g. TopBar) after creating a session so the
   *  list re-fetches without remounting the popover. */
  refreshKey?: number;
}

export function ChatHistoryPopover({
  departmentId,
  activeSessionId,
  onSelect,
  onClose,
  onActiveDeleted,
  refreshKey = 0,
}: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onMouseDown = (e: MouseEvent) => {
      const node = ref.current;
      if (!node) return;
      if (e.target instanceof Node && node.contains(e.target)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onMouseDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onMouseDown);
    };
  }, [onClose]);

  return (
    <div
      ref={ref}
      role="menu"
      data-testid="chat-history-popover"
      className="absolute left-0 top-full z-50 mt-1 flex max-h-[60vh] w-72 flex-col overflow-hidden rounded-md border border-border-subtle bg-bg-base shadow-lg"
    >
      <ChatHistoryList
        department={departmentId as Department}
        activeSessionId={activeSessionId}
        onSelect={onSelect}
        onActiveDeleted={onActiveDeleted}
        refreshKey={refreshKey}
      />
    </div>
  );
}
