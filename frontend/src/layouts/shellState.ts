import { CORE_NAV, DEPARTMENT_NAV } from "../components/sidebar/navData";

function titleCase(segment: string): string {
  if (!segment) return "";
  return segment
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const STATIC_ROOTS: Record<string, string> = {
  "/settings": "Settings",
};

export function crumbsForPath(pathname: string): string[] {
  const all = [...CORE_NAV, ...DEPARTMENT_NAV];
  const hit = all.find(
    (e) => pathname === e.path || pathname.startsWith(e.path + "/"),
  );

  let rootPath: string | null = null;
  let rootLabel: string | null = null;
  if (hit && hit.path !== "/") {
    rootPath = hit.path;
    rootLabel = hit.label;
  } else if (!hit) {
    for (const [prefix, label] of Object.entries(STATIC_ROOTS)) {
      if (pathname === prefix || pathname.startsWith(prefix + "/")) {
        rootPath = prefix;
        rootLabel = label;
        break;
      }
    }
  }

  if (!rootPath || !rootLabel) return ["Home"];

  const remainder = pathname.slice(rootPath.length).replace(/^\/+/, "");
  if (!remainder) return ["Home", rootLabel];

  const segments = remainder.split("/").filter(Boolean);
  if (segments.length === 0) return ["Home", rootLabel];
  return ["Home", rootLabel, titleCase(segments[0])];
}

export function stampsForNow(): string[] {
  const now = new Date();
  const day = now.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
  const time = now.toISOString().slice(11, 16);
  return [`${day} · ${time} UTC`];
}
