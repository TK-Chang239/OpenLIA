import { FileX } from "lucide-react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

interface Props {
  source: FileSource;
  filename: string;
}

export function UnsupportedRenderer({ source, filename }: Props): JSX.Element {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
      <FileX size={40} className="text-[--color-text-tertiary]" aria-hidden="true" />
      <p className="text-base text-[--color-text-secondary]">
        Preview not available for this file type.
      </p>
      <a
        href={sourceUrl(source)}
        download={filename}
        className="text-sm text-[--color-accent-primary] hover:underline"
      >
        Download the file to view it
      </a>
    </div>
  );
}
