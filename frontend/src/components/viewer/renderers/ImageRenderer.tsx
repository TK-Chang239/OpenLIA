import { useState } from "react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

export function ImageRenderer({ source }: { source: FileSource }): JSX.Element {
  const url = sourceUrl(source);
  const [error, setError] = useState<boolean>(false);
  const [zoom, setZoom] = useState<boolean>(false);
  const [retryToken, setRetryToken] = useState<number>(0);

  if (error) {
    return (
      <div
        role="alert"
        className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center"
      >
        <p className="text-sm text-[--color-feedback-error]">Failed to load file.</p>
        <button
          type="button"
          onClick={() => {
            setError(false);
            setRetryToken((n) => n + 1);
          }}
          className="text-sm text-[--color-accent-primary] hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full items-center justify-center p-6">
      <button
        type="button"
        aria-label={zoom ? "Close zoomed image" : "Zoom image"}
        onClick={() => setZoom((z) => !z)}
        className="h-full w-full"
      >
        <img
          key={retryToken}
          src={url}
          alt="File preview"
          onError={() => setError(true)}
          className={`mx-auto block transition-transform ${zoom ? "max-w-none cursor-zoom-out" : "max-h-full max-w-full cursor-zoom-in object-contain"}`}
        />
      </button>
    </div>
  );
}
