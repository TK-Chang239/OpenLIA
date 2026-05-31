import { useEffect, type JSX, type ReactNode } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Sidebar } from "../components/sidebar/Sidebar";
import { TopBar } from "../components/shell/TopBar";
import { MobileTabBar } from "../components/sidebar/MobileTabBar";
import { MobileSidebarOverlay } from "../components/sidebar/MobileSidebarOverlay";
import { MobileNavProvider, useMobileNav } from "./MobileNavContext";
import { ChatHeaderProvider } from "./ChatHeaderContext";
import { DevPanel } from "../components/dev/DevPanel";
import { crumbsForPath, stampsForNow } from "./shellState";
import { FileViewerProvider, useFileViewer } from "../components/viewer/FileViewerContext";
import { FileViewer } from "../components/viewer/FileViewer";
import { ToastProvider, useToast } from "../components/primitives/Toast";
import { SavedReportsProvider } from "../components/repo/SavedReportsContext";
import { useDeptHealth } from "../store/dept-health";
import { useNotificationsStream } from "../app/useNotificationsStream";

interface AppLayoutProps {
  children?: ReactNode;
}

function NotificationsWatcher(): null {
  const navigate = useNavigate();
  const { push } = useToast();
  useNotificationsStream({
    navigate,
    toast: {
      success: (msg, opts) => push({ title: msg, tone: "success", undo: opts?.action }),
      error: (msg, opts) => push({ title: msg, tone: "error", undo: opts?.action }),
      info: (msg, opts) => push({ title: msg, tone: "info", undo: opts?.action }),
    },
    onAttachedReportChanged: (data) => {
      window.dispatchEvent(
        new CustomEvent("openlia:attached_report_changed", { detail: data }),
      );
    },
  });
  return null;
}

function AppLayoutInner({ children }: AppLayoutProps): JSX.Element {
  const { pathname } = useLocation();
  const { t } = useTranslation();
  const crumbs = crumbsForPath(pathname);
  const { open, setOpen } = useMobileNav();
  const refreshHealth = useDeptHealth((s) => s.refresh);
  const { close: closeViewer } = useFileViewer();
  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);
  useEffect(() => {
    closeViewer();
  }, [pathname, closeViewer]);
  return (
    <div
      className="grid h-screen w-full bg-bg-base text-text-primary"
      style={{ gridTemplateColumns: "auto 1fr" }}
    >
      <a
        href="#main"
        className="sr-only focus:not-sr-only fixed top-2 left-2 bg-white text-black px-3 py-2 rounded shadow z-50"
      >
        {t("shell.skip_to_content")}
      </a>
      <NotificationsWatcher />
      <Sidebar />
      <MobileSidebarOverlay open={open} onOpenChange={setOpen} />
      <section
        className="grid overflow-hidden"
        style={{ gridTemplateRows: "auto 1fr" }}
      >
        <header data-om-shell="topbar">
          <TopBar
            crumbs={crumbs}
            stamps={stampsForNow()}
            live={pathname.startsWith("/morning-briefing")}
          />
        </header>
        <main
          id="main"
          data-om-shell="content"
          tabIndex={-1}
          className="flex overflow-y-auto pb-14 md:pb-0"
          style={{ scrollbarGutter: "stable" }}
        >
          <div className="flex-1 min-w-0">
            {children ?? <Outlet />}
          </div>
          <FileViewer />
        </main>
      </section>
      <MobileTabBar />
      <DevPanel />
    </div>
  );
}

export function AppLayout({ children }: AppLayoutProps = {}): JSX.Element {
  return (
    <MobileNavProvider>
      <ToastProvider>
        <SavedReportsProvider>
          <FileViewerProvider>
            <ChatHeaderProvider>
              <AppLayoutInner>{children}</AppLayoutInner>
            </ChatHeaderProvider>
          </FileViewerProvider>
        </SavedReportsProvider>
      </ToastProvider>
    </MobileNavProvider>
  );
}
