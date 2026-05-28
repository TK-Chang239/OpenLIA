import { CORE_NAV, DEPARTMENT_NAV } from "../components/sidebar/navData";

function titleCase(segment: string): string {
  if (!segment) return "";
  return segment
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const STATIC_ROOTS: Record<string, { label: string; labelKey: string }> = {
  "/settings": { label: "Settings", labelKey: "nav.settings" },
  // v3 equity-research lives at its own route but shares the
  // "Equity Research" breadcrumb label with the v1/v2 page so the
  // top-left reads "Equity Research / <subject>" consistently.
  "/equity-research-v3": {
    label: "Equity Research",
    labelKey: "nav.equity_research",
  },
};

/** Returns breadcrumb segments as i18n keys (e.g. ``nav.home``).
 *  Callers should resolve each via ``t(crumb, { defaultValue: crumb })`` so
 *  unknown segments (e.g. sub-route titles) render as-is. */
export function crumbsForPath(pathname: string): string[] {
  const all = [...CORE_NAV, ...DEPARTMENT_NAV];
  const hit = all.find(
    (e) => pathname === e.path || pathname.startsWith(e.path + "/"),
  );

  let rootPath: string | null = null;
  let rootKey: string | null = null;
  if (hit && hit.path !== "/") {
    rootPath = hit.path;
    rootKey = hit.labelKey;
  } else if (!hit) {
    for (const [prefix, info] of Object.entries(STATIC_ROOTS)) {
      if (pathname === prefix || pathname.startsWith(prefix + "/")) {
        rootPath = prefix;
        rootKey = info.labelKey;
        break;
      }
    }
  }

  if (!rootPath || !rootKey) return ["nav.home"];

  const remainder = pathname.slice(rootPath.length).replace(/^\/+/, "");
  if (!remainder) return ["nav.home", rootKey];

  const segments = remainder.split("/").filter(Boolean);
  if (segments.length === 0) return ["nav.home", rootKey];
  return ["nav.home", rootKey, titleCase(segments[0])];
}

export function stampsForNow(): string[] {
  const now = new Date();
  const day = now.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
  const time = now.toISOString().slice(11, 16);
  return [`${day} · ${time} UTC`];
}
