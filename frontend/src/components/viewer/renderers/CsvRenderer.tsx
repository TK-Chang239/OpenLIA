import { useEffect, useState } from "react";
import { type FileSource } from "../FileViewerContext";
import { sourceUrl } from "./sourceUrl";

function parseCsv(text: string): string[][] {
  return text
    .split("\n")
    .filter((l) => l.length > 0)
    .map((line) => line.split(","));
}

export function CsvRenderer({ source }: { source: FileSource }): JSX.Element {
  const [rows, setRows] = useState<string[][] | null>(null);

  useEffect(() => {
    fetch(sourceUrl(source), { credentials: "same-origin" })
      .then((r) => r.text())
      .then((t) => setRows(parseCsv(t)));
  }, [source]);

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
