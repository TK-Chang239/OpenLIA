import type { JSX, ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";
import { TopBar } from "../components/shell/TopBar";
import { MobileTabBar } from "../components/sidebar/MobileTabBar";
import { MobileSidebarOverlay } from "../components/sidebar/MobileSidebarOverlay";
import { MobileNavProvider, useMobileNav } from "./MobileNavContext";
import { crumbsForPath, stampsForNow } from "./shellState";

interface AppLayoutProps {
  children?: ReactNode;
}

function AppLayoutInner({ children }: AppLayoutProps): JSX.Element {
  const { pathname } = useLocation();
  const crumbs = crumbsForPath(pathname);
  const { open, setOpen } = useMobileNav();
  return (
    <div
      className="grid h-screen w-full bg-bg-base text-text-primary"
      style={{ gridTemplateColumns: "auto 1fr" }}
    >
      <a
        href="#main"
        className="sr-only focus:not-sr-only fixed top-2 left-2 bg-white text-black px-3 py-2 rounded shadow z-50"
      >
        Skip to content
      </a>
      <Sidebar />
      <MobileSidebarOverlay open={open} onOpenChange={setOpen} />
      <section
        className="grid overflow-hidden"
        style={{ gridTemplateRows: "auto 1fr" }}
      >
        <header>
          <TopBar
            crumbs={crumbs}
            stamps={stampsForNow()}
            live={pathname.startsWith("/morning-briefing")}
          />
        </header>
        <main id="main" tabIndex={-1} className="overflow-y-auto pb-14 md:pb-0">
          {children ?? <Outlet />}
        </main>
      </section>
      <MobileTabBar />
    </div>
  );
}

export function AppLayout({ children }: AppLayoutProps = {}): JSX.Element {
  return (
    <MobileNavProvider>
      <AppLayoutInner>{children}</AppLayoutInner>
    </MobileNavProvider>
  );
}
