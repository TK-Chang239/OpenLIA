import { useMemo, useState } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';

type Align = 'left' | 'center' | 'right';
type RowStyle = 'default' | 'subtotal' | 'total' | 'header_group';
type FormatRule = 'negative' | 'positive' | 'directional' | 'bold' | 'muted';

export interface TableBlockHeader {
  key: string;
  label: string;
  align?: Align;
  sortable?: boolean;
  sparkline?: boolean;
}

export interface TableBlockProps {
  type: 'table';
  title: string;
  headers: TableBlockHeader[];
  rows: (Record<string, unknown> & { _row_style?: RowStyle })[];
  cell_format?: Record<string, { rule: FormatRule }>;
  footnotes?: string[];
  options?: Record<string, unknown>;
}

function isNegativeString(s: string): boolean {
  const trimmed = s.trim();
  if (trimmed.startsWith('-')) return true;
  if (trimmed.startsWith('(') && trimmed.endsWith(')')) return true;
  return false;
}

function isPositiveString(s: string): boolean {
  return s.trim().startsWith('+');
}

function formatClass(value: unknown, rule: FormatRule): string {
  const text = String(value ?? '');
  switch (rule) {
    case 'negative':
      return isNegativeString(text) ? 'report-cell--negative' : '';
    case 'positive':
      return isPositiveString(text) ? 'report-cell--positive' : '';
    case 'directional':
      if (isPositiveString(text)) return 'report-cell--positive';
      if (isNegativeString(text)) return 'report-cell--negative';
      return 'report-cell--neutral';
    case 'bold':
      return 'report-cell--bold';
    case 'muted':
      return 'report-cell--muted';
  }
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const w = 60;
  const h = 20;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = values.length > 1 ? w / (values.length - 1) : 0;
  const points = values
    .map((v, i) => `${i * stepX},${h - ((v - min) / span) * h}`)
    .join(' ');
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? 'var(--report-positive)' : 'var(--report-negative)';
  return (
    <svg width={w} height={h} aria-hidden>
      <polyline fill="none" stroke={stroke} strokeWidth={1.5} points={points} />
    </svg>
  );
}

export function TableBlock(props: TableBlockProps) {
  const { headers, rows, cell_format = {}, footnotes = [] } = props;
  const [sorting, setSorting] = useState<SortingState>([]);
  const columnHelper = createColumnHelper<Record<string, unknown>>();

  const columns = useMemo(
    () =>
      headers.map((h) =>
        columnHelper.accessor((row) => row[h.key], {
          id: h.key,
          header: h.label,
          enableSorting: Boolean(h.sortable),
          cell: (info) => {
            if (h.sparkline && Array.isArray(info.getValue())) {
              return <Sparkline values={info.getValue() as number[]} />;
            }
            return String(info.getValue() ?? '');
          },
        }),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [headers],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <figure className="report-table">
      <figcaption className="report-table__title">{props.title}</figcaption>
      <table>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const header = headers.find((x) => x.key === h.column.id);
                const align = header?.align ?? 'left';
                const sortable = Boolean(header?.sortable);
                return (
                  <th
                    key={h.id}
                    style={{ textAlign: align }}
                    className={sortable ? 'report-table__th--sortable' : undefined}
                  >
                    {sortable ? (
                      <button type="button" onClick={h.column.getToggleSortingHandler()}>
                        {flexRender(h.column.columnDef.header, h.getContext())}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const style = (row.original as Record<string, unknown>)._row_style ?? 'default';
            return (
              <tr key={row.id} className={`report-row report-row--${style}`}>
                {row.getVisibleCells().map((cell) => {
                  const header = headers.find((h) => h.key === cell.column.id);
                  const rule = cell_format[cell.column.id]?.rule;
                  const classes = [rule ? formatClass(cell.getValue(), rule) : '']
                    .filter(Boolean)
                    .join(' ');
                  return (
                    <td
                      key={cell.id}
                      data-col={cell.column.id}
                      className={classes}
                      style={{ textAlign: header?.align ?? 'left' }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      {footnotes.length > 0 ? (
        <ul className="report-table__footnotes">
          {footnotes.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      ) : null}
    </figure>
  );
}
