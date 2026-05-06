import { useEffect, useState } from "react";
import type { JSX } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Cpu } from "lucide-react";

import {
  getModelsRoster,
  getPrefs,
  updatePrefs,
  type ModelsRoster,
  type RosterEntry,
} from "../../api/settings";

const TIER_ORDER: ReadonlyArray<keyof ModelsRoster> = ["thinking", "everyday", "quick"];
const TIER_LABEL: Record<keyof ModelsRoster, string> = {
  thinking: "Thinking",
  everyday: "Everyday",
  quick: "Quick",
};

/** User-level preferred LLM. Selection persists across all chats and
 *  departments (writes ``user_prefs.preferred_model_id``). Visual: design's
 *  bordered mono-10px pill in the composer toolbar with left icon + chevron. */
export function ModelPicker(): JSX.Element | null {
  const [roster, setRoster] = useState<ModelsRoster | null>(null);
  const [modelId, setModelId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getModelsRoster().catch(() => null),
      getPrefs().catch(() => null),
    ]).then(([r, p]) => {
      if (cancelled) return;
      setRoster(r);
      setModelId(p?.preferred_model_id ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!roster) return null;

  const enabledByTier = TIER_ORDER.map((tier) => ({
    tier,
    items: roster[tier].filter((m) => m.is_enabled),
  })).filter((g) => g.items.length > 0);
  const enabledFlat = enabledByTier.flatMap((g) => g.items);
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
          aria-label="Choose LLM model"
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
          {enabledByTier.map((group, gi) => (
            <DropdownMenu.Group key={group.tier}>
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
                {TIER_LABEL[group.tier]}
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
