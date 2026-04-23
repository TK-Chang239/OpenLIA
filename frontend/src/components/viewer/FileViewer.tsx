import { useEffect, useState } from "react";
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

function initialWidth(): number {
  try {
    const stored = localStorage.getItem("fileviewer_width");
    return stored ? Math.max(360, parseInt(stored, 10) || 560) : 560;
  } catch {
    return 560;
  }
}

export function FileViewer(): JSX.Element | null {
  const { current, close } = useFileViewer();
  const [width, setWidth] = useState<number>(initialWidth);
  const [viewportWidth, setViewportWidth] = useState<number>(
    typeof window !== "undefined" ? window.innerWidth : 1200,
  );

  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

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
          initial={{ x: "100%" }}
          animate={{ x: 0 }}
          exit={{ x: "100%" }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="relative flex h-full flex-shrink-0 flex-col border-l border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg"
          style={{ width }}
        >
          <ResizeHandle onWidthChange={setWidth} viewportWidth={viewportWidth} />
          <ViewerHeader
            filename={current.filename}
            metadata={current.metadata}
            source={current.source}
            reportId={
              current.source.kind === "report" ? current.source.reportId : undefined
            }
            onClose={close}
          />
          <div className="flex-1 overflow-y-auto">
            {current.kind === "markdown" && <MarkdownRenderer source={current.source} />}
            {current.kind === "pdf" && <PdfRenderer source={current.source} />}
            {current.kind === "csv" && <CsvRenderer source={current.source} />}
            {current.kind === "code" && <CodeRenderer source={current.source} />}
            {current.kind === "text" && <CodeRenderer source={current.source} />}
            {current.kind === "image" && <ImageRenderer source={current.source} />}
            {(current.kind === "docx" || current.kind === "unknown") && (
              <UnsupportedRenderer source={current.source} filename={current.filename} />
            )}
          </div>
        </motion.aside>
      ) : null}
    </AnimatePresence>
  );
}
