import { useEffect, useRef, useState } from "react";
import * as pdfjs from "pdfjs-dist";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  "pdfjs-dist/build/pdf.worker.min.mjs",
  import.meta.url,
).toString();

export function PdfRenderer({ source }: { source: FileSource }): JSX.Element {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const pdfRef = useRef<any>(null);

  useEffect(() => {
    const task = pdfjs.getDocument(sourceUrl(source));
    task.promise.then((doc) => {
      pdfRef.current = doc;
      setNumPages(doc.numPages);
      setPage(1);
    });
    return () => {
      pdfRef.current?.destroy?.();
      pdfRef.current = null;
    };
  }, [source]);

  useEffect(() => {
    if (!pdfRef.current || !canvasRef.current || numPages === 0) return;
    pdfRef.current.getPage(page).then((p: { getViewport: (o: { scale: number }) => { width: number; height: number }; render: (o: unknown) => { promise: Promise<void> } }) => {
      const viewport = p.getViewport({ scale: 1.3 });
      const canvas = canvasRef.current!;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      p.render({ canvasContext: canvas.getContext("2d"), viewport });
    });
  }, [page, numPages]);

  if (numPages === 0)
    return <div className="p-6 text-sm text-[--color-text-secondary]">Loading…</div>;

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
          Page {page} of {numPages}
        </span>
        <div className="flex gap-1">
          <button
            type="button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="flex h-7 w-7 items-center justify-center rounded-[--radius-md] hover:bg-[--color-surface-hover] disabled:opacity-40"
          >
            <ChevronLeft size={14} />
          </button>
          <button
            type="button"
            aria-label="Next page"
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
