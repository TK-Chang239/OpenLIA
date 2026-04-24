import type { JSX } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";
import { TopBar } from "../components/shell/TopBar";
import { crumbsForPath, stampsForNow } from "./shellState";

export function AppLayout(): JSX.Element {
  const { pathname } = useLocation();
  const crumbs = crumbsForPath(pathname);
  return (
    <div
      className="grid h-screen w-full bg-bg-base text-text-primary"
      style={{ gridTemplateColumns: "auto 1fr" }}
    >
      <Sidebar />
      <section
        className="grid overflow-hidden"
        style={{ gridTemplateRows: "auto 1fr" }}
      >
        <TopBar
          crumbs={crumbs}
          stamps={stampsForNow()}
          live={pathname.startsWith("/morning-briefing")}
        />
        <main className="overflow-y-auto">
          <Outlet />
        </main>
      </section>
    </div>
  );
}
