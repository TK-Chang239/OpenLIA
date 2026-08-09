import { useEffect, useMemo, useState } from "react";
import type { JSX } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Cpu } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  getEnabledModels,
  getPrefs,
  updatePrefs,
  type RosterEntry,
} from "../../api/settings";

/** User-level preferred LLM. Selection persists across all chats and
 *  departments (writes ``user_prefs.preferred_model_id``). Visual: design's
 *  bordered mono-10px pill in the composer toolbar with left icon + chevron. */
export function ModelPicker(): JSX.Element | null {
  const { t } = useTranslation();
  const [models, setModels] = useState<RosterEntry[] | null>(null);
  const [modelId, setModelId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getEnabledModels().catch(() => null),
      getPrefs().catch(() => null),
    ]).then(([m, p]) => {
      if (cancelled) return;
      setModels(m);
      const saved = p?.preferred_model_id ?? null;
      setModelId(saved);
      // Persist-on-load: the pill shows the first enabled model as selected
      // even when nothing is saved, but the resolver only honors a persisted
      // preferred_model_id. Adopt the displayed default so what the user sees
      // is what actually gets used — no per-department slot default required.
      const enabled = (m ?? []).filter((x) => x.is_enabled);
      const validSaved = saved !== null && enabled.some((x) => x.id === saved);
      if (enabled.length > 0 && !validSaved) {
        const fallback = enabled[0].id;
        updatePrefs({ preferred_model_id: fallback })
          .then(() => {
            if (!cancelled) setModelId(fallback);
          })
          .catch(() => {
            // best-effort; user can still pick manually.
          });
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    if (!models) return [];
    const byKind = new Map<string, RosterEntry[]>();
    for (const m of models) {
      if (!m.is_enabled) continue;
      const key = m.provider_kind;
      const arr = byKind.get(key) ?? [];
      arr.push(m);
      byKind.set(key, arr);
    }
    return Array.from(byKind.entries()).map(([kind, items]) => ({
      kind,
      items,
    }));
  }, [models]);

  if (!models) return null;

  const enabledFlat = grouped.flatMap((g) => g.items);
  if (enabledFlat.length === 0) return null;

  const knownIds = new Set(enabledFlat.map((m) => m.id));
  const selected = modelId && knownIds.has(modelId) ? modelId : enabledFlat[0].id;
  const selectedModel = enabledFlat.find((m) => m.id === selected) ?? enabledFlat[0];

  const handleSelect = async (next: string) => {
    if (next === selected) return;
    setBusy(true);
    try {
      await updatePrefs({ preferred_model_id: next });
      setModelId(next);
    } catch {
      // swallow; user can retry.
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={t("chat.aria_choose_model")}
          disabled={busy}
          className="inline-flex items-center gap-[6px] rounded-sm border px-2 py-[4px] font-mono text-[10px] uppercase transition-colors duration-normal ease-out disabled:opacity-60 hover:border-border-strong hover:text-text-primary"
          style={{
            letterSpacing: "0.06em",
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-base)",
            color: "var(--color-text-secondary)",
          }}
        >
          <Cpu size={10} strokeWidth={1.5} aria-hidden />
          <span className="truncate max-w-[140px]">{selectedModel.display_name}</span>
          <ChevronDown size={10} strokeWidth={1.5} aria-hidden />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={6}
          className="z-50 min-w-[220px] overflow-hidden rounded-md border p-1"
          style={{
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-elevated)",
            boxShadow: "var(--shadow-md)",
          }}
        >
          {grouped.map((group, gi) => (
            <DropdownMenu.Group key={group.kind}>
              {gi > 0 ? (
                <DropdownMenu.Separator
                  className="my-1 h-px"
                  style={{ background: "var(--color-border-subtle)" }}
                />
              ) : null}
              <DropdownMenu.Label
                className="px-2 pt-1 pb-[2px] font-mono text-[9px] uppercase"
                style={{
                  letterSpacing: "var(--tracking-micro)",
                  color: "var(--color-text-tertiary)",
                }}
              >
                {group.kind}
              </DropdownMenu.Label>
              {group.items.map((m: RosterEntry) => {
                const active = m.id === selected;
                return (
                  <DropdownMenu.Item
                    key={m.id}
                    onSelect={() => {
                      void handleSelect(m.id);
                    }}
                    className="flex cursor-pointer items-center justify-between rounded-sm px-2 py-[6px] text-[12px] outline-none data-[highlighted]:bg-surface-hover"
                    style={{
                      color: active
                        ? "var(--color-text-primary)"
                        : "var(--color-text-secondary)",
                    }}
                  >
                    <span className="truncate">{m.display_name}</span>
                    {active ? (
                      <span
                        aria-hidden="true"
                        className="ml-2 inline-block h-1.5 w-1.5 rounded-full"
                        style={{ background: "var(--color-accent-primary)" }}
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
