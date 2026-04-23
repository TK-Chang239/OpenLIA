import { useEffect, useState } from "react";
import { Pin, Archive, Trash, Pencil, Plus } from "lucide-react";
import {
  type ChatSession,
  type Department,
  createSession,
  listSessions,
  patchSession,
  deleteSession,
} from "../../api/chat";

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
  const [items, setItems] = useState<ChatSession[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const refresh = async () => {
    const r = await listSessions();
    setItems(r.items.filter((i) => i.department === department));
  };

  useEffect(() => {
    refresh();
  }, [department]);

  const newChat = async () => {
    const row = await createSession({ department, title: "New chat" });
    await refresh();
    onCreate(row.id);
  };

  const pinned = (items ?? []).filter((i) => i.is_pinned);
  const recent = (items ?? []).filter((i) => !i.is_pinned);

  const SessionRow = ({ s }: { s: ChatSession }) => {
    const active = s.id === activeSessionId;
    const isEditing = editingId === s.id;
    return (
      <li
        className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
          active
            ? "bg-[--color-surface-active] text-[--color-text-primary]"
            : "text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        }`}
      >
        {isEditing ? (
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={async () => {
              if (editTitle.trim()) await patchSession(s.id, { title: editTitle.trim() });
              setEditingId(null);
              refresh();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") setEditingId(null);
            }}
            className="flex-1 rounded bg-[--color-bg-input] px-1 py-0.5 text-[--color-text-primary] outline-none"
          />
        ) : (
          <button
            type="button"
            onClick={() => onSelect(s.id)}
            className="flex-1 truncate text-left"
          >
            {s.title}
          </button>
        )}
        <div className="hidden gap-1 group-hover:flex">
          <button
            type="button"
            aria-label="Rename"
            onClick={() => {
              setEditingId(s.id);
              setEditTitle(s.title);
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Pencil size={12} />
          </button>
          <button
            type="button"
            aria-label={s.is_pinned ? "Unpin" : "Pin"}
            onClick={async () => {
              await patchSession(s.id, { pinned: !s.is_pinned });
              refresh();
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Pin size={12} />
          </button>
          <button
            type="button"
            aria-label="Archive"
            onClick={async () => {
              await patchSession(s.id, { archived: true });
              refresh();
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            <Archive size={12} />
          </button>
          <button
            type="button"
            aria-label="Delete"
            onClick={async () => {
              if (window.confirm(`Delete "${s.title}"? This cannot be undone.`)) {
                await deleteSession(s.id);
                refresh();
              }
            }}
            className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
          >
            <Trash size={12} />
          </button>
        </div>
      </li>
    );
  };

  return (
    <aside className="flex h-full w-60 flex-col border-r border-[--color-border-subtle] bg-[--color-bg-base]">
      <div className="flex items-center justify-between p-3">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-[--color-text-tertiary]">
          Chat history
        </h2>
        <button
          type="button"
          onClick={newChat}
          aria-label="New chat"
          className="flex h-6 w-6 items-center justify-center rounded-md bg-[--color-accent-primary] text-white hover:bg-[--color-accent-hover]"
        >
          <Plus size={14} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {pinned.length > 0 ? (
          <>
            <h3 className="mt-2 px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary]">
              Pinned
            </h3>
            <ul className="mt-1 space-y-0.5">
              {pinned.map((s) => (
                <SessionRow key={s.id} s={s} />
              ))}
            </ul>
          </>
        ) : null}
        {recent.length > 0 ? (
          <>
            <h3 className="mt-4 px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary]">
              Recent
            </h3>
            <ul className="mt-1 space-y-0.5">
              {recent.map((s) => (
                <SessionRow key={s.id} s={s} />
              ))}
            </ul>
          </>
        ) : null}
        {items !== null && items.length === 0 ? (
          <p className="mt-6 px-2 text-xs text-[--color-text-tertiary]">No conversations yet.</p>
        ) : null}
      </div>
    </aside>
  );
}
