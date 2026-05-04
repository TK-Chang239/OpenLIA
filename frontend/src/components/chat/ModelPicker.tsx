import { useEffect, useState } from "react";
import type { JSX } from "react";

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
 *  departments (writes ``user_prefs.preferred_model_id``). */
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

  const enabled = TIER_ORDER.flatMap((tier) =>
    roster[tier].filter((m) => m.is_enabled),
  );
  if (enabled.length === 0) return null;

  // If the saved preference is missing from the roster (or null), fall back
  // to the first enabled model so the dropdown always shows a real value.
  const knownIds = new Set(enabled.map((m) => m.id));
  const selected = modelId && knownIds.has(modelId) ? modelId : enabled[0].id;

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
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
    <select
      aria-label="Choose LLM model"
      disabled={busy}
      value={selected}
      onChange={handleChange}
      className="h-7 max-w-[200px] truncate rounded-md border border-border-subtle bg-bg-elevated px-2 text-xs text-text-secondary outline-none hover:bg-surface-hover focus:border-yellow-600"
    >
      {TIER_ORDER.map((tier) =>
        roster[tier].filter((m) => m.is_enabled).length === 0 ? null : (
          <optgroup key={tier} label={TIER_LABEL[tier]}>
            {roster[tier]
              .filter((m) => m.is_enabled)
              .map((m: RosterEntry) => (
                <option key={m.id} value={m.id}>
                  {m.display_name}
                </option>
              ))}
          </optgroup>
        ),
      )}
    </select>
  );
}
