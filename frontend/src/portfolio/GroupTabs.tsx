import { Plus } from "lucide-react";
import { useState } from "react";

import { GroupContextMenu } from "./GroupContextMenu";

export const ALL_GROUP = "__ALL__";

export interface GroupTabsProps {
  readonly groups: readonly string[];
  readonly active: string;
  readonly onSelect: (group: string) => void;
  readonly onCreate: (name: string) => void;
  readonly onRename: (oldName: string, newName: string) => void;
  readonly onDelete: (name: string) => void;
}

export function GroupTabs({
  groups,
  active,
  onSelect,
  onCreate,
  onRename,
  onDelete,
}: GroupTabsProps): JSX.Element {
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState("");
  const [menuFor, setMenuFor] = useState<string | null>(null);

  const submitCreate = () => {
    const name = draft.trim();
    if (name) onCreate(name);
    setDraft("");
    setCreating(false);
  };

  return (
    <div role="tablist" className="flex items-center gap-1 flex-wrap" data-testid="group-tabs">
      <button
        type="button"
        role="tab"
        aria-selected={active === ALL_GROUP}
        onClick={() => onSelect(ALL_GROUP)}
        className={`px-3 py-1 text-sm rounded-[--radius-sm] ${
          active === ALL_GROUP
            ? "bg-[--color-surface-hover] text-[--color-text-primary]"
            : "text-[--color-text-tertiary]"
        }`}
        data-testid="group-tab-all"
      >
        All
      </button>
      {groups.map((g) => (
        <div key={g} className="relative">
          <button
            type="button"
            role="tab"
            aria-selected={active === g}
            onClick={() => onSelect(g)}
            onContextMenu={(e) => {
              e.preventDefault();
              setMenuFor(g);
            }}
            className={`px-3 py-1 text-sm rounded-[--radius-sm] ${
              active === g
                ? "bg-[--color-surface-hover] text-[--color-text-primary]"
                : "text-[--color-text-tertiary]"
            }`}
            data-testid={`group-tab-${g}`}
          >
            {g}
          </button>
          {menuFor === g ? (
            <GroupContextMenu
              group={g}
              onRename={(name) => {
                const next = window.prompt("Rename group", name);
                if (next && next.trim()) onRename(name, next.trim());
              }}
              onReorder={() => {
                /* drag handled at shell level for v1 */
              }}
              onDelete={(name) => onDelete(name)}
              onClose={() => setMenuFor(null)}
            />
          ) : null}
        </div>
      ))}
      {creating ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={submitCreate}
          onKeyDown={(e) => {
            if (e.key === "Enter") submitCreate();
            if (e.key === "Escape") {
              setDraft("");
              setCreating(false);
            }
          }}
          className="px-2 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
          data-testid="group-tab-new-input"
          placeholder="New group"
        />
      ) : (
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="inline-flex items-center gap-1 px-2 py-1 text-xs text-[--color-text-tertiary] hover:text-[--color-text-primary]"
          data-testid="group-tab-new"
        >
          <Plus size={12} aria-hidden="true" /> New Group
        </button>
      )}
    </div>
  );
}
