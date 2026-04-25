import { useState } from "react";

import { importCsv, type CsvImportResponse } from "../api/portfolio";

export interface ImportCsvDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onImported: (response: CsvImportResponse) => void;
}

interface ParsedRow {
  readonly index: number;
  readonly ticker: string;
  readonly errors: readonly string[];
}

function parsePreview(text: string): readonly ParsedRow[] {
  if (!text.trim()) return [];
  const lines = text.trim().split(/\r?\n/);
  const header = lines[0]?.split(",").map((c) => c.trim().toLowerCase()) ?? [];
  const tickerIdx = header.indexOf("ticker");
  return lines.slice(1).map((line, i) => {
    const cells = line.split(",");
    const ticker = (tickerIdx >= 0 ? cells[tickerIdx] : cells[0])?.trim() ?? "";
    const errs: string[] = [];
    if (!ticker) errs.push("missing ticker");
    return { index: i + 1, ticker, errors: errs };
  });
}

export function ImportCsvDialog({
  open,
  onClose,
  onImported,
}: ImportCsvDialogProps): JSX.Element | null {
  const [text, setText] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CsvImportResponse | null>(null);

  if (!open) return null;

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setText(await file.text());
  };

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await importCsv(text);
      setResult(res);
      onImported(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const preview = parsePreview(text);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Import CSV"
      className="fixed inset-0 z-40 flex items-center justify-center"
      data-testid="import-csv-dialog"
    >
      <div
        className="absolute inset-0 bg-black/30"
        onClick={onClose}
        aria-hidden="true"
      />
      <div className="relative w-[520px] max-h-[80vh] overflow-y-auto bg-[--color-surface-elevated] border border-[--color-border-subtle] rounded-[--radius-md] p-5">
        <h2 className="text-lg font-semibold mb-3">Import CSV</h2>
        <p className="text-xs text-[--color-text-tertiary] mb-2">
          Required columns: ticker. Optional: shares, cost_basis, currency, notes.
        </p>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={onFile}
          className="text-sm"
          data-testid="csv-file"
        />
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={6}
          placeholder="Paste CSV text…"
          className="block w-full mt-3 px-2 py-1 text-xs font-mono border border-[--color-border-subtle] rounded-[--radius-sm] bg-[--color-bg-input]"
          data-testid="csv-text"
        />

        {preview.length ? (
          <div className="mt-3" data-testid="csv-preview">
            <div className="text-xs text-[--color-text-tertiary] mb-1">
              {preview.length} row(s)
            </div>
            <ul className="text-xs max-h-28 overflow-y-auto">
              {preview.slice(0, 8).map((r) => (
                <li key={r.index} className="flex items-center gap-2">
                  <span className="font-mono">{r.ticker || "(empty)"}</span>
                  {r.errors.length ? (
                    <span className="text-[--color-feedback-error]">
                      {r.errors.join(", ")}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        {result ? (
          <div
            className="mt-3 text-xs"
            data-testid="csv-result"
          >
            Imported {result.created.length}; {result.errors.length} errors
          </div>
        ) : null}

        {error ? (
          <p className="text-xs text-[--color-feedback-error] mt-2">{error}</p>
        ) : null}

        <div className="flex justify-end gap-2 mt-4">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1 text-sm rounded-[--radius-sm] border border-[--color-border-subtle]"
          >
            Close
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={submitting || !text.trim()}
            className="px-3 py-1 text-sm rounded-[--radius-sm] bg-[--color-accent-primary] text-white disabled:opacity-40"
            data-testid="csv-submit"
          >
            Import
          </button>
        </div>
      </div>
    </div>
  );
}
