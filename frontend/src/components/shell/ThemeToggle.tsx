import type { JSX } from "react";
import { Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useTheme } from "../../hooks/useTheme";
import { updatePrefs } from "../../api/settings";

export function ThemeToggle(): JSX.Element {
  const { t } = useTranslation();
  const { resolved, setTheme } = useTheme();
  const next = resolved === "light" ? "dark" : "light";
  const Icon = resolved === "light" ? Moon : Sun;
  const modeLabel =
    next === "light" ? t("shell.theme_light_mode") : t("shell.theme_dark_mode");
  return (
    <button
      type="button"
      onClick={() => {
        setTheme(next);
        // Write through so Settings > Appearance shows the same choice. The
        // theme is already applied locally, so a failed request only costs
        // cross-device sync — not worth an error banner on a toggle.
        void updatePrefs({ theme: next }).catch(() => undefined);
      }}
      aria-label={t("shell.theme_switch_aria", { mode: modeLabel })}
      className="w-7 h-7 rounded-md inline-flex items-center justify-center text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors duration-normal ease-out"
    >
      <Icon size={16} strokeWidth={1.5} />
    </button>
  );
}
