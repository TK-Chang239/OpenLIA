import { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";
import { RendererError, RendererLoading } from "./RendererStates";

// pdfjs-dist runs only in real browsers (it touches `DOMMatrix`/canvas).
// We dynamic-import it on first effect so the module graph doesn't drag the
// dependency into jsdom-driven tests that never mount the renderer.
let pdfjsModule: typeof import("pdfjs-dist") | null = null;
async function getPdfJs(): Promise<typeof import("pdfjs-dist")> {
  if (pdfjsModule) return pdfjsModule;
  const mod = await import("pdfjs-dist");
  mod.GlobalWorkerOptions.workerSrc = new URL(
    "pdfjs-dist/build/pdf.worker.min.mjs",
    import.meta.url,
  ).toString();
  pdfjsModule = mod;
  return mod;
}

export function PdfRenderer({ source }: { source: FileSource }): JSX.Element {
  const { t } = useTranslation();
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const [error, setError] = useState<Error | null>(null);
  const [tick, setTick] = useState(0);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pdfRef = useRef<any>(null);

  useEffect(() => {
    setError(null);
    setNumPages(0);
    let cancelled = false;
    getPdfJs()
      .then((pdfjs) => {
        const task = pdfjs.getDocument(sourceUrl(source));
        return task.promise;
      })
      .then((doc) => {
        if (cancelled) return;
        pdfRef.current = doc;
        setNumPages(doc.numPages);
        setPage(1);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      });
    return () => {
      cancelled = true;
      pdfRef.current?.destroy?.();
      pdfRef.current = null;
    };
  }, [source, tick]);

  useEffect(() => {
    if (!pdfRef.current || !canvasRef.current || numPages === 0) return;
    pdfRef.current
      .getPage(page)
      .then(
        (p: {
          getViewport: (o: { scale: number }) => { width: number; height: number };
          render: (o: unknown) => { promise: Promise<void> };
        }) => {
          const viewport = p.getViewport({ scale: 1.3 });
          const canvas = canvasRef.current!;
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          p.render({ canvasContext: canvas.getContext("2d"), viewport });
        },
      )
      .catch((err: unknown) => {
        setError(err instanceof Error ? err : new Error(String(err)));
      });
  }, [page, numPages]);

  if (error)
    return (
      <RendererError message={error.message} onRetry={() => setTick((t) => t + 1)} />
    );
  if (numPages === 0) return <RendererLoading />;

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-auto px-6 py-4">
        <canvas
          ref={canvasRef}
          className="mx-auto block rounded-[--radius-md] bg-white shadow-sm"
        />
      </div>
      <div className="flex flex-shrink-0 items-center justify-between border-t border-[--color-border-subtle] px-4 py-2">
        <span className="text-sm text-[--color-text-secondary]">
          {t("chat.pdf_page_of", { page, total: numPages })}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label={t("chat.viewer_prev_page")}
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="flex h-7 w-7 items-center justify-center rounded-[--radius-md] hover:bg-[--color-surface-hover] disabled:opacity-40"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            aria-label={t("chat.viewer_next_page")}
            disabled={page >= numPages}
            onClick={() => setPage((p) => Math.min(numPages, p + 1))}
            className="flex h-7 w-7 items-center justify-center rounded-[--radius-md] hover:bg-[--color-surface-hover] disabled:opacity-40"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
