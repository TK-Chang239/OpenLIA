import { useEffect, useMemo, useRef, useState } from "react";
import type { JSX } from "react";
import { ArrowDown, ArrowUp, Columns3, Filter } from "lucide-react";
import { useTranslation } from "react-i18next";
import type {
  AnalyticsResponse,
  PortfolioHolding,
  PositionAnalytic,
  TickerSeriesResponse,
} from "../api/portfolio";
import { formatCurrency } from "./formatCurrency";
import { Sparkline, type SparklinePoint } from "./Sparkline";
import { useLocalJsonPref } from "./useLocalJsonPref";

export type SortKey =
  | "TICKER"
  | "SHARES"
  | "AVG_COST"
  | "PRICE"
  | "DAY_CHANGE"
  | "MKT_VALUE"
  | "POS_PL"
  | "WEIGHT";
export type SortDir = "asc" | "desc";

interface SortState {
  key: SortKey;
  dir: SortDir;
}

interface ColumnVis {
  day_change: boolean;
  pos_pl: boolean;
  weight: boolean;
  spark: boolean;
}

interface FilterState {
  groups: string[];
}

const DEFAULT_SORT: SortState = { key: "MKT_VALUE", dir: "desc" };
const DEFAULT_COLUMNS: ColumnVis = {
  day_change: true,
  pos_pl: true,
  weight: true,
  spark: true,
};
const DEFAULT_FILTER: FilterState = { groups: [] };
const UNTAGGED_KEY = "__UNTAGGED__";

export interface HoldingsTableProps {
  readonly holdings: readonly PortfolioHolding[];
  readonly analytics: AnalyticsResponse | null;
  readonly groups: readonly string[];
  readonly loading: boolean;
  readonly selectedHoldingId: string | null;
  readonly sparklines: TickerSeriesResponse | null;
  readonly onRowClick: (holding: PortfolioHolding) => void;
  readonly onManageGroups: () => void;
}

export function HoldingsTable({
  holdings,
  analytics,
  groups,
  loading,
  selectedHoldingId,
  sparklines,
  onRowClick,
  onManageGroups,
}: HoldingsTableProps): JSX.Element {
  const { t } = useTranslation();
  const [sort, setSort] = useLocalJsonPref<SortState>("portfolio:sort", DEFAULT_SORT);
  const [storedColumns, setColumns] = useLocalJsonPref<Partial<ColumnVis>>(
    "portfolio:columns",
    DEFAULT_COLUMNS,
  );
  const columns: ColumnVis = { ...DEFAULT_COLUMNS, ...storedColumns };
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
          {t("portfolio_page.holdings")}
          <span className="font-mono text-[10px] font-normal tracking-[0.08em] text-[--color-text-tertiary]">
            {t("portfolio_page.positions_sorted", {
              count: sorted.length,
              key: sort.key,
              arrow: sort.dir === "asc" ? "↑" : "↓",
            })}
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
            ? t("portfolio_page.no_holdings_match")
            : t("portfolio_page.no_holdings_yet")}
        </div>
      ) : (
        <table className="w-full table-auto border-collapse font-mono text-[12px] tabular-nums">
          <thead>
            <tr>
              <SortHeader
                label={t("portfolio_page.col_ticker")}
                column="TICKER"
                sort={sort}
                onClick={() => onHeaderClick("TICKER")}
              />
              <th className="border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-left text-[9px] font-medium uppercase tracking-[0.12em] text-[--color-text-tertiary]">
                {t("portfolio_page.col_group")}
              </th>
              <SortHeader
                label={t("portfolio_page.col_shares")}
                column="SHARES"
                sort={sort}
                onClick={() => onHeaderClick("SHARES")}
                align="right"
              />
              <SortHeader
                label={t("portfolio_page.col_avg_cost")}
                column="AVG_COST"
                sort={sort}
                onClick={() => onHeaderClick("AVG_COST")}
                align="right"
              />
              <SortHeader
                label={t("portfolio_page.col_price")}
                column="PRICE"
                sort={sort}
                onClick={() => onHeaderClick("PRICE")}
                align="right"
              />
              {columns.day_change ? (
                <SortHeader
                  label={t("portfolio_page.col_day_change")}
                  column="DAY_CHANGE"
                  sort={sort}
                  onClick={() => onHeaderClick("DAY_CHANGE")}
                  align="right"
                />
              ) : null}
              <SortHeader
                label={t("portfolio_page.col_mkt_value")}
                column="MKT_VALUE"
                sort={sort}
                onClick={() => onHeaderClick("MKT_VALUE")}
                align="right"
              />
              {columns.pos_pl ? (
                <SortHeader
                  label={t("portfolio_page.col_pos_pl")}
                  column="POS_PL"
                  sort={sort}
                  onClick={() => onHeaderClick("POS_PL")}
                  align="right"
                />
              ) : null}
              {columns.weight ? (
                <SortHeader
                  label={t("portfolio_page.col_weight")}
                  column="WEIGHT"
                  sort={sort}
                  onClick={() => onHeaderClick("WEIGHT")}
                  align="right"
                />
              ) : null}
              {columns.spark ? (
                <th className="border-b border-[--color-border-subtle] bg-[--color-bg-base] px-[14px] py-2 text-right text-[9px] font-medium uppercase tracking-[0.12em] text-[--color-text-tertiary]">
                  {t("portfolio_page.col_spark")}
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
                sparkPoints={getSparkPoints(sparklines, h.ticker)}
                onClick={() => onRowClick(h)}
              />
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

function getSparkPoints(
  sparklines: TickerSeriesResponse | null,
  ticker: string,
): SparklinePoint[] {
  if (!sparklines) return [];
  const series = sparklines.series[ticker.toUpperCase()];
  if (!series) return [];
  return series.map((p) => ({ ts: p.ts, value: Number(p.close) }));
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
    case "SHARES":
      return p?.shares ? Number(p.shares) : 0;
    case "AVG_COST":
      return p?.cost_basis ? Number(p.cost_basis) : 0;
    case "PRICE":
      return p?.last_price ? Number(p.last_price) : 0;
    case "DAY_CHANGE":
      return p?.day_change_abs ? Number(p.day_change_abs) : 0;
    case "MKT_VALUE":
      return p?.market_value ? Number(p.market_value) : 0;
    case "POS_PL":
      return p?.unrealized_pl ? Number(p.unrealized_pl) : 0;
    case "WEIGHT":
      return p?.weight ? Number(p.weight) : 0;
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
  sparkPoints,
  onClick,
}: {
  holding: PortfolioHolding;
  position: PositionAnalytic | undefined;
  columns: ColumnVis;
  selected: boolean;
  sparkPoints: SparklinePoint[];
  onClick: () => void;
}): JSX.Element {
  const ccy = (position?.currency ?? holding.currency ?? "USD").toUpperCase();
  const sharesN = position?.shares ? Number(position.shares) : null;
  const avgCostN = position?.cost_basis ? Number(position.cost_basis) : null;
  const priceN = position?.last_price ? Number(position.last_price) : null;
  const mktValueN = position?.market_value ? Number(position.market_value) : null;
  const posPlN = position?.unrealized_pl ? Number(position.unrealized_pl) : null;
  const dayAbsN =
    position?.day_change_abs !== null && position?.day_change_abs !== undefined
      ? Number(position.day_change_abs)
      : null;
  const dayPctN =
    position?.day_change_pct !== null && position?.day_change_pct !== undefined
      ? Number(position.day_change_pct)
      : null;
  const weight =
    position?.weight !== null && position?.weight !== undefined
      ? `${(Number(position.weight) * 100).toFixed(1)}%`
      : "—";

  const sharesStr =
    sharesN === null
      ? "—"
      : sharesN.toLocaleString("en-US", { maximumFractionDigits: 4 });

  const group = holding.groups[0] ?? "—";

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
        {group}
      </td>
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {sharesStr}
      </td>
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {formatCurrency(avgCostN, ccy)}
      </td>
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {formatCurrency(priceN, ccy)}
      </td>
      {columns.day_change ? (
        <td
          className={`border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right ${dayAbsN !== null && dayAbsN >= 0 ? "text-[--color-feedback-success]" : dayAbsN !== null ? "text-[--color-feedback-error]" : "text-[--color-text-tertiary]"}`}
          data-testid={`holding-day-change-${holding.ticker}`}
        >
          {dayAbsN === null || dayPctN === null ? (
            "—"
          ) : (
            <span className="inline-flex items-center justify-end gap-[6px]">
              <span>{formatCurrency(dayAbsN, ccy, { signed: true })}</span>
              <span className="text-[10px] opacity-80">
                {`${dayPctN >= 0 ? "+" : ""}${(dayPctN * 100).toFixed(2)}%`}
              </span>
            </span>
          )}
        </td>
      ) : null}
      <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
        {formatCurrency(mktValueN, ccy)}
      </td>
      {columns.pos_pl ? (
        <td
          className={`border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right ${posPlN !== null && posPlN >= 0 ? "text-[--color-feedback-success]" : posPlN !== null ? "text-[--color-feedback-error]" : "text-[--color-text-tertiary]"}`}
        >
          {posPlN === null ? "—" : formatCurrency(posPlN, ccy, { signed: true })}
        </td>
      ) : null}
      {columns.weight ? (
        <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right text-[--color-text-primary]">
          {weight}
        </td>
      ) : null}
      {columns.spark ? (
        <td className="border-b border-[--color-border-subtle] px-[14px] py-[11px] text-right">
          <Sparkline
            points={sparkPoints}
            formatTooltip={(p) => {
              const d = new Date(p.ts);
              const label = Number.isNaN(d.getTime())
                ? p.ts
                : d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
              return `${label} · ${formatCurrency(p.value, ccy)}`;
            }}
          />
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
    { key: "day_change", label: "DAY ±" },
    { key: "pos_pl", label: "POS P/L" },
    { key: "weight", label: "WEIGHT" },
    { key: "spark", label: "7D" },
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
            Locked: TICKER · GROUP · SHARES · AVG COST · PRICE · MKT VALUE
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
          className="ol-skeleton h-[44px]"
        />
      ))}
    </ul>
  );
}
