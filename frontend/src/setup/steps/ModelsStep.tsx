import { useEffect, useState } from "react";
import { saveModels } from "../../api/setup";
import { KeysScreen } from "./KeysScreen";
import type { ApiKey } from "./KeysScreen";
import { TiersScreen } from "./TiersScreen";
import type { TierEntry, TierMap, TierName } from "./TiersScreen";
import { inferProvider } from "./inferProvider";

type Screen = "keys" | "tiers";

const STORAGE_KEY = "openlia.wizard.models";

interface PersistedState {
  screen: Screen;
  keys: ApiKey[];
  tiers: TierMap;
}

function loadPersisted(): PersistedState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as PersistedState;
  } catch {
    return null;
  }
}

function savePersisted(state: PersistedState): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Ignore quota / disabled storage; state will reset but the wizard still works.
  }
}

function clearPersisted(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* noop */
  }
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
  const persisted = loadPersisted();
  const [screen, setScreen] = useState<Screen>(persisted?.screen ?? "keys");
  const [keys, setKeys] = useState<ApiKey[]>(persisted?.keys ?? []);
  const [tiers, setTiers] = useState<TierMap>(
    persisted?.tiers ?? { thinking: [], everyday: [], quick: [] },
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    savePersisted({ screen, keys, tiers });
  }, [screen, keys, tiers]);

  const updateKeys = (next: ApiKey[]) => {
    const validIds = new Set(next.map((k) => k.id));
    setKeys(next);
    setTiers((prev) => ({
      thinking: prev.thinking.filter((e) => validIds.has(e.key_id)),
      everyday: prev.everyday.filter((e) => validIds.has(e.key_id)),
      quick: prev.quick.filter((e) => validIds.has(e.key_id)),
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
      clearPersisted();
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
