import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { ArrowDown, ArrowUp, Columns3, Filter } from "lucide-react";
import type {
  AnalyticsResponse,
  PortfolioHolding,
  PositionAnalytic,
} from "../api/portfolio";
import { sparkFor, sparkPath } from "./sparkline";
import { useLocalJsonPref } from "./useLocalJsonPref";

export type SortKey = "TICKER" | "WEIGHT" | "PRICE" | "DAY_DELTA" | "POS_PL";
export type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

interface ColumnVis {
  day_delta: boolean;
  pos_pl: boolean;
  week: boolean;
  flag: boolean;
}

interface FilterState {
  groups: string[]; // [] = all (no filter); "__UNTAGGED__" = holdings with no group
  // Flag dimension is reserved for the verdicts API; not active.
}

const DEFAULT_SORT: SortState = { key: "WEIGHT", dir: "desc" };
const DEFAULT_COLUMNS: ColumnVis = {
  day_delta: true,
  pos_pl: true,
  week: true,
  flag: true,
};
const DEFAULT_FILTER: FilterState = { groups: [] };
const UNTAGGED_KEY = "__UNTAGGED__";

export interface HoldingsTableProps {
  readonly holdings: readonly PortfolioHolding[];
  readonly analytics: AnalyticsResponse | null;
  readonly groups: readonly string[];
  readonly loading: boolean;
  readonly selectedHoldingId: string | null;
  readonly onRowClick: (holding: PortfolioHolding) => void;
  readonly onManageGroups: () => void;
}

export function HoldingsTable({
  holdings,
  analytics,
  groups,
  loading,
  selectedHoldingId,
  onRowClick,
  onManageGroups,
}: HoldingsTableProps): JSX.Element {
  const [sort, setSort] = useLocalJsonPref<SortState>("portfolio:sort", DEFAULT_SORT);
  const [columns, setColumns] = useLocalJsonPref<ColumnVis>(
    "portfolio:columns",
    DEFAULT_COLUMNS,
  );
  const [filter, setFilter] = useLocalJsonPref<FilterState>(
    "portfolio:filter",
    DEFAULT_FILTER,
  );

  const positionsByHolding = useMemo(() => {
    const m = new Map<string, PositionAnalytic>();
    analytics?.positions.forEach((p) => m.set(p.holding_id, p));
    return m;
  }, [analytics]);

  const filtered = useMemo(() => {
    if (filter.groups.length === 0) return holdings;
    return holdings.filter((h) => {
      const g = h.groups[0];
      if (g) return filter.groups.includes(g);
      return filter.groups.includes(UNTAGGED_KEY);
    });
  }, [holdings, filter]);

  const sorted = useMemo(() => {
    const arr = [...filtered];
    arr.sort((a, b) => {
      const av = sortValue(sort.key, a, positionsByHolding);
      const bv = sortValue(sort.key, b, positionsByHolding);
      const cmp =
        typeof av === "string" && typeof bv === "string"
          ? av.localeCompare(bv)
          : (av as number) - (bv as number);
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filtered, sort, positionsByHolding]);

  const onHeaderClick = (key: SortKey) => {
    if (sort.key === key) {
      setSort({ key, dir: sort.dir === "asc" ? "desc" : "asc" });
    } else {
      setSort({ key, dir: "desc" });
    }
  };

  const activeFilterCount = filter.groups.length;

  return (
    <section
      className="overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated]"
      data-testid="holdings-table"
    >
      <div className="flex items-center justify-between border-b border-[--color-border-subtle] px-[18px] py-[14px]">
        <span className="inline-flex items-center gap-[10px] text-[13px] font-semibold text-[--color-text-primary]">
          Holdings
          <span className="font-mono text-[10px] font-normal tracking-[0.08em] text-[--color-text-tertiary]">
            {sorted.length} POSITIONS · SORTED BY {sort.key}{" "}
            {sort.dir === "asc" ? "↑" : "↓"}
          </span>
        </span>
        <div className="flex gap-[6px]">
          <FilterFlyout
            groups={groups}
            value={filter}
            onChange={setFilter}
            onManageGroups={onManageGroups}
            activeCount={activeFilterCount}
          />
          <ColumnsFlyout value={columns} onChange={setColumns} />
        </div>
      </div>

      {loading ? (
        <TableSkeleton />
      ) : sorted.length === 0 ? (
        <div className="px-[18px] py-10 text-center text-sm text-[--color-text-tertiary]">
          {filter.groups.length > 0
            ? "No holdings match the current filter."
            : "No holdings yet. Add a position to get started."}
        </div>
      ) : (
        <table className="w-full table-auto border-collapse font-mono text-[12px] tabular-nums">
          <thead>
            <tr>
              <SortHeader
                label="TICKER"
                column="TICKER"
                sort={sort}
                onClick={() => onHeaderClick("TICKER")}
              />
              <th className="border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-left text-[9px] font-medium uppercase tracking-[0.12em] text-[--color-text-tertiary]">
                NAME
              </th>
              <SortHeader
                label="WEIGHT"
                column="WEIGHT"
                sort={sort}
                onClick={() => onHeaderClick("WEIGHT")}
                align="right"
              />
              <SortHeader
                label="PRICE"
                column="PRICE"
                sort={sort}
                onClick={() => onHeaderClick("PRICE")}
                align="right"
              />
              {columns.day_delta ? (
                <SortHeader
                  label="DAY Δ"
                  column="DAY_DELTA"
                  sort={sort}
                  onClick={() => onHeaderClick("DAY_DELTA")}
                  align="right"
                />
              ) : null}
              {columns.pos_pl ? (
                <SortHeader
                  label="POS P/L"
                  column="POS_PL"
                  sort={sort}
                  onClick={() => onHeaderClick("POS_PL")}
                  align="right"
                />
              ) : null}
              {columns.week ? (
                <th className="border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-right text-[9px] font-medium uppercase tracking-[0.12em] text-[--color-text-tertiary]">
                  7D
                </th>
              ) : null}
              {columns.flag ? (
                <th className="border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-right text-[9px] font-medium uppercase tracking-[0.12em] text-[--color-text-tertiary]">
                  FLAG
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>
            {sorted.map((h) => (
              <HoldingRow
                key={h.id}
                holding={h}
                position={positionsByHolding.get(h.id)}
                columns={columns}
                selected={h.id === selectedHoldingId}
                onClick={() => onRowClick(h)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function sortValue(
  key: SortKey,
  h: PortfolioHolding,
  positions: Map<string, PositionAnalytic>,
): number | string {
  const p = positions.get(h.id);
  switch (key) {
    case "TICKER":
      return h.ticker;
    case "WEIGHT":
      return p?.weight ? Number(p.weight) : 0;
    case "PRICE":
      return p?.last_price ? Number(p.last_price) : 0;
    case "DAY_DELTA": {
      // Placeholder: use a deterministic per-ticker pseudo-delta for sort stability.
      const spark = sparkFor(h.ticker);
      return spark.points[spark.points.length - 1] - spark.points[0];
    }
    case "POS_PL":
      return p?.unrealized_pl ? Number(p.unrealized_pl) : 0;
  }
}

function SortHeader({
  label,
  column,
  sort,
  onClick,
  align = "left",
}: {
  label: string;
  column: SortKey;
  sort: SortState;
  onClick: () => void;
  align?: "left" | "right";
}): JSX.Element {
  const active = sort.key === column;
  return (
    <th
      className={`cursor-pointer select-none border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-[9px] font-medium uppercase tracking-[0.12em] hover:text-[--color-text-primary] ${align === "right" ? "text-right" : "text-left"} ${active ? "text-[--color-text-primary]" : "text-[--color-text-tertiary]"}`}
      onClick={onClick}
      data-testid={`sort-header-${column}`}
    >
      <span className={`inline-flex items-center gap-1 ${align === "right" ? "" : ""}`}>
        {label}
        {active ? (
          sort.dir === "asc" ? (
            <ArrowUp size={10} aria-hidden="true" />
          ) : (
            <ArrowDown size={10} aria-hidden="true" />
          )
        ) : null}
      </span>
    </th>
  );
}

function HoldingRow({
  holding,
  position,
  columns,
  selected,
  onClick,
}: {
  holding: PortfolioHolding;
  position: PositionAnalytic | undefined;
  columns: ColumnVis;
  selected: boolean;
  onClick: () => void;
}): JSX.Element {
  const spark = sparkFor(holding.ticker);
  const weight =
    position?.weight !== null && position?.weight !== undefined
      ? `${(Number(position.weight) * 100).toFixed(1)}%`
      : "—";
  const price = position?.last_price ? `$${Number(position.last_price).toFixed(2)}` : "—";
  const posPl = position?.unrealized_pl ? Number(position.unrealized_pl) : null;
  const posPlStr =
    posPl === null
      ? "—"
      : `${posPl >= 0 ? "+" : "-"}$${Math.abs(posPl).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

  // Placeholder day delta from deterministic sparkline.
  const dayDelta = spark.points[spark.points.length - 1] - spark.points[0];
  const dayPct = dayDelta * 0.4; // arbitrary scale that keeps numbers small
  const dayPos = dayPct >= 0;
  const dayStr = `${dayPos ? "+" : ""}${dayPct.toFixed(2)}%`;

  const sparkStroke =
    spark.sign === "down"
      ? "var(--color-feedback-error)"
      : spark.sign === "flat"
        ? "var(--neutral-400)"
        : "var(--yellow-600)";

  return (
    <tr
      onClick={onClick}
      className={`cursor-pointer transition-colors hover:bg-[--color-surface-hover] ${selected ? "bg-[rgba(212,255,0,0.06)]" : ""}`}
      data-testid={`holding-row-${holding.ticker}`}
      data-selected={selected ? "true" : undefined}
    >
      <td
        className={`border-b border-[--color-border-subtle] px-[14px] py-[11px] font-semibold tracking-[0.02em] text-[--color-text-primary] ${selected ? "shadow-[inset_2px_0_0_var(--color-accent-primary)]" : ""}`}
      >
        {holding.ticker}
      </td>
      <td className="font-display border-b border-[--color-border-subtle] px-[14px] py-[11px] text-[12px] text-[--color-text-secondary]">
        {holding.name ?? "—"}
      </td>
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {weight}
      </td>
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {price}
      </td>
      {columns.day_delta ? (
        <td
          className={`border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right ${dayPos ? "text-[--color-feedback-success]" : "text-[--color-feedback-error]"}`}
        >
          {dayStr}
        </td>
      ) : null}
      {columns.pos_pl ? (
        <td
          className={`border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right ${posPl !== null && posPl >= 0 ? "text-[--color-feedback-success]" : posPl !== null ? "text-[--color-feedback-error]" : "text-[--color-text-tertiary]"}`}
        >
          {posPlStr}
        </td>
      ) : null}
      {columns.week ? (
        <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right">
          <svg
            viewBox="0 0 64 22"
            preserveAspectRatio="none"
            className="inline-block h-[22px] w-[64px] align-middle"
            aria-hidden="true"
          >
            <path
              d={sparkPath(spark.points, 64)}
              fill="none"
              style={{ stroke: sparkStroke }}
              strokeWidth="1.4"
            />
          </svg>
        </td>
      ) : null}
      {columns.flag ? (
        <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right">
          <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            —
          </span>
        </td>
      ) : null}
    </tr>
  );
}

function FilterFlyout({
  groups,
  value,
  onChange,
  onManageGroups,
  activeCount,
}: {
  groups: readonly string[];
  value: FilterState;
  onChange: (v: FilterState) => void;
  onManageGroups: () => void;
  activeCount: number;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = (key: string) => {
    const has = value.groups.includes(key);
    onChange({
      groups: has ? value.groups.filter((g) => g !== key) : [...value.groups, key],
    });
  };

  return (
    <span ref={wrapRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-[6px] rounded-md border px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] transition-colors ${activeCount > 0 ? "border-[--color-accent-primary] text-[--color-text-primary]" : "border-[--color-border-subtle] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"}`}
        data-testid="filter-toggle"
        aria-expanded={open}
      >
        <Filter size={11} aria-hidden="true" />
        FILTER{activeCount > 0 ? ` · ${activeCount}` : ""}
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-20 mt-1 w-64 overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg">
          <div className="border-b border-[--color-border-subtle] px-3 py-2 font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
            Groups
          </div>
          <ul className="max-h-64 overflow-auto py-1">
            {groups.length === 0 ? (
              <li className="px-3 py-2 text-sm text-[--color-text-tertiary]">
                No groups yet
              </li>
            ) : null}
            {groups.map((g) => (
              <li key={g} className="px-3 py-1.5">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-[--color-text-primary]">
                  <input
                    type="checkbox"
                    checked={value.groups.includes(g)}
                    onChange={() => toggle(g)}
                    data-testid={`filter-group-${g}`}
                  />
                  {g}
                </label>
              </li>
            ))}
            <li className="px-3 py-1.5">
              <label className="flex cursor-pointer items-center gap-2 text-sm text-[--color-text-tertiary] italic">
                <input
                  type="checkbox"
                  checked={value.groups.includes(UNTAGGED_KEY)}
                  onChange={() => toggle(UNTAGGED_KEY)}
                  data-testid="filter-untagged"
                />
                Untagged
              </label>
            </li>
          </ul>
          <div className="border-t border-[--color-border-subtle] px-3 py-2">
            <span className="mb-1 block font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
              Flag
            </span>
            <p className="m-0 text-[11px] text-[--color-text-tertiary]">
              Available once LIA per-holding verdicts ship.
            </p>
          </div>
          <div className="flex items-center justify-between border-t border-[--color-border-subtle] px-3 py-2">
            <button
              type="button"
              onClick={() => onChange({ groups: [] })}
              className="font-mono text-[10px] tracking-[0.06em] text-[--color-text-secondary] hover:text-[--color-text-primary]"
              data-testid="filter-reset"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                onManageGroups();
              }}
              className="font-mono text-[10px] tracking-[0.06em] text-[--color-feedback-success] hover:underline"
              data-testid="filter-manage-groups"
            >
              Manage groups…
            </button>
          </div>
        </div>
      ) : null}
    </span>
  );
}

function ColumnsFlyout({
  value,
  onChange,
}: {
  value: ColumnVis;
  onChange: (v: ColumnVis) => void;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement | null>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const toggle = (key: keyof ColumnVis) => {
    onChange({ ...value, [key]: !value[key] });
  };

  const items: { key: keyof ColumnVis; label: string }[] = [
    { key: "day_delta", label: "DAY Δ" },
    { key: "pos_pl", label: "POS P/L" },
    { key: "week", label: "7D" },
    { key: "flag", label: "FLAG" },
  ];

  return (
    <span ref={wrapRef} className="relative inline-flex">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-[6px] rounded-md border border-[--color-border-subtle] px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] text-[--color-text-secondary] transition-colors hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
        data-testid="columns-toggle"
        aria-expanded={open}
      >
        <Columns3 size={11} aria-hidden="true" />
        COLUMNS
      </button>
      {open ? (
        <div className="absolute right-0 top-full z-20 mt-1 w-48 overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg">
          <ul className="py-1">
            {items.map(({ key, label }) => (
              <li key={key} className="px-3 py-1.5">
                <label className="flex cursor-pointer items-center gap-2 text-sm text-[--color-text-primary]">
                  <input
                    type="checkbox"
                    checked={value[key]}
                    onChange={() => toggle(key)}
                    data-testid={`column-toggle-${key}`}
                  />
                  {label}
                </label>
              </li>
            ))}
          </ul>
          <div className="border-t border-[--color-border-subtle] px-3 py-2 font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            Locked: TICKER · NAME · WEIGHT · PRICE
          </div>
        </div>
      ) : null}
    </span>
  );
}

function TableSkeleton(): JSX.Element {
  return (
    <ul aria-label="Loading" className="space-y-1 p-3" data-testid="holdings-loading">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <li
          key={i}
          className="h-[44px] animate-pulse rounded bg-[--color-border-subtle]"
        />
      ))}
    </ul>
  );
}
