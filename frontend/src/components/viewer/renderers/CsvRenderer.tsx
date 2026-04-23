import { useEffect, useState } from "react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  const lines = text.split(/\r?\n/);
  for (const line of lines) {
    if (line.length === 0) continue;
    const cells: string[] = [];
    let i = 0;
    while (i < line.length) {
      if (line[i] === '"') {
        let cell = "";
        i++;
        while (i < line.length) {
          if (line[i] === '"' && line[i + 1] === '"') {
            cell += '"';
            i += 2;
          } else if (line[i] === '"') {
            i++;
            break;
          } else {
            cell += line[i++];
          }
        }
        cells.push(cell);
        if (line[i] === ",") i++;
      } else {
        const end = line.indexOf(",", i);
        if (end === -1) {
          cells.push(line.slice(i));
          break;
        }
        cells.push(line.slice(i, end));
        i = end + 1;
      }
    }
    rows.push(cells);
  }
  return rows;
}

export function CsvRenderer({ source }: { source: FileSource }): JSX.Element {
  const [rows, setRows] = useState<string[][] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(sourceUrl(source), { credentials: "same-origin" })
      .then((r) => (r.ok ? r.text() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((t) => setRows(parseCsv(t)))
      .catch((e: unknown) => setError((e as Error).message));
  }, [source]);

  if (error) return <div className="p-6 text-sm text-[--color-feedback-error]">{error}</div>;
  if (rows === null)
    return <div className="p-6 text-sm text-[--color-text-secondary]">Loading…</div>;
  const [header, ...data] = rows;
  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10 bg-[--color-bg-base]">
          <tr>
            {header.map((h, i) => (
              <th
                key={i}
                className="whitespace-nowrap border-b border-[--color-border-subtle] px-3 py-2 font-medium text-[--color-text-primary]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, ri) => (
            <tr
              key={ri}
              className={`border-b border-[--color-border-subtle] last:border-0 ${ri % 2 === 1 ? "bg-[--color-surface-hover]/40" : ""}`}
            >
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className="whitespace-nowrap px-3 py-2 text-[--color-text-secondary]"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
