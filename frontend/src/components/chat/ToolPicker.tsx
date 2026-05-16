import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";

import { listConnectors, type ConnectorRow } from "../../api/connectors";
import { listSkills, type SkillSummary } from "../../api/skills";
import { patchSession } from "../../api/chat";

interface Props {
  /** Current chat session id — toggles persist on this row. When null
   *  (no session yet), the picker still renders and tracks state but
   *  skips `patchSession`; the caller is expected to push the final
   *  state via `onChange` once a session is created. */
  sessionId: string | null;
  /** Initial disabled lists from the loaded session row. */
  initialDisabledConnectorIds: string[];
  initialDisabledSkillIds: string[];
  /** Notified whenever a toggle flips, regardless of sessionId. Lets the
   *  parent hold the lifted state so it can be persisted at session
   *  creation. Optional — when omitted (e.g., from ChatInterface where
   *  sessionId is always non-null) the picker operates as before. */
  onChange?: (next: {
    disabledConnectorIds: string[];
    disabledSkillIds: string[];
  }) => void;
}

/** Per-session toggle for connectors + skills. Disabled connectors are
 *  filtered out at the dispatcher (router never sees their tools);
 *  disabled skills drop from the system prompt's skills_menu so the
 *  model never knows they exist this turn. */
export function ToolPicker({
  sessionId,
  initialDisabledConnectorIds,
  initialDisabledSkillIds,
  onChange,
}: Props): JSX.Element | null {
  const [open, setOpen] = useState(false);
  const [connectors, setConnectors] = useState<ConnectorRow[] | null>(null);
  const [skills, setSkills] = useState<SkillSummary[] | null>(null);
  const [disabledConnectors, setDisabledConnectors] = useState<Set<string>>(
    () => new Set(initialDisabledConnectorIds),
  );
  const [disabledSkills, setDisabledSkills] = useState<Set<string>>(
    () => new Set(initialDisabledSkillIds),
  );
  const rootRef = useRef<HTMLDivElement | null>(null);

  // Load the catalogues once. Both are user-installed so they don't change
  // mid-session except via the wizard, which is a different page.
  useEffect(() => {
    let cancelled = false;
    Promise.all([
      listConnectors().catch(() => [] as ConnectorRow[]),
      listSkills().catch(() => [] as SkillSummary[]),
    ])
      .then(([c, s]) => {
        if (cancelled) return;
        setConnectors((c ?? []).filter((row) => row.status === "validated"));
        setSkills((s ?? []).filter((row) => row.enabled));
      })
      .catch(() => {
        // Last-resort guard: a sync throw from a test-time mock that returns
        // a non-thenable would otherwise bubble out as an unhandled rejection.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Re-sync state when the session id changes (e.g. user picks a different
  // conversation from the dropdown).
  useEffect(() => {
    setDisabledConnectors(new Set(initialDisabledConnectorIds));
    setDisabledSkills(new Set(initialDisabledSkillIds));
  }, [sessionId, initialDisabledConnectorIds, initialDisabledSkillIds]);

  // Click-outside closes the panel.
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  if (!connectors || !skills) return null;

  const toggleConnector = async (id: string) => {
    const next = new Set(disabledConnectors);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setDisabledConnectors(next);
    onChange?.({
      disabledConnectorIds: [...next],
      disabledSkillIds: [...disabledSkills],
    });
    if (!sessionId) return;
    try {
      await patchSession(sessionId, { disabled_connector_ids: [...next] });
    } catch {
      // best-effort persist; revert on failure so UI stays in sync.
      setDisabledConnectors(disabledConnectors);
      onChange?.({
        disabledConnectorIds: [...disabledConnectors],
        disabledSkillIds: [...disabledSkills],
      });
    }
  };

  const toggleSkill = async (id: string) => {
    const next = new Set(disabledSkills);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setDisabledSkills(next);
    onChange?.({
      disabledConnectorIds: [...disabledConnectors],
      disabledSkillIds: [...next],
    });
    if (!sessionId) return;
    try {
      await patchSession(sessionId, { disabled_skill_ids: [...next] });
    } catch {
      setDisabledSkills(disabledSkills);
      onChange?.({
        disabledConnectorIds: [...disabledConnectors],
        disabledSkillIds: [...disabledSkills],
      });
    }
  };

  const enabledConnectors = connectors.length - disabledConnectors.size;
  const enabledSkills = skills.length - disabledSkills.size;
  const totalUnits = connectors.length + skills.length;
  const totalEnabled = enabledConnectors + enabledSkills;
  const allConnectorsOff =
    connectors.length > 0 && disabledConnectors.size === connectors.length;

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-xs px-2 py-1 rounded border border-zinc-300 hover:bg-zinc-50"
        aria-expanded={open}
        aria-label="Tool toggles"
      >
        Tools ({totalEnabled}/{totalUnits})
      </button>
      {open ? (
        <div className="absolute bottom-full mb-1 left-0 z-20 w-72 max-h-96 overflow-y-auto rounded border border-zinc-300 bg-white shadow-lg">
          <ToolSection
            label="Connectors"
            empty="No connectors installed."
            rows={connectors.map((c) => ({
              id: c.id,
              label: c.display_name || c.provider_id,
              enabled: !disabledConnectors.has(c.id),
            }))}
            onToggle={toggleConnector}
          />
          <ToolSection
            label="Skills"
            empty="No skills installed."
            rows={skills.map((s) => ({
              id: s.skill_id,
              label: s.display_name || s.skill_id,
              enabled: !disabledSkills.has(s.skill_id),
            }))}
            onToggle={toggleSkill}
          />
          {allConnectorsOff ? (
            <div className="px-3 py-2 text-xs text-amber-700 bg-amber-50 border-t border-amber-200">
              No connectors enabled — Lia will answer without live data.
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

interface SectionRow {
  id: string;
  label: string;
  enabled: boolean;
}

function ToolSection({
  label,
  empty,
  rows,
  onToggle,
}: {
  label: string;
  empty: string;
  rows: SectionRow[];
  onToggle: (id: string) => void;
}): JSX.Element {
  return (
    <div>
      <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-500 bg-zinc-50 border-b border-zinc-200">
        {label}
      </div>
      {rows.length === 0 ? (
        <div className="px-3 py-2 text-xs text-zinc-400">{empty}</div>
      ) : (
        rows.map((row) => (
          <label
            key={row.id}
            className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-zinc-50 cursor-pointer"
          >
            <input
              type="checkbox"
              checked={row.enabled}
              onChange={() => onToggle(row.id)}
            />
            <span className="truncate">{row.label}</span>
          </label>
        ))
      )}
    </div>
  );
}
