import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useFileViewer } from "./FileViewerContext";
import { ViewerHeader } from "./ViewerHeader";
import { ResizeHandle } from "./ResizeHandle";
import { MarkdownRenderer } from "./renderers/MarkdownRenderer";
import { PdfRenderer } from "./renderers/PdfRenderer";
import { CsvRenderer } from "./renderers/CsvRenderer";
import { CodeRenderer } from "./renderers/CodeRenderer";
import { ImageRenderer } from "./renderers/ImageRenderer";
import { UnsupportedRenderer } from "./renderers/UnsupportedRenderer";
import { StructuredReportRenderer } from "./renderers/StructuredReportRenderer";
import { useReducedMotion } from "../../hooks/useReducedMotion";

type ViewerTab = "preview" | "raw";

const TEXT_LIKE_KINDS = new Set(["markdown", "text", "code", "csv"]);

const MIN_WIDTH = 360;
const MAX_WIDTH = 1000;
const DEFAULT_VIEWPORT_FRACTION = 0.4;

function defaultWidth(): number {
  if (typeof window === "undefined") return 560;
  const target = Math.round(window.innerWidth * DEFAULT_VIEWPORT_FRACTION);
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, target));
}

function initialWidth(): number {
  try {
    const stored = localStorage.getItem("fileviewer_width");
    if (stored) {
      const parsed = parseInt(stored, 10);
      if (Number.isFinite(parsed)) {
        return Math.max(MIN_WIDTH, parsed);
      }
    }
  } catch {
    // localStorage may be unavailable (private mode, SSR) — fall through.
  }
  return defaultWidth();
}

function isMobile(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.matchMedia?.("(max-width: 767px)").matches ?? false;
  } catch {
    return false;
  }
}

export function FileViewer(): JSX.Element | null {
  const { t } = useTranslation();
  const { current, close, scrollMemory, rememberScroll } = useFileViewer();
  const reduce = useReducedMotion();
  const [width, setWidth] = useState<number>(initialWidth);
  const [viewportWidth, setViewportWidth] = useState<number>(
    typeof window !== "undefined" ? window.innerWidth : 1200,
  );
  const [mobile, setMobile] = useState<boolean>(isMobile);
  const [tab, setTab] = useState<ViewerTab>("preview");
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const previousFilenameRef = useRef<string | null>(null);

  // Reset to Preview whenever the open target changes — Raw is per-file state
  // and shouldn't leak across opens.
  useEffect(() => {
    setTab("preview");
  }, [current?.filename]);

  useEffect(() => {
    const onResize = () => {
      setViewportWidth(window.innerWidth);
      setMobile(isMobile());
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Focus the close button on open.
  useEffect(() => {
    if (current) {
      // Wait for the panel to be in the DOM.
      const t = setTimeout(() => closeButtonRef.current?.focus?.(), 0);
      return () => clearTimeout(t);
    }
  }, [current?.filename]);

  // Save outgoing scroll position; restore incoming.
  useLayoutEffect(() => {
    const prev = previousFilenameRef.current;
    const container = scrollContainerRef.current;
    if (prev && container) {
      rememberScroll(prev, container.scrollTop);
    }
    previousFilenameRef.current = current?.filename ?? null;
    if (current && container) {
      const cached = scrollMemory.get(current.filename) ?? 0;
      container.scrollTop = cached;
    }
  }, [current?.filename, rememberScroll, scrollMemory]);

  // Persist scroll on unmount of the viewer panel.
  useEffect(() => {
    return () => {
      const prev = previousFilenameRef.current;
      const container = scrollContainerRef.current;
      if (prev && container) {
        rememberScroll(prev, container.scrollTop);
      }
    };
  }, [rememberScroll]);

  const slideDuration = reduce ? 0 : 0.2;
  const fadeOutDuration = reduce ? 0 : 0.1;
  const fadeInDuration = reduce ? 0 : 0.15;

  const panelStyle: React.CSSProperties = mobile
    ? {
        position: "fixed",
        inset: 0,
        width: "100vw",
        height: "100dvh",
        zIndex: 50,
        boxShadow: "-4px 0 24px rgba(0,0,0,0.06)",
      }
    : { width, boxShadow: "-4px 0 24px rgba(0,0,0,0.06)" };

  return (
    <AnimatePresence>
      {current ? (
        <motion.aside
          key={current.filename}
          role="complementary"
          aria-label={t("chat.viewer_label_aria", { name: current.filename })}
          tabIndex={-1}
          onKeyDown={(e) => {
            if (e.key === "Escape") close();
          }}
          initial={{ x: reduce ? 0 : "100%", opacity: reduce ? 0 : 1 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: reduce ? 0 : "100%", opacity: reduce ? 0 : 1 }}
          transition={{ duration: slideDuration, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex h-full flex-shrink-0 flex-col border-l border-border-subtle bg-bg-elevated"
          style={panelStyle}
          data-mobile={mobile ? "true" : "false"}
          data-testid="file-viewer"
        >
          {!mobile ? (
            <ResizeHandle onWidthChange={setWidth} viewportWidth={viewportWidth} />
          ) : null}
          <ViewerHeader
            filename={current.filename}
            metadata={current.metadata}
            source={current.source}
            reportId={
              current.source.kind === "report" ? current.source.reportId : undefined
            }
            initialSaved={current.initialSaved}
            hideSaveToRepoButton={current.hideSaveToRepoButton ?? false}
            onClose={close}
            closeButtonRef={closeButtonRef}
          />
          <ViewerTabs tab={tab} onTabChange={setTab} />
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={`${current.filename}-${tab}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{
                  opacity: 0,
                  transition: { duration: fadeOutDuration, ease: "easeIn" },
                }}
                transition={{ duration: fadeInDuration, ease: "easeOut" }}
              >
                {tab === "preview" ? (
                  <>
                    {current.kind === "report" && <StructuredReportRenderer source={current.source} />}
                    {current.kind === "markdown" && <MarkdownRenderer source={current.source} />}
                    {current.kind === "pdf" && <PdfRenderer source={current.source} />}
                    {current.kind === "csv" && <CsvRenderer source={current.source} />}
                    {current.kind === "code" && <CodeRenderer source={current.source} />}
                    {current.kind === "text" && <CodeRenderer source={current.source} />}
                    {current.kind === "image" && <ImageRenderer source={current.source} />}
                    {(current.kind === "docx" || current.kind === "unknown") && (
                      <UnsupportedRenderer source={current.source} filename={current.filename} />
                    )}
                  </>
                ) : TEXT_LIKE_KINDS.has(current.kind) ? (
                  <CodeRenderer source={current.source} />
                ) : (
                  <RawUnavailable kind={current.kind} />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}

function ViewerTabs({
  tab,
  onTabChange,
}: {
  tab: ViewerTab;
  onTabChange: (next: ViewerTab) => void;
}): JSX.Element {
  const { t } = useTranslation();
  const tabs: ReadonlyArray<{ id: ViewerTab; label: string }> = [
    { id: "preview", label: t("chat.viewer_tab_preview") },
    { id: "raw", label: t("chat.viewer_tab_raw") },
  ];
  return (
    <div
      role="tablist"
      aria-label={t("chat.viewer_mode_aria")}
      className="flex border-b"
      style={{ borderColor: "var(--color-border-subtle)" }}
    >
      {tabs.map((t) => {
        const active = t.id === tab;
        return (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onTabChange(t.id)}
            className="-mb-px px-[14px] py-[10px] font-mono text-[10px] uppercase transition-colors duration-normal ease-out"
            style={{
              letterSpacing: "var(--tracking-label)",
              color: active
                ? "var(--color-text-primary)"
                : "var(--color-text-secondary)",
              borderBottom: `2px solid ${
                active ? "var(--color-accent-primary)" : "transparent"
              }`,
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

function RawUnavailable({ kind }: { kind: string }): JSX.Element {
  return (
    <div
      role="status"
      className="mx-auto max-w-[480px] px-6 py-12 text-center font-mono text-[12px]"
      style={{ color: "var(--color-text-tertiary)" }}
    >
      Raw view is not available for {kind} files.
    </div>
  );
}
