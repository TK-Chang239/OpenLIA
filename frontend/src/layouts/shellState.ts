import { CORE_NAV, DEPARTMENT_NAV } from "../components/sidebar/navData";

export function crumbsForPath(pathname: string): string[] {
  const all = [...CORE_NAV, ...DEPARTMENT_NAV];
  const hit = all.find(
    (e) => pathname === e.path || pathname.startsWith(e.path + "/"),
  );
  if (!hit) return ["Home"];
  return hit.path === "/" ? ["Home"] : ["Home", hit.label];
}

export function stampsForNow(): string[] {
  const now = new Date();
  const day = now.toLocaleDateString("en-US", { weekday: "short" }).toUpperCase();
  const time = now.toISOString().slice(11, 16);
  return [`${day} · ${time} UTC`];
}
