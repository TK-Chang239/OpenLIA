import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const STORAGE_KEY = "openlia:theme";

function read(): Theme {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "dark") return "dark";
  if (stored === "light") return "light";
  // No stored value: respect the OS preference so dark-mode users do not flash light.
  if (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function"
  ) {
    try {
      if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
        return "dark";
      }
    } catch {
      // matchMedia unsupported; fall through
    }
  }
  return "light";
}

export function useTheme(): { theme: Theme; setTheme: (t: Theme) => void } {
  const [theme, setThemeState] = useState<Theme>(read);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  return { theme, setTheme };
}
