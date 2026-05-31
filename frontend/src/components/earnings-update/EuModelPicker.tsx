/**
 * EuModelPicker — single-slot model picker pill for Earnings Update v2.
 *
 * Visually mirrors the chat ``ModelPicker`` (Radix dropdown, Cpu icon,
 * provider-grouped options) but stores the selection in localStorage
 * under ``eu.v2.model_id`` instead of writing to ``user_prefs``. The
 * v2 engine takes ``provider_kind + model_ref`` directly on its start
 * payload, so the picker surfaces the chosen RosterEntry to the parent
 * via ``onChange`` rather than mutating any global preference.
 */
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { AlertTriangle, ChevronDown, Cpu } from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";

import { type RosterEntry, getEnabledModels } from "../../api/settings";

const LS_KEY = "eu.v2.model_id";

export interface EuModelSelection {
  /** RosterEntry.id — opaque, used only for persistence/equality. */
  id: string;
  /** Provider kind (anthropic/openai/gemini) — wire field. */
  provider_kind: string;
  /** Provider model ref (claude-sonnet-4-6 etc.) — wire field. */
  model: string;
  /** Human label for the trigger and recent-runs decoration. */
  display_name: string;
}

interface Props {
  onChange: (selection: EuModelSelection | null) => void;
}

function entryToSelection(entry: RosterEntry): EuModelSelection {
  return {
    id: entry.id,
    provider_kind: entry.provider_kind,
    model: entry.model_ref,
    display_name: entry.display_name,
  };
}

export function EuModelPicker({ onChange }: Props): JSX.Element | null {
  const [models, setModels] = useState<RosterEntry[] | null>(null);
  const [modelId, setModelId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    try {
      return window.localStorage.getItem(LS_KEY);
    } catch {
      return null;
    }
  });
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEnabledModels()
      .then((m) => {
        if (cancelled) return;
        setModels(m);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setLoadError(e instanceof Error ? e.message : "could not load models");
        setModels([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const enabledFlat = useMemo(
    () => (models ?? []).filter((m) => m.is_enabled),
    [models],
  );

  const grouped = useMemo(() => {
    const byKind = new Map<string, RosterEntry[]>();
    for (const m of enabledFlat) {
      const arr = byKind.get(m.provider_kind) ?? [];
      arr.push(m);
      byKind.set(m.provider_kind, arr);
    }
    return Array.from(byKind.entries()).map(([kind, items]) => ({ kind, items }));
  }, [enabledFlat]);

  const selected = useMemo(() => {
    if (enabledFlat.length === 0) return null;
    const match = modelId ? enabledFlat.find((m) => m.id === modelId) : null;
    return match ?? enabledFlat[0];
  }, [enabledFlat, modelId]);

  // Propagate the resolved selection back up whenever it changes. This
  // covers first-load (default to first enabled model) and explicit
  // user picks. Stays in sync with localStorage too.
  useEffect(() => {
    if (selected === null) {
      onChange(null);
      return;
    }
    onChange(entryToSelection(selected));
    try {
      window.localStorage.setItem(LS_KEY, selected.id);
    } catch {
      /* localStorage may be disabled — pick still works for this session. */
    }
    // onChange identity changes per parent render; we intentionally
    // exclude it so the effect only fires on selection changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

  if (models === null) {
    return (
      <span className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-tertiary]">
        <Cpu size={10} strokeWidth={1.5} /> loading…
      </span>
    );
  }

  if (loadError || enabledFlat.length === 0) {
    return (
      <a
        href="/settings/models"
        title={loadError ?? "No enabled models — open Settings → Models"}
        data-testid="eu-v2-model-picker-empty"
        className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.06)] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-feedback-warning] hover:bg-[rgba(255,180,0,0.10)]"
      >
        <AlertTriangle size={10} strokeWidth={2} /> No model — open Settings
      </a>
    );
  }

  // selected is non-null when enabledFlat.length > 0, but TypeScript
  // can't see through the .find narrowing — guard once for clarity.
  if (selected === null) return null;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Choose model for Earnings Update v2"
          data-testid="eu-v2-model-picker-trigger"
          className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-secondary] transition-colors hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
        >
          <Cpu size={10} strokeWidth={1.5} aria-hidden />
          <span className="truncate max-w-[160px]">{selected.display_name}</span>
          <ChevronDown size={10} strokeWidth={1.5} aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="end"
          sideOffset={6}
          className="z-50 min-w-[240px] overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-1 shadow-[var(--shadow-md)]"
        >
          {grouped.map((group, gi) => (
            <DropdownMenu.Group key={group.kind}>
              {gi > 0 ? (
                <DropdownMenu.Separator className="my-1 h-px bg-[--color-border-subtle]" />
              ) : null}
              <DropdownMenu.Label className="px-2 pt-1 pb-[2px] font-mono text-[9px] uppercase tracking-[var(--tracking-micro)] text-[--color-text-tertiary]">
                {group.kind}
              </DropdownMenu.Label>
              {group.items.map((m) => {
                const active = m.id === selected.id;
                return (
                  <DropdownMenu.Item
                    key={m.id}
                    data-testid={`eu-v2-model-option-${m.id}`}
                    onSelect={() => setModelId(m.id)}
                    className={[
                      "flex cursor-pointer items-center justify-between rounded-sm px-2 py-[6px] text-[12px] outline-none data-[highlighted]:bg-[--color-surface-hover]",
                      active
                        ? "text-[--color-text-primary]"
                        : "text-[--color-text-secondary]",
                    ].join(" ")}
                  >
                    <span className="truncate">{m.display_name}</span>
                    {active ? (
                      <span
                        aria-hidden="true"
                        className="ml-2 inline-block h-1.5 w-1.5 rounded-full bg-[--color-accent-primary]"
                      />
                    ) : null}
                  </DropdownMenu.Item>
                );
              })}
            </DropdownMenu.Group>
          ))}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
