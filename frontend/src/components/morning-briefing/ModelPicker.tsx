import { useEffect, useState } from "react";

import {
  getDepartmentModelPref,
  setDepartmentModelPref,
} from "../../api/department-model-pref";
import { getModelsRoster, type RosterEntry } from "../../api/settings";

interface Props {
  departmentSlug: string;
  onError?: (msg: string) => void;
}

interface FlatModel {
  id: string;
  label: string;
  tier: string;
  providerKind: string;
}

function flattenRoster(roster: {
  thinking: RosterEntry[];
  everyday: RosterEntry[];
  quick: RosterEntry[];
}): FlatModel[] {
  const out: FlatModel[] = [];
  for (const tier of ["thinking", "everyday", "quick"] as const) {
    for (const m of roster[tier]) {
      if (!m.is_enabled) continue;
      out.push({
        id: m.id,
        label: `${m.display_name} (${tier})`,
        tier,
        providerKind: m.provider_kind,
      });
    }
  }
  return out;
}

export function ModelPicker({ departmentSlug, onError }: Props) {
  const [models, setModels] = useState<FlatModel[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [hasOverride, setHasOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getModelsRoster(),
      getDepartmentModelPref(departmentSlug),
    ])
      .then(([roster, pref]) => {
        if (cancelled) return;
        setModels(flattenRoster(roster));
        setSelected(pref.model_id ?? pref.effective_model_id ?? "");
        setHasOverride(pref.model_id !== null);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setLoading(false);
        if (onError)
          onError(e instanceof Error ? e.message : "Failed to load model list");
      });
    return () => {
      cancelled = true;
    };
  }, [departmentSlug, onError]);

  const onChange = async (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    setSelected(next);
    if (!next) return;
    setSaving(true);
    try {
      await setDepartmentModelPref(departmentSlug, next);
      setHasOverride(true);
    } catch (err) {
      if (onError)
        onError(err instanceof Error ? err.message : "Failed to save model preference");
    } finally {
      setSaving(false);
    }
  };

  const usingFallback = !loading && !hasOverride && selected !== "";
  const title = usingFallback
    ? "Using your default model. Pick one to override for this department."
    : "Pick the model used for this department's reports.";

  return (
    <select
      value={selected}
      onChange={onChange}
      disabled={loading || saving}
      data-testid="mb-model-picker"
      className={
        "text-xs border border-border-subtle rounded-md px-2 py-1 bg-bg-elevated text-text-primary disabled:opacity-50" +
        (usingFallback ? " italic text-muted-foreground" : "")
      }
      aria-label="Model for Morning Briefing reports"
      title={title}
    >
      <option value="" disabled>
        {loading ? "Loading models…" : "Select a model…"}
      </option>
      {models.map((m) => (
        <option key={m.id} value={m.id}>
          {m.label}
          {usingFallback && m.id === selected ? " — default" : ""}
        </option>
      ))}
    </select>
  );
}
