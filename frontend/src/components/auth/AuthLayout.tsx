import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

export function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return (
    <main
      aria-label={t("auth.layout_aria")}
      className="min-h-screen bg-bg-base flex flex-col items-center justify-center p-4"
    >
      <div className="mb-6 flex items-center gap-[10px]">
        <span className="inline-flex items-center justify-center w-[26px] h-[26px] rounded-md font-bold text-[10px] bg-accent-primary text-accent-on shadow-accent">
          LIA
        </span>
        <span className="font-display text-[15px] font-semibold text-text-primary">
          OpenLia
        </span>
      </div>
      {children}
    </main>
  );
}
