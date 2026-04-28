import { useEffect, type JSX, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "../components/sidebar/Sidebar";
import { TopBar } from "../components/shell/TopBar";
import { MobileTabBar } from "../components/sidebar/MobileTabBar";
import { MobileSidebarOverlay } from "../components/sidebar/MobileSidebarOverlay";
import { MobileNavProvider, useMobileNav } from "./MobileNavContext";
import { crumbsForPath, stampsForNow } from "./shellState";
import { FileViewerProvider } from "../components/viewer/FileViewerContext";
import { FileViewer } from "../components/viewer/FileViewer";
import { ToastProvider } from "../components/primitives/Toast";
import { useDeptHealth } from "../store/dept-health";

interface AppLayoutProps {
  children?: ReactNode;
}

function AppLayoutInner({ children }: AppLayoutProps): JSX.Element {
  const { pathname } = useLocation();
  const crumbs = crumbsForPath(pathname);
  const { open, setOpen } = useMobileNav();
  const refreshHealth = useDeptHealth((s) => s.refresh);
  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);
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
        <main id="main" tabIndex={-1} className="flex overflow-y-auto pb-14 md:pb-0">
          <div className="flex-1 min-w-0">
            {children ?? <Outlet />}
          </div>
          <FileViewer />
        </main>
      </section>
      <MobileTabBar />
    </div>
  );
}

export function AppLayout({ children }: AppLayoutProps = {}): JSX.Element {
  return (
    <MobileNavProvider>
      <ToastProvider>
        <FileViewerProvider>
          <AppLayoutInner>{children}</AppLayoutInner>
        </FileViewerProvider>
      </ToastProvider>
    </MobileNavProvider>
  );
}
