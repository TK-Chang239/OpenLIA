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
  | "unknown";

export type FileSource =
  | { kind: "attachment"; attachmentId: string }
  | { kind: "report"; reportId: string };

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
