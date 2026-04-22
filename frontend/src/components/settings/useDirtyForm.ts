import { useCallback, useMemo, useState } from 'react';

export interface DirtyForm<T extends Record<string, unknown>> {
  values: T;
  initial: T;
  isDirty: boolean;
  setField: <K extends keyof T>(key: K, value: T[K]) => void;
  setValues: (next: T) => void;
  reset: () => void;
  markSaved: () => void;
}

function shallowEqual<T extends Record<string, unknown>>(a: T, b: T): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (a[k] !== b[k]) return false;
  }
  return true;
}

export function useDirtyForm<T extends Record<string, unknown>>(initialValues: T): DirtyForm<T> {
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

  return { values, initial, isDirty, setField, setValues, reset, markSaved };
}
