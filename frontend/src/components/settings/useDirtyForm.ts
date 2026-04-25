import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { useSettingsDirty } from './dirty-context';

export interface DirtyForm<T extends object> {
  values: T;
  initial: T;
  isDirty: boolean;
  setField: <K extends keyof T>(key: K, value: T[K]) => void;
  setValues: (next: T) => void;
  reset: () => void;
  markSaved: () => void;
}

function shallowEqual<T extends object>(a: T, b: T): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if ((a as Record<string, unknown>)[k] !== (b as Record<string, unknown>)[k]) return false;
  }
  return true;
}

export function useDirtyForm<T extends object>(initialValues: T): DirtyForm<T> {
  const [initial, setInitial] = useState<T>(initialValues);
  const [values, setValuesState] = useState<T>(initialValues);

  const setField = useCallback(<K extends keyof T>(key: K, value: T[K]) => {
    setValuesState((prev) => ({ ...prev, [key]: value }));
  }, []);

  const setValues = useCallback((next: T) => {
    setValuesState(next);
  }, []);

  const reset = useCallback(() => {
    setValuesState(initial);
  }, [initial]);

  const markSaved = useCallback(() => {
    setInitial(values);
  }, [values]);

  const isDirty = useMemo(() => !shallowEqual(values, initial), [values, initial]);

  const sectionId = useId();
  const dirtyCtx = useSettingsDirty();
  useEffect(() => {
    if (!dirtyCtx) return;
    dirtyCtx.register(sectionId, isDirty);
    return () => dirtyCtx.unregister(sectionId);
  }, [dirtyCtx, sectionId, isDirty]);

  return { values, initial, isDirty, setField, setValues, reset, markSaved };
}
