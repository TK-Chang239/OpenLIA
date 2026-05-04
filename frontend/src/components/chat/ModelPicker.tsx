import { useEffect, useState } from "react";
import type { JSX } from "react";

import { setSessionModel } from "../../api/chat";
import {
  getEffectiveModel,
  getModelsRoster,
  type EffectiveModel,
  type ModelsRoster,
  type RosterEntry,
} from "../../api/settings";

interface Props {
  sessionId: string;
  departmentId: string;
  /** Per-session override; null = follow tier resolution. */
  modelId: string | null;
  onChange: (modelId: string | null) => void;
}

const TIER_ORDER: ReadonlyArray<keyof ModelsRoster> = ["thinking", "everyday", "quick"];
const TIER_LABEL: Record<keyof ModelsRoster, string> = {
  thinking: "Thinking",
  everyday: "Everyday",
  quick: "Quick",
};

export function ModelPicker({
  sessionId,
  departmentId,
  modelId,
  onChange,
}: Props): JSX.Element | null {
  const [roster, setRoster] = useState<ModelsRoster | null>(null);
  const [effective, setEffective] = useState<EffectiveModel | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getModelsRoster().catch(() => null),
      getEffectiveModel(departmentId).catch(() => null),
    ]).then(([r, e]) => {
      if (cancelled) return;
      setRoster(r);
      setEffective(e);
    });
    return () => {
      cancelled = true;
    };
  }, [departmentId]);

  if (!roster) return null;

  const enabled = TIER_ORDER.flatMap((tier) =>
    roster[tier].filter((m) => m.is_enabled).map((m) => ({ tier, ...m })),
  );
  if (enabled.length === 0) return null;

  const handleChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    const next = value === "__default__" ? null : value;
    setBusy(true);
    try {
      await setSessionModel(sessionId, next);
      onChange(next);
    } catch {
      // Re-fetch effective on failure to keep UI consistent; swallow the
      // error so the picker stays usable for retry.
    } finally {
      setBusy(false);
    }
  };

  const defaultLabel = effective
    ? `Default — ${labelFor(roster, effective.model_id) ?? effective.model_ref}`
    : "Default";

  return (
    <select
      aria-label="Choose LLM model"
      disabled={busy}
      value={modelId ?? "__default__"}
      onChange={handleChange}
      className="h-7 max-w-[180px] truncate rounded-md border border-border-subtle bg-bg-elevated px-2 text-xs text-text-secondary outline-none hover:bg-surface-hover focus:border-yellow-600"
    >
      <option value="__default__">{defaultLabel}</option>
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

function labelFor(roster: ModelsRoster, modelId: string): string | null {
  for (const tier of TIER_ORDER) {
    const hit = roster[tier].find((m) => m.id === modelId);
    if (hit) return hit.display_name;
  }
  return null;
}
