import { useEffect, useMemo, useRef, useState } from "react";
import { Pin, Archive, ArchiveRestore, Trash, Pencil, Plus, Search } from "lucide-react";
import {
  type ChatSession,
  type Department,
  createSession,
  listSessions,
  patchSession,
  deleteSession,
} from "../../api/chat";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  department: Department;
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  onCreate: (sessionId: string) => void;
}

const SEARCH_DEBOUNCE_MS = 250;

export function ChatHistoryDrawer({
  department,
  activeSessionId,
  onSelect,
  onCreate,
}: Props): JSX.Element {
  const [items, setItems] = useState<ChatSession[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [renameError, setRenameError] = useState<{ id: string; message: string } | null>(null);
  const [showArchived, setShowArchived] = useState<boolean>(false);
  const [searchInput, setSearchInput] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [pendingDelete, setPendingDelete] = useState<ChatSession | null>(null);

  // Reset list when department changes so stale data never bleeds across.
  useEffect(() => {
    setItems(null);
    setSearchInput("");
    setDebouncedQuery("");
  }, [department]);

  // Debounce the search input.
  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQuery(searchInput.trim()), SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  const refresh = async () => {
    const r = await listSessions({
      department,
      include_archived: true,
      q: debouncedQuery || undefined,
    });
    setItems(r.items);
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [department, debouncedQuery]);

  const newChat = async () => {
    const row = await createSession({ department, title: "New chat" });
    await refresh();
    onCreate(row.id);
  };

  const { pinned, recent, archived } = useMemo(() => {
    const all = items ?? [];
    return {
      pinned: all.filter((i) => !i.is_archived && i.is_pinned),
      recent: all.filter((i) => !i.is_archived && !i.is_pinned),
      archived: all.filter((i) => i.is_archived),
    };
  }, [items]);

  const onRenameCommit = async (s: ChatSession, next: string) => {
    const trimmed = next.trim();
    setEditingId(null);
    if (!trimmed || trimmed === s.title) return;
    const previousTitle = s.title;
    // Optimistic local update.
    setItems((prev) =>
      prev ? prev.map((row) => (row.id === s.id ? { ...row, title: trimmed } : row)) : prev,
    );
    try {
      await patchSession(s.id, { title: trimmed });
      setRenameError(null);
    } catch (err) {
      // Revert.
      setItems((prev) =>
        prev
          ? prev.map((row) => (row.id === s.id ? { ...row, title: previousTitle } : row))
          : prev,
      );
      setRenameError({
        id: s.id,
        message: err instanceof Error ? err.message : "Rename failed",
      });
    }
  };

  const SessionRow = ({ s }: { s: ChatSession }) => {
    const active = s.id === activeSessionId;
    const isEditing = editingId === s.id;
    const showError = renameError?.id === s.id;
    return (
      <li
        className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
          active
            ? "bg-[--color-surface-active] text-[--color-text-primary]"
            : "text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        } ${s.is_archived ? "opacity-70" : ""}`}
      >
        {isEditing ? (
          <input
            autoFocus
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            onBlur={() => onRenameCommit(s, editTitle)}
            onKeyDown={(e) => {
              if (e.key === "Enter") (e.target as HTMLInputElement).blur();
              if (e.key === "Escape") setEditingId(null);
            }}
            aria-label="Rename session"
            aria-invalid={showError ? true : undefined}
            className={`flex-1 rounded bg-[--color-bg-input] px-1 py-0.5 text-[--color-text-primary] outline-none ${showError ? "underline decoration-[--color-feedback-error] decoration-wavy" : ""}`}
          />
        ) : (
          <button
            type="button"
            onClick={() => onSelect(s.id)}
            className="flex-1 truncate text-left"
            title={showError ? renameError?.message : undefined}
          >
            {s.title}
            {showError ? (
              <span className="ml-2 text-[10px] text-[--color-feedback-error]" role="status">
                {renameError?.message}
              </span>
            ) : null}
          </button>
        )}
        <div className="hidden gap-1 group-hover:flex">
          <button
            type="button"
            aria-label="Rename"
            onClick={() => {
              setEditingId(s.id);
              setEditTitle(s.title);
              setRenameError(null);
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
            aria-label={s.is_archived ? "Unarchive" : "Archive"}
            onClick={async () => {
              await patchSession(s.id, { archived: !s.is_archived });
              refresh();
            }}
            className="rounded p-1 hover:bg-[--color-surface-hover]"
          >
            {s.is_archived ? <ArchiveRestore size={12} /> : <Archive size={12} />}
          </button>
          <button
            type="button"
            aria-label="Delete"
            onClick={() => setPendingDelete(s)}
            className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
          >
            <Trash size={12} />
          </button>
        </div>
      </li>
    );
  };

  const searchInputRef = useRef<HTMLInputElement>(null);
  const archivedHeadingId = "drawer-archived-heading";

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
      <div className="px-3 pb-2">
        <label className="relative flex items-center">
          <Search
            size={12}
            aria-hidden
            className="absolute left-2 text-[--color-text-tertiary]"
          />
          <input
            ref={searchInputRef}
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search sessions"
            aria-label="Search chat sessions"
            className="w-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] py-1 pl-7 pr-2 text-xs text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          />
        </label>
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
        {archived.length > 0 ? (
          <>
            <button
              type="button"
              onClick={() => setShowArchived((v) => !v)}
              aria-expanded={showArchived}
              aria-controls={archivedHeadingId}
              className="mt-4 flex w-full items-center justify-between px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary] hover:text-[--color-text-secondary]"
            >
              <span>Archived ({archived.length})</span>
              <span aria-hidden>{showArchived ? "−" : "+"}</span>
            </button>
            {showArchived ? (
              <ul id={archivedHeadingId} className="mt-1 space-y-0.5">
                {archived.map((s) => (
                  <SessionRow key={s.id} s={s} />
                ))}
              </ul>
            ) : null}
          </>
        ) : null}
        {items !== null && items.length === 0 ? (
          <p className="mt-6 px-2 text-xs text-[--color-text-tertiary]">
            {debouncedQuery ? "No matching sessions." : "No conversations yet."}
          </p>
        ) : null}
      </div>
      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete conversation"
        description={
          pendingDelete
            ? `Delete "${pendingDelete.title}"? This cannot be undone.`
            : undefined
        }
        confirmLabel="Delete"
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={async () => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (!target) return;
          await deleteSession(target.id);
          refresh();
        }}
      />
    </aside>
  );
}
