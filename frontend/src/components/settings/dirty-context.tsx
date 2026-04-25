/**
 * Settings-wide dirty-state collector.
 *
 * Each section calls `register(sectionId, isDirty)` from `useDirtyForm` so the
 * `SettingsShell` knows whether ANY section currently has unsaved edits. The
 * shell then triggers `<UnsavedChangesModal>` on in-app navigation
 * (`useBlocker`) and a `beforeunload` warning on hard navigation.
 */
import { createContext, ReactNode, useCallback, useContext, useMemo, useRef, useState } from 'react';

interface DirtyContextValue {
  register: (sectionId: string, isDirty: boolean) => void;
  unregister: (sectionId: string) => void;
  isAnyDirty: () => boolean;
}

const SettingsDirtyContext = createContext<DirtyContextValue | null>(null);

export function SettingsDirtyProvider({ children }: { children: ReactNode }): JSX.Element {
  const dirtyMap = useRef<Map<string, boolean>>(new Map());
  // Trigger re-renders so consumers reading `isAnyDirty()` via the provider
  // see updated state when a child registers/unregisters. Hooks like
  // `useBlocker` read the latest value at navigation time.
  const [, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);

  const register = useCallback(
    (sectionId: string, isDirty: boolean) => {
      const prev = dirtyMap.current.get(sectionId);
      if (prev === isDirty) return;
      dirtyMap.current.set(sectionId, isDirty);
      bump();
    },
    [bump],
  );
  const unregister = useCallback(
    (sectionId: string) => {
      if (dirtyMap.current.has(sectionId)) {
        dirtyMap.current.delete(sectionId);
        bump();
      }
    },
    [bump],
  );
  const isAnyDirty = useCallback(() => {
    for (const v of dirtyMap.current.values()) {
      if (v) return true;
    }
    return false;
  }, []);

  const value = useMemo(
    () => ({ register, unregister, isAnyDirty }),
    [register, unregister, isAnyDirty],
  );
  return <SettingsDirtyContext.Provider value={value}>{children}</SettingsDirtyContext.Provider>;
}

export function useSettingsDirty(): DirtyContextValue | null {
  return useContext(SettingsDirtyContext);
}
