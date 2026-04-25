import { useState } from "react";
import { encodeShareLink } from "../../lib/panic-thermometer/share-link";

interface Props {
  open: boolean;
  onClose: () => void;
  onImport: (payload: unknown) => void;
  exportPayload: unknown;
}

export function ImportExportModal({
  open,
  onClose,
  onImport,
  exportPayload,
}: Props): JSX.Element | null {
  const [text, setText] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  if (!open) return null;

  const onFile = async (file: File) => {
    try {
      const t = await file.text();
      setText(t);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const submit = () => {
    try {
      const parsed = JSON.parse(text);
      onImport(parsed);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const copyShareLink = async () => {
    const url = `${window.location.origin}${window.location.pathname}?cfg=${encodeShareLink(exportPayload)}`;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div
      role="dialog"
      data-testid="import-export-modal"
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 60,
      }}
    >
      <div
        style={{
          background: "var(--color-bg-elevated)",
          padding: "1rem",
          width: "min(560px, 90%)",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        }}
      >
        <strong>Import / Export configuration</strong>
        <input
          type="file"
          accept="application/json"
          data-testid="import-file"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void onFile(f);
          }}
        />
        <textarea
          data-testid="import-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={8}
          placeholder="Paste JSON here"
        />
        {error ? (
          <div role="alert" style={{ color: "var(--color-feedback-error)" }}>
            {error}
          </div>
        ) : null}
        <div style={{ display: "flex", gap: "0.25rem", justifyContent: "space-between" }}>
          <button type="button" data-testid="copy-share-link" onClick={copyShareLink}>
            {copied ? "Copied!" : "Copy share link"}
          </button>
          <span>
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="button" data-testid="import-submit" onClick={submit}>
              Import
            </button>
          </span>
        </div>
      </div>
    </div>
  );
}
