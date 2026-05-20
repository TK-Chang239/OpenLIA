import type { JSX } from "react";
import { useTranslation } from "react-i18next";

interface Pill {
  title: string;
  when: string;
}

// Placeholder until /api/chat/sessions or repository endpoints back this strip;
// see planning/dev-backlog/home.md (RECENT_PILLS_LIVE_DATA).
const PILLS: Pill[] = [
  { title: "NVDA Q3 one-pager", when: "YDA" },
  { title: "PLTR — bear thesis", when: "YDA" },
  { title: "Fed minutes · Nov", when: "2d" },
  { title: "Semis vs SPX correl", when: "2d" },
  { title: "TSM capex sensitivity", when: "3d" },
];

export function RecentStrip(): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex items-center pt-[14px] border-t border-border-subtle">
      <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-text-tertiary mr-[14px]">
        {t("home.recent")}
      </span>
      <div className="flex gap-[6px] flex-wrap flex-1">
        {PILLS.map((p) => (
          <span
            key={p.title}
            className="inline-flex items-center gap-[6px] px-[10px] py-[5px] border border-border-subtle rounded-full text-xs text-text-secondary bg-bg-base cursor-default transition-colors duration-normal ease-out hover:border-border-strong hover:text-text-primary"
          >
            {p.title}
            <span className="font-mono text-[9px] text-text-tertiary tracking-[0.06em]">
              {p.when}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
