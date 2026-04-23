import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

export function ImageRenderer({ source }: { source: FileSource }): JSX.Element {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <img src={sourceUrl(source)} alt="File preview" className="max-h-full max-w-full object-contain" />
    </div>
  );
}
