import { useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import type { ModelEntry } from "./RegisterModelsScreen";

interface Props {
  totalSteps: number;
  enabledDepartmentIds: string[];
  systemRoleIds: string[];
  registeredModels: ModelEntry[];
  initialDepartmentDefaults?: Record<string, string>;
  initialSystemRoleDefaults?: Record<string, string>;
  onBack: () => void;
  onSubmit: (payload: {
    department_defaults: Record<string, string>;
    system_role_defaults: Record<string, string>;
  }) => Promise<void> | void;
  loading?: boolean;
  submitError?: string | null;
}

function humanize(id: string): string {
  return id.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

const SYSTEM_ROLE_DESCRIPTIONS: Record<string, string> = {
  ai_review: "Reviews your wizard configuration and flags risks before saving.",
  connector_agentic_resolver:
    "Multi-step agent that identifies the right connector when no spec is on file.",
  connector_spec_adapter:
    "Translates a connector spec into the exact request and response shape at runtime.",
  graph_extraction:
    "Pulls entities and relationships from your sessions into the memory graph.",
  graph_summarization:
    "Condenses memory-graph clusters into short summaries used for recall.",
};

export function AssignDefaultsScreen({
  totalSteps,
  enabledDepartmentIds,
  systemRoleIds,
  registeredModels,
  initialDepartmentDefaults,
  initialSystemRoleDefaults,
  onBack,
  onSubmit,
  loading,
  submitError,
}: Props) {
  const [deptDefaults, setDeptDefaults] = useState<Record<string, string>>(
    initialDepartmentDefaults ?? {},
  );
  const [roleDefaults, setRoleDefaults] = useState<Record<string, string>>(
    initialSystemRoleDefaults ?? {},
  );

  const allFilled = useMemo(() => {
    const deptsOk = enabledDepartmentIds.every((d) => Boolean(deptDefaults[d]));
    const rolesOk = systemRoleIds.every((r) => Boolean(roleDefaults[r]));
    return deptsOk && rolesOk;
  }, [enabledDepartmentIds, systemRoleIds, deptDefaults, roleDefaults]);

  const canSubmit = allFilled && !loading;

  const handleSubmit = () => {
    if (!canSubmit) return;
    void onSubmit({
      department_defaults: deptDefaults,
      system_role_defaults: roleDefaults,
    });
  };

  return (
    <WizardShell
      title="Assign Default Models"
      stepIndex={2}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={handleSubmit}
          nextLabel="Finish"
          nextDisabled={!canSubmit}
          loading={loading}
        />
      }
    >
      <p className="text-sm text-[--color-text-secondary] mb-2">
        Assign a default model to each department and system role. You can change these
        later from Settings.
      </p>
      <p className="text-xs text-[--color-text-tertiary] mb-6">
        Each slot needs a model before you can continue.
      </p>

      <section className="mb-6">
        <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">
          Department defaults
        </h3>
        <div className="flex flex-col gap-2">
          {enabledDepartmentIds.map((d) => (
            <SlotRow
              key={d}
              id={`dept-${d}`}
              label={humanize(d)}
              value={deptDefaults[d] ?? ""}
              registeredModels={registeredModels}
              onChange={(v) => setDeptDefaults({ ...deptDefaults, [d]: v })}
            />
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-[--color-text-primary] mb-3">
          System role defaults
        </h3>
        <div className="flex flex-col gap-2">
          {systemRoleIds.map((r) => (
            <SlotRow
              key={r}
              id={`role-${r}`}
              label={humanize(r)}
              description={SYSTEM_ROLE_DESCRIPTIONS[r]}
              value={roleDefaults[r] ?? ""}
              registeredModels={registeredModels}
              onChange={(v) => setRoleDefaults({ ...roleDefaults, [r]: v })}
            />
          ))}
        </div>
      </section>

      {submitError ? (
        <p className="text-sm text-[--color-feedback-error] mt-4">{submitError}</p>
      ) : null}
    </WizardShell>
  );
}

function SlotRow({
  id,
  label,
  description,
  value,
  registeredModels,
  onChange,
}: {
  id: string;
  label: string;
  description?: string;
  value: string;
  registeredModels: ModelEntry[];
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base]">
      <div className="flex flex-col flex-1 min-w-0">
        <label htmlFor={id} className="text-sm text-[--color-text-primary] truncate">
          {label}
        </label>
        {description ? (
          <span className="text-xs text-[--color-text-tertiary] mt-0.5">
            {description}
          </span>
        ) : null}
      </div>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 px-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm min-w-[200px]"
      >
        <option value="">— select a model —</option>
        {registeredModels.map((m) => (
          <option key={`${m.key_id}-${m.model_ref}`} value={m.model_ref}>
            {m.display_name}
          </option>
        ))}
      </select>
    </div>
  );
}
