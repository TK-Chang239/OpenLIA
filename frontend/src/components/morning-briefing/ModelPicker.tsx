import { useEffect, useState } from "react";
import { ChevronDown } from "lucide-react";

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
  const current = models.find((m) => m.id === selected);
  const triggerLabel = loading
    ? "Loading…"
    : current
      ? current.label.replace(/\s*\(.*\)\s*$/, "")
      : "Select model…";

  return (
    <div className="relative inline-flex">
      <select
        value={selected}
        onChange={onChange}
        disabled={loading || saving}
        data-testid="mb-model-picker"
        aria-label="Model for Morning Briefing reports"
        title={title}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
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
      <span
        aria-hidden="true"
        className={
          "inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[13px] transition-colors duration-[--duration-normal] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]" +
          (usingFallback ? " italic" : "") +
          (loading || saving ? " opacity-50" : "")
        }
        style={{
          borderColor: "var(--color-border-secondary)",
          color: "var(--color-text-secondary)",
        }}
      >
        <ChevronDown size={13} strokeWidth={1.8} />
        <span className="max-w-[180px] truncate">{triggerLabel}</span>
      </span>
    </div>
  );
}
