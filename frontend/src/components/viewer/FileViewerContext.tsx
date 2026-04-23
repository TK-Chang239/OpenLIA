import { createContext, useCallback, useContext, useMemo, useState } from "react";

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
}

interface ContextShape {
  current: FileViewerTarget | null;
  open: (target: FileViewerTarget) => void;
  close: () => void;
}

const FileViewerContext = createContext<ContextShape | null>(null);

export function FileViewerProvider({ children }: { children: React.ReactNode }): JSX.Element {
  const [current, setCurrent] = useState<FileViewerTarget | null>(null);
  const open = useCallback((t: FileViewerTarget) => setCurrent(t), []);
  const close = useCallback(() => setCurrent(null), []);
  const value = useMemo(() => ({ current, open, close }), [current, open, close]);
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
