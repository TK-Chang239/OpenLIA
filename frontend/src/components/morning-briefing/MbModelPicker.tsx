/**
 * MbModelPicker — single-slot model picker pill for Morning Briefing.
 *
 * Forks EuModelPicker. Surfaces the chosen RosterEntry's provider_kind +
 * model_ref via ``onChange`` and seeds the trigger from a passed-in value
 * so a schedule's saved binding shows up when editing. Persists the last
 * pick under ``mb.model_id`` for new-schedule defaults.
 */
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { AlertTriangle, ChevronDown, Cpu } from "lucide-react";
import { type JSX, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { type RosterEntry, getEnabledModels } from "../../api/settings";

const LS_KEY = "mb.model_id";

export interface MbModelSelection {
  id: string;
  provider_kind: string;
  model: string;
  display_name: string;
}

interface Props {
  onChange: (selection: MbModelSelection | null) => void;
  /** Pre-select by provider_kind + model_ref (a schedule's saved binding). */
  value?: { provider_kind: string | null; model: string | null };
}

function entryToSelection(entry: RosterEntry): MbModelSelection {
  return {
    id: entry.id,
    provider_kind: entry.provider_kind,
    model: entry.model_ref,
    display_name: entry.display_name,
  };
}

export function MbModelPicker({ onChange, value }: Props): JSX.Element | null {
  const { t } = useTranslation();
  const [models, setModels] = useState<RosterEntry[] | null>(null);
  const [modelId, setModelId] = useState<string | null>(null);
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
    return Array.from(byKind.entries()).map(([kind, items]) => ({
      kind,
      items,
    }));
  }, [enabledFlat]);

  // Resolve initial selection: explicit `value` binding → localStorage →
  // first enabled model.
  const selected = useMemo(() => {
    if (enabledFlat.length === 0) return null;
    if (modelId) {
      const m = enabledFlat.find((e) => e.id === modelId);
      if (m) return m;
    }
    if (value?.provider_kind && value?.model) {
      const bound = enabledFlat.find(
        (e) =>
          e.provider_kind === value.provider_kind &&
          e.model_ref === value.model,
      );
      if (bound) return bound;
    }
    if (typeof window !== "undefined") {
      try {
        const ls = window.localStorage.getItem(LS_KEY);
        const m = ls ? enabledFlat.find((e) => e.id === ls) : null;
        if (m) return m;
      } catch {
        /* localStorage disabled */
      }
    }
    return enabledFlat[0];
  }, [enabledFlat, modelId, value?.provider_kind, value?.model]);

  useEffect(() => {
    if (selected === null) {
      onChange(null);
      return;
    }
    onChange(entryToSelection(selected));
    try {
      window.localStorage.setItem(LS_KEY, selected.id);
    } catch {
      /* localStorage may be disabled */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected?.id]);

  if (models === null) {
    return (
      <span className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-tertiary]">
        <Cpu size={10} strokeWidth={1.5} />{" "}
        {t("morning_briefing.model_picker.loading")}
      </span>
    );
  }

  if (loadError || enabledFlat.length === 0) {
    return (
      <a
        href="/settings/models"
        title={loadError ?? t("morning_briefing.model_picker.empty")}
        data-testid="mb-model-picker-empty"
        className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.06)] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-feedback-warning] hover:bg-[rgba(255,180,0,0.10)]"
      >
        <AlertTriangle size={10} strokeWidth={2} />{" "}
        {t("morning_briefing.model_picker.empty")}
      </a>
    );
  }

  if (selected === null) return null;

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={t("morning_briefing.model_picker.aria")}
          data-testid="mb-model-picker-trigger"
          className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-secondary] transition-colors hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
        >
          <Cpu size={10} strokeWidth={1.5} aria-hidden />
          <span className="truncate max-w-[160px]">
            {selected.display_name}
          </span>
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
                    data-testid={`mb-model-option-${m.id}`}
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
