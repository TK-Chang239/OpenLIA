import { useEffect, useState } from "react";
import type { JSX } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { listSessions, type ChatSession } from "../../api/chat";
import { CORE_NAV, DEPARTMENT_NAV } from "../../components/sidebar/navData";

// Slug -> route path, derived from the same nav table the sidebar uses so the
// pills deep-link to the department where each chat lives.
const PATH_BY_DEPARTMENT: Record<string, string> = Object.fromEntries(
  [...CORE_NAV, ...DEPARTMENT_NAV]
    .filter((e) => e.departmentId)
    .map((e) => [e.departmentId as string, e.path]),
);

const RECENT_LIMIT = 5;

/** Compact, language-neutral relative-time token ("now", "5m", "3h", "2d"). */
function relTime(iso: string, now: number, nowLabel: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const secs = Math.max(0, Math.floor((now - then) / 1000));
  if (secs < 60) return nowLabel;
  const mins = Math.floor(secs / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

export function RecentStrip(): JSX.Element | null {
  const { t } = useTranslation();
  const [sessions, setSessions] = useState<ChatSession[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { items } = await listSessions();
        if (cancelled) return;
        const recent = [...items]
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .slice(0, RECENT_LIMIT);
        setSessions(recent);
      } catch {
        // Home strip is best-effort; on failure just render nothing.
        if (!cancelled) setSessions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Hide the strip entirely until we have something real to show.
  if (!sessions || sessions.length === 0) return null;

  const now = Date.now();
  const nowLabel = t("home.recent_now");

  return (
    <div className="flex items-center pt-[14px] border-t border-border-subtle">
      <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-text-tertiary mr-[14px]">
        {t("home.recent")}
      </span>
      <div className="flex gap-[6px] flex-wrap flex-1">
        {sessions.map((s) => {
          const to = PATH_BY_DEPARTMENT[s.department] ?? "/secretary";
          return (
            <Link
              key={s.id}
              to={to}
              className="inline-flex items-center gap-[6px] px-[10px] py-[5px] border border-border-subtle rounded-full text-xs text-text-secondary bg-bg-base no-underline transition-colors duration-normal ease-out hover:border-border-strong hover:text-text-primary"
            >
              {s.title}
              <span className="font-mono text-[9px] text-text-tertiary tracking-[0.06em]">
                {relTime(s.created_at, now, nowLabel)}
              </span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
