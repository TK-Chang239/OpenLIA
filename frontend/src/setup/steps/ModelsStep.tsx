import { useState } from "react";
import { saveModels } from "../../api/setup";
import { KeysScreen } from "./KeysScreen";
import type { ApiKey } from "./KeysScreen";
import { TiersScreen } from "./TiersScreen";
import type { TierEntry, TierMap, TierName } from "./TiersScreen";
import { inferProvider } from "./inferProvider";
import { useWizardField } from "../storage";

type Screen = "keys" | "tiers";

interface PersistedState {
  screen: Screen;
  keys: ApiKey[];
  tiers: TierMap;
}

const MODELS_DEFAULTS: PersistedState = {
  screen: "keys",
  keys: [],
  tiers: { thinking: [], everyday: [], quick: [] },
};

function parseModels(raw: unknown): PersistedState {
  const r = (raw ?? {}) as Partial<PersistedState>;
  return {
    screen: r.screen === "tiers" ? "tiers" : "keys",
    keys: Array.isArray(r.keys) ? r.keys : [],
    tiers: r.tiers ?? MODELS_DEFAULTS.tiers,
  };
}

export function ModelsStep({
  totalSteps,
  requiredTiers,
  onBack,
  onSaved,
}: {
  totalSteps: number;
  requiredTiers: TierName[];
  onBack: () => void;
  onSaved: () => void;
}) {
  const [state, setState] = useWizardField<PersistedState>(
    "openlia.wizard.models",
    MODELS_DEFAULTS,
    parseModels,
  );
  const { screen, keys, tiers } = state;
  const setScreen = (value: Screen) => setState((s) => ({ ...s, screen: value }));
  const setTiers = (next: TierMap | ((prev: TierMap) => TierMap)) =>
    setState((s) => ({
      ...s,
      tiers: typeof next === "function" ? next(s.tiers) : next,
    }));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateKeys = (next: ApiKey[]) => {
    const validIds = new Set(next.map((k) => k.id));
    setState((s) => ({
      ...s,
      keys: next,
      tiers: {
        thinking: s.tiers.thinking.filter((e) => validIds.has(e.key_id)),
        everyday: s.tiers.everyday.filter((e) => validIds.has(e.key_id)),
        quick: s.tiers.quick.filter((e) => validIds.has(e.key_id)),
      },
    }));
  };

  const onSave = async () => {
    setLoading(true);
    setError(null);
    try {
      const expand = (entries: TierEntry[]) =>
        entries
          .filter((e) => e.status === "ok")
          .map((e) => {
            const key = keys.find((k) => k.id === e.key_id)!;
            return {
              provider: inferProvider(e.model, key.api_key, key.base_url),
              model: e.model,
              api_key: key.api_key,
              base_url: key.base_url,
            };
          });
      await saveModels({
        thinking: expand(tiers.thinking),
        everyday: expand(tiers.everyday),
        quick: expand(tiers.quick),
      });
      // Persist past Next; the wizard-wide clear runs after /setup/finish.
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
        onNext={() => setScreen("tiers")}
      />
    );
  }

  return (
    <TiersScreen
      totalSteps={totalSteps}
      requiredTiers={requiredTiers}
      keys={keys}
      tiers={tiers}
      onChange={setTiers}
      onBack={() => setScreen("keys")}
      onNext={onSave}
      loading={loading}
      submitError={error}
    />
  );
}
