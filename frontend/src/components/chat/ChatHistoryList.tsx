import { useEffect, useMemo, useState } from "react";
import { Pin, Archive, ArchiveRestore, Trash, Pencil, Search, Paperclip } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  type ChatSession,
  type Department,
  deleteSession,
  listSessions,
  patchSession,
} from "../../api/chat";
import type { ReportListItem } from "../../api/reports";
import { departmentLabel } from "../../lib/department-colors";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  department: Department;
  activeSessionId: string | null;
  onSelect: (sessionId: string) => void;
  /** Invoked after the active session is deleted, so the host can switch
   *  to a fresh session. Passed the deleted id. */
  onActiveDeleted?: (deletedId: string) => void;
  /** Imperative refresh trigger from the parent (e.g. after creating a
   *  session in the TopBar). Bumping this number re-fetches the list. */
  refreshKey?: number;
  /** Lookup map used to resolve attached_report_id → report title. */
  reportsById?: Record<string, ReportListItem>;
}

function displayTitle(
  session: ChatSession,
  reportsById: Record<string, ReportListItem>,
  discussionPrefix: string,
): string {
  if (session.attached_report_id && reportsById[session.attached_report_id]) {
    return `${discussionPrefix}: ${reportsById[session.attached_report_id].title}`;
  }
  return session.title || departmentLabel(session.department);
}

const SEARCH_DEBOUNCE_MS = 250;

export function ChatHistoryList({
  department,
  activeSessionId,
  onSelect,
  onActiveDeleted,
  refreshKey = 0,
  reportsById = {},
}: Props): JSX.Element {
  const { t } = useTranslation();
  const [items, setItems] = useState<ChatSession[] | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [renameError, setRenameError] = useState<{ id: string; message: string } | null>(null);
  const [showArchived, setShowArchived] = useState<boolean>(false);
  const [searchInput, setSearchInput] = useState<string>("");
  const [debouncedQuery, setDebouncedQuery] = useState<string>("");
  const [pendingDelete, setPendingDelete] = useState<ChatSession | null>(null);

  useEffect(() => {
    setItems(null);
    setSearchInput("");
    setDebouncedQuery("");
  }, [department]);

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
  }, [department, debouncedQuery, refreshKey]);

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
    setItems((prev) =>
      prev ? prev.map((row) => (row.id === s.id ? { ...row, title: trimmed } : row)) : prev,
    );
    try {
      await patchSession(s.id, { title: trimmed });
      setRenameError(null);
    } catch (err) {
      setItems((prev) =>
        prev
          ? prev.map((row) => (row.id === s.id ? { ...row, title: previousTitle } : row))
          : prev,
      );
      setRenameError({
        id: s.id,
        message: err instanceof Error ? err.message : t("chat.rename_aria"),
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
            aria-label={t("chat.rename_session_aria")}
            aria-invalid={showError ? true : undefined}
            className={`flex-1 rounded bg-[--color-bg-input] px-1 py-0.5 text-[--color-text-primary] outline-none ${showError ? "underline decoration-[--color-feedback-error] decoration-wavy" : ""}`}
          />
        ) : (
          <button
            type="button"
            onClick={() => onSelect(s.id)}
            className="flex min-w-0 flex-1 items-center gap-1 truncate text-left"
            title={showError ? renameError?.message : undefined}
          >
            {s.attached_report_id && (
              <span
                data-testid="attached-report-icon"
                title={t("chat.discussing_report")}
                className="shrink-0 text-[--color-text-tertiary]"
              >
                <Paperclip size={11} aria-hidden />
              </span>
            )}
            <span className="truncate">{displayTitle(s, reportsById, t("chat.discussion_prefix"))}</span>
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
            aria-label={t("chat.rename_aria")}
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
            aria-label={s.is_pinned ? t("chat.unpin_aria") : t("chat.pin_aria")}
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
            aria-label={s.is_archived ? t("chat.unarchive_aria") : t("chat.archive_aria")}
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
            aria-label={t("chat.delete_aria")}
            onClick={() => setPendingDelete(s)}
            className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
          >
            <Trash size={12} />
          </button>
        </div>
      </li>
    );
  };

  const archivedHeadingId = "drawer-archived-heading";

  return (
    <>
      <div className="px-3 pb-2">
        <label className="relative flex items-center">
          <Search
            size={12}
            aria-hidden
            className="absolute left-2 text-[--color-text-tertiary]"
          />
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={t("chat.search_sessions_placeholder")}
            aria-label={t("chat.search_sessions_aria")}
            className="w-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] py-1 pl-7 pr-2 text-xs text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          />
        </label>
      </div>
      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {pinned.length > 0 ? (
          <>
            <h3 className="mt-2 px-2 text-[11px] font-semibold uppercase text-[--color-text-tertiary]">
              {t("chat.section_pinned")}
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
              {t("chat.section_recent")}
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
              <span>{t("chat.section_archived", { count: archived.length })}</span>
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
            {debouncedQuery ? t("chat.no_matching_sessions") : t("chat.no_conversations_yet")}
          </p>
        ) : null}
      </div>
      <ConfirmDialog
        open={pendingDelete !== null}
        title={t("chat.delete_conversation_title")}
        description={
          pendingDelete
            ? t("chat.delete_conversation_description", { title: pendingDelete.title })
            : undefined
        }
        confirmLabel={t("chat.delete_aria")}
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={async () => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (!target) return;
          await deleteSession(target.id);
          if (target.id === activeSessionId && onActiveDeleted) {
            onActiveDeleted(target.id);
          }
          refresh();
        }}
      />
    </>
  );
}

