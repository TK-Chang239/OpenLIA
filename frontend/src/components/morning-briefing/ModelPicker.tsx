import { useEffect, useMemo, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import {
  getDepartmentModelPref,
  setDepartmentModelPref,
} from "../../api/department-model-pref";
import { getEnabledModels, type RosterEntry } from "../../api/settings";

interface Props {
  departmentSlug: string;
  onError?: (msg: string) => void;
}

export function ModelPicker({ departmentSlug, onError }: Props) {
  const { t } = useTranslation();
  const [models, setModels] = useState<RosterEntry[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [hasOverride, setHasOverride] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getEnabledModels(),
      getDepartmentModelPref(departmentSlug),
    ])
      .then(([roster, pref]) => {
        if (cancelled) return;
        setModels(roster.filter((m) => m.is_enabled));
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

  const grouped = useMemo(() => {
    const byKind = new Map<string, RosterEntry[]>();
    for (const m of models) {
      const arr = byKind.get(m.provider_kind) ?? [];
      arr.push(m);
      byKind.set(m.provider_kind, arr);
    }
    return Array.from(byKind.entries()).map(([kind, items]) => ({ kind, items }));
  }, [models]);

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
    ? t("morning_briefing.model_picker.fallback_title")
    : t("morning_briefing.model_picker.default_title");
  const current = models.find((m) => m.id === selected);
  const triggerLabel = loading
    ? t("morning_briefing.model_picker.loading")
    : current
      ? current.display_name
      : t("morning_briefing.model_picker.select_model");

  return (
    <div className="relative inline-flex">
      <select
        value={selected}
        onChange={onChange}
        disabled={loading || saving}
        data-testid="mb-model-picker"
        aria-label={t("morning_briefing.model_picker.aria_label")}
        title={title}
        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer disabled:cursor-not-allowed"
      >
        <option value="" disabled>
          {loading
            ? t("morning_briefing.model_picker.loading_models")
            : t("morning_briefing.model_picker.select_a_model")}
        </option>
        {grouped.map((g) => (
          <optgroup key={g.kind} label={g.kind}>
            {g.items.map((m) => (
              <option key={m.id} value={m.id}>
                {m.display_name}
                {usingFallback && m.id === selected
                  ? t("morning_briefing.model_picker.default_suffix")
                  : ""}
              </option>
            ))}
          </optgroup>
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
