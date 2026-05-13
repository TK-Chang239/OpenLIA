import { useState } from "react";
import { saveModels } from "../../api/setup";
import { KeysScreen } from "./KeysScreen";
import type { ApiKey } from "./KeysScreen";
import { RegisterModelsScreen } from "./RegisterModelsScreen";
import type { ModelEntry } from "./RegisterModelsScreen";
import { AssignDefaultsScreen } from "./AssignDefaultsScreen";
import { inferProvider } from "./inferProvider";
import { useWizardField } from "../storage";

type Screen = "keys" | "register" | "assign";

interface PersistedState {
  screen: Screen;
  keys: ApiKey[];
  entries: ModelEntry[];
  department_defaults: Record<string, string>;
  system_role_defaults: Record<string, string>;
}

const MODELS_DEFAULTS: PersistedState = {
  screen: "keys",
  keys: [],
  entries: [],
  department_defaults: {},
  system_role_defaults: {},
};

function parseModels(raw: unknown): PersistedState {
  const r = (raw ?? {}) as Partial<PersistedState>;
  const screen: Screen =
    r.screen === "assign" ? "assign" : r.screen === "register" ? "register" : "keys";
  return {
    screen,
    keys: Array.isArray(r.keys) ? r.keys : [],
    entries: Array.isArray(r.entries) ? r.entries : [],
    department_defaults:
      r.department_defaults && typeof r.department_defaults === "object"
        ? r.department_defaults
        : {},
    system_role_defaults:
      r.system_role_defaults && typeof r.system_role_defaults === "object"
        ? r.system_role_defaults
        : {},
  };
}

export function ModelsStep({
  totalSteps,
  enabledDepartmentIds,
  systemRoleIds,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  enabledDepartmentIds: string[];
  systemRoleIds: string[];
  onBack: () => void;
  onSaved: () => void;
}) {
  const [state, setState] = useWizardField<PersistedState>(
    "openlia.wizard.models",
    MODELS_DEFAULTS,
    parseModels,
  );
  const { screen, keys, entries, department_defaults, system_role_defaults } = state;
  const setScreen = (value: Screen) => setState((s) => ({ ...s, screen: value }));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateKeys = (next: ApiKey[]) => {
    const validIds = new Set(next.map((k) => k.id));
    setState((s) => ({
      ...s,
      keys: next,
      entries: s.entries.filter((e) => validIds.has(e.key_id)),
    }));
  };

  const updateEntries = (next: ModelEntry[]) => {
    const validRefs = new Set(next.map((e) => e.model_ref));
    setState((s) => {
      const filterDefaults = (d: Record<string, string>) =>
        Object.fromEntries(Object.entries(d).filter(([, v]) => validRefs.has(v)));
      return {
        ...s,
        entries: next,
        department_defaults: filterDefaults(s.department_defaults),
        system_role_defaults: filterDefaults(s.system_role_defaults),
      };
    });
  };

  const onSubmitAssign = async (payload: {
    department_defaults: Record<string, string>;
    system_role_defaults: Record<string, string>;
  }) => {
    setLoading(true);
    setError(null);
    try {
      setState((s) => ({
        ...s,
        department_defaults: payload.department_defaults,
        system_role_defaults: payload.system_role_defaults,
      }));
      const models = entries.map((e) => {
        const key = keys.find((k) => k.id === e.key_id)!;
        return {
          provider_kind: inferProvider(e.model_ref, key.api_key, key.base_url),
          api_key: key.api_key,
          base_url: key.base_url ?? null,
          env_var_name: null,
          model_ref: e.model_ref,
          display_name: e.display_name,
        };
      });
      await saveModels({
        models,
        department_defaults: payload.department_defaults,
        system_role_defaults: payload.system_role_defaults,
      });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save models.");
    } finally {
      setLoading(false);
    }
  };

  if (screen === "keys") {
    return (
      <KeysScreen
        totalSteps={totalSteps}
        keys={keys}
        onChange={updateKeys}
        onBack={onBack}
        onNext={() => setScreen("register")}
      />
    );
  }

  if (screen === "register") {
    return (
      <RegisterModelsScreen
        totalSteps={totalSteps}
        keys={keys}
        entries={entries}
        onChange={updateEntries}
        onBack={() => setScreen("keys")}
        onNext={() => setScreen("assign")}
      />
    );
  }

  return (
    <AssignDefaultsScreen
      totalSteps={totalSteps}
      enabledDepartmentIds={enabledDepartmentIds}
      systemRoleIds={systemRoleIds}
      registeredModels={entries}
      initialDepartmentDefaults={department_defaults}
      initialSystemRoleDefaults={system_role_defaults}
      onBack={() => setScreen("register")}
      onSubmit={onSubmitAssign}
      loading={loading}
      submitError={error}
    />
  );
}
