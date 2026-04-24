import type { JSX } from "react";
import { Link } from "react-router-dom";
import { DEPARTMENT_NAV } from "../components/sidebar/navData";

const MACRO_STRIP = [
  { lbl: "S&P FUT", val: "+0.34" },
  { lbl: "VIX", val: "14.2" },
  { lbl: "10Y", val: "4.28" },
  { lbl: "DXY", val: "103.1" },
];

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export default function Home(): JSX.Element {
  return (
    <div className="mx-auto w-full max-w-[960px] px-8 py-10">
      <div className="ol-greeting">{greeting()}.</div>
      <div
        className="ol-label mt-[6px]"
        style={{ letterSpacing: "var(--tracking-micro)" }}
      >
        {MACRO_STRIP.map((m, i) => (
          <span key={m.lbl}>
            {i > 0 && <span className="mx-2 text-text-tertiary">·</span>}
            {m.lbl} {m.val}
          </span>
        ))}
      </div>

      <div className="mt-10 grid grid-cols-1 md:grid-cols-2 gap-4">
        {DEPARTMENT_NAV.map((dept) => (
          <Link
            key={dept.id}
            to={dept.path}
            className="group relative block rounded-lg border border-border-subtle bg-bg-elevated p-5 transition-all duration-normal ease-out hover:-translate-y-1 hover:border-yellow-600 overflow-hidden"
          >
            <span className="ol-label-sm">DEPARTMENT</span>
            <h3 className="mt-1 font-display text-[20px] font-medium text-text-primary">
              {dept.label}
            </h3>
            <span
              aria-hidden="true"
              className="absolute bottom-0 left-0 h-[2px] w-0 bg-accent-primary transition-[width] duration-slow ease-out group-hover:w-full"
            />
          </Link>
        ))}
      </div>
    </div>
  );
}
