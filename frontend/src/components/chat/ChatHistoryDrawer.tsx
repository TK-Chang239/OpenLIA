import { useState } from "react";
import { Plus } from "lucide-react";
import { useTranslation } from "react-i18next";

import { type Department, createSession } from "../../api/chat";
import { ChatHistoryList } from "./ChatHistoryList";

interface Props {
  department: Department;
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: (sessionId: string) => void;
}

export function ChatHistoryDrawer({
  department,
  activeSessionId,
  onSelect,
  onCreate,
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [refreshKey, setRefreshKey] = useState(0);

  const newChat = async () => {
    const row = await createSession({ department, title: "New chat" });
    setRefreshKey((k) => k + 1);
    onCreate(row.id);
  };

  return (
    <aside className="flex h-full w-60 flex-col border-r border-[--color-border-subtle] bg-[--color-bg-base]">
      <div className="flex items-center justify-between p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[--color-text-tertiary]">
          {t("chat.history_title")}
        </h2>
        <button
          type="button"
          onClick={newChat}
          aria-label={t("chat.aria_new_chat")}
          className="flex h-6 w-6 items-center justify-center rounded-md bg-[--color-accent-primary] text-white hover:bg-[--color-accent-hover]"
        >
          <Plus size={14} />
        </button>
      </div>
      <ChatHistoryList
        department={department}
        activeSessionId={activeSessionId}
        onSelect={onSelect}
        refreshKey={refreshKey}
      />
    </aside>
  );
}
