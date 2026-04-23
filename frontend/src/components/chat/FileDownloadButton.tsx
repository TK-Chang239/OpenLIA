import type { FileSource } from "../viewer/FileViewerContext";

interface Props {
  variant: "chip" | "header";
  source: FileSource;
  filename: string;
}

export function FileDownloadButton({ variant: _variant, source: _source, filename: _filename }: Props): JSX.Element {
  return <button type="button" aria-label="Download" onClick={(e) => e.stopPropagation()} />;
}
