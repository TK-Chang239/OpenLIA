import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useFileViewer } from "./FileViewerContext";
import { ViewerHeader } from "./ViewerHeader";
import { ResizeHandle } from "./ResizeHandle";
import { MarkdownRenderer } from "./renderers/MarkdownRenderer";
import { PdfRenderer } from "./renderers/PdfRenderer";
import { CsvRenderer } from "./renderers/CsvRenderer";
import { CodeRenderer } from "./renderers/CodeRenderer";
import { ImageRenderer } from "./renderers/ImageRenderer";
import { UnsupportedRenderer } from "./renderers/UnsupportedRenderer";
import { useReducedMotion } from "../../hooks/useReducedMotion";

function initialWidth(): number {
  try {
    const stored = localStorage.getItem("fileviewer_width");
    return stored ? Math.max(360, parseInt(stored, 10) || 560) : 560;
  } catch {
    return 560;
  }
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
  const { current, close, scrollMemory, rememberScroll } = useFileViewer();
  const reduce = useReducedMotion();
  const [width, setWidth] = useState<number>(initialWidth);
  const [viewportWidth, setViewportWidth] = useState<number>(
    typeof window !== "undefined" ? window.innerWidth : 1200,
  );
  const [mobile, setMobile] = useState<boolean>(isMobile);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const previousFilenameRef = useRef<string | null>(null);

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
          aria-label={`File viewer: ${current.filename}`}
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
          <div ref={scrollContainerRef} className="flex-1 overflow-y-auto">
            <AnimatePresence mode="wait">
              <motion.div
                key={current.filename}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{
                  opacity: 0,
                  transition: { duration: fadeOutDuration, ease: "easeIn" },
                }}
                transition={{ duration: fadeInDuration, ease: "easeOut" }}
              >
                {current.kind === "markdown" && <MarkdownRenderer source={current.source} />}
                {current.kind === "pdf" && <PdfRenderer source={current.source} />}
                {current.kind === "csv" && <CsvRenderer source={current.source} />}
                {current.kind === "code" && <CodeRenderer source={current.source} />}
                {current.kind === "text" && <CodeRenderer source={current.source} />}
                {current.kind === "image" && <ImageRenderer source={current.source} />}
                {(current.kind === "docx" || current.kind === "unknown") && (
                  <UnsupportedRenderer source={current.source} filename={current.filename} />
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}
