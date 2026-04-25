import { useCallback, useEffect, useState } from "react";

/**
 * useLocalPref — typed localStorage-backed setting with cross-tab sync.
 *
 * Falls back to the supplied default when storage is unavailable (private
 * mode / SSR) so callers never need to guard.
 */
export function useLocalPref<T extends string>(
  key: string,
  defaultValue: T,
): readonly [T, (value: T) => void] {
  const read = useCallback((): T => {
    if (typeof window === "undefined") return defaultValue;
    try {
      const raw = window.localStorage.getItem(key);
      return raw === null ? defaultValue : (raw as T);
    } catch {
      return defaultValue;
    }
  }, [key, defaultValue]);

  const [value, setValue] = useState<T>(read);

  useEffect(() => {
    setValue(read());
  }, [read]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next);
      } catch {
        /* ignore */
      }
    },
    [key],
  );

  // Cross-tab sync via storage events.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === key && e.newValue !== null) {
        setValue(e.newValue as T);
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [key]);

  return [value, update] as const;
}
