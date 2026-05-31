import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from "react";

export type FileKind =
  | "pdf"
  | "markdown"
  | "text"
  | "code"
  | "csv"
  | "image"
  | "docx"
  | "report"
  | "unknown";

export type FileSource =
  | { kind: "attachment"; attachmentId: string }
  | { kind: "report"; reportId: string }
  // v2.2 equity-research runs persist their final HTML on the
  // pipeline_runs row, not in the v1 reports table. The viewer renders
  // that HTML inside the same chrome by branching on this source kind.
  | { kind: "v2_report"; runId: string }
  // v2.3 runs persist their structured payload on the er_v2_3_run_state
  // row. The viewer adapts the payload to the v1 ReportSchema and
  // renders through the shared ReportRenderer.
  | { kind: "v23_report"; runId: string }
  // v3 runs persist sections/charts/citations in the report_v3*
  // tables. The viewer renders them with react-markdown — see
  // V3ReportRenderer. The /html and /pdf routes stay as the
  // standalone export surface (new-tab open + Word / PDF download).
  | { kind: "v3_report"; reportId: string }
  // EU v2 runs persist sections/charts/citations in the eu_v2_*
  // tables. The viewer adapts the RunDetail to the shared ReportSchema
  // and renders through EUV2ReportRenderer (same pipeline as v3).
  | { kind: "eu_v2_report"; reportId: string };

export interface FileViewerTarget {
  filename: string;
  kind: FileKind;
  metadata: string;
  source: FileSource;
  initialSaved?: boolean;
  /** Suppress the Save-to-Repo button in the viewer header (already-saved entrypoints). */
  hideSaveToRepoButton?: boolean;
  /** Element that opened the viewer; focus returns here on close. */
  trigger?: HTMLElement | null;
}

interface ContextShape {
  current: FileViewerTarget | null;
  /** Last element that triggered an open() call. */
  lastTrigger: HTMLElement | null;
  open: (target: FileViewerTarget) => void;
  close: () => void;
  /** Cached scrollTop per filename — used for scroll preservation
   *  when the user swaps between files. */
  scrollMemory: Map<string, number>;
  rememberScroll: (filename: string, top: number) => void;
}

const FileViewerContext = createContext<ContextShape | null>(null);

export function FileViewerProvider({ children }: { children: React.ReactNode }): JSX.Element {
  const [current, setCurrent] = useState<FileViewerTarget | null>(null);
  const lastTriggerRef = useRef<HTMLElement | null>(null);
  const scrollMemoryRef = useRef<Map<string, number>>(new Map());

  const open = useCallback((t: FileViewerTarget) => {
    if (t.trigger) lastTriggerRef.current = t.trigger;
    else if (typeof document !== "undefined") {
      lastTriggerRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
    }
    setCurrent(t);
  }, []);

  const close = useCallback(() => {
    setCurrent(null);
    const trigger = lastTriggerRef.current;
    if (trigger) {
      // Defer to next tick so the unmount animation doesn't yank focus.
      setTimeout(() => trigger.focus?.(), 0);
    }
  }, []);

  const rememberScroll = useCallback((filename: string, top: number) => {
    scrollMemoryRef.current.set(filename, top);
  }, []);

  const value = useMemo<ContextShape>(
    () => ({
      current,
      lastTrigger: lastTriggerRef.current,
      open,
      close,
      scrollMemory: scrollMemoryRef.current,
      rememberScroll,
    }),
    [current, open, close, rememberScroll],
  );
  return <FileViewerContext.Provider value={value}>{children}</FileViewerContext.Provider>;
}

export function useFileViewer(): ContextShape {
  const ctx = useContext(FileViewerContext);
  if (!ctx) throw new Error("useFileViewer requires FileViewerProvider");
  return ctx;
}

/** Same as `useFileViewer` but returns null when no provider is mounted.
 *  Useful for components that are sometimes rendered in isolation (tests,
 *  storybook, embedded previews) and gracefully no-op the open() flow. */
export function useFileViewerOptional(): ContextShape | null {
  return useContext(FileViewerContext);
}

export function kindFromFilename(name: string): FileKind {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "md" || ext === "markdown") return "markdown";
  if (ext === "txt" || ext === "log") return "text";
  if (["py", "js", "ts", "tsx", "json", "yaml", "yml", "toml"].includes(ext)) return "code";
  if (ext === "csv" || ext === "tsv") return "csv";
  if (["png", "jpg", "jpeg", "gif", "svg", "webp"].includes(ext)) return "image";
  if (ext === "docx" || ext === "pptx") return "docx";
  return "unknown";
}
