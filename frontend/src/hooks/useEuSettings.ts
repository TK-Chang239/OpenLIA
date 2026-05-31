import { useCallback, useEffect, useState } from "react";
import { fetchSettings, updateSettings, type EuSettings } from "../api/earnings-update";

export interface EuSettingsState {
  settings: EuSettings | null;
  loading: boolean;
  error: Error | null;
  disabled: boolean; // true when the engine returns 503
  save: (next: EuSettings) => Promise<EuSettings>;
}

export function useEuSettings(): EuSettingsState {
  const [settings, setSettings] = useState<EuSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [disabled, setDisabled] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchSettings()
      .then((s) => { if (!cancelled) { setSettings(s); setLoading(false); } })
      .catch((e: Error) => {
        if (cancelled) return;
        if (/\b503\b/.test(e.message)) setDisabled(true);
        else setError(e);
        setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const save = useCallback(async (next: EuSettings) => {
    const saved = await updateSettings(next);
    setSettings(saved);
    return saved;
  }, []);

  return { settings, loading, error, disabled, save };
}
