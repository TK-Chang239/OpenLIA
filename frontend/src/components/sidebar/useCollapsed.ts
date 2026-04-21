import { useCallback, useState } from "react";

export const COLLAPSED_STORAGE_KEY = "sidebar_collapsed";

function readInitial(): boolean {
  try {
    return window.localStorage.getItem(COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function useCollapsed(): [boolean, (next: boolean) => void] {
  const [collapsed, setCollapsed] = useState<boolean>(readInitial);

  const update = useCallback((next: boolean) => {
    setCollapsed(next);
    try {
      window.localStorage.setItem(COLLAPSED_STORAGE_KEY, String(next));
    } catch {
      // swallow — in-memory state is the source of truth
    }
  }, []);

  return [collapsed, update];
}
